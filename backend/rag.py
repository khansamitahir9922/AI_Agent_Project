"""
Native RAG: manual chunking, local embeddings (sentence-transformers all-MiniLM-L6-v2), numpy cosine similarity.
No API keys for RAG; runs on local CPU. Vector store = local vector_store.json.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

import numpy as np

VECTOR_STORE_PATH = Path(__file__).parent / "vector_store.json"
EMBEDDING_MODEL_ID = "all-MiniLM-L6-v2"

# Names of files that have been ingested (for UI display)
UPLOADED_FILES: set = set()

# Lazy-loaded SentenceTransformer (loads on first get_embedding call)
_embedding_model = None


def _get_embedding_model():
    """Load sentence-transformers model once (local CPU, no API key)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_ID)
    return _embedding_model


def chunk_by_paragraphs(text: str) -> List[str]:
    """Split text by double newline (paragraphs). Filter empty chunks."""
    raw = text.split("\n\n")
    return [c.strip() for c in raw if c.strip()]


def get_embedding(text: str) -> List[float]:
    """Get embedding for a single text via local sentence-transformers (all-MiniLM-L6-v2)."""
    try:
        model = _get_embedding_model()
        emb = model.encode(text, convert_to_numpy=True)
        return np.asarray(emb).flatten().tolist()
    except Exception:
        pass
    return []


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity = dot(a,b) / (||a|| * ||b||)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def load_vector_store() -> List[Dict[str, Any]]:
    """Load vector store from JSON. Return list of {text, vector}."""
    if not VECTOR_STORE_PATH.exists():
        return []
    with open(VECTOR_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_vector_store(store: List[Dict[str, Any]]) -> None:
    """Persist vector store to JSON."""
    with open(VECTOR_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def ingest_file(file_path: str) -> Dict[str, Any]:
    """
    Ingest a .txt or .md file: read, chunk by paragraphs, embed, append to store.
    file_path: path to the uploaded file on disk.
    Returns summary: {chunks_created, total_chunks}.
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": "File not found", "chunks_created": 0, "total_chunks": 0}
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_by_paragraphs(text)
    if not chunks:
        return {"chunks_created": 0, "total_chunks": 0}

    store = load_vector_store()
    for c in chunks:
        vec = get_embedding(c)
        store.append({"text": c, "vector": vec})
    save_vector_store(store)
    return {"chunks_created": len(chunks), "total_chunks": len(store)}


def ingest_text(text: str, filename: str | None = None) -> Dict[str, Any]:
    """Ingest raw text (e.g. from upload content). If filename is provided, add it to UPLOADED_FILES."""
    if filename:
        UPLOADED_FILES.add(filename)
    chunks = chunk_by_paragraphs(text)
    if not chunks:
        return {"chunks_created": 0, "total_chunks": len(load_vector_store())}
    store = load_vector_store()
    for c in chunks:
        vec = get_embedding(c)
        store.append({"text": c, "vector": vec})
    save_vector_store(store)
    return {"chunks_created": len(chunks), "total_chunks": len(store)}


def get_file_list() -> List[str]:
    """Return list of uploaded filenames currently in RAG memory (for UI)."""
    return sorted(list(UPLOADED_FILES))


def retrieve(query: str, top_k: int = 3) -> List[str]:
    """
    Convert query to vector, compute cosine similarity with all stored vectors (numpy),
    return top_k chunk texts.
    """
    store = load_vector_store()
    if not store:
        return []
    q_vec = np.array(get_embedding(query), dtype=float)
    scored = []
    for item in store:
        v = np.array(item["vector"], dtype=float)
        sim = cosine_similarity(q_vec, v)
        scored.append((sim, item["text"]))
    scored.sort(key=lambda x: -x[0])
    return [text for _, text in scored[:top_k]]
