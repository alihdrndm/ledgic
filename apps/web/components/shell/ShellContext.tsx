"use client";

import { createContext, useContext } from "react";
import type { PaletteAskAction } from "@/components/ui/CommandPalette";
import type { MemberRole } from "./roles";

export interface ShellOrg {
  id: string;
  slug: string;
  name: string;
  is_demo: boolean;
  timezone: string;
}

export interface ShellUser {
  id: string;
  email?: string | null;
  fullName: string;
  initials: string;
}

export interface ShellValue {
  org: ShellOrg;
  user: ShellUser;
  role: MemberRole;
  orgs: { slug: string; name: string; role: MemberRole }[];
  version: string;
  openPalette: () => void;
  /** Register the palette's "Ask Ledgic" row (copilot). Pass null to remove. */
  setAskAction: (action: PaletteAskAction | null) => void;
}

export const ShellContext = createContext<ShellValue | null>(null);

/** Org, user, role and shell controls for any client component under AppShell. */
export function useShell(): ShellValue {
  const v = useContext(ShellContext);
  if (!v) throw new Error("useShell must be used inside <AppShell>.");
  return v;
}

/** Same as useShell but returns null outside the shell (e.g. the /_system gallery). */
export function useOptionalShell(): ShellValue | null {
  return useContext(ShellContext);
}
