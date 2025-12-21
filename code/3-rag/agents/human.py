import logging
import os

from models.state import OverallState

# OpenTelemetry imports
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("human")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")

class Human:
    def reply(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("human_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            state["final_reply"] = "Your request is escalated to an actual human. They will get back to you shortly."
            return state
