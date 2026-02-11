"use client";

import type { ReactNode } from "react";
import { Download } from "lucide-react";
import { ReasoningTrace, type ReActStep } from "./ReasoningTrace";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning: string[] | null;
  steps: ReActStep[] | null;
  networkUsed?: string;
  documentUrl?: string | null;
  /** Clickable download link for generated PDF/DOCX/XLSX */
  download_url?: string | null;
}

interface ChatMessageProps {
  message: Message;
  linkify: (text: string) => ReactNode;
  ReasoningBlock?: (props: { steps: string[] }) => ReactNode;
}

export function ChatMessage({ message, linkify, ReasoningBlock }: ChatMessageProps) {
  const downloadUrl = message.download_url ?? message.documentUrl;

  return (
    <>
      {message.role === "assistant" && message.steps && message.steps.length > 0 && (
        <ReasoningTrace steps={message.steps} />
      )}
      {message.role === "assistant" &&
        !(message.steps?.length) &&
        message.reasoning &&
        message.reasoning.length > 0 &&
        ReasoningBlock && <ReasoningBlock steps={message.reasoning} />}
      <div className="whitespace-pre-wrap text-sm">{linkify(message.content)}</div>
      {message.role === "assistant" && downloadUrl && (
        <button
          type="button"
          onClick={() => window.open(downloadUrl, "_blank")}
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-[var(--accent)]/20 px-3 py-2 text-sm font-medium text-[var(--accent)] transition hover:bg-[var(--accent)]/30"
        >
          <Download className="h-4 w-4" />
          📄 Download Generated File
        </button>
      )}
    </>
  );
}
