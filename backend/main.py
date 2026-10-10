from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

load_dotenv()

from skills import get_skill, list_skills  # noqa: E402  (scans skills/ on import)

MODEL = "gemma-4-26b-a4b-it"

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

    try:
        response = await get_client().aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=skill["instructions"]),
        )
    except errors.APIError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error ({e.code}): {e.message}")

    return ChatResponse(reply=response.text or "")
