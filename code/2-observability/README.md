# Production-Grade Observability Demo: Customer Service Agentic AI System

## Talk Track Update

In this step, we move beyond the basic MVP and introduce production-grade observability to our Customer Service Agentic AI system. This includes:
- **Distributed Tracing** with OpenTelemetry and Jaeger
- **Debug Logging**
- **LLM/Agent Tracing** with LangSmith
- **Metrics** with Langsmith (on the Monitoring tab. However, this just shows basic data which is sufficient for most use cases. For more advanced metrics, Prometheus integration can be added similarly.)

### Before
- The system was a simple local application with minimal visibility into its internal operations.
- Debugging issues or understanding performance bottlenecks was difficult.
- No way to track or explain agent decisions at scale.

### After
- Every request and agent action is instrumented for tracing and metrics.
- You can visualize traces in Jaeger and LangSmith.
- Issues can be quickly identified and explained, making the system robust for production.

---

## Hands-On Demo Steps
1. **Start Jaeger**
   - If Docker is available, run:
     ```cmd
     docker rm -f $(docker ps -aq)
     docker rmi -f $(docker images -aq)
     docker run -d --name jaeger -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one:1.50
     ```
     Browse to `http://localhost:16686` to access the Jaeger UI.
2. **Fallback (No Docker)**
   - Download Jaeger from [Jaeger Releases](https://github.com/jaegertracing/jaeger/releases) and run the binary locally.
   - Both tools provide easy-to-use executables for Windows.
3. **LangSmith Setup**
   - Delete existing projects in LangSmith to start fresh.
   - Ensure you have your LangSmith API key.
   - Set environment variables:
     ```cmd
     set LANGCHAIN_TRACING_V2=true
     set LANGCHAIN_API_KEY=your-key-here
     set LANGCHAIN_API_URL=https://api.smith.langchain.com
     ```
4. **Install Python Dependencies**
   - From the `code/2-observability` directory, run:
     ```cmd
     uv sync
     ```
5. **Run the Application**
   - Start the MCP server:
     ```cmd
     python order_mcp_server.py
     ```
   - Start the backend server:
     ```cmd
     python backend.py
     ```
   - Or, if using Uvicorn (recommended for FastAPI):
     ```cmd
     uvicorn backend:app --host 127.0.0.1 --port 8001 --reload
     ```
   - Start the UI:
     ```cmd
     python ui_gradio.py
     ```
6. **Interact with the Agents**
   - Use the API endpoint (e.g., POST to `http://127.0.0.1:8001/chat`) or UI if available.
   - Observe traces and logs in Jaeger (`http://localhost:16686`).
---

## Diagram

![Production-Grade-System](../artifacts/Production-Grade-System.png)

---

## Consistency & Coherency
- This README will be updated at every step to reflect the current state of the demo, code, and talk track.
- "Before and After" scenarios will be highlighted for each engineering improvement.
- All instructions and examples will be kept in sync with the codebase and demo.
- The demo builds directly on top of the `1-initial-setup` foundation, incrementally adding production-grade observability and engineering best practices.

---

## Incremental Engineering Hooks
- Each agent and backend component is now instrumented for observability.
- Traces, logs, and metrics are available for every request and error.
- Failure scenarios are easily identified and root-caused using these tools.
- The codebase structure is modular, making it easy to extend observability to new features.

---

## How to Run & Observe
- Interact with the agents and backend via the provided API endpoints or UI.
- Use Jaeger and LangSmith to visualize traces and debug flows.
- Simulate failures (e.g., invalid API keys, network issues) and observe how the system surfaces and explains them.

---

## Simulating Production Failure & Trace Correlation

When an error occurs in the UI or backend, use the `trace_id` returned in the API response to:
- **Search backend logs** for all entries with `TraceID=<trace_id>` to find the exact request and error.
- **View the distributed trace in Jaeger** by searching for the trace ID to see the full flow across agents and backend.
- **Check LangSmith** for the agent trace using the same trace ID (you would need to go to the `filter` option -> select `Metadata` -> select `trace_id` -> check for first few characters of the trace_id).
- **Correlate metrics and alerts**

This enables rapid root cause analysis and end-to-end observability, connecting the UI, backend, and MCP servers for any request or error scenario.

**Demo Tip:**
- Simulate a failure in the UI, copy the trace_id, and show how you can instantly find the corresponding logs, traces, and agent actions in all observability tools.

---

## Next Steps
- Add alerting and dashboards for real-time monitoring.
- Extend observability to security, guardrails, and explainability features.
- Continue updating this README for each incremental engineering improvement.

---

For more details, refer to the codebase and interact with the system to see observability in action.

