"""Azure Speech Service wrapper for voice input/output capabilities.

Supports multi-lingual speech recognition (auto-detect) and synthesis.
"""

import os
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict

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

# Language to voice mapping for TTS (Neural voices)
# Format: language_code -> (voice_name, display_name)
LANGUAGE_VOICE_MAP: Dict[str, Tuple[str, str]] = {
    # English
    "en-US": ("en-US-JennyNeural", "English (US)"),
    "en-GB": ("en-GB-SoniaNeural", "English (UK)"),
    "en-IN": ("en-IN-NeerjaNeural", "English (India)"),
    # Hindi
    "hi-IN": ("hi-IN-SwaraNeural", "Hindi"),
    # Other Indian languages
    "ta-IN": ("ta-IN-PallaviNeural", "Tamil"),
    "te-IN": ("te-IN-ShrutiNeural", "Telugu"),
    "mr-IN": ("mr-IN-AarohiNeural", "Marathi"),
    "gu-IN": ("gu-IN-DhwaniNeural", "Gujarati"),
    "kn-IN": ("kn-IN-SapnaNeural", "Kannada"),
    "ml-IN": ("ml-IN-SobhanaNeural", "Malayalam"),
    "bn-IN": ("bn-IN-TanishaaNeural", "Bengali"),
    "pa-IN": ("pa-IN-GurpreetNeural", "Punjabi"),
    # European languages
    "fr-FR": ("fr-FR-DeniseNeural", "French"),
    "de-DE": ("de-DE-KatjaNeural", "German"),
    "es-ES": ("es-ES-ElviraNeural", "Spanish"),
    "it-IT": ("it-IT-ElsaNeural", "Italian"),
    "pt-BR": ("pt-BR-FranciscaNeural", "Portuguese (Brazil)"),
    # Asian languages
    "ja-JP": ("ja-JP-NanamiNeural", "Japanese"),
    "ko-KR": ("ko-KR-SunHiNeural", "Korean"),
    "zh-CN": ("zh-CN-XiaoxiaoNeural", "Chinese (Mandarin)"),
    # Arabic
    "ar-SA": ("ar-SA-ZariyahNeural", "Arabic"),
}

# Languages to auto-detect (Azure limit: max 4 languages in DetectAudioAtStart mode)
# Configure via AZURE_AUTO_DETECT_LANGUAGES env var (comma-separated) or use default
DEFAULT_AUTO_DETECT_LANGUAGES = ["en-IN", "hi-IN", "ta-IN", "mr-IN"]

def get_auto_detect_languages() -> list:
    """Get auto-detect languages from environment or use default."""
    env_langs = os.getenv("AZURE_AUTO_DETECT_LANGUAGES")
    if env_langs:
        langs = [lang.strip() for lang in env_langs.split(",")]
        if len(langs) > 4:
            logger.warning(f"Azure Speech supports max 4 languages for auto-detect. Using first 4: {langs[:4]}")
            return langs[:4]
        return langs
    return DEFAULT_AUTO_DETECT_LANGUAGES

AUTO_DETECT_LANGUAGES = get_auto_detect_languages()


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

    def speech_to_text(self, audio_file_path: str, auto_detect: bool = True) -> Tuple[str, bool, str]:
        """
        Convert audio file to text using Azure Speech-to-Text with auto language detection.

        Args:
            audio_file_path: Path to the audio file (WAV format preferred)
            auto_detect: If True, auto-detect language from audio. If False, use configured language.

        Returns:
            Tuple of (transcribed_text, success_flag, detected_language)
        """
        with tracer.start_as_current_span("speech_to_text") as span:
            trace_id = format(span.get_span_context().trace_id, 'x')
            detected_language = self.speech_recognition_language  # Default

            if not self.is_available:
                logger.warning(f"TraceID={trace_id} Speech service not available")
                return "", False, detected_language

            if not os.path.exists(audio_file_path):
                logger.error(f"TraceID={trace_id} Audio file not found: {audio_file_path}")
                return "", False, detected_language

            try:
                speech_config = self._get_speech_config()
                audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

                if auto_detect:
                    # Configure auto language detection
                    auto_detect_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                        languages=AUTO_DETECT_LANGUAGES
                    )
                    recognizer = speechsdk.SpeechRecognizer(
                        speech_config=speech_config,
                        audio_config=audio_config,
                        auto_detect_source_language_config=auto_detect_config
                    )
                    logger.info(f"TraceID={trace_id} Starting speech recognition with auto language detection...")
                else:
                    recognizer = speechsdk.SpeechRecognizer(
                        speech_config=speech_config,
                        audio_config=audio_config
                    )
                    logger.info(f"TraceID={trace_id} Starting speech recognition (language: {self.speech_recognition_language})...")

                result = recognizer.recognize_once()

                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    text = result.text

                    # Get detected language if auto-detect was used
                    if auto_detect:
                        auto_detect_result = speechsdk.AutoDetectSourceLanguageResult(result)
                        detected_language = auto_detect_result.language or self.speech_recognition_language
                        logger.info(f"TraceID={trace_id} Detected language: {detected_language}")

                    logger.info(f"TraceID={trace_id} Recognized ({detected_language}): {text[:100]}...")
                    span.set_attribute("stt.text_length", len(text))
                    span.set_attribute("stt.success", True)
                    span.set_attribute("stt.detected_language", detected_language)
                    return text, True, detected_language

                elif result.reason == speechsdk.ResultReason.NoMatch:
                    no_match_detail = result.no_match_details
                    logger.warning(
                        f"TraceID={trace_id} No speech recognized: {no_match_detail.reason}"
                    )
                    span.set_attribute("stt.success", False)
                    span.set_attribute("stt.no_match_reason", str(no_match_detail.reason))
                    return "", False, detected_language

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    logger.error(
                        f"TraceID={trace_id} Speech recognition canceled: "
                        f"{cancellation.reason}, {cancellation.error_details}"
                    )
                    span.set_attribute("stt.success", False)
                    span.set_attribute("stt.error", cancellation.error_details)
                    return "", False, detected_language

            except Exception as e:
                logger.error(f"TraceID={trace_id} STT error: {e}", exc_info=True)
                span.record_exception(e)
                return "", False, detected_language

        return "", False, detected_language

    def get_voice_for_language(self, language: str) -> str:
        """
        Get the appropriate voice name for a given language.

        Args:
            language: Language code (e.g., 'hi-IN', 'en-US')

        Returns:
            Voice name for the language, or default voice if not found
        """
        if language in LANGUAGE_VOICE_MAP:
            voice_name, _ = LANGUAGE_VOICE_MAP[language]
            return voice_name

        # Try to match by language prefix (e.g., 'en' for any English variant)
        lang_prefix = language.split("-")[0]
        for lang_code, (voice_name, _) in LANGUAGE_VOICE_MAP.items():
            if lang_code.startswith(lang_prefix):
                return voice_name

        # Fallback to default voice
        return self.voice_name

    def text_to_speech(
        self, text: str, output_path: Optional[str] = None, language: Optional[str] = None
    ) -> Tuple[str, bool]:
        """
        Convert text to audio using Azure Text-to-Speech with language-specific voice.

        Args:
            text: Text to synthesize into speech
            output_path: Optional path for output audio file.
                        If not provided, generates a temp file.
            language: Optional language code for voice selection (e.g., 'hi-IN', 'en-US').
                     If not provided, uses default configured voice.

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

            # Select voice based on language
            voice_name = self.get_voice_for_language(language) if language else self.voice_name

            try:
                speech_config = self._get_speech_config()
                speech_config.speech_synthesis_voice_name = voice_name

                # Configure audio output to file
                audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)

                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )

                logger.info(
                    f"TraceID={trace_id} Starting speech synthesis "
                    f"(text length: {len(text)}, voice: {voice_name}, language: {language or 'default'})"
                )

                # Clean text for synthesis (remove markdown, trace info)
                clean_text = self._clean_text_for_synthesis(text)

                result = synthesizer.speak_text(clean_text)

                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    logger.info(f"TraceID={trace_id} TTS completed: {output_path} (voice: {voice_name})")
                    span.set_attribute("tts.success", True)
                    span.set_attribute("tts.output_path", output_path)
                    span.set_attribute("tts.voice", voice_name)
                    span.set_attribute("tts.language", language or "default")
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
            Cleaned text suitable for TTS (preserves non-English text like Hindi, Tamil, etc.)
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

        # Remove emoji (but keep non-English text like Hindi, Tamil, etc.)
        # This pattern targets common emoji Unicode ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
            "\U00002600-\U000026FF"  # misc symbols
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

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
