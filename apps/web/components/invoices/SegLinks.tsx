import Link from "next/link";
import styles from "./invoices.module.css";

export interface SegLink {
  key: string;
  label: string;
  href: string;
}

/** Segmented control as links (URL holds the state). Active option is ink-filled. */
export function SegLinks({ items, current, label }: { items: SegLink[]; current: string; label: string }) {
  return (
    <nav className={styles.seg} aria-label={label}>
      {items.map((i) => (
        <Link
          key={i.key}
          href={i.href}
          className={styles.segOpt}
          aria-current={i.key === current ? "page" : undefined}
          scroll={false}
          replace
        >
          {i.label}
        </Link>
      ))}
    </nav>
  );
}
