from pydantic import BaseModel
from typing import Optional


class ChatResponse(BaseModel):
    reply: str
    intent: str
    trace_id: str
    session_id: str
    awaiting_human_input: bool = False
    conversation_context: Optional[dict] = None
