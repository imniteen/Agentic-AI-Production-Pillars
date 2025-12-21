import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from state import OverallState

class TriageAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
                You are a supervisor for a customer-service assistant.
                You MUST respond as a JSON object with these keys:
                - "intent": one of "faq", "order", "human"
                - "order_id": null or a string like "ORD-123"
                - "needs_human": true or false
    
                Use:
                - "order" when the user clearly asks about a specific order.
                - "faq" for general questions, policies, or chit-chat.
                - "human" when the user is angry, confused, or the request feels sensitive or risky.
            """

    async def triage(self, state: OverallState) -> OverallState:
        """
            Decide:
            - is this an FAQ vs order-status vs needs-human?
            - extract an order_id if present.
        """
        supervisor_agent_prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=state["user_message"]),
            ]
        )
        support_customer_chain = supervisor_agent_prompt_template | self.chat_llm
        result = await support_customer_chain.ainvoke({})

        cleaned = result.content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()

        fallback = {"intent": "faq", "order_id": None, "needs_human": False}
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            parsed = fallback

        state["intent"] = parsed.get("intent", "faq")
        state["order_id"] = parsed.get("order_id")
        state["needs_human"] = bool(parsed.get("needs_human", False))
        return state
