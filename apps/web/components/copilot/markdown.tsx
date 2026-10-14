"use client";

import { Fragment, type ReactNode } from "react";
import { CitationChip, type Citation } from "./CitationChip";

/**
 * Markdown-lite renderer for model output. Everything is rendered as React TEXT nodes —
 * never dangerouslySetInnerHTML. Supports paragraphs, `-`/`*`/`1.` lists, `#` headings,
 * **bold**, `code`, and citation markers `[1]` / `[^1]` → citation chips.
 */
export function MarkdownLite({ text, citations = [] }: { text: string; citations?: Citation[] }) {
  const blocks = toBlocks(text);
  return (
    <div className="cp-md">
      {blocks.map((b, i) => {
        if (b.kind === "ul")
          return (
            <ul key={i}>
              {b.items.map((it, j) => (
                <li key={j}>{inline(it, citations)}</li>
              ))}
            </ul>
          );
        if (b.kind === "ol")
          return (
            <ol key={i}>
              {b.items.map((it, j) => (
                <li key={j}>{inline(it, citations)}</li>
              ))}
            </ol>
          );
        if (b.kind === "h") return <p key={i} className="cp-md-h">{inline(b.text, citations)}</p>;
        if (b.kind === "p") return <p key={i}>{inline(b.text, citations)}</p>;
        return null;
      })}
    </div>
  );
}

type Block = { kind: "p" | "h"; text: string } | { kind: "ul" | "ol"; items: string[] };

function toBlocks(src: string): Block[] {
  const out: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) out.push({ kind: "p", text: para.join(" ") });
    para = [];
  };
  for (const raw of src.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const h = /^\s*#{1,6}\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flush();
      continue;
    }
    if (ul || ol) {
      flush();
      const kind = ul ? "ul" : "ol";
      const item = (ul ?? ol)![1] ?? "";
      const last = out[out.length - 1];
      if (last && last.kind === kind) last.items.push(item);
      else out.push({ kind, items: [item] });
      continue;
    }
    if (h) {
      flush();
      out.push({ kind: "h", text: h[1] ?? "" });
      continue;
    }
    // Continuation of a list item (indented) stays with the list.
    const last = out[out.length - 1];
    if (!para.length && last && (last.kind === "ul" || last.kind === "ol") && /^\s{2,}/.test(raw)) {
      last.items[last.items.length - 1] += ` ${line.trim()}`;
      continue;
    }
    para.push(line.trim());
  }
  flush();
  return out;
}

const TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|\[\^?\d{1,2}\])/g;

function inline(s: string, citations: Citation[]): ReactNode {
  const parts = s.split(TOKEN).filter((p) => p !== "");
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`") && p.length > 2) return <code key={i}>{p.slice(1, -1)}</code>;
    const m = /^\[\^?(\d{1,2})\]$/.exec(p);
    if (m) {
      const n = Number(m[1]);
      const c = citations.find((x) => x.n === n) ?? citations[n - 1];
      if (c) return <CitationChip key={i} citation={{ ...c, n }} />;
    }
    return <Fragment key={i}>{p}</Fragment>;
  });
}
