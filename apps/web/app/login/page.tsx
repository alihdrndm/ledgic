import type { Metadata } from "next";
import { LoginScreen } from "@/components/login/LoginScreen";
import { createClient } from "@/lib/supabase/server";
import { safeNext } from "@/lib/auth/redirect";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

const ERRORS: Record<string, string> = {
  link: "That sign-in link is invalid or has expired. Request a new one.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[]; error?: string | string[] }>;
}) {
  const sp = await searchParams;
  const next = safeNext(Array.isArray(sp.next) ? sp.next[0] : sp.next);
  const errorKey = Array.isArray(sp.error) ? sp.error[0] : sp.error;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <LoginScreen
      next={next}
      error={errorKey ? (ERRORS[errorKey] ?? null) : null}
      signedInAs={user?.email ?? null}
      repoUrl={process.env.NEXT_PUBLIC_REPO_URL ?? "https://github.com/alihdrndm/ledgic"}
    />
  );
}
