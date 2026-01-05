import uvicorn
from fastapi import FastAPI, Request
import logging
from opentelemetry import trace
from dotenv import load_dotenv
import asyncio
from models.chat_request import ChatRequest
from models.chat_response import ChatResponse
from graph import run_agent, init_checkpointer, cleanup_checkpointer

# OpenTelemetry imports
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import get_current_span

from fastapi.responses import JSONResponse

load_dotenv(override=True)

app = FastAPI(title="Customer Service Agent")

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Set up OTLP exporter for Jaeger
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: "customer-service-agent"
            }
        )
    )
)

# Temporarily disabled to avoid connection errors
# otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
# span_processor = BatchSpanProcessor(otlp_exporter)
# # Fix: Ensure span processor is only added once and not duplicated on reload
# tracer_provider: TracerProvider = trace.get_tracer_provider()
# if not hasattr(tracer_provider, "_otlp_span_processor_added"):
#     tracer_provider.add_span_processor(span_processor)
#     tracer_provider._otlp_span_processor_added = True
tracer = trace.get_tracer(__name__)
logger = logging.getLogger("backend")


@app.on_event("startup")
async def startup_event():
    """Initialize checkpointer on startup."""
    logger.info("Initializing backend services...")
    await init_checkpointer()
    logger.info("Backend services initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down backend services...")
    await cleanup_checkpointer()
    logger.info("Backend services shutdown complete")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest) -> ChatResponse:
    with tracer.start_as_current_span("backend_chat_endpoint") as span:
        logger.info("=== RECEIVED CHAT REQUEST ===")
        trace_id = format(span.get_span_context().trace_id, 'x')
        logger.info(f"TraceID={trace_id} user_id={body.user_id} session_id={body.session_id} message={body.message[:50]}...")
        
        # Run agent with session management
        state, session_id = await run_agent(body.user_id, body.message, body.session_id)
        
        # Extract response data
        reply = state.get("final_reply")
        intent = state.get("intent", "unknown")
        awaiting_human_input = state.get("awaiting_human_input", False)
        
        # Handle cases where reply is not generated
        if reply is None:
            if awaiting_human_input:
                reply = "Your request has been escalated for human review.\n\n⏳ *Connecting you with a support engineer...*"
            else:
                reply = "Sorry, the server encountered an error. Please try again later."
        
        # Build conversation context
        conversation_context = {
            "order_id": state.get("order_id"),
            "pending_action": state.get("pending_action"),
            "conversation_history": state.get("conversation_history", []),
        }
        
        logger.info(f"TraceID={trace_id} Response: intent={intent} awaiting_human={awaiting_human_input} session_id={session_id}")
        
        return ChatResponse(
            reply=reply,
            intent=intent, # type: ignore
            trace_id=state.get("trace_id", trace_id), # type: ignore
            session_id=session_id,
            awaiting_human_input=awaiting_human_input, # type: ignore
            conversation_context=conversation_context
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    span = get_current_span()
    trace_id = "N/A"
    if span and span.get_span_context():
        trace_id = format(span.get_span_context().trace_id, 'x')
    logger.error(f"TraceID={trace_id} Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "reply": "Sorry, the server encountered an error. Please try again later.",
            "intent": "error",
            "trace_id": trace_id,
            "session_id": "",
            "awaiting_human_input": False,
            "conversation_context": None
        }
    )


if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8001, reload=True)