from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# OpenTelemetry imports
from opentelemetry import trace
import logging

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("tone_agent")

# No Prometheus usage in this file

class ToneAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a senior customer-service copy editor.
            Improve the tone of the reply:
            - Be clear, concise, and empathetic.
            - Keep all factual content.
            - Do NOT invent new details.
        """

    async def format_tone(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("tone_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received tone analysis request: {state['user_message']}")
            try:
                tone_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["draft_reply"]),
                ])
                tone_chain = tone_agent_prompt_template | self.chat_llm
                result = await tone_chain.ainvoke({},
                                                  config=RunnableConfig(
                                                      metadata={
                                                          "run_name": "tone_agent_reply",
                                                          "trace_id": trace_id,
                                                      }))
                logger.info(f"TraceID={trace_id} Tone reply: {result.content}")
                span.set_attribute("tone.reply", result.content)
                state["final_reply"] = result.content
                return state
            except Exception as e:
                logger.error(f"TraceID={trace_id} Tone agent failed: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
