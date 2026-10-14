import { randomUUID } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import { createAdminClient } from "@/lib/auth/admin";
import { isRateLimited } from "@/lib/auth/rate-limit";
import { ipFrom } from "@/lib/auth/request";
import {
  authorizeCapture,
  CAPTURE_TYPES,
  jsonError,
  MAX_UPLOAD_BYTES,
  readJson,
  type CaptureContentType,
} from "@/lib/auth/capture";

export const dynamic = "force-dynamic";

/**
 * POST { org_id, content_type: "image/jpeg" | "application/pdf", size }
 * → { ok, data: { upload_url, storage_path } } — a one-shot signed upload URL into the private
 * `documents` bucket under org/<org_id>/uploads/<uuid>.<ext>.
 */
export async function POST(request: NextRequest) {
  const body = await readJson(request);
  if (!body) return jsonError(400, "INVALID", "Expected a JSON body.");

  const contentType = body.content_type;
  if (typeof contentType !== "string" || !(contentType in CAPTURE_TYPES)) {
    return jsonError(422, "INVALID", "Send a JPEG photo or a PDF.");
  }
  const size = Number(body.size);
  if (!Number.isFinite(size) || size <= 0 || size > MAX_UPLOAD_BYTES) {
    return jsonError(422, "INVALID", "Files must be 10 MB or smaller.");
  }

  const auth = await authorizeCapture(body.org_id);
  if (!auth.ok) return auth.response;
  const orgId = body.org_id as string;

  const ip = ipFrom(request.headers);
  if (await isRateLimited({ key: `capture:ip:${ip}`, limit: 10, windowSeconds: 86_400 })) {
    return jsonError(429, "RATE_LIMITED", "Upload limit reached for today (10 per network).", true);
  }

  const admin = createAdminClient();
  if (!admin) return jsonError(503, "UNAVAILABLE", "Uploads aren't configured on this deployment.", true);

  const ext = CAPTURE_TYPES[contentType as CaptureContentType];
  const storagePath = `org/${orgId}/uploads/${randomUUID()}.${ext}`;
  const { data, error } = await admin.storage.from("documents").createSignedUploadUrl(storagePath);
  if (error || !data) {
    console.warn("[capture] createSignedUploadUrl failed:", error?.message);
    return jsonError(503, "UNAVAILABLE", "Storage is unavailable. Try again shortly.", true);
  }

  return NextResponse.json({ ok: true, data: { upload_url: data.signedUrl, storage_path: data.path ?? storagePath } });
}
