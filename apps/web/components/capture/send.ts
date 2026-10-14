import type { QueuedCapture } from "./queue";

export const MAX_EDGE = 1600;
export const MAX_BYTES = 10 * 1024 * 1024;

/** Downscale a photo to ≤1600px on the long edge and re-encode as JPEG (respects EXIF orientation). */
export async function downscaleToJpeg(file: Blob, maxEdge = MAX_EDGE, quality = 0.85): Promise<Blob> {
  let source: ImageBitmap | HTMLImageElement;
  let width: number;
  let height: number;
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    source = bmp;
    width = bmp.width;
    height = bmp.height;
  } catch {
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      source = img;
      width = img.naturalWidth;
      height = img.naturalHeight;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.drawImage(source, 0, 0, w, h);
  if ("close" in source) source.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("JPEG encoding failed"))), "image/jpeg", quality),
  );
}

export class SendError extends Error {
  constructor(
    message: string,
    /** True when a later retry may succeed (offline, 5xx, rate-limited). */
    public readonly retryable: boolean,
  ) {
    super(message);
  }
}

interface Envelope<T> {
  ok: boolean;
  data?: T;
  error?: { code: string; message: string; retryable?: boolean };
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new SendError("You're offline.", true);
  }
  const env = (await res.json().catch(() => null)) as Envelope<T> | null;
  if (!res.ok || !env?.ok || env.data === undefined) {
    throw new SendError(env?.error?.message ?? `Request failed (${res.status}).`, env?.error?.retryable ?? res.status >= 500);
  }
  return env.data;
}

export interface SendResult {
  redelivered: boolean;
  runNumber: number | null;
}

/** upload-url → PUT to storage → complete (core ingest). */
export async function sendCapture(item: QueuedCapture): Promise<SendResult> {
  const { upload_url, storage_path } = await postJson<{ upload_url: string; storage_path: string }>(
    "/api/capture/upload-url",
    { org_id: item.orgId, content_type: item.contentType, size: item.blob.size },
  );
  let put: Response;
  try {
    put = await fetch(upload_url, {
      method: "PUT",
      headers: { "content-type": item.contentType, "x-upsert": "false" },
      body: item.blob,
    });
  } catch {
    throw new SendError("You're offline.", true);
  }
  if (!put.ok) throw new SendError(`Upload failed (${put.status}).`, put.status >= 500);

  const data = await postJson<{ run_number: number | null; redelivered: boolean }>("/api/capture/complete", {
    org_id: item.orgId,
    storage_path,
    original_filename: item.filename,
    location_id: item.locationId,
    channel: item.channel,
  });
  return { redelivered: data.redelivered, runNumber: data.run_number };
}
