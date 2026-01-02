"""
Customer Service Agent UI with Voice + Text support.

This Gradio interface provides both text and voice input/output capabilities
for interacting with the HITL Customer Service Agent.
"""

import os
import requests
import gradio as gr
import time
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(override=True)

API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001/chat")
VOICE_API_URL = API_URL.replace("/chat", "/voice-chat")
SPEECH_STATUS_URL = API_URL.replace("/chat", "/speech-status")

# Session state to track session_id
session_state = {"session_id": None}


def check_speech_available() -> dict:
    """Check if Azure Speech Service is configured and available."""
    try:
        response = requests.get(SPEECH_STATUS_URL, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {"available": False}


def call_agent(message: str, history: list) -> tuple:
    """
    Call the text chat agent API with session management and return the response.
    Returns: (updated_history, empty_string_for_textbox)
    """
    if not message.strip():
        return history, ""

    # Add user message to history
    history.append({"role": "user", "content": message})

    payload = {
        "user_id": "demo-user",
        "message": message,
        "session_id": session_state.get("session_id"),
    }
    response = None
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        reply = data["reply"]
        trace_id = data.get("trace_id", "N/A")
        session_id = data.get("session_id")
        awaiting_human_input = data.get("awaiting_human_input", False)

        # Store session_id for conversation continuity
        if session_id:
            session_state["session_id"] = session_id

        # Handle HITL with progressive messages
        if awaiting_human_input:
            # Step 1: Escalation message
            history.append({"role": "assistant", "content": "Your request has been escalated for human review."})
            yield history, ""
            time.sleep(2)

            # Step 2: Connecting message
            history.append({"role": "assistant", "content": "⏳ *Connecting you with a support engineer...*"})
            yield history, ""
            time.sleep(5)

            # Step 3: David joins
            history.append({"role": "assistant", "content": "👨‍💼 **David (Support Engineer) has joined the chat**"})
            yield history, ""
            time.sleep(3)

            # Step 4: David's greeting
            david_message = (
                "**David:** Hello! I understand you're experiencing some frustration with your order. "
                "I'm here to help you resolve this issue. Could you please provide me with your order ID "
                "or any relevant details? I'll do my best to assist you promptly and ensure we find a solution together."
            )
            history.append({"role": "assistant", "content": david_message})
            yield history, ""
            time.sleep(0.5)

            # Add final note with trace info
            final_note = f"\n\n🔔 **Human review required** - Please provide your input or approval below.\n\n_Trace ID: {trace_id} | Session: {session_id[:8]}..._"
            history[-1]["content"] += final_note
            yield history, ""
        else:
            # Normal response
            reply += f"\n\n_Trace ID: {trace_id} | Session: {session_id[:8]}..._"
            history.append({"role": "assistant", "content": reply})
            yield history, ""

    except requests.RequestException as e:
        # User-friendly error message with trace_id if available
        trace_id = "N/A"
        try:
            data = response.json()  # type: ignore
            trace_id = data.get("trace_id", "N/A")
        except Exception:
            pass
        error_msg = f"⚠️ Sorry, the server encountered an error. Please try again later.\n\n_Trace ID: {trace_id}_"
        history.append({"role": "assistant", "content": error_msg})
        yield history, ""


def call_voice_agent(audio_path: str, history: list) -> tuple:
    """
    Call the voice chat agent API with audio input.
    Returns: (updated_history, audio_output_path)
    """
    if audio_path is None:
        return history, None

    # Check if file exists and has content
    if not os.path.exists(audio_path):
        history.append({"role": "assistant", "content": "⚠️ No audio recorded. Please try again."})
        yield history, None
        return

    # Add user message placeholder
    history.append({"role": "user", "content": "🎤 *Recording voice message...*"})
    yield history, None

    try:
        # Send audio to voice-chat endpoint
        with open(audio_path, "rb") as audio_file:
            files = {"audio_file": ("recording.wav", audio_file, "audio/wav")}
            data = {
                "user_id": "demo-user",
                "session_id": session_state.get("session_id") or "",
            }

            response = requests.post(VOICE_API_URL, files=files, data=data, timeout=60)
            response.raise_for_status()

        result = response.json()
        transcribed_text = result.get("transcribed_text", "")
        reply = result.get("reply", "")
        trace_id = result.get("trace_id", "N/A")
        session_id = result.get("session_id")
        awaiting_human_input = result.get("awaiting_human_input", False)
        audio_file_path = result.get("audio_file")

        # Store session_id for conversation continuity
        if session_id:
            session_state["session_id"] = session_id

        # Update user message with transcription
        if transcribed_text:
            history[-1]["content"] = f"🎤 {transcribed_text}"
        else:
            history[-1]["content"] = "🎤 *(Could not transcribe audio)*"

        yield history, None

        # Handle HITL flow
        if awaiting_human_input:
            history.append({"role": "assistant", "content": "Your request has been escalated for human review."})
            yield history, audio_file_path
            time.sleep(2)

            history.append({"role": "assistant", "content": "⏳ *Connecting you with a support engineer...*"})
            yield history, audio_file_path
            time.sleep(5)

            history.append({"role": "assistant", "content": "👨‍💼 **David (Support Engineer) has joined the chat**"})
            yield history, audio_file_path
            time.sleep(3)

            david_message = (
                "**David:** Hello! I understand you're experiencing some frustration. "
                "I'm here to help you resolve this issue. Please continue the conversation using text "
                "so I can better assist you."
            )
            final_note = f"\n\n🔔 **Human review required** - Please type your response below.\n\n_Trace ID: {trace_id} | Session: {session_id[:8]}..._"
            history.append({"role": "assistant", "content": david_message + final_note})
            yield history, audio_file_path
        else:
            # Normal response
            reply += f"\n\n_Trace ID: {trace_id} | Session: {session_id[:8]}..._"
            history.append({"role": "assistant", "content": reply})
            yield history, audio_file_path

    except requests.RequestException as e:
        error_msg = f"⚠️ Voice processing failed: {str(e)}\n\nPlease try again or use text chat."
        history[-1]["content"] = "🎤 *(Voice input failed)*"
        history.append({"role": "assistant", "content": error_msg})
        yield history, None

    except Exception as e:
        error_msg = f"⚠️ An unexpected error occurred: {str(e)}"
        history.append({"role": "assistant", "content": error_msg})
        yield history, None


def clear_chat():
    """Clear the chat history and reset session."""
    session_state["session_id"] = None
    return [], "", None


# Check speech availability on startup
speech_status = check_speech_available()
speech_available = speech_status.get("available", False)

# Create chatbot interface with custom CSS
with gr.Blocks(
    title="Customer Service Agent with Voice + Text",
    theme=gr.themes.Soft(),
    css="""
        .chatbot-container { height: 500px; }
        .input-box { border-radius: 8px; }
        .voice-section {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
        }
        .voice-status {
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .voice-enabled { background-color: #e8f5e9; color: #2e7d32; }
        .voice-disabled { background-color: #ffebee; color: #c62828; }
    """
) as demo:
    gr.Markdown(
        """
        # 🤖 Customer Service Agent (Voice + Text)

        Welcome to the Customer Service Agent demo! You can ask questions about your orders, returns, and more.

        **Features:**
        - 💬 **Text Chat**: Type your message in the text box
        - 🎤 **Voice Chat**: Record your question using the microphone
        - 🔄 **Session Continuity**: Conversation history is preserved
        - 🤝 **Human Escalation**: Complex issues are escalated for review
        """
    )

    # Voice status indicator
    if speech_available:
        gr.Markdown(
            f"""
            <div class="voice-status voice-enabled">
            ✅ Voice enabled | Region: {speech_status.get('region')} | Voice: {speech_status.get('voice')}
            </div>
            """,
            elem_classes=["voice-status"]
        )
    else:
        gr.Markdown(
            """
            <div class="voice-status voice-disabled">
            ⚠️ Voice disabled - Azure Speech Service not configured. Text chat still available.
            </div>
            """,
            elem_classes=["voice-status"]
        )

    chatbot = gr.Chatbot(
        label="Conversation",
        type="messages",
        height=450,
        show_copy_button=True,
        avatar_images=(None, "🤖"),
    )

    with gr.Row():
        msg = gr.Textbox(
            label="Text Input",
            placeholder="Type your message here... (e.g., 'What's the status of my order?')",
            lines=2,
            scale=8,
            container=False,
        )
        send_btn = gr.Button("📤 Send", variant="primary", scale=1)

    # Voice input section
    with gr.Row(elem_classes=["voice-section"]):
        with gr.Column(scale=3):
            voice_input = gr.Audio(
                sources=["microphone"],
                type="filepath",
                label="🎤 Voice Input (Click to record, click again to stop)",
                interactive=speech_available,
            )
        with gr.Column(scale=2):
            voice_output = gr.Audio(
                label="🔊 Agent Response",
                autoplay=True,
                interactive=False,
            )

    with gr.Row():
        clear_btn = gr.Button("🗑️ Clear Chat & Start New Session", variant="secondary")

    # Event handlers for text chat
    msg.submit(call_agent, inputs=[msg, chatbot], outputs=[chatbot, msg])
    send_btn.click(call_agent, inputs=[msg, chatbot], outputs=[chatbot, msg])

    # Event handler for voice chat
    voice_input.stop_recording(
        call_voice_agent,
        inputs=[voice_input, chatbot],
        outputs=[chatbot, voice_output]
    )

    # Clear button
    clear_btn.click(clear_chat, outputs=[chatbot, msg, voice_output])

    gr.Markdown(
        """
        ---

        ### 💡 Tips:
        - **Text Chat**: Simply type your question and press Enter or click Send
        - **Voice Chat**: Click the microphone button, speak your question, then click again to stop recording
        - **Session Persistence**: Your conversation is automatically saved - you can close and reopen without losing context
        - **Human Review**: When the agent requests human review, respond with your approval or additional instructions

        ### 🔧 Troubleshooting Voice:
        - Ensure your browser has microphone permissions
        - Speak clearly and wait a moment before stopping the recording
        - If voice doesn't work, Azure Speech Service may not be configured - use text chat instead
        """
    )


if __name__ == "__main__":
    demo.launch()
