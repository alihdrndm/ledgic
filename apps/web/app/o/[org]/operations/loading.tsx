import { Screen } from "@/components/shell";
import { SectionHeader, Skeleton } from "@/components/ui";
import styles from "@/components/operations/operations.module.css";

const METRICS = ["Cost per invoice", "Touchless rate", "Median cycle", "Held back this quarter"];

/** Skeleton in the real Operations layout. */
export default function OperationsLoading() {
  return (
    <Screen title="Operations">
      <div className={styles.disclosure}>
        <Skeleton rows={1} columns={[1, 12]} label="Loading disclosure" />
      </div>
      <div className={styles.metrics}>
        {METRICS.map((m) => (
          <div key={m} className="metric-cell">
            <div className="field-label">{m}</div>
            <Skeleton rows={2} columns={[2, 1]} label={`Loading ${m}`} />
          </div>
        ))}
      </div>
      <div className={styles.grid}>
        <section className={styles.col}>
          <SectionHeader label="Largest catches this quarter" />
          <Skeleton rows={3} columns={[1, 5]} label="Loading catches" />
        </section>
        <section className={styles.col}>
          <SectionHeader label="By location" />
          <Skeleton rows={8} columns={[2, 6, 1, 1]} label="Loading locations" />
        </section>
        <section className={styles.col}>
          <SectionHeader label="Extraction accuracy · 12 weeks" />
          <Skeleton rows={5} columns={[1]} label="Loading accuracy" />
        </section>
      </div>
    </Screen>
  );
}
