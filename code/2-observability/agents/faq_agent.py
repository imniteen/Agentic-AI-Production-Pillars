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

class FAQAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a friendly customer support agent.
            Answer the user's question clearly and concisely.
            Keep it under 4–5 sentences.
        """

    async def reply(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("faq_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received user message: {state['user_message']}")
            try:
                faq_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
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
