import os
from uuid import UUID

from dotenv import load_dotenv
from langchain_core.callbacks import CallbackManager
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers import LangChainTracer
from langgraph.graph import StateGraph, START, END
from models.state import OverallState
from agents.triage_agent import TriageAgent
from agents.faq_agent import FAQAgent
from agents.order_agent import OrderAgent
from agents.tone_agent import ToneAgent
from agents.rag_agent import RAGAgent
from agents.human import Human
from agents.policy_agent import PolicyAgent
import constants
from edges import route_by_intent, route_by_faq, route_by_policy

# OpenTelemetry imports
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

load_dotenv(override=True)

workflow = StateGraph(state_schema=OverallState)
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")

triage_agent = TriageAgent()
async def triage_with_trace(state, config=None):
    with tracer.start_as_current_span("triage_agent"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return await triage_agent.classify_intent(state, callback_manager=callback_manager)
workflow.add_node(node=constants.TRIAGE_AGENT, action=triage_with_trace)

faq_agent = FAQAgent()
async def faq_with_trace(state, config=None):
    with tracer.start_as_current_span("faq_agent"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return await faq_agent.reply(state, callback_manager=callback_manager)
workflow.add_node(node=constants.FAQ_AGENT, action=faq_with_trace)

order_agent = OrderAgent()
async def order_with_trace(state, config=None):
    with tracer.start_as_current_span("order_agent"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return await order_agent.order_details(state, callback_manager=callback_manager)
workflow.add_node(node=constants.ORDER_AGENT, action=order_with_trace)

tone_agent = ToneAgent()
async def tone_with_trace(state, config=None):
    with tracer.start_as_current_span("tone_agent"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return await tone_agent.format_tone(state, callback_manager=callback_manager)
workflow.add_node(node=constants.TONE_AGENT, action=tone_with_trace)

rag_agent = RAGAgent()
async def rag_with_trace(state, config=None):
    with tracer.start_as_current_span("rag_agent"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return await rag_agent.search(state, callback_manager=callback_manager)
workflow.add_node(node=constants.RAG_AGENT, action=rag_with_trace)

human = Human()
def human_escalation(state, config=None):
    with tracer.start_as_current_span("human_escalation"):
        callback_manager = config.callbacks if config and hasattr(config, 'callbacks') else None
        return human.reply(state, callback_manager=callback_manager)
workflow.add_node(node=constants.HUMAN, action=human_escalation)

policy_agent = PolicyAgent()
async def policy_in_with_trace(state, config=None):
    with tracer.start_as_current_span("policy_in"):
        callback_manager = config.callbacks if config and hasattr(config, "callbacks") else None
        return await policy_agent.enforce_input(state, callback_manager=callback_manager)
workflow.add_node(node=constants.POLICY_IN_AGENT, action=policy_in_with_trace)

async def policy_out_with_trace(state, config=None):
    with tracer.start_as_current_span("policy_out"):
        callback_manager = config.callbacks if config and hasattr(config, "callbacks") else None
        return await policy_agent.enforce_output(state, callback_manager=callback_manager)
workflow.add_node(node=constants.POLICY_OUT_AGENT, action=policy_out_with_trace)

# Add edges
workflow.add_conditional_edges(
    source=constants.POLICY_IN_AGENT,
    path=route_by_policy,
    path_map={
        constants.TRIAGE_AGENT: constants.TRIAGE_AGENT,
        constants.HUMAN: constants.HUMAN,
    }
)

workflow.add_conditional_edges(
    source=constants.TRIAGE_AGENT,
    path=route_by_intent,
    path_map={
        constants.FAQ_AGENT: constants.FAQ_AGENT,
        constants.ORDER_AGENT: constants.ORDER_AGENT,
        constants.POLICY_OUT_AGENT: constants.POLICY_OUT_AGENT,
        constants.HUMAN: constants.HUMAN
    })

workflow.add_conditional_edges(
    source=constants.FAQ_AGENT,
    path=route_by_faq,
    path_map={
        constants.RAG_AGENT: constants.RAG_AGENT,
        constants.POLICY_OUT_AGENT: constants.POLICY_OUT_AGENT
    })

workflow.add_edge(constants.RAG_AGENT, constants.POLICY_OUT_AGENT)
workflow.add_edge(constants.ORDER_AGENT, constants.POLICY_OUT_AGENT)
workflow.add_edge(constants.POLICY_OUT_AGENT, constants.TONE_AGENT)
workflow.add_edge(constants.TONE_AGENT, END)

# Add start
workflow.add_edge(START, constants.POLICY_IN_AGENT)

graph = workflow.compile()


async def run_agent(user_id, user_message, run_id=None):
    """
    Thin wrapper the FastAPI backend will call.
    """
    state = OverallState(user_id=user_id, user_message=user_message, run_id=run_id)
    print(graph.get_graph().draw_mermaid())  # For debugging
    tracer_instance = LangChainTracer(project_name=LANGSMITH_PROJECT_NAME)
    callback_manager = CallbackManager([tracer_instance])
    result = await graph.ainvoke(
        input=state,
        callbacks=callback_manager,
        config=RunnableConfig(
            run_id=UUID(state["run_id"]),
            metadata={
                "run_name": "graph_run",
                "run_id": state["run_id"],
            }
    ))

    # result: OverallState = await graph.ainvoke(
    #     input=state,
    #     config=RunnableConfig(
    #         callbacks=callback_manager,
    #         run_id=UUID(state["run_id"]),
    #         metadata={
    #             "run_name": "graph_run",
    #             "run_id": state["run_id"],
    #         }
    #     )
    # )

    return result
