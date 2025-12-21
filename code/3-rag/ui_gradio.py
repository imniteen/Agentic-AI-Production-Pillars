import logging
import os
import requests
import gradio as gr
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import uuid

load_dotenv(override=True)

# Set up OTLP exporter for Jaeger
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: "customer-service-agent-ui"
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
API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001/chat")
FEEDBACK_URL = os.getenv("FEEDBACK_API_URL", "http://127.0.0.1:8001/feedback")
DATASET_API_URL = os.getenv("DATASET_API_URL", "http://127.0.0.1:8001/dataset")
EVALUATE_API_URL = os.getenv("EVALUATE_API_URL", "http://127.0.0.1:8001/evaluate")

logger = logging.getLogger("ui")
logger.setLevel(logging.INFO)

# Store last trace_id for feedback
last_run_id = None

def call_agent(message: str) -> str:
    global last_run_id
    # Generate unique trace_id for each request
    run_id = str(uuid.uuid4())
    with tracer.start_as_current_span("ui_gradio_request") as span:
        span.set_attribute("run_id", run_id)
        payload = {
            "user_id": "demo-user",
            "message": message,
            "run_id": run_id,
        }
        response = None
        try:
            response = requests.post(API_URL, json=payload, timeout=900)
            response.raise_for_status()
            data = response.json()
            reply = data["reply"]
            last_run_id = data.get("run_id", run_id)
            run_id = last_run_id
            if "human" in data.get("intent"):
                reply += "\n\n[Backend has flagged this for human review 📎]"
            reply += f"\n\nTrace ID: {run_id}"
            return reply
        except requests.RequestException as e:
            run_id = last_run_id or run_id
            try:
                data = response.json()
                run_id = data.get("run_id", run_id)
            except Exception:
                pass
            return f"Sorry, the server encountered an error. Please try again later.\n\nRun ID: {run_id}"

# Feedback function

def send_feedback(is_positive_feedback: bool, comments: str) -> str:
    global last_run_id
    payload = {
        "user_id": "demo-user",
        "run_id": last_run_id,
        "is_positive_feedback": is_positive_feedback,
        "comments": comments
    }
    response = None
    try:
        response = requests.post(FEEDBACK_URL, json=payload, timeout=900)
        response.raise_for_status()
        return "Thank you for your feedback!"
    except requests.RequestException:
        reply = "Failed to submit feedback. Please try again later."
        trace_id = last_run_id or "N/A"
        if response is not None:
            try:
                data = response.json()
                reply = data.get("reply", reply)
                trace_id = data.get("trace_id", trace_id)
            except Exception:
                pass
        return f"{reply}\nTrace ID: {trace_id}"

def refresh_dataset():
    trace_id = str(uuid.uuid4())
    payload = {
        "trace_id": trace_id,
        "user_id": "demo-user"
    }
    response = None
    try:
        response = requests.post(DATASET_API_URL, json=payload, timeout=900)
        response.raise_for_status()
        return "Dataset refreshed."
    except requests.RequestException as e:
        reply = "Failed to start dataset creation. Please try again later."
        trace_id_val = trace_id
        if response is not None:
            try:
                data = response.json()
                reply = data.get("reply", reply)
                trace_id_val = data.get("trace_id", trace_id_val)
            except Exception:
                pass
        return f"{reply}\nTrace ID: {trace_id_val}"

with gr.Blocks() as demo:
    gr.Markdown("# Customer Service Agent\nNaive multi-agent, MCP-backed customer support assistant.")
    with gr.Row():
        user_input = gr.Textbox(lines=2, label="Ask the Customer Service Agent")
        agent_reply = gr.Textbox(lines=6, label="Agent reply")
    submit_btn = gr.Button("Submit")
    submit_btn.click(call_agent, inputs=user_input, outputs=agent_reply)

    gr.Markdown("## Was this response helpful?")
    with gr.Row():
        thumbs_up = gr.Button("👍")
        thumbs_down = gr.Button("👎")
        feedback_comments = gr.Textbox(lines=2, label="Comments (optional)")
    feedback_status = gr.Textbox(label="Feedback status", interactive=False)

    thumbs_up.click(lambda comments: send_feedback(True, comments), inputs=feedback_comments, outputs=feedback_status)
    thumbs_down.click(lambda comments: send_feedback(False, comments), inputs=feedback_comments, outputs=feedback_status)

    dataset_btn = gr.Button("Refresh Dataset")
    dataset_status = gr.Textbox(label="Dataset status", interactive=False)
    dataset_btn.click(refresh_dataset, inputs=None, outputs=dataset_status)

    def evaluate_dataset():
        trace_id = str(uuid.uuid4())
        payload = {
            "trace_id": trace_id,
            "user_id": "demo-user"
        }
        response = None
        try:
            response = requests.post(EVALUATE_API_URL, json=payload, timeout=900)
            response.raise_for_status()
            return "Evaluation started. Refer the dashboard for results."
        except requests.RequestException as e:
            reply = "Failed to start evaluation. Please try again later."
            trace_id_val = trace_id
            if response is not None:
                try:
                    data = response.json()
                    reply = data.get("reply", reply)
                    trace_id_val = data.get("trace_id", trace_id_val)
                except Exception:
                    pass
            return f"{reply}\nTrace ID: {trace_id_val}"

    evaluate_btn = gr.Button("Evaluate")
    evaluate_status = gr.Textbox(label="Evaluation status", interactive=False)
    evaluate_btn.click(evaluate_dataset, inputs=None, outputs=evaluate_status)

if __name__ == "__main__":
    demo.launch()