# Human-In-The-Loop (HITL) State Management Demo: Customer Service Agentic AI System

## Overview

This step demonstrates a production-ready **Human-In-The-Loop (HITL)** implementation with **persistent state management** using PostgreSQL and LangGraph checkpointers. The system enables multi-turn conversations with session continuity, allowing agents to pause for human review and resume seamlessly.

## Key Features

- **🔄 Session Persistence**: PostgreSQL-based state management with LangGraph checkpointers
- **🤝 Human-In-The-Loop**: Agents can interrupt workflow for human review and resume after approval
- **💬 Multi-Turn Conversations**: Full conversation history preserved across sessions
- **🎯 Interrupt/Resume**: LangGraph's built-in checkpoint mechanism pauses at human node
- **📊 Observability**: OpenTelemetry tracing with trace ID correlation
- **🔐 Production-Ready**: Connection pooling, error handling, graceful fallbacks

---

## Why Durability & State Management Matter for Production Agents

### The Three Pillars

**1. Durability** - Data survives system failures (crashes, restarts, network issues)  
**2. Persistence** - State saved to durable storage (Maintain checkpointers in PostgreSQL)  
**3. State Management** - Conversation context maintained across interactions

### Real Customer Support Example

**❌ Without State Management:**
```
Customer: "My order #12345 is late, what's happening?"
Agent: "Your order will arrive in 2 days. Anything else?"
[Network glitch - connection drops]

Customer: [Reconnects] "Hello? Are you there?"
Agent: "Hi! How can I help you today?" 
Customer: 😤 "I JUST told you about order #12345!"
Agent: "Could you provide your order number?"
```
**Result:** Frustrated customer, 45-minute resolution, agent looks incompetent

---

**✅ With State Management (This Implementation):**
```
Customer: "My order #12345 is late, what's happening?"
Agent: "Let me check order #12345... It's in transit, arriving Thursday."
Customer: "That's unacceptable, I need it refunded NOW!"
[Agent detects anger → triggers HITL → saves state to PostgreSQL]
[Backend server restarts due to deployment]

Customer: [Continues in same chat] "Hello? Anyone there?"
Agent: [Resumes from PostgreSQL checkpoint]
       "David (Support Engineer) has joined to help with your refund 
       request for order #12345. He has your full conversation history."
David: "I can see you need this urgently. I've approved a full refund..."
```
**Result:** Happy customer, 8-minute resolution, seamless experience

---

### What Gets Persisted in PostgreSQL

```python
# Every conversation checkpoint stores:
- session_id: "a1b2c3d4-5678-90ab-cdef"
- conversation_history: [msg1, msg2, msg3...]
- user_context: order_id, intent, pending_action
- agent_state: which node (FAQ/Order/Human)
- awaiting_human_input: true/false
- trace_id: for debugging
```

### The Production Impact

| Without State | With State (This Demo) |
|--------------|------------|
| Customer repeats issue after disconnect ❌ | Conversation survives restarts ✅ |
| Context lost during HITL escalation ❌ | Seamless pause/resume workflow ✅ |
| No audit trail for compliance ❌ | Full history in PostgreSQL ✅ |
| Resolution time: 45 min ⏱️ | Resolution time: 8 min ⚡ |
| Agent looks broken 🤖 | Agent looks professional 🎯 |

**Bottom Line:** State management transforms a fragile demo into a production system customers trust. Without it, you're rebuilding context from scratch every time—with it, you're building on what you already know.

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Gradio UI │─────▶│ FastAPI      │─────▶│   LangGraph     │
│   (Session) │◀─────│  Backend     │◀─────│   Workflow      │
└─────────────┘      └──────────────┘      └─────────────────┘
                            │                        │
                            │                        ▼
                            │               ┌─────────────────┐
                            │               │  PostgreSQL     │
                            │               │  Checkpointer   │
                            │               │  (State Store)  │
                            │               └─────────────────┘
                            ▼
                     ┌──────────────┐
                     │  LangSmith   │
                     │  Tracing     │
                     └──────────────┘
```

**Key Improvements:**
- Agents → Triage → FAQ/Order/Human nodes
- Human node triggers `interrupt_before` pause
- State persisted in PostgreSQL with session_id
- UI maintains session_id for conversation continuity
- Resume workflow with new user input after HITL approval

---

## Prerequisites

- **Python 3.10+**
- **Docker Desktop** (for PostgreSQL)
- **OpenAI API Key**
- **LangSmith API Key** (optional, for tracing)

---

## Setup Instructions

### 1. Install Docker Desktop

Download and install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/)

**Start Docker Desktop:**
- Launch Docker Desktop from the Start Menu or Desktop shortcut
- Wait for Docker to start (you'll see "Docker Desktop is running" in the system tray)
- This may take 30-60 seconds on first startup

Verify installation:
```powershell
docker --version
docker ps
```

**Common Issue:** If `docker ps` fails with `failed to connect to the docker API` or `The system cannot find the file specified`, Docker Desktop is not running. Start it from the Start Menu and wait until the Docker icon in the system tray shows "Docker Desktop is running".

### 2. Start PostgreSQL Database

Run PostgreSQL in Docker with the required configuration:

```powershell
# Start PostgreSQL container
docker run -d `
  --name agent-postgres `
  -e POSTGRES_DB=agent_state `
  -e POSTGRES_USER=agent_app `
  -e POSTGRES_PASSWORD=secure_password `
  -p 5432:5432 `
  postgres:15

# Verify container is running
docker ps

# View logs (optional)
docker logs agent-postgres
```

**Container Details:**
- **Name**: `agent-postgres`
- **Database**: `agent_state`
- **User**: `agent_app`
- **Password**: `secure_password`
- **Port**: `5432` (mapped to host)

**Useful Docker Commands:**
```powershell
# Stop container
docker stop agent-postgres

# Start existing container
docker start agent-postgres

# Remove container (if needed)
docker rm -f agent-postgres

# Connect to PostgreSQL (optional, for debugging)
docker exec -it agent-postgres psql -U agent_app -d agent_state
```

### 3. Install Python Dependencies

Navigate to the project root and install dependencies:

```powershell
cd \talks-demos-presentations\code

# Install dependencies using uv
uv sync
```

**New Dependencies Added:**
- `asyncpg>=0.30.0` - PostgreSQL async driver
- `langgraph-checkpoint-postgres>=3.0.0` - PostgreSQL checkpointer for LangGraph

### 4. Configure Environment Variables

Copy the example environment file and configure:

```powershell
cd 3-HITL-state
copy .env.example .env
```

Edit `.env` with your actual values:

```env
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# LangSmith Configuration (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key-here
LANGSMITH_PROJECT="Customer Service Agent - HITL"

# Backend API URL
AGENT_API_URL=http://127.0.0.1:8001/chat

# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agent_state
POSTGRES_USER=agent_app
POSTGRES_PASSWORD=secure_password
POSTGRES_MIN_POOL_SIZE=10
POSTGRES_MAX_POOL_SIZE=100
```

### 5. Start the MCP Server (Order Service)

In a new terminal:

```powershell
cd \talks-demos-presentations\code\3-HITL-state
python order_mcp_server.py
```

Expected output:
```
MCP Server started on stdio
```

### 6. Start the Backend Server

In a new terminal:

```powershell
cd \talks-demos-presentations\code\3-HITL-state
python backend.py
```

Expected output:
```
INFO:graph:Initializing PostgreSQL connection pool: localhost:5432/agent_state
INFO:graph:PostgreSQL checkpointer initialized successfully
INFO:backend:Backend services initialized successfully
INFO:     Started server process [xxxxx]
INFO:     Uvicorn running on http://127.0.0.1:8001
```

**If PostgreSQL connection fails**, the system automatically falls back to in-memory storage (MemorySaver):
```
ERROR:graph:Failed to initialize PostgreSQL checkpointer: ...
WARNING:graph:Falling back to in-memory checkpointer (MemorySaver)
```

### 7. Start the Gradio UI

In a new terminal:

```powershell
cd \talks-demos-presentations\code\3-HITL-state
python ui_gradio.py
```

Expected output:
```
Running on local URL:  http://127.0.0.1:7860
```

Open your browser to `http://127.0.0.1:7860`

---

## How to Use the HITL System

### Basic Usage

1. **Start a Conversation**: Type a message like "What's the status of my order?"
2. **Agent Responds**: The triage agent routes to FAQ, Order, or Human nodes
3. **Session Maintained**: Your conversation is automatically saved with a unique session_id

### Testing HITL Workflow

To trigger the Human-In-The-Loop flow:

1. **Type a Sensitive Request**: 
   - "I want to cancel my order"
   - "This is unacceptable, I need a refund NOW!"
   - "I'm very angry about this service"

2. **Agent Pauses**: When the triage agent detects anger/complexity, it routes to the Human node
   - Workflow interrupts before executing Human node
   - State is saved to PostgreSQL
   - UI shows: "🔔 **Human review required** - Please provide your input or approval below."

3. **Provide Approval/Feedback**: 
   - Type your response: "Approved, proceed with cancellation"
   - Or: "Please explain the cancellation policy first"

4. **Workflow Resumes**: 
   - Backend loads checkpoint from PostgreSQL
   - Resumes from Human node with your input
   - Completes the workflow

### Session Management

- **Automatic Session**: Each conversation gets a unique `session_id`
- **Session Continuity**: All messages in the same chat window share the same session
- **Reset Session**: Click "🗑️ Clear Chat & Start New Session" to start fresh
- **View Session ID**: Displayed at the bottom of each message (e.g., `Session: a1b2c3d4...`)

---

## Database Schema

LangGraph automatically creates the following tables in PostgreSQL:

```sql
-- Checkpoints table (created automatically)
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);

CREATE INDEX idx_thread_id ON checkpoints(thread_id);
CREATE INDEX idx_created_at ON checkpoints(created_at);
```

**Thread ID Format**: `{user_id}:{session_id}`
- Example: `demo-user:a1b2c3d4-5678-90ab-cdef-1234567890ab`

### Querying State (Optional)

Connect to PostgreSQL and query conversation state:

```powershell
# Connect to database
docker exec -it agent-postgres psql -U agent_app -d agent_state

# List all active sessions
SELECT thread_id, checkpoint_id, created_at 
FROM checkpoints 
ORDER BY created_at DESC 
LIMIT 10;

# View specific session state
SELECT checkpoint 
FROM checkpoints 
WHERE thread_id = 'demo-user:your-session-id' 
ORDER BY created_at DESC 
LIMIT 1;
```

---

## State Management Details

### State Schema

The `OverallState` now includes session management fields:

```python
class OverallState(TypedDict):
    messages: Optional[list[str]]
    user_message: str
    user_id: Optional[str]
    session_id: Optional[str]              # NEW
    intent: Optional[str]
    order_id: Optional[str]
    draft_reply: Optional[str]
    final_reply: Optional[str]
    trace_id: Optional[str]
    awaiting_human_input: Optional[bool]   # NEW
    conversation_history: Optional[list]   # NEW
    pending_action: Optional[str]          # NEW
```

### Checkpoint Lifecycle

1. **New Conversation**: 
   - Generate unique `session_id`
   - Create `thread_id = user_id:session_id`
   - Initialize state in PostgreSQL

2. **Each Message**:
   - Save checkpoint after each node execution
   - Store full state including conversation history

3. **HITL Interrupt**:
   - Save state before Human node
   - Return to UI with `awaiting_human_input=true`
   - Workflow pauses, connection released

4. **Resume**:
   - User provides input
   - Backend loads checkpoint from PostgreSQL
   - Resume graph execution with updated state

5. **Cleanup** (Optional):
   - Set TTL policy for old checkpoints
   - Archive or delete sessions after 90 days

---

## Troubleshooting

### PostgreSQL Connection Issues

**Problem**: Backend fails to connect to PostgreSQL

**Solution**:
```powershell
# Verify container is running
docker ps | findstr agent-postgres

# Check logs
docker logs agent-postgres

# Restart container
docker restart agent-postgres

# Verify network connectivity
Test-NetConnection localhost -Port 5432
```

### Fallback to MemorySaver

If PostgreSQL is unavailable, the system automatically uses in-memory storage:
- **Pros**: System still works, no setup required
- **Cons**: Sessions lost on restart, no persistence

To force PostgreSQL connection, ensure:
1. Docker container is running
2. `.env` variables are correct
3. Port 5432 is not blocked by firewall

### Session Not Persisting

**Problem**: Conversation resets on each message

**Check**:
1. Backend logs for PostgreSQL connection success
2. UI session_state is being updated
3. Network tab in browser shows `session_id` in requests

### Graph Not Interrupting

**Problem**: Human node executes without pausing

**Check**:
```python
# In graph.py, verify:
workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=[constants.HUMAN]  # Must be present
)
```

---

## Monitoring & Observability

### Trace ID Correlation

Every request includes a `trace_id` for debugging:

1. **UI Display**: Shown at bottom of each message
2. **Backend Logs**: Search logs with `TraceID={trace_id}`
3. **LangSmith**: Filter traces by trace_id metadata
4. **PostgreSQL**: Stored in checkpoint metadata

### Useful Queries

```sql
-- Count sessions per user
SELECT user_id, COUNT(DISTINCT session_id) as session_count
FROM (
    SELECT 
        SPLIT_PART(thread_id, ':', 1) as user_id,
        SPLIT_PART(thread_id, ':', 2) as session_id
    FROM checkpoints
) subquery
GROUP BY user_id;

-- Find interrupted sessions (awaiting HITL)
SELECT checkpoint->'awaiting_human_input', checkpoint->'intent', created_at
FROM checkpoints
WHERE checkpoint->>'awaiting_human_input' = 'true'
ORDER BY created_at DESC;
```

---

## Production Considerations

### Performance

- **Connection Pool**: 10-100 connections (configurable via `POSTGRES_MIN/MAX_POOL_SIZE`)
- **Checkpoint Latency**: 5-50ms per write (acceptable for customer service)
- **Throughput**: 1,000+ concurrent sessions supported

### Security

- **Production Database**: Use managed PostgreSQL (AWS RDS, Azure Database)
- **Credentials**: Store in Azure Key Vault or AWS Secrets Manager
- **Network**: Restrict PostgreSQL to backend VPC only
- **Encryption**: Enable SSL/TLS for database connections

### Scaling

1. **Horizontal**: Add more backend instances (FastAPI)
2. **Database**: PostgreSQL read replicas for scale-out
3. **Caching**: Add Redis layer for hot sessions (Phase 2)
4. **Partitioning**: Partition checkpoints table by date

### Monitoring

- **Metrics**: Track checkpoint write latency, pool usage
- **Alerts**: Database connection failures, checkpoint errors
- **Retention**: Auto-delete checkpoints older than 90 days

---

## Next Steps

- **Phase 2**: Add Redis caching layer for active sessions
- **Enhanced HITL**: Implement approval workflows with multiple human reviewers
- **Analytics**: Build dashboard for conversation patterns and escalation rates
- **Security**: Add user authentication and row-level security
- **Compliance**: Implement audit logs and data retention policies

---

## Comparison: Before vs After

### Before (Step 2)
- No state persistence (lost on restart)
- Single-turn conversations only
- No HITL support
- In-memory only

### After (Step 3)
- ✅ PostgreSQL-based persistence
- ✅ Multi-turn conversation history
- ✅ HITL interrupt/resume workflows
- ✅ Session management with continuity
- ✅ Production-ready architecture

---

## Simulating HITL Failure & Recovery

### Test Scenario: Backend Restart During HITL

1. **Start conversation** and trigger HITL:
   ```
   User: "I'm extremely angry, cancel my order immediately!"
   Agent: "🔔 Human review required..."
   ```

2. **Note the session_id** (shown in UI)

3. **Restart backend** (Ctrl+C and restart `python backend.py`)

4. **Continue conversation** in same UI window:
   ```
   User: "Approved, proceed with cancellation"
   Agent: [Resumes from checkpoint, completes workflow]
   ```

✅ **State persisted across restart** - PostgreSQL preserves session

---

## Resources

- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **PostgreSQL Checkpointer**: https://langchain-ai.github.io/langgraph/reference/checkpoints/
- **Docker Desktop**: https://www.docker.com/products/docker-desktop/
- **OpenTelemetry**: https://opentelemetry.io/

---

For questions or issues, refer to the main project README or check backend logs for detailed error messages.

