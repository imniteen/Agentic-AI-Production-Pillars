from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from state import OverallState
from agents.triage_agent import TriageAgent
from agents.faq_agent import FAQAgent
from agents.order_agent import OrderAgent
from agents.tone_agent import ToneAgent
import constants
from edges import route_by_intent

load_dotenv(override=True)

workflow = StateGraph(state_schema=OverallState)

# Add nodes
triage_agent = TriageAgent()
workflow.add_node(node=constants.TRIAGE_AGENT, action=triage_agent.triage)

faq_agent = FAQAgent()
workflow.add_node(node=constants.FAQ_AGENT, action=faq_agent.reply)

order_agent = OrderAgent()
workflow.add_node(node=constants.ORDER_AGENT, action=order_agent.order_details)

tone_agent = ToneAgent()
workflow.add_node(node=constants.TONE_AGENT, action=tone_agent.reply)

# Add a dummy action for human approval node
def human_approval_action(state: OverallState):
    # Placeholder for human approval logic
    return state

workflow.add_node(node=constants.HUMAN_APPROVAL, action=human_approval_action)

# Add edges
workflow.add_conditional_edges(
    source=constants.TRIAGE_AGENT,
    path=route_by_intent,
    path_map={
        constants.FAQ_AGENT: constants.FAQ_AGENT,
        constants.ORDER_AGENT: constants.ORDER_AGENT,
        constants.HUMAN_APPROVAL: constants.HUMAN_APPROVAL
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