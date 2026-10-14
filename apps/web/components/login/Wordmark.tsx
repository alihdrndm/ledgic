import styles from "./login.module.css";

/**
 * The Ledgic wordmark: three bars + "Ledgic". The red middle bar appears only here
 * (login) and on the thumbnail — the in-app rail logo is all ink (02-design-system §3).
 * `tone="inverse"` draws the outer bars and text in the ground color, for ink panels.
 */
export function Wordmark({ size = 58, tone = "inverse" }: { size?: number; tone?: "inverse" | "ink" }) {
  const barH = Math.round(size * 0.66);
  const barW = Math.round((barH * 78) / 58);
  const outer = tone === "inverse" ? "var(--color-bg)" : "var(--color-text)";
  return (
    <span className={styles.wordmark} style={{ fontSize: size, color: outer }} role="img" aria-label="Ledgic">
      <svg width={barW} height={barH} viewBox="0 0 78 58" aria-hidden="true" focusable="false">
        <rect x="0" y="0" width="48" height="10" style={{ fill: outer }} />
        <rect x="0" y="24" width="78" height="10" style={{ fill: "var(--color-accent)" }} />
        <rect x="0" y="48" width="62" height="10" style={{ fill: outer }} />
      </svg>
      <span aria-hidden="true">Ledgic</span>
    </span>
  );
}
