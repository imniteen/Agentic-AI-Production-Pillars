from typing import TypedDict, Optional, Annotated

from langgraph.graph import add_messages


class OverallState(TypedDict):
    messages: Optional[Annotated[list[str], add_messages]]
    user_message: str
    user_id: Optional[str]
    intent: Optional[str]  # "faq" | "order" | "human"
    order_id: Optional[str]
    needs_human: Optional[bool]
    draft_reply: Optional[str]
    final_reply: Optional[str]
