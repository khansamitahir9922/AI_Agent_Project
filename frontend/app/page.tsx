"use client";

import { useState, useCallback, useEffect, type ReactNode } from "react";
import {
  Send,
  Upload,
  Wifi,
  WifiOff,
  ChevronDown,
  ChevronRight,
  Loader2,
  FileText,
  Bot,
  User,
} from "lucide-react";
import { ReasoningTrace, type ReActStep } from "./components/ReasoningTrace";
import { ChatMessage } from "./components/ChatMessage";
import { Sidebar, type RagStatus } from "./components/Sidebar";
import { useNetworkSensing } from "../hooks/useNetworkSensing";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type NetworkQuality = "slow" | "fast";

/** Turn URLs in text into clickable links. */
function linkify(text: string): ReactNode {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = text.split(urlRegex);
  return parts.map((part, i) =>
    part.match(urlRegex) ? (
      <a
        key={i}
        href={part}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--accent)] underline break-all"
      >
        {part}
      </a>
    ) : (
      part
    )
  );
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning: string[] | null;
  steps: ReActStep[] | null;
  networkUsed: NetworkQuality;
  documentUrl: string | null;
  /** Clickable download link for generated file (PDF/DOCX/XLSX) */
  download_url?: string | null;
}

export default function Home() {
  const networkQuality = useNetworkSensing();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [ragStatus, setRagStatus] = useState<RagStatus>({
    has_documents: false,
    chunk_count: 0,
    file_list: [],
  });

  const fetchRagStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/rag/status`);
      const data = await r.json();
      setRagStatus({
        has_documents: data.has_documents ?? false,
        chunk_count: data.chunk_count ?? 0,
        file_list: data.file_list ?? [],
      });
    } catch {
      setRagStatus({ has_documents: false, chunk_count: 0, file_list: [] });
    }
  }, []);

  useEffect(() => {
    fetchRagStatus();
  }, [fetchRagStatus]);

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return;
      setUploadError(null);
      setUploading(true);
      for (const file of Array.from(files)) {
        const ext = file.name.toLowerCase().slice(-4);
        if (ext !== ".txt" && file.name.toLowerCase().slice(-3) !== ".md") {
          setUploadError("Only .txt and .md files are allowed.");
          continue;
        }
        const form = new FormData();
        form.append("file", file);
        try {
          const r = await fetch(`${API_BASE}/api/upload`, {
            method: "POST",
            body: form,
          });
          if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            setUploadError(err.detail || "Upload failed.");
          } else {
            await fetchRagStatus();
          }
        } catch (e) {
          setUploadError("Network error during upload.");
        }
      }
      setUploading(false);
    },
    [fetchRagStatus]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleUpload(e.dataTransfer.files);
    },
    [handleUpload]
  );
  const onDragOver = useCallback((e: React.DragEvent) => e.preventDefault(), []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      reasoning: null,
      steps: null,
      networkUsed: networkQuality,
      documentUrl: null,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    // When user asks for "PDF of the comparison/response", send last assistant message so the PDF contains that content.
    const lastAssistant = messages.filter((m) => m.role === "assistant").pop();
    const lower = text.toLowerCase();
    const wantsDocument =
      lower.includes("pdf") ||
      lower.includes("download") ||
      lower.includes("comparison") ||
      lower.includes("response") ||
      (lower.includes("document") && (lower.includes("that") || lower.includes("this") || lower.includes("it")));
    const contextForDocument = lastAssistant?.content?.trim() && wantsDocument ? lastAssistant.content : undefined;
    try {
      const r = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Network-Quality": networkQuality,
          "X-Reasoning-Mode": "auto",
        },
        body: JSON.stringify({
          message: text,
          ...(contextForDocument ? { context_for_document: contextForDocument } : {}),
        }),
      });
      const data = await r.json();
      const docUrl = data.document_url ?? null;
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.answer ?? "No response.",
        reasoning: data.reasoning ?? null,
        steps: data.steps ?? null,
        networkUsed: networkQuality,
        documentUrl: docUrl,
        download_url: docUrl,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Failed to reach the server. Is the backend running on " + API_BASE + "?",
          reasoning: null,
          steps: null,
          networkUsed: networkQuality,
          documentUrl: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-[var(--bg)]">
      {/* Top Bar: Auto network sensing indicator */}
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <h1 className="text-lg font-semibold text-[var(--text)]">
          Adaptive Reasoning Agent
        </h1>
        <div className="flex items-center gap-2 text-sm">
          {networkQuality === "slow" ? (
            <WifiOff className="h-4 w-4 text-amber-500" />
          ) : (
            <Wifi className="h-4 w-4 text-emerald-500" />
          )}
          <span className="text-[var(--muted)]">Network:</span>
          <span
            className={
              networkQuality === "slow"
                ? "font-medium text-amber-500"
                : "font-medium text-emerald-500"
            }
          >
            {networkQuality === "slow" ? "Slow" : "Fast"}
          </span>
          <span className="text-[var(--muted)]">(Auto-Optimizing Reasoning)</span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          ragStatus={ragStatus}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onFileSelect={handleUpload}
          uploading={uploading}
          uploadError={uploadError}
        />

        {/* Main: Chat */}
        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex h-full items-center justify-center text-[var(--muted)]">
                <p className="text-center">
                  Send a message. Reasoning depth switches automatically by network: <strong>Slow</strong> → fast single-pass; <strong>Fast</strong> → deep reasoning with tools. Simulate &quot;Slow 3G&quot; in DevTools to see the switch.
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}
              >
                {m.role === "assistant" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/20">
                    <Bot className="h-4 w-4 text-[var(--accent)]" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    m.role === "user"
                      ? "bg-[var(--accent-dim)]/30 text-[var(--text)]"
                      : "bg-[var(--surface)] border border-[var(--border)]"
                  }`}
                >
                  {m.role === "assistant" ? (
                    <ChatMessage
                      message={{ ...m, download_url: m.download_url ?? m.documentUrl }}
                      linkify={linkify}
                      ReasoningBlock={ReasoningBlock}
                    />
                  ) : (
                    <div className="whitespace-pre-wrap text-sm">{linkify(m.content)}</div>
                  )}
                </div>
                {m.role === "user" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--border)]">
                    <User className="h-4 w-4 text-[var(--muted)]" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/20">
                  <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
                </div>
                <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] px-4 py-3">
                  <span className="text-sm text-[var(--muted)]">Thinking...</span>
                </div>
              </div>
            )}
          </div>
          <div className="shrink-0 border-t border-[var(--border)] bg-[var(--surface)] p-4">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message..."
                className="flex-1 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3 text-[var(--text)] placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-xl bg-[var(--accent)] px-4 py-3 text-white transition hover:bg-[var(--accent-dim)] disabled:opacity-50"
              >
                <Send className="h-5 w-5" />
              </button>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}

function ReasoningBlock({ steps }: { steps: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-3 border-b border-[var(--border)] pb-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1 text-xs font-medium text-[var(--accent)]"
      >
        {open ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        Show Reasoning
      </button>
      {open && (
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-[var(--muted)]">
          {steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
