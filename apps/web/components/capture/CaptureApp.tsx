"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { captureQueue, type QueuedCapture } from "./queue";
import { downscaleToJpeg, MAX_BYTES, SendError, sendCapture } from "./send";
import styles from "./capture.module.css";

export interface CaptureLocation {
  id: string;
  name: string;
  code: string;
}

export interface CaptureAppProps {
  org: { id: string; name: string; slug: string };
  locations: CaptureLocation[];
  canUpload: boolean;
  desktop: boolean;
}

type Phase =
  | { kind: "idle" }
  | { kind: "preparing" }
  | { kind: "ready" }
  | { kind: "sending" }
  | { kind: "sent"; redelivered: boolean }
  | { kind: "queued" }
  | { kind: "error"; message: string };

interface Pending {
  blob: Blob;
  filename: string;
  contentType: "image/jpeg" | "application/pdf";
  channel: "photo" | "upload";
  previewUrl: string | null;
}

const SENT_COPY = "Sent · it will appear in the pipeline in about a minute.";

function locationKey(orgId: string) {
  return `ledgic.capture.location.${orgId}`;
}

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function CaptureApp({ org, locations, canUpload, desktop }: CaptureAppProps) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [locationId, setLocationId] = useState<string>("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [queued, setQueued] = useState(0);
  const flushing = useRef(false);

  // Remembered location (per org).
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(locationKey(org.id));
      // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is only readable after hydration
      if (saved && locations.some((l) => l.id === saved)) setLocationId(saved);
    } catch {
      /* storage blocked: start unselected */
    }
  }, [org.id, locations]);

  function chooseLocation(id: string) {
    setLocationId(id);
    try {
      window.localStorage.setItem(locationKey(org.id), id);
    } catch {
      /* ignore */
    }
  }

  // Preview URL lifecycle.
  useEffect(() => {
    const url = pending?.previewUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [pending?.previewUrl]);

  const refreshQueued = useCallback(async () => {
    try {
      const items = await captureQueue.all();
      setQueued(items.filter((i) => i.orgId === org.id).length);
    } catch {
      setQueued(0);
    }
  }, [org.id]);

  /** Retry everything in the offline queue (on load and whenever the device comes back online). */
  const flushQueue = useCallback(async () => {
    if (flushing.current || !canUpload) return;
    flushing.current = true;
    try {
      const items = (await captureQueue.all()).filter((i) => i.orgId === org.id).sort((a, b) => a.createdAt - b.createdAt);
      for (const item of items) {
        try {
          await sendCapture(item);
          await captureQueue.remove(item.id);
        } catch (err) {
          if (err instanceof SendError && err.retryable) break; // still offline / server busy: try later
          await captureQueue.remove(item.id); // permanent rejection: drop it
          setPhase({ kind: "error", message: `A queued upload was rejected: ${err instanceof Error ? err.message : "unknown error"}` });
        }
      }
    } catch {
      /* IndexedDB unavailable */
    } finally {
      flushing.current = false;
      await refreshQueued();
    }
  }, [canUpload, org.id, refreshQueued]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- flushQueue only sets state after an await
    void flushQueue();
    const onOnline = () => void flushQueue();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [flushQueue]);

  async function onPicked(file: File | undefined, fromCamera: boolean) {
    if (!file) return;
    if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
      if (file.size > MAX_BYTES) return setPhase({ kind: "error", message: "PDFs must be 10 MB or smaller." });
      setPending({ blob: file, filename: file.name, contentType: "application/pdf", channel: "upload", previewUrl: null });
      return setPhase({ kind: "ready" });
    }
    if (!file.type.startsWith("image/")) return setPhase({ kind: "error", message: "Choose a photo or a PDF." });
    setPhase({ kind: "preparing" });
    try {
      const jpeg = await downscaleToJpeg(file);
      const base = file.name.replace(/\.[^.]+$/, "") || "invoice";
      setPending({
        blob: jpeg,
        filename: `${base}.jpg`,
        contentType: "image/jpeg",
        channel: fromCamera || !desktop ? "photo" : "upload",
        previewUrl: URL.createObjectURL(jpeg),
      });
      setPhase({ kind: "ready" });
    } catch {
      setPhase({ kind: "error", message: "That image couldn't be read. Try another photo." });
    }
  }

  async function onSend() {
    if (!pending) return;
    const item: QueuedCapture = {
      id: newId(),
      orgId: org.id,
      locationId: locationId || null,
      blob: pending.blob,
      filename: pending.filename,
      contentType: pending.contentType,
      channel: pending.channel,
      createdAt: Date.now(),
    };
    setPhase({ kind: "sending" });
    const queueIt = async () => {
      try {
        await captureQueue.add(item);
        setPending(null);
        setPhase({ kind: "queued" });
        await refreshQueued();
      } catch {
        setPhase({ kind: "error", message: "You're offline and this browser can't store the photo. Try again when connected." });
      }
    };
    if (typeof navigator !== "undefined" && navigator.onLine === false) return queueIt();
    try {
      const res = await sendCapture(item);
      setPending(null);
      setPhase({ kind: "sent", redelivered: res.redelivered });
    } catch (err) {
      if (err instanceof SendError && err.retryable && err.message === "You're offline.") return queueIt();
      setPhase({ kind: "error", message: err instanceof Error ? err.message : "Sending failed." });
    }
  }

  function reset() {
    setPending(null);
    setPhase({ kind: "idle" });
  }

  const busy = phase.kind === "sending" || phase.kind === "preparing";
  const primaryLabel = desktop ? "Upload invoice" : "Take photo";

  return (
    <div className={`${styles.body} ${desktop ? styles.desktop : ""}`}>
      <h1 className={styles.title}>{desktop ? "Upload an invoice" : "Send an invoice"}</h1>
      <p className={styles.meta}>{org.name}</p>

      {!canUpload ? (
        <div className={styles.notice} role="note">
          <p className={styles.noticeTitle}>Read-only access</p>
          <p className={styles.noticeText}>
            The demo viewer can look around but can&apos;t send invoices. Sign in as Elena (AP manager) to try a real upload.
          </p>
          <a className={`btn btn-outline ${styles.tallLink}`} href="/login?next=%2Fcapture">
            Sign in as Elena
          </a>
        </div>
      ) : null}

      <div className={styles.field}>
        <label htmlFor="capture-location" className="field-label">
          Location
        </label>
        <select
          id="capture-location"
          className={`input ${styles.select}`}
          value={locationId}
          onChange={(e) => chooseLocation(e.target.value)}
          disabled={!canUpload}
        >
          <option value="">Choose a location</option>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>

      <input
        ref={cameraRef}
        className="sr-only"
        type="file"
        accept="image/*"
        capture="environment"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          void onPicked(e.target.files?.[0], true);
          e.target.value = "";
        }}
      />
      <input
        ref={fileRef}
        className="sr-only"
        type="file"
        accept="image/*,application/pdf"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          void onPicked(e.target.files?.[0], false);
          e.target.value = "";
        }}
      />

      {pending ? (
        <figure className={styles.preview}>
          {pending.previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img src={pending.previewUrl} alt="Preview of the invoice photo" className={styles.previewImg} />
          ) : (
            <div className={styles.pdf}>PDF</div>
          )}
          <figcaption className={styles.meta}>
            {pending.filename} · {formatSize(pending.blob.size)}
          </figcaption>
        </figure>
      ) : null}

      <div className={styles.actions}>
        {pending ? (
          <>
            <Button variant="ink" block className={styles.big} onClick={onSend} loading={phase.kind === "sending"} disabled={!canUpload}>
              Send
            </Button>
            <Button variant="outline" block className={styles.tall} onClick={() => (desktop ? fileRef : cameraRef).current?.click()} disabled={busy}>
              {desktop ? "Choose another file" : "Retake"}
            </Button>
            <Button variant="ghost" block className={styles.tall} onClick={reset} disabled={busy}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="ink"
              block
              className={styles.big}
              onClick={() => (desktop ? fileRef : cameraRef).current?.click()}
              disabled={!canUpload}
              loading={phase.kind === "preparing"}
            >
              {primaryLabel}
            </Button>
            {!desktop ? (
              <Button variant="outline" block className={styles.tall} onClick={() => fileRef.current?.click()} disabled={!canUpload}>
                Choose a photo or PDF
              </Button>
            ) : null}
          </>
        )}
      </div>

      <div className={styles.status} role="status" aria-live="polite">
        {phase.kind === "sent" ? (
          <p className={styles.ok}>
            {phase.redelivered ? "Already received · this document is already in the pipeline." : SENT_COPY}
          </p>
        ) : null}
        {phase.kind === "queued" ? <p className={styles.ok}>Saved offline · it will send when you&apos;re back online.</p> : null}
        {phase.kind === "error" ? <p className={styles.error}>{phase.message}</p> : null}
        {queued > 0 ? (
          <p className={styles.meta}>
            {queued} waiting to send ·{" "}
            <button type="button" className={styles.linkBtn} onClick={() => void flushQueue()}>
              Retry now
            </button>
          </p>
        ) : null}
      </div>

      <p className={styles.meta}>
        Photos are resized to 1600px before upload. {desktop ? "PDFs up to 10 MB." : null}{" "}
        <a className={styles.inkLink} href={desktop ? "/capture" : "/capture?desktop=1"}>
          {desktop ? "Phone camera view" : "Desktop upload"}
        </a>
      </p>
    </div>
  );
}
