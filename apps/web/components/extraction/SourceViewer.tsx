"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { Minus, Plus, Maximize2 } from "lucide-react";
import "./extraction.css";

export interface ViewerBox {
  key: string;
  page?: number;
  x: number;
  y: number;
  w: number;
  h: number;
  /** flagged = .flag-region (below floor); focus = currently selected field. */
  tone: "flag" | "focus";
  label: string;
}

export interface SourceViewerHandle {
  zoomTo: (b: { x: number; y: number; w: number; h: number }) => void;
  reset: () => void;
}

interface View {
  s: number;
  tx: number;
  ty: number;
}

const PAD = 40;
const MIN_S = 0.5;
const MAX_S = 6;

/**
 * Document image with wheel-zoom, drag-pan and bbox overlays positioned from normalized (0–1) coordinates.
 * Overlays live inside the transformed layer, so they stay locked to the page at every zoom.
 */
export const SourceViewer = forwardRef<SourceViewerHandle, { src: string | null; kind: "image" | "pdf" | null; boxes: ViewerBox[]; alt: string }>(
  function SourceViewer({ src, kind, boxes, alt }, ref) {
    const vpRef = useRef<HTMLDivElement>(null);
    const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
    const [vp, setVp] = useState<{ w: number; h: number }>({ w: 600, h: 800 });
    const [view, setView] = useState<View>({ s: 1, tx: PAD, ty: PAD });
    const [failed, setFailed] = useState(false);
    const drag = useRef<{ x: number; y: number; tx: number; ty: number; moved: boolean } | null>(null);

    // Base (s = 1) page size: fit the page inside the viewport with padding.
    const base = (() => {
      if (!natural) return { w: Math.max(100, vp.w - PAD * 2), h: Math.max(100, (vp.w - PAD * 2) * 1.3) };
      const fitW = vp.w - PAD * 2;
      const fitH = vp.h - PAD * 2;
      const r = natural.h / natural.w;
      const w = Math.max(100, Math.min(fitW, fitH / r));
      return { w, h: w * r };
    })();

    const fit = useCallback((): View => {
      return { s: 1, tx: (vp.w - base.w) / 2, ty: Math.max(PAD / 2, (vp.h - base.h) / 2) };
    }, [vp.w, vp.h, base.w, base.h]);

    useEffect(() => {
      const el = vpRef.current;
      if (!el) return;
      const ro = new ResizeObserver(([entry]) => {
        if (!entry) return;
        setVp({ w: entry.contentRect.width, h: entry.contentRect.height });
      });
      ro.observe(el);
      return () => ro.disconnect();
    }, []);

    // Re-fit when the page or the viewport changes size.
    useEffect(() => {
      setView(fit());
    }, [fit]);

    useEffect(() => {
      const el = vpRef.current;
      if (!el || kind !== "image") return;
      const onWheel = (e: WheelEvent) => {
        e.preventDefault();
        const rect = el.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        setView((v) => {
          const s = Math.min(MAX_S, Math.max(MIN_S, v.s * Math.exp(-e.deltaY * 0.0015)));
          const k = s / v.s;
          return { s, tx: cx - (cx - v.tx) * k, ty: cy - (cy - v.ty) * k };
        });
      };
      el.addEventListener("wheel", onWheel, { passive: false });
      return () => el.removeEventListener("wheel", onWheel);
    }, [kind]);

    useImperativeHandle(
      ref,
      () => ({
        zoomTo: (b) => {
          const bw = Math.max(b.w * base.w, 8);
          const bh = Math.max(b.h * base.h, 8);
          const s = Math.min(4, Math.max(1.4, Math.min((vp.w * 0.45) / bw, (vp.h * 0.25) / bh)));
          const cx = (b.x + b.w / 2) * base.w;
          const cy = (b.y + b.h / 2) * base.h;
          setView({ s, tx: vp.w / 2 - cx * s, ty: vp.h / 2 - cy * s });
        },
        reset: () => setView(fit()),
      }),
      [base.w, base.h, vp.w, vp.h, fit],
    );

    function onPointerDown(e: RPointerEvent<HTMLDivElement>) {
      if (e.button !== 0) return;
      drag.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty, moved: false };
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    function onPointerMove(e: RPointerEvent<HTMLDivElement>) {
      const d = drag.current;
      if (!d) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true;
      setView((v) => ({ ...v, tx: d.tx + dx, ty: d.ty + dy }));
    }
    function onPointerUp(e: RPointerEvent<HTMLDivElement>) {
      drag.current = null;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
    }

    const zoomBy = (k: number) =>
      setView((v) => {
        const s = Math.min(MAX_S, Math.max(MIN_S, v.s * k));
        const cx = vp.w / 2;
        const cy = vp.h / 2;
        return { s, tx: cx - (cx - v.tx) * (s / v.s), ty: cy - (cy - v.ty) * (s / v.s) };
      });

    if (!src || failed) {
      return (
        <div className="ex-viewer" ref={vpRef}>
          <div className="ex-viewer-empty">
            <div className="section-label">Source unavailable</div>
            <p>The document image couldn&apos;t be loaded. Field values and confidences are still shown on the right.</p>
          </div>
        </div>
      );
    }

    if (kind === "pdf") {
      return (
        <div className="ex-viewer" ref={vpRef}>
          <iframe className="ex-viewer-pdf" src={`${src}#toolbar=0&view=FitH`} title={alt} />
        </div>
      );
    }

    return (
      <div
        className="ex-viewer"
        ref={vpRef}
        data-grab
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={() => setView(fit())}
      >
        <div
          className="ex-viewer-layer"
          role="img"
          aria-label={`${alt}. Scroll to zoom, drag to pan, double-click to fit.`}
          style={{ width: base.w, height: base.h, transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.s})` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- signed, short-lived Storage URL; next/image can't optimize it */}
          <img
            className="grayscale ex-viewer-img"
            src={src}
            alt=""
            draggable={false}
            onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth || 1, h: e.currentTarget.naturalHeight || 1 })}
            onError={() => setFailed(true)}
          />
          {boxes.map((b) => (
            <div
              key={`${b.key}-${b.tone}`}
              className={b.tone === "flag" ? "flag-region" : "ex-focus-region"}
              title={b.label}
              style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
            />
          ))}
        </div>
        <div className="ex-viewer-tools" onPointerDown={(e) => e.stopPropagation()}>
          <button type="button" className="btn-square" aria-label="Zoom in" onClick={() => zoomBy(1.25)}>
            <Plus size={14} strokeWidth={2} aria-hidden="true" />
          </button>
          <button type="button" className="btn-square" aria-label="Zoom out" onClick={() => zoomBy(0.8)}>
            <Minus size={14} strokeWidth={2} aria-hidden="true" />
          </button>
          <button type="button" className="btn-square" aria-label="Fit page" onClick={() => setView(fit())}>
            <Maximize2 size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  },
);
