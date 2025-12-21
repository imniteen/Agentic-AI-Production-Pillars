from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import logging
from opentelemetry import trace
import json

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("triage_agent")

class TriageAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.system_prompt = f"""
            You are a supervisor for a customer-service assistant.
            You MUST respond as a JSON object with these keys:
            - "intent": one of "faq", "order", "human"
            - "order_id": null or a string like "ORD-123"

            Use:
            - "order" when the user clearly asks about a specific order.
            - "faq" for general questions, policies, or chit-chat.
            - "human" when the user is angry, confused, or the request feels sensitive or risky.
        """

    async def classify_intent(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("triage_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received triage request: {state['user_message']}")
            try:
                triage_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                triage_chain = triage_agent_prompt_template | self.chat_llm
                result = await triage_chain.ainvoke({},
                                                    config=RunnableConfig(
                                                        metadata={
                                                            "trace_id": trace_id,
                                                            "run_name": "triage_agent_reply"
                                                        }
                                                    ))
                logger.info(f"TraceID={trace_id} Triage reply: {result.content}")
                span.set_attribute("triage.reply", result.content)
                # Parse JSON reply
                cleaned = result.content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`")
                    cleaned = cleaned.replace("json", "", 1).strip()
                fallback = {"intent": "faq", "order_id": None}
                try:
                    parsed = json.loads(cleaned)
                except Exception as e:
                    logger.error(f"Triage agent JSON parse failed: {e}")
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    parsed = fallback
                state["intent"] = parsed.get("intent", "faq")
                state["order_id"] = parsed.get("order_id")
                state["draft_reply"] = result.content
                return state
            except Exception as e:
                logger.error(f"TraceID={trace_id} Triage agent failed: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
