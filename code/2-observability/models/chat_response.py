from pydantic import BaseModel


class ChatResponse(BaseModel):
    reply: str
    intent: str
    trace_id: str