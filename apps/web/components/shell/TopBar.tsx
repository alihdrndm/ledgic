"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Search } from "lucide-react";
import { DemoBadge } from "@/components/ui/Chip";
import { createClient } from "@/lib/supabase/client";
import { useOptionalShell } from "./ShellContext";
import { ROLE_LABEL } from "./roles";

export interface TopBarStatus {
  /** e.g. "running · last run 09:41:23" or "Pipeline paused — core unreachable" */
  text: ReactNode;
  /** Outline-only square (degraded). */
  degraded?: boolean;
}

export interface TopBarProps {
  /** Page title, 17px 800, e.g. "Pipeline". */
  title: string;
  /** Context text (12.5px neutral-700, ellipsis), e.g. "ap-invoice-pipeline". */
  context?: ReactNode;
  /** Running indicator after a 1px rule. */
  status?: TopBarStatus;
  /** Optional risk chip, e.g. <Chip variant="risk">Price variance</Chip>. */
  riskChip?: ReactNode;
  /** Hide the search trigger below 1440px (Match screen). Default false. */
  searchOptional?: boolean;
  /** Hide the search trigger entirely. */
  hideSearch?: boolean;
}

function useDismiss(open: boolean, close: () => void, ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close, ref]);
}

function OrgMenu() {
  const shell = useOptionalShell();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  useDismiss(open, () => setOpen(false), ref);
  if (!shell) return null;
  const { org, orgs } = shell;
  return (
    <div className="ledgic-menu-wrap" ref={ref}>
      <button
        type="button"
        className="ledgic-org"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
      >
        {org.name}
      </button>
      {open ? (
        <ul className="ledgic-menu" id={menuId} role="menu" aria-label="Switch organization">
          {orgs.map((o) => (
            <li key={o.slug} role="none">
              <Link
                role="menuitem"
                className="ledgic-menu-item"
                href={`/o/${o.slug}/pipeline`}
                aria-current={o.slug === org.slug ? "true" : undefined}
                onClick={() => setOpen(false)}
              >
                {o.name}
                <span className="meta" style={{ marginLeft: "auto" }}>
                  {ROLE_LABEL[o.role]}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function UserMenu() {
  const shell = useOptionalShell();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  useDismiss(open, () => setOpen(false), ref);
  if (!shell) return null;
  const { user, role } = shell;

  async function signOut() {
    setBusy(true);
    try {
      await createClient().auth.signOut();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="ledgic-menu-wrap" ref={ref}>
      <button
        type="button"
        className="ledgic-avatar"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`${user.fullName}, ${ROLE_LABEL[role]} — account menu`}
        onClick={() => setOpen((o) => !o)}
      >
        {user.initials}
      </button>
      {open ? (
        <ul className="ledgic-menu" id={menuId} role="menu" aria-label="Account">
          <li role="none" className="ledgic-menu-head">
            <div style={{ fontWeight: 600 }}>{user.fullName}</div>
            {user.email ? <div className="meta">{user.email}</div> : null}
            <div style={{ marginTop: 6 }}>
              <span className="ledgic-role">{ROLE_LABEL[role]}</span>
            </div>
          </li>
          <li role="none">
            <button type="button" role="menuitem" className="ledgic-menu-item" onClick={signOut} disabled={busy}>
              {busy ? "Signing out…" : "Sign out"}
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}

/** 56px top bar: title · context · status · risk chip · [search · Demo badge · org · avatar]. */
export function TopBar({ title, context, status, riskChip, searchOptional, hideSearch }: TopBarProps) {
  const shell = useOptionalShell();
  return (
    <header className="ledgic-topbar">
      <h1 className="ledgic-topbar-title">{title}</h1>
      {context ? <span className="ledgic-topbar-context">{context}</span> : null}
      {status ? (
        <span className="ledgic-topbar-status" role="status">
          <span className="ledgic-status-square" data-degraded={status.degraded || undefined} aria-hidden="true" />
          {status.text}
        </span>
      ) : null}
      {riskChip}
      <div className="ledgic-topbar-right">
        {!hideSearch ? (
          <button
            type="button"
            className="ledgic-search"
            data-optional={searchOptional || undefined}
            onClick={() => shell?.openPalette()}
            aria-label="Search invoices, vendors (Ctrl+K)"
            aria-keyshortcuts="Meta+K Control+K"
          >
            <Search size={16} strokeWidth={2} aria-hidden="true" />
            Search invoices, vendors
            <kbd aria-hidden="true">⌘K</kbd>
          </button>
        ) : null}
        {shell?.org.is_demo ? <DemoBadge /> : null}
        <OrgMenu />
        <UserMenu />
      </div>
    </header>
  );
}
