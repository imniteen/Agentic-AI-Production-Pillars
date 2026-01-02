"""Azure Speech Service wrapper for voice input/output capabilities."""

import os
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from opentelemetry import trace

# Ensure environment variables are loaded
load_dotenv(override=True)

# Azure Speech SDK
try:
    import azure.cognitiveservices.speech as speechsdk
    SPEECH_SDK_AVAILABLE = True
except ImportError:
    SPEECH_SDK_AVAILABLE = False
    speechsdk = None

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("speech_service")


class SpeechService:
    """Azure Speech Service wrapper for STT and TTS operations."""

    def __init__(self):
        """Initialize SpeechService with Azure credentials from environment."""
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
        self.voice_name = os.getenv("AZURE_SPEECH_VOICE", "en-US-JennyNeural")
        self.speech_recognition_language = os.getenv("AZURE_SPEECH_LANGUAGE", "en-US")

        # Temp directory for audio files
        self.temp_dir = Path(tempfile.gettempdir()) / "speech_agent"
        self.temp_dir.mkdir(exist_ok=True)

        self._validate_config()

    def _validate_config(self) -> None:
        """Validate Azure Speech configuration."""
        if not SPEECH_SDK_AVAILABLE:
            logger.warning(
                "Azure Speech SDK not installed. "
                "Install with: pip install azure-cognitiveservices-speech"
            )
            return

        if not self.speech_key:
            logger.warning(
                "AZURE_SPEECH_KEY not configured. "
                "Voice features will be disabled."
            )
        else:
            logger.info(
                f"SpeechService initialized: region={self.speech_region}, "
                f"voice={self.voice_name}, language={self.speech_recognition_language}"
            )

    @property
    def is_available(self) -> bool:
        """Check if speech service is properly configured and available."""
        return SPEECH_SDK_AVAILABLE and bool(self.speech_key)

    def _get_speech_config(self) -> Optional["speechsdk.SpeechConfig"]:
        """Create and return Azure Speech configuration."""
        if not self.is_available:
            return None

        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        speech_config.speech_recognition_language = self.speech_recognition_language
        return speech_config

    def speech_to_text(self, audio_file_path: str) -> Tuple[str, bool]:
        """
        Convert audio file to text using Azure Speech-to-Text.

        Args:
            audio_file_path: Path to the audio file (WAV format preferred)

        Returns:
            Tuple of (transcribed_text, success_flag)
        """
        with tracer.start_as_current_span("speech_to_text") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')

            if not self.is_available:
                logger.warning(f"TraceID={trace_id} Speech service not available")
                return "", False

            if not os.path.exists(audio_file_path):
                logger.error(f"TraceID={trace_id} Audio file not found: {audio_file_path}")
                return "", False

            try:
                speech_config = self._get_speech_config()
                audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )

                logger.info(f"TraceID={trace_id} Starting speech recognition...")
                result = recognizer.recognize_once()

                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    text = result.text
                    logger.info(f"TraceID={trace_id} Recognized: {text[:100]}...")
                    span.set_attribute("stt.text_length", len(text))
                    span.set_attribute("stt.success", True)
                    return text, True

                elif result.reason == speechsdk.ResultReason.NoMatch:
                    no_match_detail = result.no_match_details
                    logger.warning(
                        f"TraceID={trace_id} No speech recognized: {no_match_detail.reason}"
                    )
                    span.set_attribute("stt.success", False)
                    span.set_attribute("stt.no_match_reason", str(no_match_detail.reason))
                    return "", False

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    logger.error(
                        f"TraceID={trace_id} Speech recognition canceled: "
                        f"{cancellation.reason}, {cancellation.error_details}"
                    )
                    span.set_attribute("stt.success", False)
                    span.set_attribute("stt.error", cancellation.error_details)
                    return "", False

            except Exception as e:
                logger.error(f"TraceID={trace_id} STT error: {e}", exc_info=True)
                span.record_exception(e)
                return "", False

        return "", False

    def text_to_speech(self, text: str, output_path: Optional[str] = None) -> Tuple[str, bool]:
        """
        Convert text to audio using Azure Text-to-Speech.

        Args:
            text: Text to synthesize into speech
            output_path: Optional path for output audio file.
                        If not provided, generates a temp file.

        Returns:
            Tuple of (audio_file_path, success_flag)
        """
        with tracer.start_as_current_span("text_to_speech") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')

            if not self.is_available:
                logger.warning(f"TraceID={trace_id} Speech service not available")
                return "", False

            if not text or not text.strip():
                logger.warning(f"TraceID={trace_id} Empty text provided for TTS")
                return "", False

            # Generate output path if not provided
            if output_path is None:
                output_path = str(self.temp_dir / f"tts_{uuid.uuid4().hex}.wav")

            try:
                speech_config = self._get_speech_config()
                speech_config.speech_synthesis_voice_name = self.voice_name

                # Configure audio output to file
                audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)

                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )

                logger.info(
                    f"TraceID={trace_id} Starting speech synthesis "
                    f"(text length: {len(text)}, voice: {self.voice_name})"
                )

                # Clean text for synthesis (remove markdown, trace info)
                clean_text = self._clean_text_for_synthesis(text)

                result = synthesizer.speak_text(clean_text)

                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    logger.info(f"TraceID={trace_id} TTS completed: {output_path}")
                    span.set_attribute("tts.success", True)
                    span.set_attribute("tts.output_path", output_path)
                    return output_path, True

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    logger.error(
                        f"TraceID={trace_id} Speech synthesis canceled: "
                        f"{cancellation.reason}, {cancellation.error_details}"
                    )
                    span.set_attribute("tts.success", False)
                    span.set_attribute("tts.error", cancellation.error_details)
                    return "", False

            except Exception as e:
                logger.error(f"TraceID={trace_id} TTS error: {e}", exc_info=True)
                span.record_exception(e)
                return "", False

        return "", False

    def _clean_text_for_synthesis(self, text: str) -> str:
        """
        Clean text for speech synthesis by removing markdown and metadata.

        Args:
            text: Raw text that may contain markdown formatting

        Returns:
            Cleaned text suitable for TTS
        """
        import re

        # Remove trace/session info lines
        text = re.sub(r'_Trace ID:.*?_', '', text)
        text = re.sub(r'Session:.*?\.\.\._', '', text)

        # Remove markdown formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
        text = re.sub(r'_(.+?)_', r'\1', text)  # Underscore italic
        text = re.sub(r'`(.+?)`', r'\1', text)  # Code

        # Remove emoji
        text = re.sub(r'[^\x00-\x7F]+', '', text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def cleanup_temp_files(self, max_age_hours: int = 1) -> int:
        """
        Clean up old temporary audio files.

        Args:
            max_age_hours: Delete files older than this many hours

        Returns:
            Number of files deleted
        """
        import time

        deleted = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        try:
            for file_path in self.temp_dir.glob("*.wav"):
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    deleted += 1

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old temp audio files")

        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")

        return deleted


# Singleton instance
_speech_service: Optional[SpeechService] = None


def get_speech_service() -> SpeechService:
    """Get or create singleton SpeechService instance."""
    global _speech_service
    if _speech_service is None:
        _speech_service = SpeechService()
    return _speech_service
