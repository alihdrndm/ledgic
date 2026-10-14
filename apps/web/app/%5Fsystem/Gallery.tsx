"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  AttritionBars,
  Button,
  Chip,
  CommandPalette,
  DataTable,
  DemoBadge,
  Dialog,
  EmptyState,
  KeyValueRow,
  MetricCell,
  Panel,
  RiskCallout,
  SectionHeader,
  Skeleton,
  SparkLine,
  StatCell,
  StatRow,
  ToastProvider,
  Tooltip,
  useToast,
  type Column,
  type PaletteGroup,
  type PaletteSearch,
} from "@/components/ui";
import { AppShell, Screen, StatusBar, needsRole } from "@/components/shell";
import { money, pct, time, age, count, conf, duration } from "@/lib/format";

interface Run {
  time: string;
  vendor: string;
  invoice: string;
  location: string;
  amount: string;
  stage: string;
  status: string;
  risk?: boolean;
}

const RUNS: Run[] = [
  { time: "09:41:23", vendor: "Broadline Distributor", invoice: "BD-104882", location: "Bayside", amount: "1982.47", stage: "Posted", status: "Touchless" },
  { time: "09:40:58", vendor: "Janitorial Services", invoice: "JS-3310", location: "Riverside", amount: "742.00", stage: "Posted", status: "Touchless" },
  { time: "09:40:12", vendor: "Protein Supplier", invoice: "PS-88214", location: "Riverside", amount: "2847.60", stage: "Match", status: "Price variance", risk: true },
  { time: "09:38:51", vendor: "Produce Supplier", invoice: "PR-2214", location: "Riverside", amount: "491.60", stage: "Extraction", status: "Below gate", risk: true },
];

const COLUMNS: Column<Run>[] = [
  { key: "time", header: "Time", muted: true },
  { key: "vendor", header: "Vendor" },
  { key: "invoice", header: "Invoice" },
  { key: "location", header: "Location" },
  { key: "amount", header: "Amount", numeric: true, render: (r) => money(r.amount) },
  { key: "stage", header: "Stage", muted: true },
  {
    key: "status",
    header: "Status",
    render: (r) => (r.risk ? <span className="risk-text-strong">{r.status}</span> : r.status),
  },
];

const SAMPLE: PaletteGroup[] = [
  {
    label: "Invoices",
    items: [
      { id: "1", title: "PS-88214", meta: "Protein Supplier · $2,847.60", href: "#" },
      { id: "2", title: "PR-2214", meta: "Produce Supplier · $491.60", href: "#" },
    ],
  },
  { label: "Vendors", items: [{ id: "3", title: "Protein Supplier", meta: "Seafood", href: "#" }] },
  { label: "Exceptions", items: [{ id: "4", title: "shrimp 12% over contract", meta: "price variance · $88.00", href: "#" }] },
];

const sampleSearch: PaletteSearch = async (q) => {
  const needle = q.toLowerCase();
  return SAMPLE.map((g) => ({
    ...g,
    items: g.items.filter((i) => !needle || `${i.title} ${i.meta}`.toLowerCase().includes(needle)),
  }));
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="system-section">
      <SectionHeader label={title} />
      {children}
    </section>
  );
}

function ToastDemo() {
  const { toast } = useToast();
  return (
    <Button variant="outline" size="sm" onClick={() => toast("Short-paid PS-88214 · $2,759.60 posted to QuickBooks")}>
      Show toast
    </Button>
  );
}

export function Gallery() {
  const [loading, setLoading] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [palette, setPalette] = useState(false);
  const [received, setReceived] = useState(214);
  // Fixed instant so server and client render identical text (no hydration mismatch).
  const now = new Date("2026-07-13T13:41:23Z");

  return (
    <ToastProvider>
      <div className="system-page">
        <div>
          <h1 style={{ fontSize: 28 }}>Ledgic design system</h1>
          <p className="meta">Dev-only gallery of every component in components/ui and components/shell. Not available in production.</p>
        </div>

        <Section title="Buttons">
          <div className="system-row">
            <Button variant="ink">Short-pay $2,759.60 and notify vendor</Button>
            <Button variant="outline">Approve as-is</Button>
            <Button variant="ghost">View full trail</Button>
            <Button variant="ink" size="sm" kbd="↵">
              Confirm 4 × $31.25
            </Button>
            <Button variant="outline" size="sm" kbd="E">
              Edit value
            </Button>
            <Button
              variant="ink"
              loading={loading}
              onClick={() => {
                setLoading(true);
                setTimeout(() => setLoading(false), 1800);
              }}
            >
              Click to load
            </Button>
            <Button variant="outline" disabledReason={needsRole("ap_manager", "controller")}>
              Release hold
            </Button>
            <Button variant="outline" disabledReason={needsRole("viewer", "ap_manager")}>
              Dispute
            </Button>
            <Tooltip content="Previous document">
              <button type="button" className="btn-square" aria-label="Previous document">
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
            </Tooltip>
          </div>
        </Section>

        <Section title="Chips">
          <div className="system-row">
            <Chip variant="ink">Touchless</Chip>
            <Chip variant="neutral">16s end to end</Chip>
            <Chip variant="outline">Computed</Chip>
            <Chip variant="risk">Price variance</Chip>
            <Chip variant="risk" size="sm">
              Held
            </Chip>
            <Chip variant="risk-outline">Qty unclear</Chip>
            <DemoBadge />
          </div>
        </Section>

        <Section title="Attrition bars">
          <div style={{ padding: "18px 24px 20px", border: "var(--rule-major)" }}>
            <SectionHeader
              label="Today · volume through the pipeline"
              meta="durable agent orchestrator + LLM extraction · retries and dead-letter on every stage"
              rule={false}
            />
            <div style={{ marginTop: 14 }}>
              <AttritionBars
                items={[
                  { label: "received", value: received },
                  { label: "extracted above gate", value: 209 },
                  { label: "enriched, PO linked", value: 198 },
                  { label: "matched clean → ERP", value: 152 },
                  { label: "routed to people", value: 41, risk: true },
                ]}
              />
            </div>
          </div>
          <div className="system-row">
            <Button size="sm" variant="outline" onClick={() => setReceived((r) => (r === 214 ? 260 : 214))}>
              Change max (animates)
            </Button>
          </div>
        </Section>

        <Section title="Stat cells and metric cells">
          <div style={{ border: "var(--rule-major)" }}>
            <StatRow>
              <StatCell label="Field accuracy, sampled" value="96.4%" />
              <StatCell label="Auto-passed today" value="209 / 214" />
              <StatCell label="Median extraction" value={duration(11.8, { precise: true })} />
              <StatCell
                label="Queue position"
                value="3 of 5"
                aside={
                  <span style={{ display: "flex", gap: 6 }}>
                    <button type="button" className="btn-square" aria-label="Previous document">
                      <ChevronLeft size={16} aria-hidden="true" />
                    </button>
                    <button type="button" className="btn-square" aria-label="Next document">
                      <ChevronRight size={16} aria-hidden="true" />
                    </button>
                  </span>
                }
              />
            </StatRow>
            <StatRow>
              <MetricCell
                label="Cost per invoice"
                value="$3.10"
                meta="Industry benchmark for manual: $12–30"
                info={<>(LLM + infra + human minutes × loaded rate) ÷ invoices posted. Loaded rate assumption: $35.00/h.</>}
              />
              <MetricCell label="Touchless rate" value="71%" meta="Up from 54% at dataset start" />
              <MetricCell label="Median cycle" value="24h" meta="Receipt to posted" />
              <MetricCell label="Held back this quarter" value="$6,084" meta="$4,860 variances · $1,224 duplicates" risk />
            </StatRow>
          </div>
        </Section>

        <Section title="Stage column + key/value rows">
          <div className="stage-grid" style={{ border: "var(--rule-major)", gridTemplateColumns: "repeat(2, 280px)" }}>
            <div className="stage-col">
              <div className="section-label stage-col-head">02 Extraction</div>
              <KeyValueRow label="Auto-passed" value="209" />
              <KeyValueRow label="Below gate → review" value="5" risk />
              <KeyValueRow label="Median time" value="11.8s" />
              <div className="stage-col-note">
                Confidence gate at <strong style={{ color: "var(--color-text)" }}>0.90</strong>. Every field carries a score; anything
                under the gate goes to a person before it moves.
              </div>
              <div className="stage-col-foot">model extraction-v14 · prompt p-38</div>
            </div>
            <div className="stage-col">
              <div className="section-label stage-col-head">05 Approve + post</div>
              <KeyValueRow label="Awaiting a person" value="41" risk />
              <KeyValueRow label="Posted · QuickBooks" value="104" />
              <KeyValueRow label="Slack digest" value="09:30 sent" plainValue />
              <div className="stage-col-foot">Nothing posts without entity + location + GL coding attached.</div>
            </div>
          </div>
        </Section>

        <Section title="Data table">
          <DataTable
            columns={COLUMNS}
            rows={RUNS}
            getRowKey={(r) => r.invoice}
            selectedKey="BD-104882"
            onRowClick={() => undefined}
            caption="Recent runs"
          />
          <DataTable
            columns={COLUMNS}
            rows={RUNS.slice(2)}
            getRowKey={(r) => r.invoice}
            isRiskRow={(r) => Boolean(r.risk)}
            density="comfortable"
            caption="Risk rows"
            footer={
              <tr>
                <td colSpan={4}>Totals</td>
                <td className="is-num">{money("3339.20")}</td>
                <td colSpan={2} className="risk-text-strong">
                  Δ {money(88)}
                </td>
              </tr>
            }
          />
        </Section>

        <Section title="Panel">
          <div style={{ display: "flex", border: "var(--rule-major)", height: 300 }}>
            <div style={{ flex: 1 }} />
            <Panel
              label="Run inspector"
              meta="run 88,412"
              width={392}
              footer="No person opened this invoice. The 41 that needed one are in the exception queue."
            >
              <div style={{ padding: "16px 20px" }}>
                <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 16 }}>Broadline Distributor</div>
                <div className="meta">BD-104882 · $1,982.47 · Bayside</div>
                <div className="system-row" style={{ marginTop: 10 }}>
                  <Chip variant="ink">Touchless</Chip>
                  <Chip variant="neutral">16s end to end</Chip>
                </div>
              </div>
            </Panel>
          </div>
        </Section>

        <Section title="Callouts">
          <RiskCallout
            title="One field needs confirmation — quantity, line 2"
            actions={
              <>
                <Button variant="ink" size="sm">
                  Confirm 4 × $31.25
                </Button>
                <Button variant="outline" size="sm">
                  Edit value
                </Button>
              </>
            }
          >
            Model read 4 at confidence 0.71. Cross-check: $125.00 ÷ $31.25 unit = 4.0, so the arithmetic agrees with the smudged digit.
          </RiskCallout>
          <RiskCallout tone="neutral" title="Couldn’t load recent runs" actions={<Button size="sm">Retry</Button>}>
            The database didn’t respond in time. Nothing was changed.
          </RiskCallout>
        </Section>

        <Section title="Sparkline">
          <SparkLine
            points={[0.959, 0.957, 0.961, 0.955, 0.958, 0.956, 0.962, 0.965, 0.963, 0.966, 0.964, 0.964].map((v, i) => ({
              label: `wk ${i + 1}`,
              value: v,
            }))}
            floor={0.95}
            markers={[{ index: 6, label: "prompt p-38 shipped" }]}
          />
        </Section>

        <Section title="Empty and loading">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <EmptyState title="Queue clear">Every document today passed the confidence gate.</EmptyState>
            <Skeleton rows={4} />
          </div>
        </Section>

        <Section title="Dialog, palette, toast">
          <div className="system-row">
            <Button variant="outline" onClick={() => setDialog(true)}>
              Open approval dialog
            </Button>
            <Button variant="outline" onClick={() => setPalette(true)}>
              Open command palette
            </Button>
            <ToastDemo />
          </div>
          <Dialog
            open={dialog}
            onClose={() => setDialog(false)}
            title="Approve PS-88214 as invoiced?"
            amount={money("2847.60")}
            confirmLabel="Approve and post"
            comment={{ required: true, label: "Reason for paying above contract" }}
            acknowledge="I verified the bank details with the vendor by phone"
            onConfirm={async () => {
              await new Promise((r) => setTimeout(r, 800));
            }}
          >
            This pays $88.00 above the contract price in clause 4.2.
          </Dialog>
          <CommandPalette
            open={palette}
            onOpenChange={setPalette}
            search={sampleSearch}
            askAction={{ onSelect: () => undefined }}
          />
        </Section>

        <Section title="Status bar">
          <div style={{ border: "var(--rule-major)" }}>
            <StatusBar items={["Last run 09:41:23", "214 runs today", "Dead-letter queue 0"]} version="v14" />
            <StatusBar items={["Refreshed 09:41:23", { text: "QuickBooks sync failing", risk: true }]} version="v14" degraded="core unreachable" />
          </div>
        </Section>

        <Section title="Format helpers">
          <ul className="meta" style={{ margin: 0, paddingLeft: 18 }}>
            <li>money(&quot;2759.6&quot;) → {money("2759.6")}</li>
            <li>money(88, signed) → {money(88, { signed: true })}</li>
            <li>money(6084, 0dp) → {money(6084, { decimals: 0 })}</li>
            <li>pct(0.12, signed) → {pct(0.12, { signed: true })}</li>
            <li>count(88412) → {count(88412)}</li>
            <li>conf(0.7) → {conf(0.7)}</li>
            <li>time(now, America/New_York) → {time(now, "America/New_York")}</li>
            <li>age(2h ago) → {age(new Date(now.getTime() - 2 * 3600_000), now)}</li>
          </ul>
        </Section>

        <Section title="App shell (1600 canvas, scaled to width)">
          <div className="system-frame system-shell">
            <AppShell
              org={{ id: "00000000-0000-0000-0000-000000000000", slug: "northside", name: "Northside Group", is_demo: true, timezone: "America/New_York" }}
              user={{ id: "u", email: "elena.marsh@demo.ledgic.dev", fullName: "Elena Marsh", initials: "EM" }}
              role="ap_manager"
              exceptionsCount={14}
              version="v14"
              search={sampleSearch}
            >
              <Screen
                title="Pipeline"
                context="ap-invoice-pipeline"
                status={{ text: "running · last run 09:41:23" }}
                statusItems={["Last run 09:41:23", "214 runs today", "Dead-letter queue 0"]}
              >
                <EmptyState title="No documents yet today">The first delivery usually lands around 06:00.</EmptyState>
              </Screen>
            </AppShell>
          </div>
        </Section>
      </div>
    </ToastProvider>
  );
}
