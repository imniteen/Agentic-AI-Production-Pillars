import os
from datetime import datetime
from uuid import UUID

from langchain_core.callbacks import CallbackManager
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers import LangChainTracer

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import logging
from opentelemetry import trace
import json

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("triage_agent")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class TriageAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.system_prompt = f"""
            You are a supervisor for a customer-service assistant.
            You MUST respond as a JSON object with these keys:
            - "intent": one of "faq", "order", "human"
            - "order_id": null or a string like "ORD-123"

            Use:
            - "order" when the user clearly asks about a specific order and provides an order ID.
            - "faq" for general questions about company, orders, policies, returns and refunds, etc., without a specific order ID.
            - "chit-chat" for casual conversation not related to customer service.
            - "human" when the user is angry, confused, or the request feels sensitive or risky.
        """

    async def classify_intent(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("triage_agent_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            try:
                triage_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                triage_chain = triage_agent_prompt_template | self.chat_llm
                tracer_instance = LangChainTracer(project_name=LANGSMITH_PROJECT_NAME)
                # Use provided callback_manager if available
                callback_manager = callback_manager if callback_manager else CallbackManager([tracer_instance])

                run_metadata = {
                    "run_name": f"Triage Agent: Intent Classification for '{state['user_message'][:40]}{'...' if len(state['user_message']) > 40 else ''}'",
                    "run_id": state["run_id"],
                    "agent_name": "Triage",
                    "user_message": state["user_message"],
                    "timestamp": str(span.start_time) if hasattr(span, 'start_time') else datetime.now().isoformat()
                }

                result = await triage_chain.ainvoke({},
                                                    config=RunnableConfig(
                                                        callbacks=callback_manager,
                                                        metadata=run_metadata
                                                    ))
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
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
