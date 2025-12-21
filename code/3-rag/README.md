# Production-Grade RAG System: Step-by-Step Engineering Journey

## Context & Journey So Far
We started with a basic MVP ("vibe-coded") agentic AI system, then enhanced it with observability and monitoring in `2-observability`. Now, in `3-rag`, we focus on building a production-grade Retrieval-Augmented Generation (RAG) system, emphasizing engineering rigor and real-world deployment challenges.

## Architecture Reference
The system architecture (see diagram above) integrates multiple agents, channels, and guardrails to ensure reliability, trust, and explainability. Key components include:
- Channels (Web, Mobile, Email)
- API Gateway
- Supervisor/Router Agent
- Specialized Agents (RAG, Action, Empathy, Policy, Summarizer)
- Guardrails (Moderation, PII filter, Channel Formatter)
- Observability & Traces
- Human-in-the-Loop (HTL) for escalation

## Focus Areas for Production-Grade RAG
- **Groundedness:** Ensuring answers are based on retrieved, factual sources. Log and show source documents for every response.
- **Hallucination Mitigation:** Reducing AI-generated misinformation by validating answers against retrieved context and using moderation filters.
- **User Trust:** Transparent, reliable responses with source citations and confidence scores. Escalate ambiguous queries to human agents.
- **Explainability:** Showing users which documents were referenced and why. Summarizer agent clarifies complex answers.
- **Metrics:** Precision, recall, F1-score, and more for RAG responses.
- **Evaluation Framework:** Integration with `ragas` for automated, robust evaluation (faithfulness, answer relevance, context recall, etc.).
- **Continuous Improvement:** Use offline/online evals and observability dashboards for ongoing quality.

## Step 1: Setting Up the Evaluation Framework
Before building further RAG logic, we set up an evaluation framework using the `ragas` library. This enables:
- Automated measurement of answer quality (groundedness, faithfulness, relevance)
- Tracking metrics like precision, recall, F1-score
- Early detection and mitigation of hallucinations
- Building trust and explainability into the system

### Hands-On Instructions
1. **Start Jaeger**
   - If Docker is available, run:
     ```cmd
     docker rm -f $(docker ps -aq)
     docker rmi -f $(docker images -aq)
     docker run -d --name jaeger -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one:1.50
     ```
2. Browse to `http://localhost:16686` to access the Jaeger UI.

---

## Before & After (Talk Track)
**Before:**
- No systematic way to measure answer quality or detect hallucinations.
- Evaluation is manual and subjective.
- **Example 1:**
    - *Input*: "What is the return policy?"
    - *Output*: "You can return items anytime you want."
    - *Issue*: Hallucination, not grounded in actual policy from customer_docs.
- **Example 2:**
    - *Input*: "How do I reset my password?"
    - *Output*: "Contact support to reset your password."
    - *Issue*: Not using available self-service instructions from customer_docs, lacks explainability.
- **Example 3:**
    - *Input*: "Is my data secure?"
    - *Output*: "Yes, your data is always secure."
    - *Issue*: Vague, no supporting evidence or references from customer_docs.
- **Example 4:**
    - *Input*: "How long does shipping take?"
    - *Output*: "Shipping is instant."
    - *Issue*: Hallucination, not grounded in actual shipping policy.
- **Example 5:**
    - *Input*: "Can I get a refund for a digital product?"
    - *Output*: "Refunds are always available."
    - *Issue*: Overgeneralization, not reflecting actual refund policy in customer_docs.
- **Example 6:**
    - *Input*: "How do I change my account email?"
    - *Output*: "You can't change your email."
    - *Issue*: Incorrect, not referencing actual account management instructions.

**After:**
- Automated, objective evaluation using industry-standard metrics.
- Immediate feedback on groundedness, faithfulness, and relevance.
- Foundation for continuous improvement and production readiness.

---

## Next Step
Follow the instructions above to install dependencies and create `rag_evaluation.py`. Once done, share the output and we will proceed to implement the evaluation logic with sample data. The README.md will be updated at each step to ensure consistency and coherency with the evolving system and talk track.
