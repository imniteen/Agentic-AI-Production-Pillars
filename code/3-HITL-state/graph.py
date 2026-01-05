from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from models.state import OverallState
from agents.triage_agent import TriageAgent
from agents.faq_agent import FAQAgent
from agents.order_agent import OrderAgent
from agents.tone_agent import ToneAgent
from agents.human import Human
import constants
from edges import route_by_intent
import os
import uuid
import logging

# OpenTelemetry imports
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
logger = logging.getLogger("graph")

load_dotenv(override=True)

# Global checkpointer instance and context manager
_checkpointer = None
_checkpointer_context = None


async def init_checkpointer():
    """Initialize PostgreSQL checkpointer with connection string."""
    global _checkpointer, _checkpointer_context
    
    if _checkpointer is not None:
        return _checkpointer
    
    try:
        # Get PostgreSQL configuration from environment
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_db = os.getenv("POSTGRES_DB", "agent_state")
        pg_user = os.getenv("POSTGRES_USER", "agent_app")
        pg_password = os.getenv("POSTGRES_PASSWORD", "secure_password")
        
        # Build PostgreSQL connection string
        connection_string = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        
        logger.info(f"Initializing PostgreSQL checkpointer: {pg_host}:{pg_port}/{pg_db}")
        
        # Create and store the context manager, then enter it
        _checkpointer_context = AsyncPostgresSaver.from_conn_string(connection_string)
        _checkpointer = await _checkpointer_context.__aenter__()
        
        # Setup database schema (creates tables if they don't exist)
        await _checkpointer.setup()
        
        logger.info("PostgreSQL checkpointer initialized successfully")
        return _checkpointer
        
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
        logger.warning("Falling back to in-memory checkpointer (MemorySaver)")
        # Fallback to MemorySaver for development
        _checkpointer = MemorySaver()
        _checkpointer_context = None
        return _checkpointer


async def get_checkpointer():
    """Get or initialize the checkpointer instance."""
    if _checkpointer is None:
        return await init_checkpointer()
    return _checkpointer


async def cleanup_checkpointer():
    """Cleanup resources on shutdown."""
    global _checkpointer, _checkpointer_context
    
    if _checkpointer_context:
        logger.info("Closing PostgreSQL checkpointer connections")
        try:
            await _checkpointer_context.__aexit__(None, None, None)
            logger.info("PostgreSQL checkpointer cleanup complete")
        except Exception as e:
            logger.error(f"Error during checkpointer cleanup: {e}")
    
    _checkpointer = None
    _checkpointer_context = None


# Build workflow
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
workflow.add_edge(constants.HUMAN, END)  # Human node ends conversation (awaits input)

# Add start
workflow.add_edge(START, constants.TRIAGE_AGENT)

async def compile_graph():
    """Compile the graph with checkpointer."""
    checkpointer = await get_checkpointer()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[constants.HUMAN]  # Pause execution before human node
    )


async def run_agent(
    user_id: str,
    user_message: str,
    session_id: str | None = None,
    response_language: str | None = None
) -> tuple[OverallState, str]:
    """
    Run the agent workflow with state persistence.

    Args:
        user_id: User identifier
        user_message: User's message
        session_id: Optional session ID for conversation continuity
        response_language: Optional language code for multi-lingual responses (e.g., "hi-IN")

    Returns:
        Tuple of (final_state, session_id)
    """
    # Generate session_id if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Create thread_id for checkpointing
    thread_id = f"{user_id}:{session_id}"

    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "customer_service"
        }
    }

    # Get compiled graph
    graph = await compile_graph()

    # print mermaid diagram for debugging
    mermaid = graph.get_graph().draw_mermaid()
    logger.info("Compiled StateGraph:\n" + mermaid)

    # Check if we're resuming from a checkpoint
    checkpointer = await get_checkpointer()
    existing_state = await checkpointer.aget(config)

    if existing_state:
        logger.info(f"Resuming conversation for session: {session_id}")
        # Resume with new user message
        initial: OverallState = {
            "user_message": user_message,
            "user_id": user_id,
            "session_id": session_id,
            "response_language": response_language,
        }
    else:
        logger.info(f"Starting new conversation for session: {session_id}")
        # New conversation
        initial: OverallState = {
            "user_id": user_id,
            "user_message": user_message,
            "session_id": session_id,
            "conversation_history": [],
            "awaiting_human_input": False,
            "response_language": response_language,
        }

    # Execute graph
    result: OverallState = await graph.ainvoke(initial, config=config)

    # Check if we hit an interrupt (human node)
    if result.get("intent") == "human" and not result.get("final_reply"):
        result["awaiting_human_input"] = True
        logger.info(f"Conversation paused for human review: {session_id}")

    return result, session_id
