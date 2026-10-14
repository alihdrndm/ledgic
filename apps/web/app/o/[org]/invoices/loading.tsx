import { Screen } from "@/components/shell";
import { Skeleton } from "@/components/ui";
import styles from "@/components/invoices/invoices.module.css";

/** Skeleton in the real Invoices layout: filter bar + table rows. */
export default function InvoicesLoading() {
  return (
    <Screen title="Invoices">
      <div className={styles.filterBar}>
        <Skeleton rows={1} columns={[3, 2, 2, 1, 1]} label="Loading filters" />
      </div>
      <div className={styles.list}>
        <Skeleton rows={14} columns={[1.2, 2, 1.4, 1.4, 0.6, 1, 1.4, 1.4]} label="Loading invoices" />
      </div>
    </Screen>
  );
}
