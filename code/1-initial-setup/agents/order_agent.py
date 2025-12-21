import json
from state import OverallState
from tools.order_tool import call_order_mcp
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain_openai import ChatOpenAI


class OrderAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a customer service agent.
            You receive structured order-status data from a backend service.
            Write a short, empathetic update to the customer, based on the JSON data.
            Do NOT expose raw JSON. Translate it into natural language.
        """

    async def order_details(self, state: OverallState) -> OverallState:
        """
        Order-status agent.

        - Reads order_id from state (if missing, ask user for it).
        - Calls MCP get_order_status tool.
        - Drafts a reply based on the tool result.
        """
        order_id = state.get("order_id")
        if not order_id:
            draft = (
                "I tried to look up your order, but I couldn't find an order ID in your "
                "message. Please reply with your order ID (e.g. ORD-123)."
            )
            state["draft_reply"] = draft
            return state

        tool_result = await call_order_mcp(order_id)
        tool_json = json.dumps(tool_result[0].text, indent=2)

        order_agent_prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                HumanMessagePromptTemplate.from_template("{user_message}"),
            ]
        )
        user_message = f"Original user message:\n{state['user_message']}\n\nOrder data:\n{tool_json}"
        order_agent_prompt_chain = order_agent_prompt_template | self.chat_llm
        result = await order_agent_prompt_chain.ainvoke({
            "user_message": user_message
        })
        state["draft_reply"] = result.content
        return state