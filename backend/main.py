from dotenv import load_dotenv

# Load .env first so all API keys are available before any other imports or logic
load_dotenv()

import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reasoning_engine import run
from rag import ingest_text, load_vector_store, get_file_list

app = FastAPI(title="Adaptive Reasoning Agent")

# Serve generated documents for download links (clickable download_url)
STATIC_PATH = Path(__file__).parent / "static"
os.makedirs(STATIC_PATH, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")


@app.on_event("startup")
def startup_check():
    """Log whether Groq API key is set at startup (RAG uses local embeddings, no key)."""
    if os.environ.get("GROQ_API_KEY"):
        print("[startup] GROQ_API_KEY is set; Groq chat ready.")
    else:
        print("[startup] GROQ_API_KEY not set; chat will fail. RAG uses local embeddings (no key).")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    # When user asks for "PDF of the comparison/response", send the previous assistant reply here so the PDF contains that content.
    context_for_document: str | None = None


class ReActStepModel(BaseModel):
    thought: str
    tool_name: str
    tool_input: str
    observation: str


class ChatResponse(BaseModel):
    answer: str
    reasoning: list[str] | None = None
    steps: list[ReActStepModel] | None = None
    document_url: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


def _extract_document_url(steps: list, request: Request) -> str | None:
    """If any step is Document_Create_* and observation contains success url, return full URL."""
    base = str(request.base_url).rstrip("/")
    for step in steps or []:
        name = (step.get("tool_name") or "").strip()
        if not name.startswith("Document_Create_"):
            continue
        obs = (step.get("observation") or "").strip()
        # 1) Try JSON: {"status": "success", "url": "...", "download_url": "http://..."} (clickable link)
        try:
            data = json.loads(obs)
            if data.get("status") == "success":
                if data.get("download_url"):
                    return data["download_url"]
                if data.get("url"):
                    return base + data["url"] if not data["url"].startswith("http") else data["url"]
        except (json.JSONDecodeError, TypeError):
            pass
        # 2) Look for "/static/..." in observation
        m = re.search(r'"/static/[^"]+"', obs)
        if m:
            path = m.group(0).strip('"')
            return base + path
        m = re.search(r"(/static/[^\s\"']+)", obs)
        if m:
            return base + m.group(1)
        # 3) Fallback: "Created: filename.pdf" or "Created: Generated_Document.pdf"
        created = re.search(r"Created:\s*([^\s,\.]+\.(?:pdf|docx|xlsx))", obs, re.IGNORECASE)
        if created:
            return base + "/static/" + created.group(1).strip()
        # 4) Last resort: default filename by tool type
        if "PDF" in name:
            return base + "/static/Generated_Document.pdf"
        if "DOCX" in name:
            return base + "/static/Generated_Document.docx"
        if "XLSX" in name:
            return base + "/static/Generated_Document.xlsx"
    return None


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: Request,
    body: ChatRequest,
    x_network_quality: str | None = Header(None, alias="X-Network-Quality"),
    x_reasoning_mode: str | None = Header(None, alias="X-Reasoning-Mode"),
):
    """
    Adaptive reasoning: mode = fast | standard | deep | auto.
    Network = slow | fast (used when mode is auto).
    """
    out = run(
        body.message,
        reasoning_mode=x_reasoning_mode or "auto",
        network_quality=x_network_quality or "fast",
        context_for_document=body.context_for_document,
    )

    # Observability: print Work Trace to terminal for examiner verification
    mode = (x_reasoning_mode or "auto").strip().lower()
    network = (x_network_quality or "fast").strip().lower()
    if out.get("steps"):
        print(f"\n[AGENT TRACE] Query: {body.message}")
        for i, step in enumerate(out["steps"]):
            print(f"  Step {i + 1}:")
            print(f"    THOUGHT: {step.get('thought', '')}")
            print(f"    ACTION: {step.get('tool_name', '')}({step.get('tool_input', '')})")
            obs = step.get("observation", "")
            print(f"    OBSERVATION: {obs[:100]}{'...' if len(obs) > 100 else ''}")
    elif mode == "auto" and network in ("slow", "3g"):
        print(f"\n[AGENT] Network slow + auto → Mode A (Direct), no tool steps. Query: {body.message[:60]}...")

    document_url = _extract_document_url(out.get("steps") or [], request)
    answer = out["answer"] or ""
    if document_url:
        answer = answer.rstrip()
        if answer and not answer.endswith("\n"):
            answer += "\n\n"
        answer += f"Download your document: {document_url}"

    return ChatResponse(
        answer=answer,
        reasoning=out.get("reasoning"),
        steps=out.get("steps"),
        document_url=document_url,
    )


# --- RAG: upload and ingest ----------------------------------------------------------------------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Accept .txt or .md; ingest (chunk + embed), store in vector_store.json."""
    if not file.filename:
        raise HTTPException(400, "No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".txt", ".md"):
        raise HTTPException(400, "Only .txt and .md files are allowed")
    content = await file.read()
    try:
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    except Exception:
        raise HTTPException(400, "Could not decode file as UTF-8")
    result = ingest_text(text, filename=file.filename)
    return result


@app.get("/api/rag/status")
def rag_status():
    """Return RAG status and list of uploaded filenames for UI."""
    store = load_vector_store()
    return {
        "has_documents": len(store) > 0,
        "chunk_count": len(store),
        "file_list": get_file_list(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
