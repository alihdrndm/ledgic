import { NextResponse, type NextRequest } from "next/server";
import { getSessionContext } from "@/lib/supabase/session";
import { searchOrg } from "@/lib/queries/search";

export const dynamic = "force-dynamic";

/**
 * GET /api/search?org=<slug>&q=<text> → PaletteGroup[] for the ⌘K palette.
 * Runs as the signed-in user (RLS); 401 when signed out, 404 when not a member of the org.
 */
export async function GET(req: NextRequest) {
  const org = req.nextUrl.searchParams.get("org") ?? "";
  const q = req.nextUrl.searchParams.get("q") ?? "";
  if (!org) return NextResponse.json({ error: "org is required" }, { status: 400 });
  const session = await getSessionContext(org);
  if (session.status === "unauthenticated") return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  if (session.status === "forbidden") return NextResponse.json({ error: "Not found" }, { status: 404 });
  try {
    const groups = await searchOrg(session.context.org.id, session.context.org.slug, q);
    return NextResponse.json({ groups }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Search is unavailable right now." }, { status: 503 });
  }
}
