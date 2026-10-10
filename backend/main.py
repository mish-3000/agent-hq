import asyncio
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

load_dotenv()

from github_tools import WRITE_CODE_FILE, write_code_file  # noqa: E402
from skills import get_skill, list_skills  # noqa: E402  (scans skills/ on import)

MODEL = "gemma-4-26b-a4b-it"
MAX_TOOL_ROUNDS = 5

# Tools available to each skill, and the Python functions that implement the function-calling ones.
SKILL_TOOLS = {
    "dev-agent": [types.Tool(function_declarations=[WRITE_CODE_FILE])],
    "research-agent": [types.Tool(google_search=types.GoogleSearch())],
}
TOOL_FUNCTIONS = {
    "write_code_file": write_code_file,
}

app = FastAPI(title="Agent HQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
            _client = genai.Client()  # reads GEMINI_API_KEY from the environment
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Gemini client not configured: {e}")
    return _client


class HistoryMessage(BaseModel):
    role: Literal["user", "model", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []


class ChatResponse(BaseModel):
    reply: str
    tool_used: str | None = None
    url: str | None = None


def used_search(response: types.GenerateContentResponse) -> bool:
    """True if the model grounded this response with Google Search."""
    gm = response.candidates[0].grounding_metadata if response.candidates else None
    return bool(gm and (gm.web_search_queries or gm.grounding_chunks))


async def run_tool(call: types.FunctionCall) -> dict:
    func = TOOL_FUNCTIONS.get(call.name)
    if func is None:
        return {"error": f"Unknown tool: {call.name}"}
    try:
        # Tools make blocking HTTP calls, so run them off the event loop.
        return await asyncio.to_thread(func, **(call.args or {}))
    except TypeError as e:
        return {"error": f"Invalid arguments for {call.name}: {e}"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills")
def skills():
    return list_skills()


@app.post("/chat/{skill_name}", response_model=ChatResponse)
async def chat(skill_name: str, req: ChatRequest):
    skill = get_skill(skill_name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    contents = [
        types.Content(
            role="user" if m.role == "user" else "model",
            parts=[types.Part(text=m.content)],
        )
        for m in req.history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=req.message)]))

    config = types.GenerateContentConfig(
        system_instruction=skill["instructions"],
        tools=SKILL_TOOLS.get(skill_name),
    )
    tool_used = url = None

    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = await get_client().aio.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
            if used_search(response):
                tool_used = "searched the web"
            if not response.function_calls:
                break

            # Send the model's turn back unchanged (it may carry thought signatures),
            # followed by one function response per call.
            contents.append(response.candidates[0].content)
            result_parts = []
            for call in response.function_calls:
                result = await run_tool(call)
                if "tool_used" in result:
                    tool_used, url = result["tool_used"], result.get("url")
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

    return ChatResponse(reply=response.text or "", tool_used=tool_used, url=url)
