import { Screen } from "@/components/shell";
import { Skeleton } from "@/components/ui";
import styles from "@/components/invoices/invoices.module.css";

const CELLS = ["Invoice", "Purchase order", "Goods receipt", "Posted to"];

/** Skeleton in the real invoice-detail layout: header trio, tabs, table. */
export default function InvoiceLoading() {
  return (
    <Screen title="Invoice">
      <div className={styles.trio}>
        {CELLS.map((c) => (
          <div key={c} className={styles.trioCell}>
            <div className="field-label">{c}</div>
            <Skeleton rows={2} columns={[3, 1]} label={`Loading ${c}`} />
          </div>
        ))}
      </div>
      <div className={styles.tabs}>
        <Skeleton rows={1} columns={[1, 1, 1, 1, 6]} label="Loading tabs" />
      </div>
      <div className={styles.tabBody}>
        <Skeleton rows={8} columns={[3, 1.4, 1.4, 1, 2]} label="Loading lines" />
      </div>
    </Screen>
  );
}
