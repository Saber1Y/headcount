import type { Shares } from "@/lib/snapshots";
import { pct } from "@/lib/format";
import styles from "./ShareBar.module.css";

const SEGMENTS = [
  { key: "share_no_signals", label: "No signals", className: styles.real },
  { key: "share_possibly_scripted", label: "Possibly scripted", className: styles.mixed },
  { key: "share_likely_scripted", label: "Likely scripted", className: styles.scripted },
] as const;

/** Who an app's traffic comes from, as one bar: no signals, then possibly, then likely scripted. */
export function ShareBar({ shares, size = "sm" }: { shares: Shares; size?: "sm" | "lg" }) {
  const label = SEGMENTS.map((s) => `${s.label} ${pct(shares[s.key])}`).join(", ");
  return (
    <div className={`${styles.bar} ${size === "lg" ? styles.lg : ""}`} role="img" aria-label={label}>
      {SEGMENTS.map((s) =>
        shares[s.key] > 0 ? <span key={s.key} className={s.className} style={{ flexGrow: shares[s.key] }} /> : null,
      )}
    </div>
  );
}

export function ShareLegend({ shares }: { shares?: Shares }) {
  return (
    <ul className={styles.legend}>
      {SEGMENTS.map((s) => (
        <li key={s.key}>
          <span className={`${styles.swatch} ${s.className}`} aria-hidden="true" />
          {s.label}
          {shares ? <span className="mono"> {pct(shares[s.key])}</span> : null}
        </li>
      ))}
    </ul>
  );
}
