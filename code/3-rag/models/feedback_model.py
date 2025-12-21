from pydantic import BaseModel


class FeedbackModel(BaseModel):
    user_id: str = "demo-user"
    run_id: str
    is_positive_feedback: bool
    comments: str = ""