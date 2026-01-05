from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str
    session_id: Optional[str] = None
