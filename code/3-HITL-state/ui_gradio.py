import os
import requests
import gradio as gr
import time
from dotenv import load_dotenv

load_dotenv(override=True)

API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001/chat")

# Session state to track session_id
session_state = {"session_id": None}


def call_agent(message: str, history: list) -> tuple:
    """
    Call the agent API with session management and return the response.
    Returns: (updated_history, empty_string_for_textbox)
    """
    if not message.strip():
        return history, ""
    
    # Add user message to history
    history.append({"role": "user", "content": message})
    
    payload = {
        "user_id": "demo-user",
        "message": message,
        "session_id": session_state.get("session_id"),  # Include session_id for continuity
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
            data = response.json() # type: ignore
            trace_id = data.get("trace_id", "N/A")
        except Exception:
            pass
        error_msg = f"⚠️ Sorry, the server encountered an error. Please try again later.\n\n_Trace ID: {trace_id}_"
        history.append({"role": "assistant", "content": error_msg})
        yield history, ""


def clear_chat():
    """Clear the chat history and reset session."""
    session_state["session_id"] = None
    return [], ""


# Create chatbot interface with custom CSS
with gr.Blocks(
    title="Customer Service Agent with HITL",
    theme=gr.themes.Soft(),
    css="""
        .chatbot-container { height: 500px; }
        .input-box { border-radius: 8px; }
    """
) as demo:
    gr.Markdown(
        """
        # 🤖 Customer Service Agent
        
        Welcome to the Customer Service Agent demo! You can ask questions about your orders, returns, and more. 
        If the agent needs human assistance, it will notify you for review.
        """
    )
    
    chatbot = gr.Chatbot(
        label="Conversation",
        type="messages",
        height=500,
        show_copy_button=True,
        avatar_images=(None, "🤖"),
    )
    
    with gr.Row():
        msg = gr.Textbox(
            label="Your message",
            placeholder="Type your message here... (e.g., 'What's the status of my order?')",
            lines=2,
            scale=9,
            container=False,
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)
    
    with gr.Row():
        clear_btn = gr.Button("🗑️ Clear Chat & Start New Session", variant="secondary")
    
    # Event handlers
    msg.submit(call_agent, inputs=[msg, chatbot], outputs=[chatbot, msg])
    send_btn.click(call_agent, inputs=[msg, chatbot], outputs=[chatbot, msg])
    clear_btn.click(clear_chat, outputs=[chatbot, msg])
    
    gr.Markdown(
        """
        ---
        💡 **Tip:** Your conversation is automatically saved. When the agent requests human review, 
        simply respond with your approval or additional instructions to continue.
        """
    )


if __name__ == "__main__":
    demo.launch()