import logging
from models.state import OverallState

# OpenTelemetry imports
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("human")


class Human:
    def reply(self, state: OverallState) -> OverallState:
        with tracer.start_as_current_span("human_reply") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            state["trace_id"] = trace_id
            logger.info(f"TraceID={trace_id} Received order request: {state['user_message']}")
            state["final_reply"] = "Your request is escalated to an actual human. They will get back to you shortly."
            return state
