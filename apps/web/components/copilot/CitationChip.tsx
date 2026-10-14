"use client";

import { useEffect, useId, useRef, useState } from "react";
import "./copilot.css";

export interface Citation {
  n?: number;
  chunk_id?: string;
  document_id?: string;
  title?: string;
  kind?: string;
  clause_ref?: string | null;
  quote?: string;
}

/** Citation chip "[1] clause 4.2" → popover with the source title and the quoted snippet (text only). */
export function CitationChip({ citation, showTitle = false }: { citation: Citation; showTitle?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const label = [
    citation.n !== undefined ? `[${citation.n}]` : null,
    citation.clause_ref ? `clause ${citation.clause_ref}` : showTitle || !citation.n ? citation.title : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className="cp-cite-wrap" ref={ref}>
      <button
        type="button"
        className="cp-cite"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`Source ${citation.n ?? ""}: ${citation.title ?? "document"}${citation.clause_ref ? `, clause ${citation.clause_ref}` : ""}`}
        onClick={() => setOpen((o) => !o)}
      >
        {label || "source"}
      </button>
      {open ? (
        <span id={id} role="note" className="cp-cite-pop">
          <span className="field-label">
            {citation.title ?? "Source"}
            {citation.clause_ref ? ` · clause ${citation.clause_ref}` : ""}
          </span>
          {citation.quote ? <span className="cp-cite-quote">“{citation.quote}”</span> : null}
        </span>
      ) : null}
    </span>
  );
}
