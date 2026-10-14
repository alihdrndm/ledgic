import type { Metadata, Viewport } from "next";
import { redirect } from "next/navigation";
import { CaptureApp, type CaptureLocation } from "@/components/capture/CaptureApp";
import styles from "@/components/capture/capture.module.css";
import { createClient } from "@/lib/supabase/server";
import { canCapture, userOrgs } from "@/lib/auth/membership";
import { DEFAULT_ORG_SLUG } from "@/lib/auth/redirect";

export const metadata: Metadata = {
  title: "Capture",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Ledgic Capture", statusBarStyle: "black" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#201e1d" /* tokens-ignore: meta needs a literal */ };
export const dynamic = "force-dynamic";

export default async function CapturePage({
  searchParams,
}: {
  searchParams: Promise<{ org?: string; desktop?: string }>;
}) {
  const sp = await searchParams;
  const desktop = sp.desktop === "1";
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(desktop ? "/capture?desktop=1" : "/capture")}`);

  const orgs = await userOrgs(supabase, user.id);
  const wanted = (sp.org ?? DEFAULT_ORG_SLUG).toLowerCase();
  const org = orgs.find((o) => o.slug.toLowerCase() === wanted) ?? orgs[0];

  let locations: CaptureLocation[] = [];
  if (org) {
    const { data } = await supabase.from("locations").select("id, name, code").eq("org_id", org.id).order("name");
    locations = (data ?? []) as CaptureLocation[];
  }

  return (
    <div className={styles.page}>
      <header className={styles.bar}>
        <svg className={styles.barLogo} width="24" height="20" viewBox="0 0 24 20" aria-hidden="true">
          <rect x="0" y="1" width="15" height="3" fill="currentColor" />
          <rect x="0" y="8" width="24" height="3" fill="currentColor" />
          <rect x="0" y="15" width="19" height="3" fill="currentColor" />
        </svg>
        <span className={styles.barName}>Ledgic</span>
        <form className={styles.barRight} action="/auth/signout" method="post">
          <button type="submit" className={styles.barBtn}>
            Sign out
          </button>
        </form>
      </header>
      {org ? (
        <CaptureApp
          org={{ id: org.id, name: org.name, slug: org.slug }}
          locations={locations}
          canUpload={canCapture(user, org.role)}
          desktop={desktop}
        />
      ) : (
        <div className={styles.body}>
          <h1 className={styles.title}>No organisation</h1>
          <p className={styles.meta}>Your account isn&apos;t a member of any organisation yet. Ask an admin to invite you.</p>
        </div>
      )}
    </div>
  );
}
