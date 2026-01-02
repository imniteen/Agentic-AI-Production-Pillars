import uvicorn
import tempfile
import os
import base64
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
import logging
from opentelemetry import trace
from dotenv import load_dotenv
import asyncio
from typing import Optional
from pydantic import BaseModel
from models.chat_request import ChatRequest
from models.chat_response import ChatResponse
from graph import run_agent, init_checkpointer, cleanup_checkpointer
from services.speech_service import get_speech_service

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


class VoiceChatResponse(BaseModel):
    """Response model for voice chat endpoint."""
    reply: str
    intent: str
    trace_id: str
    session_id: str
    awaiting_human_input: bool = False
    conversation_context: Optional[dict] = None
    transcribed_text: str = ""
    audio_file: Optional[str] = None  # Path to audio response file


@app.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat_endpoint(
    audio_file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user_id: str = Form("demo-user")
) -> VoiceChatResponse:
    """
    Voice chat endpoint that handles audio input and returns audio + text response.

    Args:
        audio_file: Audio file from microphone (WAV format)
        session_id: Optional session ID for conversation continuity
        user_id: User identifier

    Returns:
        VoiceChatResponse with text reply, audio path, and session info
    """
    with tracer.start_as_current_span("backend_voice_chat_endpoint") as span:
        trace_id = format(span.get_span_context().trace_id, 'x')
        logger.info(f"=== RECEIVED VOICE CHAT REQUEST ===")
        logger.info(f"TraceID={trace_id} user_id={user_id} session_id={session_id}")

        speech_service = get_speech_service()

        # Save uploaded audio to temp file
        temp_dir = Path(tempfile.gettempdir()) / "voice_agent"
        temp_dir.mkdir(exist_ok=True)
        input_audio_path = temp_dir / f"input_{trace_id}.wav"

        try:
            # Save uploaded audio
            content = await audio_file.read()
            with open(input_audio_path, "wb") as f:
                f.write(content)
            logger.info(f"TraceID={trace_id} Saved audio file: {input_audio_path}")

            # Speech-to-Text
            transcribed_text, stt_success = speech_service.speech_to_text(str(input_audio_path))

            if not stt_success or not transcribed_text:
                logger.warning(f"TraceID={trace_id} STT failed or empty result")
                return VoiceChatResponse(
                    reply="I couldn't understand your voice input. Please try again or use text chat.",
                    intent="error",
                    trace_id=trace_id,
                    session_id=session_id or "",
                    awaiting_human_input=False,
                    transcribed_text="",
                    audio_file=None
                )

            logger.info(f"TraceID={trace_id} Transcribed: {transcribed_text[:100]}...")

            # Run agent with transcribed text
            state, result_session_id = await run_agent(user_id, transcribed_text, session_id)

            # Extract response data
            reply = state.get("final_reply")
            intent = state.get("intent", "unknown")
            awaiting_human_input = state.get("awaiting_human_input", False)

            # Handle cases where reply is not generated
            if reply is None:
                if awaiting_human_input:
                    reply = "Your request has been escalated for human review. A support engineer will assist you shortly."
                else:
                    reply = "Sorry, the server encountered an error. Please try again later."

            # Text-to-Speech for response
            output_audio_path = None
            if speech_service.is_available:
                tts_output_path, tts_success = speech_service.text_to_speech(reply)
                if tts_success:
                    output_audio_path = tts_output_path
                    logger.info(f"TraceID={trace_id} TTS output: {output_audio_path}")

            # Build conversation context
            conversation_context = {
                "order_id": state.get("order_id"),
                "pending_action": state.get("pending_action"),
                "conversation_history": state.get("conversation_history", []),
            }

            logger.info(
                f"TraceID={trace_id} Response: intent={intent} "
                f"awaiting_human={awaiting_human_input} session_id={result_session_id}"
            )

            return VoiceChatResponse(
                reply=reply,
                intent=intent,
                trace_id=state.get("trace_id", trace_id),
                session_id=result_session_id,
                awaiting_human_input=awaiting_human_input,
                conversation_context=conversation_context,
                transcribed_text=transcribed_text,
                audio_file=output_audio_path
            )

        except Exception as e:
            logger.error(f"TraceID={trace_id} Voice chat error: {e}", exc_info=True)
            span.record_exception(e)
            return VoiceChatResponse(
                reply="Sorry, an error occurred processing your voice input.",
                intent="error",
                trace_id=trace_id,
                session_id=session_id or "",
                awaiting_human_input=False,
                transcribed_text="",
                audio_file=None
            )

        finally:
            # Cleanup input audio file
            try:
                if input_audio_path.exists():
                    input_audio_path.unlink()
            except Exception:
                pass


@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio files."""
    temp_dir = Path(tempfile.gettempdir()) / "speech_agent"
    file_path = temp_dir / filename

    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Audio file not found"})

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=filename
    )


@app.get("/speech-status")
async def speech_status():
    """Check if speech service is available and configured."""
    speech_service = get_speech_service()
    return {
        "available": speech_service.is_available,
        "region": speech_service.speech_region if speech_service.is_available else None,
        "voice": speech_service.voice_name if speech_service.is_available else None,
        "language": speech_service.speech_recognition_language if speech_service.is_available else None
    }


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