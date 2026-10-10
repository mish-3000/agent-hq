import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import errors, types
from pydantic import AliasChoices, BaseModel, Field

load_dotenv()

from github_tools import WRITE_CODE_FILE, write_code_file  # noqa: E402
from skills import (  # noqa: E402  (scans skills/ on import)
    InvalidSkillError,
    SkillExistsError,
    create_skill,
    get_skill,
    list_skills,
)

MODEL = "gemma-4-26b-a4b-it"
MAX_TOOL_ROUNDS = 5

GOOGLE_SEARCH = types.Tool(google_search=types.GoogleSearch())

# Gemini built-in tools for each skill. Any other skill (e.g. one created via POST /skills)
# gets DEFAULT_BUILTIN_TOOLS, so custom agents can search like research-agent.
SKILL_BUILTIN_TOOLS = {
    "dev-agent": [],
    "research-agent": [GOOGLE_SEARCH],
}
DEFAULT_BUILTIN_TOOLS = [GOOGLE_SEARCH]
# Function-calling tools for each skill (ask_agent is added for every skill), and the Python
# functions that implement them. write_code_file is deliberately dev-agent only: custom agents
# never get tools that write to the repo.
SKILL_FUNCTIONS = {
    "dev-agent": [WRITE_CODE_FILE],
}
TOOL_FUNCTIONS = {
    "write_code_file": write_code_file,
}
# Tools with side effects. They're removed only when a skill is answering another agent's
# ask_agent call; chatting with a skill directly always gets its full tool set.
WRITE_TOOLS = {"write_code_file"}

DELEGATED_NOTE = (
    "\n\n---\nYou are answering a question from another agent on the team, not the user. "
    "In this conversation you are read-only: you cannot write files, commit, or call other "
    "agents. Answer in text (you may include code in your reply), and don't claim to have "
    "made any changes."
)

# Tool use across all chats (search, ask_agent, write_code_file), oldest first.
# In memory only, so it resets when the server restarts.
ACTIVITY_LIMIT = 20
_activity: deque[dict] = deque(maxlen=ACTIVITY_LIMIT)


def log_activity(agent: str, action: str) -> None:
    _activity.append({
        "agent": agent,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


app = FastAPI(title="Agent HQ API")
logger = logging.getLogger("uvicorn.error")


# Registered before CORSMiddleware so CORS wraps it: unhandled errors become JSON 500s that
# still carry CORS headers. Otherwise the browser blocks the response and the frontend can only
# report "can't reach the backend" instead of the actual error.
@app.middleware("http")
async def unhandled_errors_as_json(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {type(e).__name__}: {e}"},
        )


app.add_middleware(
    CORSMiddleware,
    # The Vite dev server on any local port: it moves to 5174, 5175, ... when 5173 is taken.
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Create the Gemini client on first use, so the server still starts without an API key."""
    global _client
    if _client is None:
        try:
            # Reads GEMINI_API_KEY from the environment. Retries transient errors (429/5xx) with
            # backoff, since one chat can make several model calls.
            _client = genai.Client(
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=3))
            )
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Gemini client not configured: {e}")
    return _client


class HistoryMessage(BaseModel):
    role: Literal["user", "model", "assistant"]
    text: str = Field(validation_alias=AliasChoices("text", "content"))


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []


class CreateSkillRequest(BaseModel):
    name: str
    description: str
    role_prompt: str


class SkillSummary(BaseModel):
    name: str
    description: str


class ChatResponse(BaseModel):
    reply: str
    tool_used: str | None = None
    url: str | None = None


def ask_agent_declaration(skill_name: str) -> types.FunctionDeclaration | None:
    """Declare ask_agent with the other skills as the allowed agents (None if there are none)."""
    others = [s for s in list_skills() if s["name"] != skill_name]
    if not others:
        return None
    roster = "\n".join(f"- {s['name']}: {s['description']}" for s in others)
    return types.FunctionDeclaration(
        name="ask_agent",
        description=(
            "Ask another agent on the team a question and get its text reply. "
            "The question must be self-contained; the agent sees no other context. "
            "The agent answers read-only: it can't write files or make changes for you.\n"
            f"Available agents:\n{roster}"
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "enum": [s["name"] for s in others]},
                "question": {"type": "string", "description": "The full question or request."},
            },
            "required": ["agent_name", "question"],
        },
    )


def skill_functions(skill_name: str, delegated: bool) -> list[types.FunctionDeclaration]:
    """The skill's own function tools; write tools are dropped only for delegated runs."""
    return [
        f for f in SKILL_FUNCTIONS.get(skill_name, [])
        if not (delegated and f.name in WRITE_TOOLS)
    ]


def build_config(skill_name: str, instructions: str, delegated: bool) -> types.GenerateContentConfig:
    functions = skill_functions(skill_name, delegated)
    if not delegated and (ask := ask_agent_declaration(skill_name)):
        functions.append(ask)
    if delegated:
        instructions += DELEGATED_NOTE
    builtin = SKILL_BUILTIN_TOOLS.get(skill_name, DEFAULT_BUILTIN_TOOLS)

    tools = list(builtin)
    if functions:
        tools.append(types.Tool(function_declarations=functions))
    return types.GenerateContentConfig(
        system_instruction=instructions,
        tools=tools or None,
        # We run function calls ourselves in run_agent.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        # The API requires this flag to combine built-in tools with function calling.
        tool_config=(
            types.ToolConfig(include_server_side_tool_invocations=True)
            if builtin and functions
            else None
        ),
    )


def used_search(response: types.GenerateContentResponse) -> bool:
    """True if the model grounded this response with Google Search."""
    gm = response.candidates[0].grounding_metadata if response.candidates else None
    return bool(gm and (gm.web_search_queries or gm.grounding_chunks))


def describe_search(response: types.GenerateContentResponse) -> str:
    """Activity text for a grounded response, e.g. 'searched the web for "x" (+1 more)'."""
    queries = response.candidates[0].grounding_metadata.web_search_queries or []
    if not queries:
        return "searched the web"
    more = f" (+{len(queries) - 1} more)" if len(queries) > 1 else ""
    return f'searched the web for "{queries[0]}"{more}'


def reply_text(response: types.GenerateContentResponse) -> str:
    """The model's visible text (skips thoughts and server-side tool call/response parts)."""
    if not response.candidates or not response.candidates[0].content:
        return ""
    parts = response.candidates[0].content.parts or []
    return "".join(p.text for p in parts if p.text and not p.thought)


async def ask_agent(caller: str, agent_name: str, question: str) -> dict:
    """Run another skill's chat flow once, read-only and unable to delegate further."""
    if agent_name == caller:
        return {"error": "You can't ask yourself; pick a different agent."}
    if get_skill(agent_name) is None:
        names = ", ".join(s["name"] for s in list_skills())
        return {"error": f"Unknown agent {agent_name!r}. Available agents: {names}"}

    # Logged when the handoff starts, so the feed shows it while the other agent works.
    log_activity(caller, f"asked {agent_name}")
    try:
        result = await run_agent(agent_name, question, [], delegated=True)
    except HTTPException as e:
        return {"error": f"{agent_name} failed: {e.detail}"}

    tool_used = f"asked {agent_name}"
    if result.tool_used:
        tool_used += f" ({result.tool_used})"
    return {"reply": result.reply, "tool_used": tool_used, "url": result.url}


async def run_tool(call: types.FunctionCall, skill_name: str, delegated: bool) -> dict:
    """Run one function call and record it in the activity feed."""
    result = await _run_tool(call, skill_name, delegated)
    if "error" in result:
        log_activity(skill_name, f"{call.name} failed: {str(result['error'])[:200]}")
    elif call.name != "ask_agent":  # ask_agent logs itself when it starts
        log_activity(skill_name, result.get("tool_used") or f"used {call.name}")
    return result


async def _run_tool(call: types.FunctionCall, skill_name: str, delegated: bool) -> dict:
    args = call.args or {}
    try:
        if call.name == "ask_agent" and not delegated:
            return await ask_agent(skill_name, **args)
        # Only run functions this skill was actually given in this run.
        allowed = {f.name for f in skill_functions(skill_name, delegated)}
        if call.name not in allowed:
            return {"error": f"Unknown tool: {call.name}"}
        # Tools make blocking HTTP calls, so run them off the event loop.
        return await asyncio.to_thread(TOOL_FUNCTIONS[call.name], **args)
    except TypeError as e:
        return {"error": f"Invalid arguments for {call.name}: {e}"}


async def run_agent(
    skill_name: str,
    message: str,
    history: list[HistoryMessage],
    delegated: bool = False,
) -> ChatResponse:
    """Chat with a skill, running any tool calls it makes until it replies with text.

    delegated=False (the default, used by /chat): the skill gets all of its tools plus ask_agent.
    delegated=True (only via ask_agent): read-only, with no write tools and no ask_agent.
    """
    skill = get_skill(skill_name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    contents = [
        types.Content(
            role="user" if m.role == "user" else "model",
            parts=[types.Part(text=m.text)],
        )
        for m in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = build_config(skill_name, skill["instructions"], delegated)
    tools_used: list[str] = []
    url = None

    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = await get_client().aio.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
            if used_search(response):
                log_activity(skill_name, describe_search(response))
                if "searched the web" not in tools_used:
                    tools_used.append("searched the web")
            if not response.function_calls:
                break

            # Send the model's turn back unchanged (it may carry thought signatures),
            # followed by one function response per call.
            contents.append(response.candidates[0].content)
            result_parts = []
            for call in response.function_calls:
                result = await run_tool(call, skill_name, delegated)
                if result.get("tool_used"):
                    tools_used.append(result["tool_used"])
                if result.get("url"):
                    url = result["url"]
                result_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=call.id, name=call.name, response=result
                        )
                    )
                )
            contents.append(types.Content(role="user", parts=result_parts))
        else:
            raise HTTPException(status_code=502, detail="Model kept calling tools without replying")
    except errors.APIError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error ({e.code}): {e.message}")

    return ChatResponse(reply=reply_text(response), tool_used=", ".join(tools_used) or None, url=url)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/activity")
def activity():
    """The most recent tool uses across all chats, newest first."""
    return list(reversed(_activity))


@app.get("/skills")
def skills():
    return list_skills()


@app.post("/skills", response_model=SkillSummary, status_code=201)
def new_skill(req: CreateSkillRequest):
    """Create backend/skills/<name>/SKILL.md and make the agent available immediately."""
    try:
        return create_skill(req.name, req.description, req.role_prompt)
    except InvalidSkillError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SkillExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/chat/{skill_name}", response_model=ChatResponse)
async def chat(skill_name: str, req: ChatRequest):
    return await run_agent(skill_name, req.message, req.history)
