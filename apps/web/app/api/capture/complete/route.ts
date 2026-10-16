import { NextResponse, type NextRequest } from "next/server";
import { ipFrom } from "@/lib/auth/request";
import { authorizeCapture, jsonError, readJson, UUID } from "@/lib/auth/capture";

export const dynamic = "force-dynamic";

interface IngestData {
  document_id: string;
  run_id: string | null;
  run_number: number | null;
  redelivered: boolean;
}

/**
 * POST { org_id, storage_path, original_filename?, location_id?, channel? }
 * Hands an uploaded object to core: POST {CORE_URL}/v1/documents/ingest as the signed-in user
 * (core re-checks role ≥ ap_clerk). Falls back to HMAC only if core rejects the user token.
 */
export async function POST(request: NextRequest) {
  const body = await readJson(request);
  if (!body) return jsonError(400, "INVALID", "Expected a JSON body.");

  const auth = await authorizeCapture(body.org_id);
  if (!auth.ok) return auth.response;
  const orgId = body.org_id as string;

  const storagePath = body.storage_path;
  const pathRe = new RegExp(`^org/${orgId}/uploads/[0-9a-f-]{36}\\.(jpg|pdf)$`, "i");
  if (typeof storagePath !== "string" || !pathRe.test(storagePath)) {
    return jsonError(422, "INVALID", "storage_path is not an upload path for this organisation.");
  }

  let locationId: string | undefined;
  if (typeof body.location_id === "string" && body.location_id) {
    if (!UUID.test(body.location_id)) return jsonError(422, "INVALID", "location_id must be a uuid");
    const { data: loc } = await auth.supabase
      .from("locations")
      .select("id")
      .eq("id", body.location_id)
      .eq("org_id", orgId)
      .maybeSingle();
    if (!loc) return jsonError(422, "INVALID", "Unknown location.");
    locationId = body.location_id;
  }

  const originalFilename =
    typeof body.original_filename === "string" ? body.original_filename.slice(0, 200) : null;
  const channel = body.channel === "upload" ? "upload" : "photo";

  const coreUrl = process.env.CORE_URL?.replace(/\/+$/, "");
  if (!coreUrl) return jsonError(503, "UNAVAILABLE", "The pipeline isn't configured on this deployment.", true);

  const {
    data: { session },
  } = await auth.supabase.auth.getSession();

  const raw = JSON.stringify({
    org_id: orgId,
    channel,
    storage_path: storagePath,
    original_filename: originalFilename,
    source_meta: { ...(locationId ? { location_id: locationId } : {}), uploaded_by: auth.user.id, via: "capture" },
  });
  const baseHeaders: Record<string, string> = {
    "content-type": "application/json",
    "x-forwarded-for": ipFrom(request.headers),
  };

  async function callCore(headers: Record<string, string>) {
    return fetch(`${coreUrl}/v1/documents/ingest`, {
      method: "POST",
      headers: { ...baseHeaders, ...headers },
      body: raw,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  }

  let res: Response;
  try {
    res = session?.access_token
      ? await callCore({ authorization: `Bearer ${session.access_token}` })
      : new Response(null, { status: 401 });
    // No service-signed retry: core must see the user, so its role check and upload limit apply.
  } catch (err) {
    console.warn("[capture] core ingest unreachable:", err);
    return jsonError(503, "UNAVAILABLE", "The pipeline is unreachable. Your upload is saved; try again shortly.", true);
  }

  const envelope = (await res.json().catch(() => null)) as
    | { ok: true; data: IngestData }
    | { ok: false; error: { code: string; message: string; retryable?: boolean } }
    | null;
  if (!res.ok || !envelope || !envelope.ok) {
    const err = envelope && !envelope.ok ? envelope.error : null;
    return jsonError(
      res.ok ? 502 : res.status,
      err?.code ?? "INTERNAL",
      err?.message ?? "The pipeline rejected this document.",
      err?.retryable ?? res.status >= 500,
    );
  }
  return NextResponse.json({ ok: true, data: envelope.data }, { status: 201 });
}
