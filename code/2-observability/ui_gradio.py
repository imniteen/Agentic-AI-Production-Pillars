import os
import requests
import gradio as gr
from dotenv import load_dotenv

load_dotenv(override=True)

API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001/chat")

def call_agent(message: str) -> str:
    payload = {
        "user_id": "demo-user",
        "message": message,
    }
    response = None
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        reply = data["reply"]
        trace_id = data.get("trace_id", "N/A")
        if "human" in data.get("intent"):
            reply += "\n\n[Backend has flagged this for human review 📎]"
        reply += f"\n\nTrace ID: {trace_id}"
        return reply
    except requests.RequestException as e:
        # User-friendly error message with trace_id if available
        trace_id = "N/A"
        try:
            data = response.json()
            trace_id = data.get("trace_id", "N/A")
        except Exception:
            pass
        return f"Sorry, the server encountered an error. Please try again later.\n\nTrace ID: {trace_id}"


demo = gr.Interface(
    fn=call_agent,
    inputs=gr.Textbox(lines=2, label="Ask the Customer Service Agent"),
    outputs=gr.Textbox(lines=6, label="Agent reply"),
    title="Customer Service Agent",
    description="Observable multi-agent, MCP-backed customer support assistant.",
    flagging_mode="never"
)

# No Prometheus usage in this file

if __name__ == "__main__":
    demo.launch()