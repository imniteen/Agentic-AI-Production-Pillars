# ui_gradio.py
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
    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    reply = data["reply"]
    if data.get("needs_human"):
        reply += "\n\n[Backend has flagged this for human review 📎]"
    return reply


demo = gr.Interface(
    fn=call_agent,
    inputs=gr.Textbox(lines=2, label="Ask the Customer Service Agent"),
    outputs=gr.Textbox(lines=6, label="Agent reply"),
    title="Vibe-Coded Customer Service Agent (MVP)",
    description="Naive multi-agent, MCP-backed customer support assistant.",
    flagging_mode="never"
)

if __name__ == "__main__":
    demo.launch()