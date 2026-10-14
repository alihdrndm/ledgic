import { pct } from "@/lib/format";

export interface SparkPoint {
  /** e.g. "wk 1" */
  label: string;
  /** Ratio 0..1 (0.964 = 96.4%). */
  value: number;
}

export interface SparkMarker {
  /** Index into `points` where the marker sits. */
  index: number;
  /** e.g. "prompt p-38 shipped" */
  label: string;
}

export interface SparkLineProps {
  points: SparkPoint[];
  /** Dashed floor line, ratio (0.95). */
  floor?: number;
  floorLabel?: string;
  markers?: SparkMarker[];
  width?: number;
  height?: number;
  /** Accessible description; defaults to a first/last summary. */
  label?: string;
  /** Show "wk 1 · x%" / "wk 12 · y%" under the chart (default true). */
  showEnds?: boolean;
}

const PAD_L = 8;
const PAD_R = 8;
const TOP = 16;
const BASE = 120;

/** 352×140 line: 2px ink polyline, dashed neutral-400 floor, dashed neutral-500 version markers with ring points. */
export function SparkLine({
  points,
  floor,
  floorLabel,
  markers = [],
  width = 352,
  height = 140,
  label,
  showEnds = true,
}: SparkLineProps) {
  const values = points.map((p) => p.value);
  const lo0 = Math.min(...values, floor ?? Infinity);
  const hi0 = Math.max(...values, floor ?? -Infinity);
  const span = hi0 - lo0 || 0.01;
  const lo = lo0 - span * 0.35;
  const hi = hi0 + span * 0.25;
  const n = points.length;
  const x = (i: number) => (n <= 1 ? width / 2 : PAD_L + (i * (width - PAD_L - PAD_R)) / (n - 1));
  const y = (v: number) => BASE - ((v - lo) / (hi - lo)) * (BASE - TOP);
  const poly = points.map((p, i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const first = points[0];
  const last = points[n - 1];
  const summary =
    label ?? (first && last ? `${first.label} ${pct(first.value)} to ${last.label} ${pct(last.value)}` : "No data");

  return (
    <figure style={{ margin: 0 }}>
      <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
        <line x1={0} y1={BASE} x2={width} y2={BASE} stroke="var(--color-neutral-400)" strokeWidth={1} />
        {floor !== undefined ? (
          <>
            <line x1={0} y1={y(floor)} x2={width} y2={y(floor)} stroke="var(--color-neutral-400)" strokeWidth={1} strokeDasharray="3 4" />
            <text x={0} y={y(floor) - 6} fill="var(--color-neutral-700)">
              {floorLabel ?? `${pct(floor)} floor`}
            </text>
          </>
        ) : null}
        {markers.map((m) => {
          const p = points[m.index];
          if (!p) return null;
          const mx = x(m.index);
          return (
            <g key={`${m.index}-${m.label}`}>
              <line x1={mx} y1={TOP} x2={mx} y2={BASE} stroke="var(--color-neutral-500)" strokeWidth={1} strokeDasharray="3 4" />
              <text x={mx + 6} y={14} fill="var(--color-text)" textAnchor={mx > width * 0.7 ? "end" : "start"} dx={mx > width * 0.7 ? -12 : 0}>
                {m.label}
              </text>
            </g>
          );
        })}
        {n > 0 ? <polyline points={poly} fill="none" stroke="var(--color-text)" strokeWidth={2} /> : null}
        {markers.map((m) => {
          const p = points[m.index];
          return p ? (
            <circle key={`c-${m.index}`} cx={x(m.index)} cy={y(p.value)} r={3.5} fill="var(--color-bg)" stroke="var(--color-text)" strokeWidth={2} />
          ) : null;
        })}
      </svg>
      {showEnds && first && last ? (
        <figcaption className="sparkline-foot" style={{ width }}>
          <span>
            {first.label} · {pct(first.value)}
          </span>
          <span>
            {last.label} · {pct(last.value)}
          </span>
        </figcaption>
      ) : null}
    </figure>
  );
}
