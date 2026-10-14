"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import { CommandPalette, useCommandPaletteHotkey, type PaletteAskAction, type PaletteSearch } from "@/components/ui/CommandPalette";
import { ToastProvider } from "@/components/ui/Toast";
import { Rail } from "./Rail";
import { ShellContext, type ShellOrg, type ShellUser, type ShellValue } from "./ShellContext";
import { makeDefaultSearch } from "./defaultSearch";
import type { MemberRole } from "./roles";

export interface AppShellProps {
  org: ShellOrg;
  user: ShellUser;
  role: MemberRole;
  /** Orgs for the switcher (defaults to the current org only). */
  orgs?: { slug: string; name: string; role: MemberRole }[];
  /** Open exception count for the rail badge. */
  exceptionsCount?: number;
  /** Deployed workflow version label (rail + status bar), e.g. "v14". */
  version: string;
  /** Palette search; defaults to RLS-scoped invoices/vendors/exceptions lookup. Server actions work here. */
  search?: PaletteSearch;
  showVendors?: boolean;
  showSettings?: boolean;
  children: ReactNode;
}

/**
 * Authenticated chrome: 64px rail + main column (pages render <Screen> for top bar + status bar),
 * ⌘K palette and toasts. Below 1280px a notice replaces the console.
 */
export function AppShell({
  org,
  user,
  role,
  orgs,
  exceptionsCount = 0,
  version,
  search,
  showVendors = true,
  showSettings = true,
  children,
}: AppShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [askAction, setAskActionState] = useState<PaletteAskAction | null>(null);
  useCommandPaletteHotkey(setPaletteOpen);

  const defaultSearch = useMemo(() => makeDefaultSearch(org.id, org.slug), [org.id, org.slug]);
  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const setAskAction = useCallback((a: PaletteAskAction | null) => setAskActionState(() => a), []);

  const value: ShellValue = useMemo(
    () => ({
      org,
      user,
      role,
      orgs: orgs ?? [{ slug: org.slug, name: org.name, role }],
      version,
      openPalette,
      setAskAction,
    }),
    [org, user, role, orgs, version, openPalette, setAskAction],
  );

  return (
    <ShellContext.Provider value={value}>
      <ToastProvider>
        <a href="#main" className="sr-only">
          Skip to content
        </a>
        <div className="ledgic-app">
          <Rail
            orgSlug={org.slug}
            exceptionsCount={exceptionsCount}
            version={version}
            showVendors={showVendors}
            showSettings={showSettings}
          />
          <div className="ledgic-main">{children}</div>
        </div>
        <div className="ledgic-narrow-notice" role="note">
          <div className="section-label">Ledgic</div>
          <p>Ledgic is designed for screens 1280px and wider.</p>
          <p className="meta">Receiving staff can still send invoice photos from /capture on a phone.</p>
        </div>
        <CommandPalette
          open={paletteOpen}
          onOpenChange={setPaletteOpen}
          search={search ?? defaultSearch}
          askAction={askAction}
        />
      </ToastProvider>
    </ShellContext.Provider>
  );
}
