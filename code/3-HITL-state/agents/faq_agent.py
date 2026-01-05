from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# OpenTelemetry imports
from opentelemetry import trace
import logging

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("faq_agent")

# No Prometheus usage in this file

# Language code to name mapping for multi-lingual support
LANGUAGE_NAMES = {
    "en-US": "English", "en-IN": "English", "en-GB": "English",
    "hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu",
    "mr-IN": "Marathi", "gu-IN": "Gujarati", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "bn-IN": "Bengali", "pa-IN": "Punjabi",
}


class FAQAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.base_system_prompt = """
            You are a friendly customer support agent.
            Answer the user's question clearly and concisely.
            If you don't know, say you don't know instead of hallucinating.
            Keep it under 4–5 sentences.
        """

    def _get_system_prompt(self, response_language: str | None) -> str:
        """Get system prompt with language instruction if needed."""
        if response_language and not response_language.startswith("en"):
            lang_name = LANGUAGE_NAMES.get(response_language, response_language)
            return f"""
            {self.base_system_prompt}

            CRITICAL LANGUAGE REQUIREMENT: The user is communicating in {lang_name}.
            You MUST respond ENTIRELY in {lang_name} language only. Do NOT use English at all.
            """
        return self.base_system_prompt

    async def reply(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("faq_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            response_language = state.get("response_language")
            logger.info(f"TraceID={trace_id} Received user message: {state['user_message']} (language: {response_language})")
            try:
                system_prompt = self._get_system_prompt(response_language)
                faq_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                faq_chain = faq_agent_prompt_template | self.chat_llm
                result = await faq_chain.ainvoke({},
                                                 config=RunnableConfig(
                                                     metadata={
                                                         "run_name": "faq_agent_reply",
                                                         "trace_id": trace_id,
                                                     }))
                logger.info(f"TraceID={trace_id} Draft reply: {result.content}")
                span.set_attribute("faq.reply", result.content)
                state["draft_reply"] = result.content
                return state
            except Exception as e:
                logger.error(f"TraceID={trace_id} FAQ agent failed: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
