import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { cx } from "./cx";

export interface Column<T> {
  /** Stable key; also used to read `row[key]` when no `render` is given. */
  key: string;
  header: ReactNode;
  /** Right-align + tabular numerals (amounts, counts). */
  numeric?: boolean;
  /** Secondary text color (neutral-700), e.g. Time and Stage columns. */
  muted?: boolean;
  width?: number | string;
  render?: (row: T, index: number) => ReactNode;
  /** Accessible header text when `header` isn't plain text. */
  ariaLabel?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T, index: number) => string;
  /** Tinted risk row (accent-100 fill + 3px accent left rule). */
  isRiskRow?: (row: T) => boolean;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  /** Rendered in a <tfoot> row (heading font 800, 2px rule above). */
  footer?: ReactNode;
  caption?: string;
  stickyHeader?: boolean;
  density?: "compact" | "comfortable";
  empty?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

function cellValue<T>(row: T, col: Column<T>, i: number): ReactNode {
  if (col.render) return col.render(row, i);
  const v = (row as Record<string, unknown>)[col.key];
  return v === null || v === undefined ? "—" : (v as ReactNode);
}

/** Modernist table: 10px uppercase headers on a 2px rule, 1px row rules, numerics right-aligned. */
export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  isRiskRow,
  onRowClick,
  selectedKey,
  footer,
  caption,
  stickyHeader = true,
  density = "compact",
  empty,
  className,
  style,
}: DataTableProps<T>) {
  const clickable = Boolean(onRowClick);
  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (!onRowClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick(row);
    }
  };
  return (
    <div className={cx("ledgic-table-wrap", className)} style={style}>
      <table className="ledgic-table" data-sticky={stickyHeader || undefined} data-density={density}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cx(c.numeric && "is-num")}
                style={c.width !== undefined ? { width: c.width } : undefined}
                aria-label={c.ariaLabel}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && empty ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: 0, borderBottom: 0 }}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => {
              const key = getRowKey(row, i);
              const selected = selectedKey !== undefined && selectedKey !== null && key === selectedKey;
              return (
                <tr
                  key={key}
                  data-risk={isRiskRow?.(row) || undefined}
                  data-clickable={clickable || undefined}
                  aria-selected={clickable ? selected : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={clickable ? (e) => onKey(e, row) : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cx(c.numeric && "is-num", c.muted && "is-muted")}>
                      {cellValue(row, c, i)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
        {footer ? <tfoot>{footer}</tfoot> : null}
      </table>
    </div>
  );
}
