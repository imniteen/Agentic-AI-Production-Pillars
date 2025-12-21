import uvicorn
from fastapi import FastAPI, Request
import logging
from opentelemetry import trace
from dotenv import load_dotenv
import asyncio
from models.chat_request import ChatRequest
from models.chat_response import ChatResponse
from graph import run_agent

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

otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
# Fix: Ensure span processor is only added once and not duplicated on reload
tracer_provider: TracerProvider = trace.get_tracer_provider()
if not hasattr(tracer_provider, "_otlp_span_processor_added"):
    tracer_provider.add_span_processor(span_processor)
    tracer_provider._otlp_span_processor_added = True
tracer = trace.get_tracer(__name__)
logger = logging.getLogger("backend")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest) -> ChatResponse:
    with tracer.start_as_current_span("backend_chat_endpoint") as span:
        trace_id = format(span.get_span_context().trace_id, 'x')
        logger.info(f"TraceID={trace_id} Incoming chat request from user_id={body.user_id}")
        state = await run_agent(body.user_id, body.message)
        reply = state.get("final_reply")
        if reply is None and state.get("intent") != "human":
            reply = "Sorry, the server encountered an error. Please try again later."
        intent = state.get("intent", "unknown")
        return ChatResponse(
            reply=reply,
            intent=intent,
            trace_id=state.get("trace_id", trace_id))

@app.exception_handler(Exception)
async def global_exception_handler(exc: Exception):
    span = get_current_span()
    trace_id = "N/A"
    if span and span.get_span_context():
        trace_id = format(span.get_span_context().trace_id, 'x')
    logger.error(f"TraceID={trace_id} Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "reply": "Sorry, the server encountered an error. Please try again later.",
            "intent": "error",
            "needs_human": False,
            "trace_id": trace_id
        }
    )

if __name__ == "__main__":
    #asyncio.run(chat_endpoint(ChatRequest(user_id="demo-user", message="Where is my order?")))
    uvicorn.run("backend:app", host="127.0.0.1", port=8001, reload=True)