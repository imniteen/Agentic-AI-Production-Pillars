import logging

from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# OpenTelemetry imports
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("order_agent")


# Language code to name mapping for multi-lingual support
LANGUAGE_NAMES = {
    "en-US": "English", "en-IN": "English", "en-GB": "English",
    "hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu",
    "mr-IN": "Marathi", "gu-IN": "Gujarati", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "bn-IN": "Bengali", "pa-IN": "Punjabi",
}


class OrderAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.base_system_prompt = """
            You are a customer service agent.
            You receive structured order-status data from a backend service.
            Write a short, empathetic update to the customer, based on the JSON data.
            **If you do not have sufficient information, politely ask the customer for more details.**
            Do NOT expose raw JSON. Translate it into natural language.
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

    async def order_details(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("order_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            response_language = state.get("response_language")
            logger.info(f"TraceID={trace_id} Received order request: {state['user_message']} (language: {response_language})")
            try:
                system_prompt = self._get_system_prompt(response_language)
                order_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                order_chain = order_agent_prompt_template | self.chat_llm
                result = await order_chain.ainvoke({},
                                                   config=RunnableConfig(
                                                         metadata={
                                                             "run_name": "order_agent_reply",
                                                             "trace_id": trace_id,
                                                         }))
                logger.info(f"TraceID={trace_id} Order reply: {result.content}")
                span.set_attribute("order.reply", result.content)
                state["draft_reply"] = result.content
                return state
            except Exception as e:
                logger.error(f"TraceID={trace_id} Order agent failed: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
