import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from graph import run_agent
from dotenv import load_dotenv

load_dotenv(override=True)


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str
    needs_human: bool


app = FastAPI(title="Customer Service Agent")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest) -> ChatResponse:
    state = await run_agent(body.user_id, body.message)

    reply = (
        state.get("final_reply")
        or state.get("draft_reply")
        or "Sorry, I had trouble generating an answer."
    )

    return ChatResponse(
        reply=reply,
        intent=state.get("intent", "unknown"),
        needs_human=bool(state.get("needs_human", False)),
    )


if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8001, reload=True)