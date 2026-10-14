import { Screen } from "@/components/shell";
import { Panel, Skeleton } from "@/components/ui";
import styles from "@/components/pipeline/pipeline.module.css";

const STAGES = ["01 Intake", "02 Extraction", "03 Enrichment", "04 Three-way match", "05 Approve + post"];

/** Skeleton in the real Pipeline layout: ledger, stage grid, recent runs, inspector. */
export default function PipelineLoading() {
  return (
    <Screen title="Pipeline" context="ap-invoice-pipeline">
      <section className={styles.ledger}>
        <div className={styles.ledgerHead}>
          <h2 className="section-label">Today · volume through the pipeline</h2>
        </div>
        <div className={styles.ledgerBars}>
          <Skeleton rows={2} columns={[1, 1, 1, 1, 1]} label="Loading pipeline volume" />
        </div>
      </section>
      <div className={styles.body}>
        <div className={styles.left}>
          <div className="stage-grid">
            {STAGES.map((s) => (
              <section key={s} className="stage-col">
                <h3 className="section-label stage-col-head" style={{ margin: 0 }}>
                  {s}
                </h3>
                <Skeleton rows={4} columns={[3, 1]} label={`Loading ${s}`} />
              </section>
            ))}
          </div>
          <section className={styles.runs}>
            <div className={styles.runsHead}>
              <h2 className="section-label">Recent runs</h2>
            </div>
            <Skeleton rows={9} columns={[1, 2, 1.4, 1.4, 1, 1, 1.4]} label="Loading recent runs" />
          </section>
        </div>
        <Panel label="Run inspector" className={styles.inspector} style={{ flex: "none", borderLeft: "var(--rule-major)" }}>
          <div style={{ padding: "4px 20px" }}>
            <Skeleton rows={6} columns={[1, 4]} label="Loading run" />
          </div>
        </Panel>
      </div>
    </Screen>
  );
}
