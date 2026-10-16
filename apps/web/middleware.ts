import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { contentSecurityPolicy, newNonce } from "@/lib/security/csp";

/** Routes that need a signed-in user; everything else is public (login, auth callbacks, health, assets). */
const PROTECTED = [/^\/o(\/|$)/, /^\/capture(\/|$)/];

/**
 * Supabase session refresh (official @supabase/ssr pattern for Next 15) + route protection + the per-request
 * CSP nonce. Server Components can't write cookies, so the refreshed tokens are written here.
 */
export async function middleware(request: NextRequest) {
  const nonce = newNonce();
  const csp = contentSecurityPolicy(nonce);
  // Rebuilt after every cookie refresh so the forwarded request carries both the new cookies and the nonce.
  const forward = () => {
    const headers = new Headers(request.headers);
    headers.set("x-nonce", nonce);
    headers.set("Content-Security-Policy", csp);
    return NextResponse.next({ request: { headers } });
  };
  const withCsp = (res: NextResponse) => {
    res.headers.set("Content-Security-Policy", csp);
    return res;
  };
  let response = forward();

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return withCsp(response);

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = forward();
        for (const { name, value, options } of cookiesToSet) response.cookies.set(name, value, options);
      },
    },
  });

  // Do not put code between createServerClient and getUser(): it must run to refresh the session.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, search } = request.nextUrl;
  if (!user && PROTECTED.some((re) => re.test(pathname))) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.search = "";
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    const redirect = NextResponse.redirect(loginUrl);
    // Carry over any cookie changes (e.g. a cleared, expired session).
    for (const c of response.cookies.getAll()) redirect.cookies.set(c);
    return withCsp(redirect);
  }

  return withCsp(response);
}

export const config = {
  matcher: [
    /*
     * Everything except static assets, image optimisation, the PWA manifest/icons and the
     * health probe (which must answer without touching auth).
     */
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|icons/|manifest.webmanifest|robots.txt|api/health|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?)$).*)",
  ],
};
