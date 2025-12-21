from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from models.state import OverallState
from agents.triage_agent import TriageAgent
from agents.faq_agent import FAQAgent
from agents.order_agent import OrderAgent
from agents.tone_agent import ToneAgent
from agents.human import Human
import constants
from edges import route_by_intent

# OpenTelemetry imports
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

load_dotenv(override=True)

workflow = StateGraph(state_schema=OverallState)

# Add nodes with tracing
triage_agent = TriageAgent()
async def triage_with_trace(state):
    with tracer.start_as_current_span("triage_agent"):
        return await triage_agent.classify_intent(state)
workflow.add_node(node=constants.TRIAGE_AGENT, action=triage_with_trace)

faq_agent = FAQAgent()
async def faq_with_trace(state):
    with tracer.start_as_current_span("faq_agent"):
        return await faq_agent.reply(state)
workflow.add_node(node=constants.FAQ_AGENT, action=faq_with_trace)

order_agent = OrderAgent()
async def order_with_trace(state):
    with tracer.start_as_current_span("order_agent"):
        return await order_agent.order_details(state)
workflow.add_node(node=constants.ORDER_AGENT, action=order_with_trace)

tone_agent = ToneAgent()
async def tone_with_trace(state):
    with tracer.start_as_current_span("tone_agent"):
        return await tone_agent.format_tone(state)
workflow.add_node(node=constants.TONE_AGENT, action=tone_with_trace)

human = Human()
def human_escalation(state: OverallState):
    with tracer.start_as_current_span("human_escalation"):
        return human.reply(state)
workflow.add_node(node=constants.HUMAN, action=human_escalation)

# Add edges
workflow.add_conditional_edges(
    source=constants.TRIAGE_AGENT,
    path=route_by_intent,
    path_map={
        constants.FAQ_AGENT: constants.FAQ_AGENT,
        constants.ORDER_AGENT: constants.ORDER_AGENT,
        constants.HUMAN: constants.HUMAN
    })
workflow.add_edge(constants.FAQ_AGENT, constants.TONE_AGENT)
workflow.add_edge(constants.ORDER_AGENT, constants.TONE_AGENT)
workflow.add_edge(constants.TONE_AGENT, END)

# Add start
workflow.add_edge(START, constants.TRIAGE_AGENT)

graph = workflow.compile()

async def run_agent(user_id: str, user_message: str) -> OverallState:
    """
    Thin wrapper the FastAPI backend will call.
    """
    initial: OverallState = {
        "user_id": user_id,
        "user_message": user_message
    }
    print(graph.get_graph().draw_mermaid())  # For debugging
    result: OverallState = await graph.ainvoke(initial)
    return result