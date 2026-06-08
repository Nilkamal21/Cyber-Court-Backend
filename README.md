# 🏛️ Cyber Court: Backend Gateway API

This is the backend server for the **Cyber Court** application. It exposes a health check endpoint, a synchronous REST run endpoint, and a real-time WebSocket channel that streams multi-agent debate interactions (Prosecutor, Defender, Judge, and Verdict) using **LangGraph** (StateGraph) and database clients (**Supabase** and **Neo4j**).

---

## 🚀 Key Features

* **LangGraph Engine**: Manages debate turn-taking and state updates.
* **WebSocket Streams**: Emits token-by-token streaming from debaters and structured scorecards from the AI Judge.
* **Graph-RAG Lookup**: Queries **Neo4j Aura Cloud** to retrieve behavioural metrics about opponent fallacies to improve arguments dynamically.
* **Self-Healing Transcripts**: Database writer that automatically handles network connection timeouts or database latency by self-healing missing session metrics before appending turn transcripts.

---

## 🎭 The 4 Courtroom Agents

The backend coordinates four core AI agents, each with dedicated prompts, operational scopes, and responsibilities:

1. **📢 Prosecutor Agent** (`prosecutor_node`):
   * **Role**: The affirmative debater.
   * **Action**: Argues in favor of the active topic using a dynamically configured persona (e.g., *Tech Optimist*).
   * **Graph-RAG Integration**: Queries Neo4j Aura Cloud to pull behavioral intel on the defender, checking for their previous fallacies to counter them, and opening with corrections for any past judge criticisms.

2. **🛡️ Defender Agent** (`defender_node`):
   * **Role**: The negative/refuting debater.
   * **Action**: Opposes the topic and refutes the prosecutor's points under a configured persona (e.g., *Civil Liberties Advocate*).
   * **Graph-RAG Integration**: Queries Neo4j Aura Cloud to pull behavioral intel on the prosecutor, dynamically pointing out their fallacies and structuring refutations based on historical judge evaluations.

3. **👩‍⚖️ Supreme Court Judge Agent** (`judge_node` / `verdict_node`):
   * **Role**: The referee, evaluator, and verdict writer.
   * **Action**: Evaluates every speech turn in real-time. Systematically scans argument inputs to identify up to **15 types of logical fallacies**, grades argument novelty, generates a sentence-by-sentence score, and compiles a structured JSON scorecard. In the final round, it compiles the trial record to deliver the absolute judicial verdict.
   * **Persistence Node**: Coordinates the self-healing sync routines that log scores, entities, and relationships to Supabase and Neo4j.

4. **👮 Marshall Directive Agent** (`main.py` gateway):
   * **Role**: The courtroom bailiff and pipeline coordinator.
   * **Action**: Manages the socket session, accepts configurations, handles clean exits on user abort, sanitizes invalid token feeds, and catches system exceptions, routing details back to the client as court error protocols.

---

## 📁 Folder Structure

```text
backend/
├── app/
│   ├── agents.py       # Debater & Judge prompt systems
│   ├── database.py     # Supabase DB client & self-healing loggers
│   ├── graph.py        # LangGraph StateGraph engine & transition rules
│   ├── main.py         # FastAPI WebSocket Gateway server endpoints
│   ├── neo4j_db.py     # Neo4j Graph-RAG database connector queries
│   └── state.py        # Pydantic schemas & state variables
├── .env                # Secret keys (Excluded from Git)
├── .gitignore          # Backend git ignore configuration
└── requirements.txt    # Python packages
```

---

## ⚙️ Environment Configuration (`.env`)

Create a `.env` file in this directory with the following variables:

```ini
# Groq LLM Key
GROQ_API_KEY="your-groq-api-key"

# Supabase Credentials (PostgreSQL Sync)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-anon-key"

# Neo4j Aura Cloud Credentials (Graph-RAG Integration)
NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD="your-neo4j-password"
NEO4J_DATABASE="neo4j"
```

---

## 🛠️ Local Development & Running

1. **Create & Activate a Virtual Environment** (Optional but recommended):
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install Packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the FastAPI Server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Verify Server Status**:
   * Open `http://localhost:8000/` in your browser. You should see:
     ```json
     {"status": "online", "engine": "AI Courtroom Input Core"}
     ```

---

## 🌐 API & WebSockets Reference

### 1. HTTP GET `/`
* **Purpose**: Health check endpoint. Used by the React frontend to detect online/offline status of the judge.

### 2. WebSocket `/ws/debate`
* **Purpose**: Accepts configurations and streams progress frames.
* **Handshake Payload**:
  ```json
  {
    "topic": "AI should replace human judges",
    "max_rounds": 2,
    "prosecutor_persona": "Tech Optimist",
    "defender_persona": "Civil Liberties Advocate"
  }
  ```
* **Event Frames Streamed**:
  * `court_initialized`: Broadcasts session ID and parameters.
  * `node_transition`: Emits active speaker token streams and round transitions.
  * `judge_evaluation`: Emits structured scorecards containing scores, novelty, and fallacy maps.
  * `court_adjourned`: Signals final debate verdict completion.
  * `court_error`: Dispatched when an execution crash occurs.
