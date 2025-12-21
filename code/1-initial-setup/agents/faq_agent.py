from state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

class FAQAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a friendly customer support agent.
            Answer the user's question clearly and concisely.
            Keep it under 4–5 sentences.
        """

    async def reply(self, state: OverallState) -> OverallState:
        faq_agent_prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=state["user_message"]),
            ]
        )
        faq_chain = faq_agent_prompt_template | self.chat_llm
        result = await faq_chain.ainvoke({})
        state["draft_reply"] = result.content
        return state
