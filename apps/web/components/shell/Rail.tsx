"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowRightLeft,
  Building2,
  ChartColumn,
  FileText,
  Receipt,
  Settings,
  TriangleAlert,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { Fragment } from "react";

export type RailKey =
  | "pipeline"
  | "extraction"
  | "match"
  | "exceptions"
  | "operations"
  | "invoices"
  | "vendors"
  | "settings";

interface RailItemDef {
  key: RailKey;
  label: string;
  icon: LucideIcon;
  /** Path segment under /o/[org]/ */
  segment: string;
  /** Extra segments that also activate this item. */
  alsoActive?: string[];
}

const PRIMARY: RailItemDef[] = [
  { key: "pipeline", label: "Pipeline", icon: Workflow, segment: "pipeline" },
  { key: "extraction", label: "Extraction review", icon: FileText, segment: "extraction" },
  { key: "match", label: "Three-way match", icon: ArrowRightLeft, segment: "match" },
  { key: "exceptions", label: "Exceptions", icon: TriangleAlert, segment: "exceptions" },
  { key: "operations", label: "Operations", icon: ChartColumn, segment: "operations" },
];

const SECONDARY: RailItemDef[] = [
  { key: "invoices", label: "Invoices", icon: Receipt, segment: "invoices" },
  { key: "vendors", label: "Vendors", icon: Building2, segment: "vendors" },
  { key: "settings", label: "Settings", icon: Settings, segment: "settings" },
];

export interface RailProps {
  orgSlug: string;
  /** Open exceptions; badge shown when > 0. */
  exceptionsCount?: number;
  /** Deployed workflow/orchestrator version, e.g. "v14". */
  version: string;
  /** Hide derived items whose screens aren't built yet. Default: all shown. */
  showVendors?: boolean;
  showSettings?: boolean;
  /** Where the Match item links when no invoice is in context (default: exceptions queue filtered to variances). */
  matchHref?: string;
}

/** Three ink bars 15/24/19 (no red in-app). */
export function LedgicMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={(size * 20) / 24} viewBox="0 0 24 20" aria-hidden="true" className="ledgic-rail-logo">
      <rect x="0" y="1" width="15" height="3" fill="currentColor" />
      <rect x="0" y="8" width="24" height="3" fill="currentColor" />
      <rect x="0" y="15" width="19" height="3" fill="currentColor" />
    </svg>
  );
}

export function Rail({ orgSlug, exceptionsCount = 0, version, showVendors = true, showSettings = true, matchHref }: RailProps) {
  const pathname = usePathname() ?? "";
  const base = `/o/${orgSlug}`;
  const current = pathname.startsWith(base) ? (pathname.slice(base.length).split("/")[1] ?? "") : "";
  const secondary = SECONDARY.filter(
    (i) => (i.key !== "vendors" || showVendors) && (i.key !== "settings" || showSettings),
  );

  const renderItem = (item: RailItemDef) => {
    const active = current === item.segment || Boolean(item.alsoActive?.includes(current));
    const Icon = item.icon;
    const href = item.key === "match" && matchHref ? matchHref : `${base}/${item.segment}`;
    const badge = item.key === "exceptions" && exceptionsCount > 0 ? exceptionsCount : null;
    const aria = badge ? `${item.label}, ${badge} open` : item.label;
    return (
      <li key={item.key}>
        <Link href={href} className="ledgic-rail-item" aria-current={active ? "page" : undefined} aria-label={aria}>
          <Icon size={18} strokeWidth={2} aria-hidden="true" />
          {badge ? (
            <span className="ledgic-rail-badge" aria-hidden="true">
              {badge > 99 ? "99+" : badge}
            </span>
          ) : null}
          <span className="ledgic-rail-tip" aria-hidden="true">
            {item.label}
          </span>
        </Link>
      </li>
    );
  };

  return (
    <nav className="ledgic-rail" aria-label="Primary">
      <Link href={`${base}/pipeline`} aria-label="Ledgic home" style={{ color: "var(--color-text)" }}>
        <LedgicMark />
      </Link>
      <ul className="ledgic-rail-nav">
        {PRIMARY.map(renderItem)}
        {secondary.length ? (
          <Fragment>
            <li className="ledgic-rail-rule" role="separator" aria-hidden="true" style={{ margin: "4px 0" }} />
            {secondary.map(renderItem)}
          </Fragment>
        ) : null}
      </ul>
      <div className="ledgic-rail-version" aria-label={`Version ${version}`}>
        {version}
      </div>
    </nav>
  );
}
