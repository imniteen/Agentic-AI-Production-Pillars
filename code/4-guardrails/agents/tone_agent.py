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
import logging

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("tone_agent")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class ToneAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.system_prompt = f"""
            You are a senior customer-service copy editor.
            Improve the tone of the reply:
            - Be clear, concise, and empathetic.
            - Keep all factual content.
            - Do NOT invent new details.
        """

    async def format_tone(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("tone_agent_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            try:
                tone_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["draft_reply"]),
                ])
                tone_chain = tone_agent_prompt_template | self.chat_llm
                tracer_instance = LangChainTracer(project_name=LANGSMITH_PROJECT_NAME)
                # Use provided callback_manager if available
                callback_manager = callback_manager if callback_manager else CallbackManager([tracer_instance])
                run_metadata = {
                    "run_name": f"Tone Agent: Tone Formatting for '{state['user_message'][:40]}{'...' if len(state['user_message']) > 40 else ''}'",
                    "run_id": state["run_id"],
                    "agent_name": "Tone",
                    "user_message": state["user_message"],
                    "timestamp": str(span.start_time) if hasattr(span, 'start_time') else datetime.now().isoformat()
                }
                result = await tone_chain.ainvoke({},
                                                  config=RunnableConfig(
                                                      callbacks=callback_manager,
                                                      metadata=run_metadata))
                span.set_attribute("tone.reply", result.content)
                state["final_reply"] = result.content
                if state.get("citations"):
                    state["final_reply"] += f"\n\n[Citations: {state.get('citations', 'none')}]"
                return state
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
