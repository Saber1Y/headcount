import type { ReactNode } from "react";
import styles from "./Figures.module.css";

export type Figure = { label: string; value: string; note?: ReactNode; tone?: "scripted" | "real" };

/** A row of headline figures, each a label, a large number and an optional note. */
export function Figures({ items }: { items: Figure[] }) {
  return (
    <dl className={styles.figures}>
      {items.map((f) => (
        <div key={f.label} className={styles.figure}>
          <dt>{f.label}</dt>
          <dd className={`${styles.value} ${f.tone ? styles[f.tone] : ""}`}>{f.value}</dd>
          {f.note ? <dd className={styles.note}>{f.note}</dd> : null}
        </div>
      ))}
    </dl>
  );
}
