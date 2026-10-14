"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { clientIp, siteOrigin } from "@/lib/auth/request";
import { isRateLimited } from "@/lib/auth/rate-limit";
import { demoCredentials, type DemoPersona } from "@/lib/auth/demo";
import { safeNext } from "@/lib/auth/redirect";

export interface LoginState {
  status: "idle" | "sent" | "error";
  message?: string;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Email magic link. Same response whether or not the address has an account (no enumeration). */
export async function sendSignInLink(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const next = safeNext(String(formData.get("next") ?? ""));
  if (!EMAIL.test(email) || email.length > 254) return { status: "error", message: "Enter a valid email address." };

  const ip = await clientIp();
  if (await isRateLimited({ key: `login:ip:${ip}`, limit: 5, windowSeconds: 3600 })) {
    return { status: "error", message: "Too many sign-in attempts. Try again in an hour." };
  }

  const supabase = await createClient();
  const origin = await siteOrigin();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      shouldCreateUser: false,
      emailRedirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}`,
    },
  });
  if (error && error.status === 429) {
    return { status: "error", message: "Too many sign-in emails. Try again in a few minutes." };
  }
  if (error) console.warn("[login] signInWithOtp:", error.status, error.message);
  return { status: "sent", message: `If ${email} has access, a sign-in link is on its way.` };
}

/**
 * Demo sign-in ("Open the demo" / "Try as Elena"): password grant done server-side with
 * credentials from server env, so no password ever reaches the browser.
 */
export async function openDemo(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const persona: DemoPersona = formData.get("persona") === "elena" ? "elena" : "viewer";
  const next = safeNext(String(formData.get("next") ?? ""));
  const creds = demoCredentials(persona);
  if (!creds) return { status: "error", message: "The demo isn't configured on this deployment." };

  const ip = await clientIp();
  if (await isRateLimited({ key: `demo:ip:${ip}`, limit: 30, windowSeconds: 3600 })) {
    return { status: "error", message: "Too many demo sign-ins from this network. Try again in an hour." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword(creds);
  if (error) {
    console.warn(`[login] demo sign-in (${persona}) failed:`, error.status, error.message);
    return { status: "error", message: "The demo is unavailable right now (it may be resetting). Try again shortly." };
  }
  redirect(next);
}
