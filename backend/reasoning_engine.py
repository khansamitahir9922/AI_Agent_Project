"""
Adaptive Reasoning Engine: Fast / Standard / Deep / Auto.
Custom logic with standard LLM only. ReAct returns visible steps: Thought → Action → Observation.
"""
import os
import re
from datetime import datetime
from typing import List, Dict, Any, TypedDict

import pytz
from groq import Groq

from tools import (
    tavily_search,
    rag_retrieve,
    datetime_tool,
    document_create,
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_NAME = "llama-3.3-70b-versatile"

# Reasoning modes: fast (single-pass), standard (step-based), deep (multi-step ReAct), auto (by network)
REASONING_MODES = ("fast", "standard", "deep", "auto")


class ReActStep(TypedDict):
    """Exact format for observability and terminal Work Trace: thought, tool_name, tool_input, observation."""

    thought: str
    tool_name: str
    tool_input: str
    observation: str


def _client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def get_local_time() -> str:
    """Current local time in Pakistan (PKT, Asia/Karachi)."""
    pk_tz = pytz.timezone("Asia/Karachi")
    return datetime.now(pk_tz).strftime("%Y-%m-%d %I:%M:%S %p")


def _system_prompt() -> str:
    """System prompt prefix so the LLM is always aware of Pakistan local time."""
    return f"The current local time in Pakistan is: {get_local_time()}."


# --- Fast: single-pass (efficient thinking) ------------------------------------------------------
def run_fast(user_message: str) -> Dict[str, Any]:
    """Single-pass reasoning. No tools, no steps. Answer quality constant, path minimal."""
    try:
        client = _client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )
        answer = ""
        if response.choices and len(response.choices) > 0:
            msg = response.choices[0].message
            if msg and getattr(msg, "content", None):
                answer = (msg.content or "").strip()
        return {"answer": answer, "reasoning": None, "steps": None}
    except Exception as e:
        return {"answer": f"Error: {e}", "reasoning": None, "steps": None}


# --- Standard: step-based logic (one explicit reasoning step) ------------------------------------
STANDARD_PROMPT = """Think through the following question step by step. Then give your final answer in a clear, concise way.

Question: {query}

First reason step by step (brief), then conclude with: ANSWER: <your final answer>"""


def run_standard(user_message: str) -> Dict[str, Any]:
    """Step-based reasoning: one CoT-style call, then extract answer. One step in trace."""
    try:
        client = _client()
        prompt = STANDARD_PROMPT.format(query=user_message)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1024,
        )
        raw = ""
        if response.choices and len(response.choices) > 0 and response.choices[0].message:
            raw = (response.choices[0].message.content or "").strip()
        # Extract ANSWER: ... if present
        answer_match = re.search(r"ANSWER:\s*(.+)", raw, re.DOTALL | re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1).strip()
            thought = raw[: answer_match.start()].strip()
        else:
            answer = raw
            thought = "(Step-based reasoning applied.)"
        step: ReActStep = {
            "thought": thought[:1500],
            "tool_name": "none",
            "tool_input": "",
            "observation": "(No tool used; standard step-based reasoning.)",
        }
        reasoning = [f"Thought: {step['thought']}", f"Answer: {answer[:200]}..."]
        return {"answer": answer, "reasoning": reasoning, "steps": [step]}
    except Exception as e:
        return {"answer": f"Error: {e}", "reasoning": None, "steps": None}


# --- Deep: ReAct loop — Thought → Action → Observation (all tools) ------------------------------
REACT_THOUGHT_ACTION_PROMPT = """You are a reasoning assistant with access to tools. The user has asked a question. State your thought and choose ONE action.

User question: "{query}"

Available tools:
- Web_Search: Shallow/fast web search for recent facts (use for quick lookups).
- Web_Search_deep: Deep web search for thorough coverage (use when you need comprehensive results).
- RAG_Tool: Search the user's uploaded documents (use when the question is about uploaded file content).
- Datetime: Get current date and time (use when the user asks for time, date, or "now").
- Document_Create_PDF: Document generation tool (PDF). Use when the user asks to generate, create, or download a document/file/report—e.g. "generate a report", "generate a document", "create a PDF", "make a document". Default to this when they ask for "a document" or "report" without specifying format. Do NOT say you cannot create documents; use this tool.
- Document_Create_DOCX: Create a Word document (use when user asks for Word/docx or a report in docx).
- Document_Create_XLSX: Create an Excel spreadsheet (use when user asks for Excel/spreadsheet).
- none: Answer from general knowledge (do NOT use none when the user asks to generate/create a document or file—use Document_Create_PDF).

Respond with exactly this format (no other text):
THOUGHT: <your brief reasoning in 1-2 sentences>
ACTION: <one of: Web_Search, Web_Search_deep, RAG_Tool, Datetime, Document_Create_PDF, Document_Create_DOCX, Document_Create_XLSX, none>"""


def _parse_thought_and_action(llm_output: str) -> tuple[str, str]:
    thought = ""
    action = "none"
    if not llm_output:
        return thought, action
    thought_m = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|\Z)", llm_output, re.DOTALL | re.IGNORECASE)
    if thought_m:
        thought = thought_m.group(1).strip()
    action_m = re.search(r"ACTION:\s*(\w+)", llm_output, re.IGNORECASE)
    if action_m:
        raw = action_m.group(1).strip().lower()
        if "web_search_deep" in raw or "web_search_deep" in llm_output:
            action = "Web_Search_deep"
        elif "search" in raw:
            action = "Web_Search"
        elif "rag" in raw:
            action = "RAG_Tool"
        elif "datetime" in raw or "date" in raw or "time" in raw:
            action = "Datetime"
        elif "pdf" in raw or ("document" in raw and "create" in raw):
            action = "Document_Create_PDF"
        elif "docx" in raw or "word" in raw:
            action = "Document_Create_DOCX"
        elif "xlsx" in raw or "excel" in raw:
            action = "Document_Create_XLSX"
        else:
            action = "none"
    return thought, action


def run_deep(user_message: str, context_for_document: str | None = None) -> Dict[str, Any]:
    """
    Deep reasoning: ReAct loop with full tool set.
    Tools: Web_Search (shallow), Web_Search_deep, RAG_Tool, Datetime, Document_Create (PDF/DOCX/XLSX).
    When user asks for "PDF of the comparison/response", pass that content as context_for_document so the PDF contains it.
    """
    client = _client()
    steps: List[ReActStep] = []

    prompt = REACT_THOUGHT_ACTION_PROMPT.format(query=user_message)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=250,
        )
        raw = ""
        if response.choices and len(response.choices) > 0 and response.choices[0].message:
            raw = (response.choices[0].message.content or "").strip()
    except Exception as e:
        raw = f"THOUGHT: Error. ACTION: none"
    thought, action = _parse_thought_and_action(raw)
    if not thought:
        thought = "Considering which tool to use for this question."

    # If user asks to generate/create a document or file but the model chose "none", force document tool (default PDF)
    q_lower = (user_message or "").lower()
    wants_document = _user_wants_document(user_message)
    if action == "none" and wants_document:
        # Prefer PDF unless they asked for Word or Excel
        if "docx" in q_lower or "word" in q_lower:
            action = "Document_Create_DOCX"
            thought = "The user asked for a Word document. I will use the document tool to create it."
        elif "xlsx" in q_lower or "excel" in q_lower:
            action = "Document_Create_XLSX"
            thought = "The user asked for an Excel file. I will use the document tool to create it."
        else:
            action = "Document_Create_PDF"
            thought = "The user asked for a document. I will use the document generation tool to create a PDF."

    tool_name = "none"
    tool_input = ""
    observation = "(No tool used.)"

    if action == "Web_Search":
        tool_name = "Web_Search"
        tool_input = f'query="{user_message}"'
        observation = tavily_search(user_message, depth="basic")
    elif action == "Web_Search_deep":
        tool_name = "Web_Search_deep"
        tool_input = f'query="{user_message}"'
        observation = tavily_search(user_message, depth="advanced")
    elif action == "RAG_Tool":
        tool_name = "RAG_Tool"
        tool_input = f'query="{user_message}"'
        observation = rag_retrieve(user_message, top_k=3)
    elif action == "Datetime":
        tool_name = "Datetime"
        tool_input = ""
        observation = datetime_tool()
    elif action in ("Document_Create_PDF", "Document_Create_DOCX", "Document_Create_XLSX"):
        tool_name = action
        fmt = "pdf" if "PDF" in action else "docx" if "DOCX" in action else "xlsx"
        tool_input = f'format={fmt}, title="Generated Document", body="<content>"'
        title = "Generated Document"
        # Use previous response (e.g. comparison) as PDF body when provided; otherwise user message
        body = (context_for_document or user_message).strip()[:5000] or user_message[:5000]
        observation = document_create(fmt, title, body)
    else:
        tool_name = "none"

    steps.append({
        "thought": thought,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "observation": observation[:2000] + ("..." if len(observation) > 2000 else ""),
    })

    FINAL_ANSWER_PROMPT = """The user asked: "{query}"

Tool used: {tool_name}
Tool input: {tool_input}
Observation:
{observation}

Using the above, provide a clear and concise final answer. If no tool was used or the observation is not helpful, answer from general knowledge.
If the tool was Document_Create_PDF (Python PDF generator) or DOCX/XLSX and the observation shows success, say briefly that the document was created with the Python PDF generator and the user can download it below. Do NOT give generic advice like "use Adobe Acrobat" or "I cannot create PDFs"—you already created it via the tool."""

    final_prompt = FINAL_ANSWER_PROMPT.format(
        query=user_message,
        tool_name=tool_name,
        tool_input=tool_input or "(none)",
        observation=observation,
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0,
        )
        answer = ""
        if response.choices and len(response.choices) > 0 and response.choices[0].message:
            answer = (response.choices[0].message.content or "").strip()
    except Exception as e:
        answer = f"Error generating answer: {e}"

    reasoning = []
    for s in steps:
        reasoning.append(f"Thought: {s['thought']}")
        reasoning.append(f"Action: {s['tool_name']}({s['tool_input']})")
        reasoning.append(f"Observation: {s['observation'][:200]}{'...' if len(s['observation']) > 200 else ''}")

    return {"answer": answer, "reasoning": reasoning, "steps": steps}


def _user_wants_document(user_message: str) -> bool:
    """True if the user is asking to generate/create a document, report, or file (needs tool path)."""
    q = (user_message or "").lower()
    return (
        "pdf" in q or "docx" in q or "word" in q or "excel" in q or "xlsx" in q
        or ("download" in q and ("document" in q or "response" in q or "comparison" in q or "file" in q or "report" in q))
        or ("create" in q and ("document" in q or "file" in q or "pdf" in q or "report" in q))
        or ("generate" in q and ("document" in q or "file" in q or "report" in q))
        or ("export" in q and ("pdf" in q or "document" in q))
        or ("give" in q and ("document" in q or "file" in q))
        or ("make" in q and ("document" in q or "pdf" in q or "file" in q))
    )


# --- Auto: select strategy at runtime (by network) ---------------------------------------------
def run_auto(user_message: str, network_slow: bool, context_for_document: str | None = None) -> Dict[str, Any]:
    """
    Auto mode: always use deep (tool-capable) path so answer quality stays constant.
    Reasoning path is the same; network indicator is for UX. Tools (e.g. Web_Search) must
    remain available so real-time questions (weather, etc.) get real answers.
    """
    return run_deep(user_message, context_for_document=context_for_document)


# --- Entrypoint used by main.py -----------------------------------------------------------------
def run(
    user_message: str,
    reasoning_mode: str,
    network_quality: str,
    context_for_document: str | None = None,
) -> Dict[str, Any]:
    """
    reasoning_mode: fast | standard | deep | auto
    network_quality: slow | fast (for auto mode).
    context_for_document: when user asks for PDF of "the comparison/response", pass that content here.
    """
    mode = (reasoning_mode or "auto").strip().lower()
    if mode not in REASONING_MODES:
        mode = "auto"
    network_quality_lower = (network_quality or "").strip().lower()
    network_slow = network_quality_lower in ("slow", "3g")

    # Always use Deep (ReAct) in auto mode so every response includes the reasoning trace (thought → action → observation)
    if mode == "auto":
        mode = "deep"

    if mode == "fast":
        return run_fast(user_message)
    if mode == "standard":
        return run_standard(user_message)
    if mode == "deep":
        return run_deep(user_message, context_for_document=context_for_document)
    return run_auto(user_message, network_slow, context_for_document=context_for_document)
