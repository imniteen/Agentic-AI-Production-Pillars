from pydantic import BaseModel


class ChatResponse(BaseModel):
    run_id: str | None = None
    reply: str
    intent: str
