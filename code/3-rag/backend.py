import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from langchain_openai import OpenAIEmbeddings

from evals_framework.continuous_evaluator import ContinuousEvaluator
from evals_framework.dynamic_dataset_builder import DynamicDatasetBuilder
from models.feedback_model import FeedbackModel
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
BASE_DIR_3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "3-rag"))
sys.path.insert(0, BASE_DIR_3)  # put 3 *before* 2

import uvicorn
from fastapi import FastAPI, Request
import logging
from opentelemetry import trace
from dotenv import load_dotenv
from models.chat_request import ChatRequest
from models.chat_response import ChatResponse
from graph import run_agent
from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan

# OpenTelemetry imports
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import get_current_span
from evals_framework.feedback_collector import FeedbackCollector

from fastapi.responses import JSONResponse

load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "customer-service-rag")

app = FastAPI(title="Customer Service Agent")

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Set up OTLP exporter for Jaeger
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: "customer-service-agent-backend"
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
logger.setLevel(logging.INFO)

def index_documents():
    pinecone_instance = Pinecone(
        api_key=os.environ.get("PINECONE_API_KEY")
    )

    # Delete the index if it exists
    index_names = [index.name for index in pinecone_instance.list_indexes().indexes]
    if PINECONE_INDEX in index_names:
        pinecone_instance.delete_index(PINECONE_INDEX)

    index_names = [index.name for index in pinecone_instance.list_indexes().indexes]
    if PINECONE_INDEX in index_names:
        # If the index still exists, wait for it to be deleted
        import time
        while PINECONE_INDEX in index_names:
            time.sleep(1)
            index_names = [index.name for index in pinecone_instance.list_indexes().indexes]

    pinecone_instance.create_index(
        PINECONE_INDEX,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    docs_path = Path(__file__).resolve().parent / "customer_docs"
    docs = []
    for path in docs_path.iterdir():
        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))  # PDF → text
        else:
            loader = TextLoader(str(path), encoding="utf-8")  # TXT → text
        docs.extend(loader.load())

    # Split using RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    chunks = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()

    # Deduplicate chunks by page_content and metadata
    unique_chunks = []
    seen = set()
    for chunk in chunks:
        # Use a tuple of page_content and sorted metadata items as a unique key
        meta_tuple = tuple(sorted(chunk.metadata.items())) if hasattr(chunk, 'metadata') else ()
        key = (chunk.page_content, meta_tuple)
        if key not in seen:
            seen.add(key)
            unique_chunks.append(chunk)

    PineconeVectorStore.from_documents(
        documents=unique_chunks,
        embedding=embeddings,
        index_name=PINECONE_INDEX,
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest) -> ChatResponse:
    with tracer.start_as_current_span("backend_chat_endpoint") as span:
        span.set_attribute("run_id", body.run_id)
        state = await run_agent(body.user_id, body.message, run_id=body.run_id)
        reply = state.get("final_reply")
        if reply is None and state.get("intent") != "human":
            reply = "Sorry, the server encountered an error. Please try again later."
        intent = state.get("intent", "unknown")
        return ChatResponse(
            run_id=body.run_id,
            reply=reply,
            intent=intent)

@app.post("/feedback")
async def feedback_endpoint(body: FeedbackModel) -> None:
    with tracer.start_as_current_span("backend_feedback_endpoint") as span:
        span.set_attribute("run_id", body.run_id)
        feedback_collector = FeedbackCollector()
        feedback_collector.add_thumbs_feedback(
            run_id=body.run_id,
            is_positive_feedback=body.is_positive_feedback,
            comment=body.comments or ""
        )

@app.post("/dataset")
async def dataset_creation_endpoint():
    with tracer.start_as_current_span("backend_dataset_endpoint") as span:
        dynamic_dataset_builder = DynamicDatasetBuilder()
        dynamic_dataset_builder.create_dataset_from_production()

@app.post("/evaluate")
async def evaluate():
    with tracer.start_as_current_span("backend_evaluate_endpoint") as span:
        evaluator = ContinuousEvaluator()
        evaluator.evaluate_production_sample()

@app.exception_handler(Exception)
async def global_exception_handler(exc: Exception):
    span = get_current_span()
    span.record_exception(exc)
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
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
    index_documents()
    uvicorn.run("backend:app", host="127.0.0.1", port=8001, reload=True)