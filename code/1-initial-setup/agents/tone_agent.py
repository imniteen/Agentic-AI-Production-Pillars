from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from state import OverallState

class ToneAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a senior customer-service copy editor.
            You are a senior customer-service copy editor.
            Improve the tone of the reply:
            - Be clear, concise, and empathetic.
            - Keep all factual content.
            - Do NOT invent new details.
        """

    async def reply(self, state: OverallState) -> OverallState:
        """Last-mile polishing agent for tone & phrasing."""
        draft = state.get("draft_reply") or ""
        tone_agent_prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=draft),
            ]
        )
        tone_chain = tone_agent_prompt_template | self.chat_llm
        result = await tone_chain.ainvoke({})
        state["final_reply"] = result.content
        return state