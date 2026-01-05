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

    async def order_details(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("order_agent_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received order request: {state['user_message']}")
            try:
                order_agent_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
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
