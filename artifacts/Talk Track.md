# Introduction Slide
1. "Who has done vibe-coding?" 
2. "Who has done vibe-coding AND DEPLOYED to production?"
3. Optional - "Who has done vibe-coding AND DEPLOYED to production AND everything worked fine?"
4. "Why? What's missing?"

5. Everyone sees the 10% (the cool demos). Production lives in the other 90.
6. Most AI agents talks focus on the top 10%—the prompt, the model, the magic moment when it answers correctly (which we will see).
7. But production systems don’t fail because the prompt was wrong. They fail because the other 90% was missing.
8. Today, we’ll start with the same magic... and then we’ll systematically break it until it's engineered enough (well, we will see how much we can cover in time) to survive production.
---
# Slide 1 - Vibe-coded MVP
1. Let's start simple and something familiar. This is a customer service agent for an e-commerce use case — vibe-coded.
2. Mermaid diagram -> Langgraph -> Agents as nodes. MCP server for orders.
   - We begin with a Triage Agent — it looks at the user query and decides what kind of request this is. 
   - If it’s a common question, we route it to an FAQ Agent.
   - If it’s order-related, we route it to an Order Agent. 
   - Before responding to the user, everything flows through a Tone Agent — so the response sounds empathetic and customer-friendly. 
   - And for anything sensitive or ambiguous, we’ve added a Human Approval step.
3. From a functional perspective, this is already multi-agent.
4. It has separation of concerns, routing, even human-in-the-loop.
5. If I showed this diagram in isolation, most of us would say — yes, this looks reasonable. 
6. Run locally (run `order_mcp_server.py`, `backend.py`, and `ui_gradio.py` from the `code/1-initial-setup` folder).
   - "Where is my order?"
   - "Where is my order #ORD-123?"
   - "I need a refund."
   - "Can I speak to a human?"
7. At this stage, we have something that answers. But we don’t yet have something that operates.
8. And production doesn’t care how elegant your agent graph looks — it cares about how the system behaves under stress, failure, and ambiguity.
9. Introduce failure 
   - Stop the MCP server. 
   - Now input -> "Where is my order #ORD-123?"
---
# Slide 2 - Transition slide to observability
1. Walk through the slide.
2. Let's try to answer most of these questions through something called as "observability".
3. First we will see it in action and then we will talk more about it.
---
# Demo
Demo. Run the observability-enhanced version from `code/2-observability`.
1. `docker rm -f $(docker ps -aq)`
2. `docker rmi -f $(docker images -aq)`
3. `docker run -d --name jaeger -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one:1.50`

Browse to `http://localhost:16686` to access the Jaeger UI.
Browse langsmith dashboard to see traces.
Run locally (run `order_mcp_server.py`, `backend.py`, and `ui_gradio.py` from the `code/2-observability` folder).

1. "Where is my order #ORD-123?" Copy the trace ID from UI and search in Jaeger.
   - Show Jaeger traces. Talk about
     - Waterfall model of calls.
     - Traces
     - Spans (expand it to show "tags" and "process" in each span)
       - In agentic systems, each agent execution should:
         - Start a child span
         - Inherit the parent context
         - Propagate context into tools and downstream calls
     - Note the agent reply in tags. "Should we be logging this in span or traces?" (question to audience)
     - OpenTelemetry turns distributed systems from opaque behavior into explainable execution.
   - Go to https://smith.langchain.com/
     - Show "Tracing Projects" -> "LangGraph" -> Same trace ID and waterfall model of calls.
     - Show "Monitoring" Dashboard.
2. Stop the MCP server.
   - "Where is my order #ORD-123?"
   - Show Jaeger traces.
   - Show LangSmith traces.
3. Every request and agent action is instrumented for tracing and metrics.
4. You can visualize traces in Jaeger and LangSmith.
---
# Slide 4 - Production Pillar: Observability 
- Walk through the slide.
- Langsmith (Langchain encosystem), Langfuse (More open-source, polygot kind of system).

--- 
# Slide 5 - Transition to RAG
1. Walk through the slide
2. When we talk about RAG — Retrieval Augmented Generation — we’re not talking about giving the model more context. We’re talking about making answers defensible.
3. Let's check this in action
---
# Demo - RAG
Demo. Go to `code/3-rag` folder.
1. Run locally (run `order_mcp_server.py`, `backend.py`, and `ui_gradio.py` from the `code/3-rag` folder).
Let the backend come-up fully.
2. Walk through Customer docs.
3. Open langsmith and Pinecone dashboard.
4. Go to UI: http://127.0.0.1:7860
5. Input - "What is your return policy?"
   - You get answer.
   - Go to citation and show the source documents (trace in one of the document should be available).
   - Show Langsmith trace. Show RAG Agent flow.
   - Enter comment "sounds good" and then Thumbs up.
   - Show feedback in Langsmith.
   - Ask audience - how can I use this feedback? Generate data sets and evals which we will see.
   - Now let's try something else, "What is the warranty period for products?" (this is nowhere in the docs)
     - You might get a hallucinated answer or something vague which of-course can be polished further.
     - Enter comment "Could be better" and Thumbs down.
     - Show feedback in Langsmith.
6. Ok, now that we have the feedbacks and runs and observability etc. over time we will accumulate data. RAG in action.
How can I measure and what can I measure to observe and improve and objectively show that improvements - especially with RAG?
Enter evals framework using `ragas` library. There are 2 ways to do it - online and offline.
We will first see online - which is real-time evals as requests come in.

7. Click on `Refresh Dataset` in langsmith. 
   - Show the dataset created with 2 records. 
   - Note that we don't have reference answers, still you can rely on some very powerful metrics to measure. That's the beauty. 
   - Of-course with reference answers, it gets even better and more metrics can be subsequently added.
8. Click on `Evaluate`
    - Wait for it to complete. Meantime, Go to previous langsmith traces and check feedbacks.
    - Show `ragas` evaluation results. 
    - Explain what is `ragas` (https://docs.ragas.io/en/stable/)
    - Describe about each score what they mean.
      - (If required on how its calculated etc.)
        - Faithfulness: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
        - Answer relevancy: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/
        - LLMContextPrecisionWithoutReference: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/#context-precision-without-reference
        - NV Response Groundedness: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/nvidia_metrics/#response-groundedness
        - NV Context Relevance: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/nvidia_metrics/#context-relevance
9. Show `ragas evaluation` in Langsmith
---
# Slide 3 - HITL with State Management & Durability (3-HITL-state)
## 5-Minute Speech (10 minutes for code demo)

### Opening: The Memory Problem (30 seconds)
So we've built observability into our agent. We can trace every call, measure latency, debug failures. But there's a fundamental problem we haven't solved yet—**memory**.

Imagine you're calling customer support. You explain your problem in detail. The agent says "let me check on that." Then the line drops. You call back. And the new agent says: "How can I help you today?"

That's what happens when your AI agent doesn't have state management. Every disconnect, every server restart, every deployment—your customer starts from scratch. In production, this isn't just annoying. It's a deal-breaker.

### The Three Pillars: Durability, Persistence, State (1 minute)
When we talk about production-grade agents, we need three things working together:

**1. Durability** — State survives crashes, restarts, network failures. Not just in memory, but written to disk.

**2. Persistence** — We're using PostgreSQL to store conversation checkpoints. Every agent decision, every message, every piece of context gets saved.

**3. State Management** — The ability to pause a conversation, resume it later, and pick up exactly where we left off.

Without these three, your agent is stateless. And stateless agents can't handle real customer interactions.

### Real Example: Customer Support Chaos vs. Continuity (1.5 minutes)
Let me paint two scenarios.

**Scenario 1: Without state management**
- Customer: "My order #12345 is late, what's happening?"
- Agent: "Your order will arrive in 2 days."
- [Network glitch, connection drops]
- Customer reconnects: "Hello? Are you there?"
- Agent: "Hi! How can I help you today?"
- Customer is now furious: "I JUST told you about order #12345!"
- Result: 45-minute resolution time, frustrated customer, and your agent looks broken.

**Scenario 2: With state management (what we've built)**
- Customer: "My order #12345 is late!"
- Agent: "Let me check order #12345... It's in transit, arriving Thursday."
- Customer: "That's unacceptable, I need it refunded NOW!"
- [Agent detects escalation → triggers Human-in-the-Loop → saves checkpoint to PostgreSQL]
- [Backend server restarts due to deployment — but state is in PostgreSQL]
- Customer: "Hello? Anyone there?"
- Agent: [Resumes from PostgreSQL checkpoint] "David from Support has your full history and is ready to help with your refund for order #12345."
- Result: 8-minute resolution, seamless experience, customer feels heard.

### LangGraph Checkpointers: The Technical Foundation (1.5 minutes)
So how does this work? LangGraph provides something called **checkpointers**—and we're using two types.

**PostgreSQL Checkpointer (Production)**
- Every conversation turn creates a checkpoint in PostgreSQL.
- We store: session_id, conversation_history, user_context, agent_state, and whether we're awaiting human input.
- When the graph hits an interrupt point—like our Human node—it pauses execution and saves state.
- Later, when the human responds, we resume from that exact checkpoint. Same session. Same context. No data loss.

**MemorySaver Checkpointer (Fallback)**
- For development or when PostgreSQL is unavailable, we fall back to an in-memory store.
- It's not durable—if your backend crashes, state is gone.
- But it lets us develop and test locally without running a database.

This is what I call the **hybrid approach**: PostgreSQL for production durability, MemorySaver for development velocity.

### Human-in-the-Loop with Interrupts (1 minute)
The key LangGraph feature here is `interrupt_before=[constants.HUMAN]`.

When we compile our graph, we tell it: "Before executing the Human node, pause and save a checkpoint."

This means:
- The customer's angry message triggers an escalation.
- The graph routes to the Human node.
- **Before** invoking that node, LangGraph saves the entire state to PostgreSQL.
- The UI shows: "Your request has been escalated. A support engineer will join shortly."
- Behind the scenes, the graph is paused. The backend can restart. No problem.
- When the human (or automated approval) provides input, we call the graph again with the same session_id.
- LangGraph loads the checkpoint, resumes execution, and continues seamlessly.

### Production Impact (30 seconds)
Without state management:
- Context lost on every disconnect ❌
- Customer repeats themselves constantly ❌
- No audit trail for compliance ❌
- 45-minute resolution times ⏱️

With PostgreSQL-backed checkpointers:
- Conversations survive restarts ✅
- Seamless Human-in-the-Loop escalation ✅
- Full audit trail in PostgreSQL ✅
- 8-minute resolution times ⚡

This transforms a demo into a production system that customers trust.

---
### Code Demo Highlights (10 minutes)
**[Show code for:]**
1. **graph.py**: PostgreSQL checkpointer initialization with fallback to MemorySaver
   - `AsyncPostgresSaver.from_conn_string()`
   - Connection string from environment variables
   - `await checkpointer.setup()` to create tables
2. **graph.py**: Interrupt configuration
   - `interrupt_before=[constants.HUMAN]`
   - Thread-based session management: `thread_id = f"{user_id}:{session_id}"`
3. **backend.py**: Session management in the API
   - `await run_agent(body.user_id, body.message, body.session_id)`
   - Checking `awaiting_human_input` flag
4. **ui_gradio.py**: Multi-step HITL flow
   - Progressive messages: "Escalated → Connecting → David joins"
   - Session persistence across messages
5. **PostgreSQL schema** (briefly show tables)
   - `checkpoints` table with thread_id, checkpoint_ns, state blob
6. **Live Demo**: 
   - Start conversation: "My order #12345 is late and I'm furious!"
   - Show escalation to human
   - **Kill backend server** (Ctrl+C)
   - Restart backend
   - Continue conversation → state persists
   - Show PostgreSQL query: `SELECT * FROM checkpoints WHERE thread_id = 'demo-user:...'`

---
# Slide 4 - Production Guardrails & Policy Enforcement (4-guardrails)
## 5-7 Minute Speech (3-5 minutes for code demo)

### Opening: The Trust Problem (45 seconds)
We've built observability. We've built state management. Our agent can trace requests, survive crashes, and maintain conversation context. But there's a critical question we haven't answered yet: **Can we trust what the agent says and does?**

Here's the reality check:
- What if a customer shares their credit card number in the chat and your agent logs it?
- What if your agent generates a toxic response when frustrated?
- What if the AI hallucinates and promises a full refund when your policy says otherwise?
- What if someone tries to jailbreak your agent with prompt injection?

In production, your AI agent is a representative of your company. Every response it generates is legally your company's statement. Without guardrails, you're one bad response away from a compliance violation, a PR disaster, or a lawsuit.

### The Two Dimensions of Guardrails (1 minute)
Production-grade guardrails operate in two critical places:

**1. Input Guardrails (PolicyIn Agent)**
- **Before** your agent processes anything, we check the user's message
- Detect toxic content (violence, self-harm, harassment) using OpenAI Moderation API
- Detect and redact PII (credit cards, SSNs, emails, phone numbers) using Microsoft Presidio
- Block unsafe requests or escalate to human review
- **Goal**: Protect your system from malicious or unsafe input

**2. Output Guardrails (PolicyOut Agent)**
- **After** your agent generates a response, we check it before showing to the user
- Detect if the AI generated toxic content
- Redact any PII that slipped through (order IDs, customer names, addresses)
- Block hallucinated promises that violate company policy
- **Goal**: Protect your users and your company from unsafe AI output

This is what I call **defense in depth**—guardrails at both entry and exit points.

### Real-World Examples: Before and After (2 minutes)

**Example 1: PII Leakage**

*Without Guardrails:*
```
Customer: "My credit card 4532-1234-5678-9010 was charged twice for order #12345"
Agent: "I see your credit card 4532-1234-5678-9010 was charged twice. Let me check..."
[Logged in plain text → compliance violation → $50K GDPR fine]
```

*With Guardrails (PolicyIn):*
```
Customer: "My credit card 4532-1234-5678-9010 was charged twice"
PolicyIn Agent: [Detects CREDIT_CARD entity → redacts]
Triage Agent sees: "My credit card [REDACTED] was charged twice"
Agent responds: "I understand you were charged twice. Let me investigate..."
[No PII in logs → compliance maintained]
```

**Example 2: Toxic User Input**

*Without Guardrails:*
```
Customer: "You're a useless piece of garbage! I'll destroy your company!"
Agent: [Processes normally] "I'm sorry you feel that way. How can I help?"
[Agent wastes time on abusive user → support team burnout]
```

*With Guardrails (PolicyIn):*
```
Customer: "You're a useless piece of garbage! I'll destroy your company!"
PolicyIn Agent: [OpenAI Moderation flags: harassment=0.92, threat=0.87]
Decision: block_to_human
Response: "This conversation requires human review. Connecting you to a supervisor..."
[Escalated → trained human handles it → AI agent protected]
```

**Example 3: Toxic AI Output (Hallucination)**

*Without Guardrails:*
```
Customer: "This is ridiculous! I want my money back NOW!"
Agent: [Hallucinates] "Fine! I've processed a full refund. You'll get $500 back."
[No authorization → unauthorized refund → company loses money]
```

*With Guardrails (PolicyOut):*
```
Agent generates: "Fine! I've processed a full refund..."
PolicyOut Agent: [Moderation flags inappropriate tone + unauthorized action]
Decision: block
Final response: "I understand your frustration. Let me connect you with our refund team..."
[Hallucination blocked → escalated properly → company protected]
```

### The Technical Architecture (1.5 minutes)

Looking at our flow diagram, notice the new PolicyIn and PolicyOut agents:

**PolicyIn Agent (Entry Point)**
- **First node** in the graph after START
- Checks every user message before routing to Triage
- Uses OpenAI Moderation API for toxicity detection
- Uses Microsoft Presidio for PII detection
- Returns a structured `PolicyDecision`:
  - `allowed: true/false`
  - `action: "allow" | "redact_and_allow" | "block_to_human" | "block"`
  - `transformed_text`: redacted version if PII found
  - `pii_entities`: list of detected PII (for audit)
  - `moderation_flagged`: true if toxic

**PolicyOut Agent (Exit Point)**
- **Last node** before ToneAgent
- All paths (FAQ, Order, RAG) flow through PolicyOut
- Checks the draft response before formatting
- Can redact AI-generated PII (e.g., accidentally leaked customer data)
- Can block toxic AI responses
- Writes decision to state for traceability

**Audit Trail**
Every decision is logged in the state:
- `state["policy_input"]`: input guardrail decision
- `state["policy_output"]`: output guardrail decision
- Spans include attributes: `policy.input.action`, `policy.input.flagged`, `policy.input.pii_count`
- Full traceability for compliance audits

### Why This Matters for Production (1 minute)
Let me be very clear: **you cannot deploy a customer-facing AI agent without guardrails**.

Here's what you're risking without them:

| Without Guardrails | With Policy Agents (This Demo) |
|-------------------|-------------------------------|
| PII logged in plain text ❌ | PII auto-redacted ✅ |
| AI can generate toxic responses ❌ | Moderation blocks unsafe output ✅ |
| Abuse and jailbreaks succeed ❌ | Escalated to human review ✅ |
| No compliance audit trail ❌ | Every decision logged ✅ |
| Legal liability exposure 🔥 | Defensible system 🛡️ |

In regulated industries—finance, healthcare, government—this isn't optional. It's mandatory.

**Bottom line:** Guardrails transform your agent from a liability into a trustworthy system. They're the difference between "we can't deploy this" and "this is production-ready."

---
### Code Demo Highlights (3-5 minutes)
**[Show code for:]**
1. **policy_agent.py**: The PolicyAgent class
   - `_moderate()`: OpenAI Moderation API integration
   - `_detect_pii()`: Presidio analyzer for PII entities
   - `_redact()`: Presidio anonymizer replacing PII with [REDACTED]
   - `_decide()`: Core logic that combines moderation + PII checks
   - `enforce_input()`: Input guardrails with state routing
   - `enforce_output()`: Output guardrails with safe fallback
   
2. **graph.py**: Guardrail integration
   - PolicyIn as first node: `workflow.add_edge(START, constants.POLICY_IN_AGENT)`
   - PolicyOut before Tone: All paths converge at PolicyOut
   - Conditional routing: `route_by_policy()` in edges.py
   
3. **edges.py**: Policy routing logic
   - If input flagged → route to HUMAN
   - If input safe → route to TRIAGE_AGENT
   
4. **models/state.py**: Policy state fields
   - `policy_route`: routing decision from PolicyIn
   - `policy_input`: full PolicyDecision object (input)
   - `policy_output`: full PolicyDecision object (output)
   
5. **Live Demo Examples**:
   - **PII Test**: "My SSN is 123-45-6789 and my email is john@example.com"
     - Show redaction in logs
     - Show `state["policy_input"]["pii_entities"]`
   - **Toxic Input Test**: "You're all idiots and I'll sue you!"
     - Show moderation flagged
     - Show escalation to human
   - **Agent Hallucination Test**: Trigger an aggressive response from FAQ
     - Show PolicyOut blocking it
     - Show safe fallback message
   - **Trace Inspection**: Open Jaeger/LangSmith
     - Show `policy_in` and `policy_out` spans
     - Show attributes: `policy.input.flagged=true`, `policy.input.pii_count=2`
   
6. **Production Configuration**:
   - Show environment variables for moderation model
   - Show configurable behavior: `on_input_flagged="block_to_human"` vs `"block"`
   - Show `redact_pii=True` flag

---
# Final Slide - The Lethal Trifecta (Closing - 1 minute)

So we've covered observability, state management, and guardrails. We've taken a vibe-coded demo and systematically engineered it for production. But before we wrap up, I want to leave you with one critical framework that should guide every AI agent decision you make.

Simon Willison calls this **"The Lethal Trifecta"**—three conditions that, when combined, create maximum risk:

**1. Access to Private Data** (Yellow circle)
Your agent has access to customer PII, financial records, health data, internal documents—sensitive information that must be protected.

**2. Ability to Externally Communicate** (Green circle)
Your agent can send emails, post to APIs, make phone calls, interact with external systems—it has agency in the real world.

**3. Exposure to Untrusted Content** (Pink circle)
Your agent processes user input, scrapes websites, consumes external data—it's exposed to potential prompt injections, jailbreaks, and malicious content.

When all three overlap? **You have a ticking time bomb.**

This is why everything we've built today matters:
- **Observability** lets you see when the trifecta is being exploited
- **State management** ensures you can trace back how it happened
- **Guardrails** actively prevent the exploitation from succeeding

Here's the reality: Most production AI agents operate in this danger zone. They have to. The question isn't whether you're in the trifecta—it's whether you've engineered your way out of the risk.

Today, we've shown you how. This isn't about fear—it's about building responsibly.

**Thank you.**

---
*Source: [The Lethal Trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) by Simon Willison*




