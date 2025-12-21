from typing import TypedDict, Optional, Annotated, List, Dict, Any

from langgraph.graph import add_messages


class OverallState(TypedDict):
    messages: Optional[Annotated[list[str], add_messages]]
    user_message: str
    user_id: Optional[str]
    intent: Optional[str]  # "faq" | "order" | "human"
    order_id: Optional[str]
    draft_reply: Optional[str]
    final_reply: Optional[str]
    citations: Optional[str]
    run_id: Optional[str]
    # 🔹 RAG-specific fields for evaluation & observability
    rag_contexts: List[str]  # ONLY the chunk texts used as context
    rag_sources: List[Dict[str, Any]]  # structured metadata per chunk
    # Optional: if you have gold answers
    ground_truth: Optional[str]

