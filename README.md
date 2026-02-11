# Module 3: Adaptive Reasoning Agent

Network-aware chatbot that adapts its reasoning based on simulated connection speed. **No agent frameworks** (LangChain, CrewAI, LlamaIndex); **no RAG libraries** (ChromaDB, langchain-community). Raw Python + Next.js.

## Quick Start

### 1. Backend (Python FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set:

- `GROQ_API_KEY` – required for chat (Groq llama-3.3-70b-versatile). RAG uses local sentence-transformers (no key).
- `TAVILY_API_KEY` – required for web search in Fast mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend (Next.js 14)

```bash
cd frontend
npm install
npm run dev
```

Optional: create `frontend/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000` if the API is not on that URL.

Open [http://localhost:3000](http://localhost:3000).

## Custom Reasoning Engine (no agent frameworks)

Reasoning depth adapts to network and mode; answer quality stays constant. Four modes (select in UI or via `X-Reasoning-Mode`):

| Mode       | Behavior |
|------------|----------|
| **Fast**   | Single-pass reasoning. No tools, minimal path. |
| **Standard** | Step-based logic: one explicit "think step by step" then answer. One reasoning step in trace. |
| **Deep**   | Multi-step ReAct: Thought → Action → Observation. Full tool set (web, RAG, datetime, document creation). |
| **Auto**   | Selects at runtime: Fast when connection is 3G (slow), Deep when Fiber (fast). |

## Tool-Oriented Agent

In **Deep** mode the agent routes between:

- **Web_Search** – Shallow/fast web search (Tavily, basic depth).
- **Web_Search_deep** – Deep retrieval (Tavily, advanced depth).
- **RAG_Tool** – Search over uploaded documents (native RAG pipeline).
- **Datetime** – Live date/time (UTC).
- **Document_Create_PDF / DOCX / XLSX** – Create PDF, Word, or Excel files (saved under `backend/outputs/`).

Each step is logged in the **Reasoning Trace** (Thought, Action, Observation).

## Connection & behavior

- **Connection: 3G (Slow)** – Simulates slow network; **Auto** mode uses Fast reasoning.
- **Connection: Fiber (Fast)** – **Auto** mode uses Deep reasoning with tools. You can still force Fast/Standard/Deep via the Reasoning dropdown.

## RAG (manual implementation)

- **Upload**: Sidebar accepts `.txt` or `.md` (drag-and-drop or click).
- **Ingest**: Text is chunked by paragraphs (`\n\n`), embedded with local `sentence-transformers/all-MiniLM-L6-v2` (no API key), and stored in `backend/vector_store.json`.
- **Retrieval**: Query is embedded; cosine similarity (numpy) is used to return the top 3 chunks. No external vector DB.

## Tech Stack

| Layer    | Stack                                      |
|----------|--------------------------------------------|
| Frontend | Next.js 14 (App Router), Tailwind, Lucide  |
| Backend  | FastAPI                                    |
| LLM      | Groq Cloud llama-3.3-70b-versatile (groq)     |
| Search   | Tavily API (requests)                     |
| Vectors  | Local JSON + numpy (cosine similarity)     |
