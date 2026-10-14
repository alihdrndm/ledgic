# 02 — Design system (Modernist) and app shell

The product uses the **Modernist** system: flat, architectural, Archivo only, a near-mono red on a light ground, visible grid, **zero corner radius**, strong 2px rules. Alignment and the strength of dividers do the organising. Labels are flush left, including inside buttons.

## 1. How to implement

1. Copy `design/modernist-styles.css` to `packages/ui/src/modernist.css` **verbatim**. It is the single source of tokens and base component classes. Import it once in `apps/web/app/layout.tsx`.
2. Add `packages/ui/src/ledgic.css` for the few app-specific classes listed in §7 (shell, stage column, attrition bar, verdict chip). Every value there must come from a token.
3. Build React components in `packages/ui` that **render the Modernist classes** (`.btn`, `.tag`, `.table`, `.input`, `.seg`, `.card`, `.dialog`, `.hr`, `.grayscale`) rather than re-implementing their styles.
4. Tailwind is **optional**. If used (v4), map its theme to the CSS variables only (`--color-*`, `--space-*`), disable its default palette, and set `borderRadius` to `0`. Do not introduce any color, radius, font or shadow not in the token sheet.
5. Font: Archivo 400/600/800 via `next/font/google` (subset latin, `display: swap`), exposed as the `--font-heading`/`--font-body` variables. Enable `font-variant-numeric: tabular-nums` on `body` — every number in the product is tabular.

## 2. Tokens (from `modernist-styles.css`)

### 2.1 Color
| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#f3f2f2` | Page ground; text on dark fills |
| `--color-surface` | `#eae9e9` | Inputs, cards, dialogs |
| `--color-text` | `#201e1d` | Ink: text, primary button fill, active rail item, bars |
| `--color-accent` | `#ec3013` | **Risk only** (see §3) — large numerals, bars, rules, outlines |
| `--color-divider` | `color-mix(in srgb, #201e1d 40%, transparent)` | All rules (1px minor, 2px major) |
| `--color-neutral-100` | `#f8f4f4` | Selected queue row fill |
| `--color-neutral-200` | `#eae7e7` | Group headers, disclosure bar, source-document pane ground, HEIC chip |
| `--color-neutral-300` | `#d7d3d3` | Bar tracks |
| `--color-neutral-400` | `#bab6b6` | Document borders, chart axis |
| `--color-neutral-500` | `#9b9797` | Chart marker line |
| `--color-neutral-600` | `#7d7979` | **Inactive rail icons only** (non-text UI, 3.85:1) |
| `--color-neutral-700` | `#605d5d` | All secondary/muted text (5.83:1) |
| `--color-neutral-800`/`900` | `#444141` / `#2d2b2b` | Reserved |
| `--color-accent-100` | `#fff2ef` | Tinted fill for risk rows, exception blocks |
| `--color-accent-300` | `#ffc4b8` | Reserved (tinted borders) |
| `--color-accent-600` | `#dd2b0f` | Hover of accent elements |
| `--color-accent-700` | `#ae1800` | **Solid risk chips** (with `--color-bg` label) and accent text at body size (6.41:1) |
| `--color-accent-800` | `#7c1405` | Accent text on `accent-100` tints |
| `--color-accent-900` | `#4d170e` | Body text inside accent-tinted blocks |

### 2.2 Spacing
`--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4` 16 · `--space-6` 24 · `--space-8` 32 px. The designs also use 6, 7, 9, 10, 11, 14, 18, 20, 22 px paddings inline; in code, express those as `calc()` of tokens or add them to `ledgic.css` as named spacings (`--pad-cell: 10px`, `--pad-row: 11px`, `--pad-panel: 20px`, `--pad-page: 24px`). Match the design values exactly.

### 2.3 Radius & shadow
All radii **0**. Shadows: `--shadow-sm`, `--shadow-md`, `--shadow-lg` (only `lg` is used, on floating surfaces: command palette, dialogs, toasts). App screens themselves are flat.

### 2.4 Type scale (Archivo)
| Role | Size / weight / tracking / case | Where |
|---|---|---|
| Page title | 17px / 800 | Top bar page name |
| Section label | 10.5px / 400 / 0.14em / UPPERCASE / `neutral-700` | "TODAY · VOLUME THROUGH THE PIPELINE", "RUN INSPECTOR" |
| Field label | 9.5–10px / 400 / 0.10–0.12em / UPPERCASE / `neutral-700` | Stat cells, extracted-field cells, table headers |
| Table header | 10px / 800 (heading font) / 0.10em / UPPERCASE / `neutral-700`, 2px bottom rule | All tables |
| Body | 12–12.5px / 400 | Rows, lists |
| Meta | 11–11.5px / 400 / `neutral-700` | Row sublines, footnotes |
| Status bar | 10.5px / 400 / 0.06em / UPPERCASE / `neutral-700` | Footer |
| KPI numeral S | 17px / 800 | Stage column counts, secondary metrics |
| KPI numeral M | 22px / 800 | Stat cells, attrition counts |
| KPI numeral L | 30px / 800 | "+$88.00" |
| KPI numeral XL | 46px / 800 / line-height 1 | Operations headline metrics |
| Recommendation title | 20px / 800 / lh 1.2 | Match decision rail |
| Detail title | 18px / 800 | Exceptions detail heading |

## 3. Color semantics — the rule that matters most

**Red means exceptions and money at risk. Nothing else.**
- Brand chrome is ink on paper: the wordmark's middle bar is the only red in the brand mark (and only on the thumbnail/login; in-app rail logo is all ink).
- Primary actions are **ink-filled** (`--color-text` background, `--color-bg` label) — *not* accent. This intentionally overrides `.btn-primary`: create `.btn-ink` in `ledgic.css`:
  ```css
  .btn-ink{background:var(--color-text);color:var(--color-bg);font-family:var(--font-heading);font-weight:800}
  .btn-ink:hover{background:var(--color-neutral-800)}
  .btn-ink:active{background:var(--color-neutral-900)}
  ```
- Secondary actions: 1px `--color-text` border, transparent fill, 400 weight.
- Accent usage allowed: exception counts and their bars, tinted risk rows (`accent-100` fill + 3px `accent` left rule), solid risk chips (`accent-700` fill), risk numerals ≥ 22px in `accent`, risk text at body size in `accent-700`/`accent-800`, flagged regions on source documents (2px `accent` outline + 18% accent fill), focus rings (system default).
- Never: accent for navigation, active states, links in chrome, success, or decoration.

## 4. Components (React, in `packages/ui`)

Every component: zero radius, flush-left labels, themed hover/active/focus (`:focus-visible` 2px accent outline, offset 2px), disabled at 45% opacity.

| Component | Spec |
|---|---|
| `Button` | variants `ink` (primary), `outline` (1px ink border), `ghost`. Sizes: `md` (padding 11px 18px, 12.5–13px), `sm` (9px 14px, 11.5–12px). Label flush-left; optional trailing kbd hint. Loading: label replaced by "Working…" + 2px ink progress bar along the bottom edge (no spinners). |
| `Chip` | `risk` (accent-700 fill, bg label, 9.5–10px 800 0.08em UPPERCASE, padding 2–4px 8–9px), `riskOutline` (1px accent border, accent-800 label), `ink` (text fill, bg label), `outline` (1px ink 2px border for the demo badge), `neutral` (1px divider). |
| `DemoBadge` | Chip `outline` with **2px** `--color-text` border, 10px 800 0.10em UPPERCASE, padding 3px 8px, copy exactly `Demo · sample data`. Rendered only when `org.is_demo`. Only in the top bar. |
| `StatCell` | label (field-label style) + numeral M, padding 14px 24px, 1px right rule between cells. |
| `MetricCell` | label + numeral XL + meta line, padding 18px 24px. Accent variant for "Held back". |
| `DataTable` | Modernist `.table` with: header 2px rule; rows 1px rules; cell padding 7–12px 10px; numeric columns right-aligned; `riskRow` variant (accent-100 fill, 3px accent left border on first cell); row hover `color-mix(ink 4%)`. Sticky header when scrolling. |
| `KeyValueRow` | label left / value right (800) with 1px bottom rule, 10px vertical padding; `risk` variant fills `accent-100` edge-to-edge (negative margins equal to column padding). |
| `SectionHeader` | section-label text + optional right-aligned meta, 2px bottom rule, 7–8px bottom padding. |
| `Panel` | right-rail container: header row (section label, 14px 20px, 2px bottom rule), body, footer (2px top rule). |
| `RiskCallout` | 2px `accent` border, `accent-100` fill, 14–16px padding; title 13.5–14px 800 `accent-800`; body 12px `accent-900`; actions on the right. |
| `AttritionBars` | see §7. |
| `SparkLine` | SVG polyline 2px ink, dashed floor line (neutral-400, 3/4 dash), dashed version marker (neutral-500) with 3.5r ring point and 9.5px label. |
| `CommandPalette` | ⌘K / Ctrl+K. Dialog at `--shadow-lg`, 640px wide, input `.input`, results grouped (Invoices, Vendors, Exceptions) with 1px rules. |
| `Toast` | Bottom-right, ink fill, bg text, 12.5px, 4s; for decision confirmations ("Short-paid PS-88214 · $2,759.60 posted to QuickBooks"). |
| `Dialog` | Modernist `.dialog` for confirmations that move money (Approve as-is, Release hold): title, the exact amount, required comment for controller-only actions. |
| `EmptyState` | Section label + one sentence in `neutral-700`, flush left, inside the region it replaces. No illustrations. |
| `Skeleton` | 1px-ruled rows with `neutral-200` blocks where text would be; no shimmer (Modernist is static) — use a subtle 1.2s opacity pulse 1 → 0.6 only if load > 300ms. |

## 5. App shell (all authenticated screens)

Canvas reference: **1600 × 1000**. Shell = rail + main column.

### 5.1 Rail — 64px wide, full height, 2px right rule
- Top padding 14px. Logo: 24×20 SVG of three ink bars (widths 15/24/19, height 3, y = 1/8/15). No red in-app.
- Nav items start 22px below logo, 6px apart: 36×36 squares, icon 18px, stroke 2. **Active**: `--color-text` fill, `--color-bg` icon. **Inactive**: `--color-neutral-600` icon, hover `color-mix(ink 7%)` fill. Tooltip on hover (right side, ink fill, 11px).
- Order (designed): Pipeline, Extraction, Match, Exceptions, Operations. Below them, after a 1px rule with 10px margin: Invoices, Vendors, Settings (derived — same styling).
- Bottom: build/workflow version in 10px 800 0.1em `neutral-700`, `writing-mode: vertical-rl` (design shows `v14` = the n8n workflow version; bind to the deployed workflow version).
- Exceptions item shows a count badge when open exceptions > 0: 16px min-width, accent-700 fill, bg text 9.5px 800, top-right of the square.

### 5.2 Top bar — 56px high, 2px bottom rule, padding 0 24px, gap 18px
Left → right: page title (17px 800) · context text (12.5px `neutral-700`) · optional status (e.g., running indicator: 8×8 ink square + text, separated by a 1px left rule, 18px left padding) · optional risk chip · **right cluster** (margin-left auto, gap 14px): search field (1px divider border, 6px 12px, 12px `neutral-700`, "Search invoices, vendors" + `⌘K` kbd chip) · `DemoBadge` (demo orgs only) · org name (12.5px `neutral-700`; click = org switcher menu) · avatar (28×28 **square** ink fill, initials 11px 800 bg; click = menu: Profile, Sign out).

All text in the top bar is `white-space: nowrap`; truncate context text with ellipsis if space runs out.

### 5.3 Status bar — 34px high, 2px top rule, padding 0 24px, gap 22px
10.5px UPPERCASE 0.06em `neutral-700`. **Only real, live system status** — never marketing, never disclosures. Right-aligned item is the workflow version. Per screen:
- Pipeline: `Last run 09:41:23` · `214 runs today` · `Dead-letter queue 0` · right `v14`
- Extraction: `Autosaved 09:41:12` · `5 documents in queue` · right `v14`
- Match: `Payment on hold` (only when held) · `Matched in 0.4s` · right `v14`
- Exceptions: `14 open` · `2 payments blocked` · right `v14`
- Operations: `Refreshed 09:41:23` · `ERP in sync` (or `QuickBooks sync failing` in accent-700) · right `v14`

## 6. Icons (Lucide, `lucide-react`, size 18, strokeWidth 2)
| Use | Lucide name |
|---|---|
| Pipeline | `Workflow` |
| Extraction | `FileText` |
| Match | `ArrowRightLeft` |
| Exceptions | `TriangleAlert` |
| Operations | `ChartColumn` |
| Invoices | `Receipt` |
| Vendors | `Building2` |
| Settings | `Settings` |
| Search | `Search` (16) |
| Queue prev/next | `ChevronLeft` / `ChevronRight` in 30×30 1px-bordered squares |
| Received ✓ in tables | literal `✓` glyph (as designed) |

## 7. App-specific classes (`ledgic.css`)

- `.ledgic-rail`, `.ledgic-topbar`, `.ledgic-statusbar` — dimensions in §5.
- `.stage-col` — 5 equal columns (`grid-template-columns: repeat(5,1fr)`), 1px right rule except last, padding 16px 18px; header = section label + 2px bottom rule; rows = `KeyValueRow`; footnote pinned to bottom (`margin-top:auto`), 11px `neutral-700`.
- `.attrition` — 5 equal columns, gap 2px. Each column: numeral M above a **44px track**; bar height = `value / max × 100%` of the track, ink fill; the "routed to people" bar and numeral are accent. Labels below at 11px `neutral-700` (the last in `accent-700`). Numerals and bars bottom-aligned. Animate height changes 200ms ease-out; respect `prefers-reduced-motion`.
- `.flag-region` — for highlighting a region on a source document image: absolutely positioned by bbox, 2px accent outline, `rgba(236,48,19,.18)` fill.

## 8. Accessibility
- Contrast: all text ≥ 4.5:1 on its ground (the ramp steps in §2.1 are chosen for this); accent (#ec3013) text only at ≥ 22px bold.
- Every icon-only control has an `aria-label` and tooltip.
- Tables use real `<table>` semantics with `<th scope>`.
- Keyboard: full tab order; ⌘K palette; on Extraction review `Enter` = confirm, `E` = edit, `J`/`K` = next/previous document; on Exceptions `J`/`K` moves in the queue.
- Focus ring is the system's 2px accent outline — never removed.
- Live regions: pipeline counts update politely (`aria-live="polite"`, throttled to once per 10s).

## 9. Responsive behavior
The operator console is desktop-first. Minimum supported width **1280px**; design at 1600. Between 1280–1599: right rails shrink to 340px, stage columns tighten padding to 12px, tables truncate low-priority columns (Location, then Stage). Below 1280: show a single notice ("Ledgic is designed for screens 1280px and wider") except `/capture` and `/login`, which are mobile-first.
