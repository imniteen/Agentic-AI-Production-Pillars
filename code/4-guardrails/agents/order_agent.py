import logging
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

# OpenTelemetry imports
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("order_agent")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class OrderAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.system_prompt = f"""
            You are a customer service agent.
            You receive structured order-status data from a backend service.
            Write a short, empathetic update to the customer, based on the JSON data.
            **If you do not have sufficient information, politely ask the customer for more details.**
            Do NOT expose raw JSON. Translate it into natural language.
        """

    async def order_details(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("order_agent_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            try:
                order_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                order_chain = order_agent_prompt_template | self.chat_llm
                tracer_instance = LangChainTracer(project_name=LANGSMITH_PROJECT_NAME)
                # Use provided callback_manager if available
                callback_manager = callback_manager if callback_manager else CallbackManager([tracer_instance])
                run_metadata = {
                    "run_name": f"Order Agent: Order Lookup for '{state['user_message'][:40]}{'...' if len(state['user_message']) > 40 else ''}'",
                    "run_id": state["run_id"],
                    "agent_name": "Order",
                    "user_message": state["user_message"],
                    "timestamp": str(span.start_time) if hasattr(span, 'start_time') else datetime.now().isoformat()
                }
                result = await order_chain.ainvoke({},
                                                   config=RunnableConfig(
                                                       callbacks=callback_manager,
                                                       metadata=run_metadata))
                span.set_attribute("order.reply", result.content)
                state["draft_reply"] = result.content
                return state
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
