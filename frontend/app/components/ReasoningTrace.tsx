"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Search, FileText, Minus, Calendar, FileDown } from "lucide-react";

export interface ReActStep {
  thought: string;
  tool_name: string;
  tool_input: string;
  observation: string;
}

interface ReasoningTraceProps {
  steps: ReActStep[];
}

export function ReasoningTrace({ steps }: ReasoningTraceProps) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;

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
        Reasoning Trace ({steps.length} step{steps.length !== 1 ? "s" : ""})
      </button>
      {open && (
        <div className="mt-3 space-y-4">
          {steps.map((step, i) => (
            <StepCard key={i} step={step} index={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function StepCard({ step, index }: { step: ReActStep; index: number }) {
  const name = step.tool_name;
  const ToolIcon =
    name === "Web_Search" || name === "Web_Search_deep"
      ? Search
      : name === "RAG_Tool"
        ? FileText
        : name === "Datetime"
          ? Calendar
          : name.startsWith("Document_Create_")
            ? FileDown
            : Minus;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)]/50 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
        <span className="rounded bg-[var(--accent)]/20 px-1.5 py-0.5 text-[var(--accent)]">
          Step {index}
        </span>
        {step.tool_name !== "none" && (
          <span className="flex items-center gap-1">
            <ToolIcon className="h-3.5 w-3.5" />
            {step.tool_name}
          </span>
        )}
      </div>
      <div className="space-y-2 p-3 text-xs">
        <div>
          <span className="font-medium text-[var(--accent)]">Thought</span>
          <p className="mt-0.5 text-[var(--text)]">{step.thought || "—"}</p>
        </div>
        {step.tool_name !== "none" && (
          <>
            <div>
              <span className="font-medium text-[var(--accent)]">Action</span>
              <p className="mt-0.5 font-mono text-[var(--text)]">
                {step.tool_name}({step.tool_input})
              </p>
            </div>
            <div>
              <span className="font-medium text-[var(--accent)]">Observation</span>
              <p className="mt-0.5 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-[var(--muted)]">
                {step.observation}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
