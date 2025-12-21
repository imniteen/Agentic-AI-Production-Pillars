import json
import logging

from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_openai import ChatOpenAI

# OpenTelemetry imports
from opentelemetry import trace

from tools.order_tool import call_order_mcp

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("order_agent")


class OrderAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI(model="gpt-4o-mini")
        self.system_prompt = f"""
            You are a customer service agent.
            You receive structured order-status data from a backend service.
            Write a short, empathetic update to the customer, based on the JSON data.
            Do NOT expose raw JSON. Translate it into natural language.
        """

    async def order_details(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("order_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received order request: {state['user_message']}")
            try:
                order_id = state.get("order_id")
                if not order_id:
                    draft = (
                        "I tried to look up your order, but I couldn't find an order ID in your "
                        "message. Please reply with your order ID (e.g. ORD-123)."
                    )
                    state["draft_reply"] = draft
                    return state

                tool_result = await call_order_mcp(order_id)
                tool_json = json.dumps(tool_result[0].text, indent=2)

                user_message = f"Original user message:\n{state['user_message']}\n\nOrder data:\n{tool_json}"
                order_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                order_chain = order_agent_prompt_template | self.chat_llm
                result = await order_chain.ainvoke({
                    "user_message": user_message
                },
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
