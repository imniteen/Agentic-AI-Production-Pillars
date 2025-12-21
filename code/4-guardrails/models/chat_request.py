from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str
    run_id: str | None = None