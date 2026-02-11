"""
Tools for the ReAct agent: Web search (shallow/deep), RAG, datetime, document creation (PDF/Word/Excel).
No agent frameworks; raw requests and local libs.
"""
import os
from datetime import datetime
from pathlib import Path

import pytz
import requests

from rag import retrieve

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
# Generated documents go here; served at /static/ for download links
STATIC_DIR = Path(__file__).parent / "static"


# --- Web search: shallow vs deep ----------------------------------------------------------------
def tavily_search(
    query: str,
    max_results: int = 5,
    depth: str = "basic",
) -> str:
    """Call Tavily API. depth: 'basic' (shallow) or 'advanced' (deep retrieval)."""
    if not TAVILY_API_KEY:
        return "[Tavily API key not set. Set TAVILY_API_KEY.]"
    search_depth = "advanced" if depth == "advanced" else "basic"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
    }
    try:
        r = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            return "No search results found."
        parts = []
        for i, hit in enumerate(results, 1):
            title = hit.get("title", "")
            content = hit.get("content", "")
            url = hit.get("url", "")
            parts.append(f"[{i}] {title}\n{content}\nSource: {url}")
        return "\n\n".join(parts)
    except Exception as e:
        return f"[Search error: {e}]"


# --- RAG ----------------------------------------------------------------------------------------
def rag_retrieve(query: str, top_k: int = 3) -> str:
    """Retrieve top_k chunks from local RAG store."""
    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        return "No relevant documents found in the uploaded files."
    return "\n\n---\n\n".join(chunks)


# --- Live datetime (Pakistan Standard Time) ------------------------------------------------------
def datetime_tool() -> str:
    """Return current date and time in Pakistan (PKT, Asia/Karachi). No API key."""
    pk_tz = pytz.timezone("Asia/Karachi")
    now = datetime.now(pk_tz)
    return f"Current local time in Pakistan (PKT): {now.strftime('%Y-%m-%d %I:%M:%S %p')}"


# --- Document creation (PDF, Word, Excel) -------------------------------------------------------
def _ensure_static_dir() -> Path:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    return STATIC_DIR


def python_pdf_generator(title: str, body: str) -> str:
    """
    Python PDF generator tool: create a PDF file using fpdf2 and save under static/.
    Use this whenever the user asks for a PDF. Returns JSON with status and url for download.
    """
    try:
        from fpdf import FPDF
        _ensure_static_dir()
        safe = (title or "Generated_Document")[:50].replace(" ", "_").strip("_") or "Generated_Document"
        path = STATIC_DIR / f"{safe}.pdf"
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, (title or "Document")[:200], ln=True)
        pdf.ln(5)
        for line in (body or "").replace("\r", "").split("\n")[:200]:
            pdf.multi_cell(0, 6, line[:200])
        pdf.output(str(path))
        return f'{{"status": "success", "message": "File created.", "url": "/static/{path.name}", "download_url": "http://localhost:8000/static/{path.name}"}}'
    except Exception as e:
        return f'{{"status": "error", "message": "{str(e)[:100]}"}}'


def create_document_pdf(title: str, body: str) -> str:
    """Create a PDF in static/ using the Python PDF generator. Returns status with url for backend."""
    return python_pdf_generator(title, body)


def create_document_docx(title: str, body: str) -> str:
    """Create a Word doc in static/. Returns status with DOCUMENT_URL."""
    try:
        from docx import Document
        _ensure_static_dir()
        safe = title[:50].replace(" ", "_").strip("_") or "Generated_Document"
        path = STATIC_DIR / f"{safe}.docx"
        doc = Document()
        doc.add_heading(title[:200], 0)
        for para in body.replace("\r", "").split("\n")[:200]:
            doc.add_paragraph(para[:200])
        doc.save(str(path))
        return f'{{"status": "success", "message": "File created.", "url": "/static/{path.name}", "download_url": "http://localhost:8000/static/{path.name}"}}'
    except Exception as e:
        return f'{{"status": "error", "message": "{str(e)[:100]}"}}'


def create_document_xlsx(title: str, body: str) -> str:
    """Create an Excel file in static/. Returns status with DOCUMENT_URL."""
    try:
        from openpyxl import Workbook
        _ensure_static_dir()
        safe = title[:50].replace(" ", "_").strip("_") or "Generated_Document"
        path = STATIC_DIR / f"{safe}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = title[:31] if title else "Sheet1"
        for i, line in enumerate(body.replace("\r", "").split("\n")[:500], 1):
            cells = [c.strip() for c in line.split("\t")[:20]] or [line[:200]]
            for j, val in enumerate(cells, 1):
                ws.cell(row=i, column=j, value=val)
        wb.save(str(path))
        return f'{{"status": "success", "message": "File created.", "url": "/static/{path.name}", "download_url": "http://localhost:8000/static/{path.name}"}}'
    except Exception as e:
        return f'{{"status": "error", "message": "{str(e)[:100]}"}}'


def document_create(format: str, title: str, body: str) -> str:
    """Create a document in static/. format: pdf | docx | xlsx. Returns JSON with status and url."""
    if not title:
        title = "Document"
    if format == "pdf":
        return create_document_pdf(title, body)
    if format == "docx":
        return create_document_docx(title, body)
    if format == "xlsx":
        return create_document_xlsx(title, body)
    return f'{{"status": "error", "message": "Unknown format: {format}"}}'
