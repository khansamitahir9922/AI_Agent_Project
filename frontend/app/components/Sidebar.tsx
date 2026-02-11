"use client";

import { FileText, Upload, Loader2 } from "lucide-react";

export interface RagStatus {
  has_documents: boolean;
  chunk_count: number;
  file_list: string[];
}

interface SidebarProps {
  ragStatus: RagStatus;
  onDrop: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onFileSelect: (files: FileList | null) => void;
  uploading: boolean;
  uploadError: string | null;
}

export function Sidebar({
  ragStatus,
  onDrop,
  onDragOver,
  onFileSelect,
  uploading,
  uploadError,
}: SidebarProps) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-[var(--muted)]">
        <FileText className="h-4 w-4" /> Documents (RAG)
      </h2>
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        className="upload-zone cursor-pointer"
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".txt,.md"
          multiple
          className="hidden"
          onChange={(e) => onFileSelect(e.target.files)}
        />
        {uploading ? (
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--accent)]" />
        ) : (
          <Upload className="mx-auto h-8 w-8 text-[var(--muted)]" />
        )}
        <p className="mt-2 text-sm text-[var(--muted)]">
          Drop .txt or .md here
        </p>
      </div>
      {uploadError && (
        <p className="mt-2 text-xs text-red-400">{uploadError}</p>
      )}
      {ragStatus.file_list && ragStatus.file_list.length > 0 ? (
        <div className="mt-3 space-y-1">
          <p className="text-xs font-medium text-[var(--muted)]">
            In RAG memory ({ragStatus.chunk_count} chunk{ragStatus.chunk_count !== 1 ? "s" : ""})
          </p>
          <ul className="space-y-1.5">
            {ragStatus.file_list.map((name) => (
              <li
                key={name}
                className="flex items-center gap-2 truncate text-xs text-[var(--text)]"
                title={name}
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
                <span className="min-w-0 truncate">{name}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        ragStatus.has_documents && (
          <p className="mt-2 text-xs text-emerald-400">
            {ragStatus.chunk_count} chunk(s) in store
          </p>
        )
      )}
    </aside>
  );
}
