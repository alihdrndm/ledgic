"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Button } from "./Button";

export interface DialogResult {
  comment: string;
  acknowledged: boolean;
}

export interface DialogProps {
  open: boolean;
  /** Called on Cancel, Escape, or after a successful confirm. */
  onClose: () => void;
  title: ReactNode;
  /** The exact amount the action moves, e.g. "$2,847.60" (22px 800). */
  amount?: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** Comment field. `required` blocks confirm until non-blank (controller-only actions). */
  comment?: { label?: string; placeholder?: string; required?: boolean };
  /** Required acknowledgement checkbox, e.g. "I verified the bank details with the vendor by phone". */
  acknowledge?: string;
  /**
   * Performs the action. Throw or return an error string to keep the dialog open and show it.
   * Resolves → dialog closes.
   */
  onConfirm: (result: DialogResult) => Promise<void | string> | void | string;
}

/**
 * Modal confirmation for actions that move money (Approve as-is, Release hold).
 * Native <dialog>.showModal(): focus is contained, background is inert, Escape cancels.
 */
export function Dialog({
  open,
  onClose,
  title,
  amount,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  comment,
  acknowledge,
  onConfirm,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const bodyId = useId();
  const commentId = useId();
  const [text, setText] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      setText("");
      setAck(false);
      setError(null);
      el.showModal();
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  const commentMissing = Boolean(comment?.required) && text.trim().length === 0;
  const ackMissing = Boolean(acknowledge) && !ack;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (commentMissing || ackMissing || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await onConfirm({ comment: text.trim(), acknowledged: ack });
      if (typeof res === "string" && res) setError(res);
      else onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Nothing was posted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      className="ledgic-dialog"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      {open ? (
        <form className="dialog" onSubmit={submit}>
          <h2 id={titleId} className="dialog-title">
            {title}
          </h2>
          <div id={bodyId} className="dialog-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {amount ? <div className="dialog-amount">{amount}</div> : null}
            {children}
          </div>
          {comment ? (
            <div className="dialog-field">
              <label htmlFor={commentId}>
                {comment.label ?? "Comment"}
                {comment.required ? " (required)" : ""}
              </label>
              <textarea
                id={commentId}
                className="input"
                value={text}
                placeholder={comment.placeholder}
                required={comment.required}
                aria-required={comment.required || undefined}
                onChange={(e) => setText(e.target.value)}
                autoFocus
              />
            </div>
          ) : null}
          {acknowledge ? (
            <label className="dialog-check">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} required />
              <span>{acknowledge}</span>
            </label>
          ) : null}
          {error ? (
            <p className="dialog-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="dialog-actions">
            <Button variant="outline" size="sm" onClick={onClose} disabled={busy}>
              {cancelLabel}
            </Button>
            <Button variant="ink" size="sm" type="submit" loading={busy} disabled={commentMissing || ackMissing}>
              {confirmLabel}
            </Button>
          </div>
        </form>
      ) : null}
    </dialog>
  );
}
