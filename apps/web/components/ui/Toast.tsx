"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";

export interface ToastOptions {
  /** ms before dismiss (default 4000). */
  duration?: number;
  /** "risk" for failures that leave money at risk (accent-700 fill). Default ink. */
  tone?: "ink" | "risk";
}

interface ToastItem extends Required<ToastOptions> {
  id: number;
  message: ReactNode;
}

interface ToastApi {
  /** toast("Short-paid PS-88214 · $2,759.60 posted to QuickBooks") */
  toast: (message: ReactNode, opts?: ToastOptions) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider> (AppShell provides one).");
  return ctx;
}

function ToastView({ item, onDone }: { item: ToastItem; onDone: (id: number) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onDone(item.id), item.duration);
    return () => clearTimeout(t);
  }, [item, onDone]);
  return (
    <div className="toast" data-tone={item.tone}>
      <span>{item.message}</span>
      <button type="button" className="toast-close" aria-label="Dismiss notification" onClick={() => onDone(item.id)}>
        <X size={14} strokeWidth={2} aria-hidden="true" />
      </button>
    </div>
  );
}

/** Bottom-right ink toasts, 12.5px, 4s, announced politely. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const toast = useCallback((message: ReactNode, opts: ToastOptions = {}) => {
    seq.current += 1;
    const item: ToastItem = { id: seq.current, message, duration: opts.duration ?? 4000, tone: opts.tone ?? "ink" };
    setItems((xs) => [...xs.slice(-3), item]);
  }, []);
  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" role="status" aria-live="polite" aria-atomic="false">
        {items.map((it) => (
          <ToastView key={it.id} item={it} onDone={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
