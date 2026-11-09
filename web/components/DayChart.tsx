"use client";

import { useState } from "react";
import type { Window } from "@/lib/snapshots";
import { int, utcDateTime, utcTime } from "@/lib/format";
import styles from "./DayChart.module.css";

const W = 960;
const H = 260;
const PAD = { top: 12, right: 8, bottom: 28, left: 44 };

/** Round tick values (steps of 1, 2 or 5 times a power of ten) covering 0..value in about four steps. */
function niceTicks(value: number): number[] {
  const rough = value / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough) ?? 10 * power;
  const top = Math.ceil(value / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
}

/** Sampled transactions per window: the busiest contract stacked under everything else. */
export function DayChart({ windows, contractLabel }: { windows: Window[]; contractLabel: string }) {
  const [active, setActive] = useState<number | null>(null);
  const ticks = niceTicks(Math.max(...windows.map((w) => w.top_contract + w.everything_else)));
  const max = ticks[ticks.length - 1];
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const step = innerW / windows.length;
  const barW = Math.min(step * 0.72, 18);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const hovered = active === null ? null : windows[active];

  return (
    <figure className={styles.figure}>
      <div className={styles.chart} onPointerLeave={() => setActive(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Sampled transactions in each of ${windows.length} windows over 24 hours`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className={styles.grid} />
              <text x={PAD.left - 8} y={y(t)} className={styles.tick} textAnchor="end" dominantBaseline="middle">
                {t >= 1000 ? `${t / 1000}k` : t}
              </text>
            </g>
          ))}
          {windows.map((w, i) => {
            const x = PAD.left + i * step + (step - barW) / 2;
            const dim = active !== null && active !== i;
            return (
              <g key={w.window} className={dim ? styles.dim : undefined}>
                <rect x={x} y={y(w.top_contract)} width={barW} height={innerH + PAD.top - y(w.top_contract)} className={styles.contract} rx={1} />
                <rect
                  x={x}
                  y={y(w.top_contract + w.everything_else)}
                  width={barW}
                  height={y(w.top_contract) - y(w.top_contract + w.everything_else) - 1}
                  className={styles.rest}
                  rx={1}
                />
                <rect
                  x={PAD.left + i * step}
                  y={PAD.top}
                  width={step}
                  height={innerH}
                  fill="transparent"
                  onPointerEnter={() => setActive(i)}
                />
              </g>
            );
          })}
          {windows.map((w, i) =>
            i % 6 === 0 ? (
              <text key={w.window} x={PAD.left + i * step + step / 2} y={H - 8} className={styles.tick} textAnchor="middle">
                {utcTime(w.start)}
              </text>
            ) : null,
          )}
        </svg>
        {hovered && active !== null ? (
          <div
            className={styles.tip}
            style={{ left: `${Math.min(Math.max(((PAD.left + active * step + step / 2) / W) * 100, 12), 82)}%` }}
          >
            <span className={styles.tipTime}>{utcDateTime(hovered.start)} UTC</span>
            <span>
              <i className={`${styles.swatch} ${styles.contract}`} /> {contractLabel}: <b className="mono">{int(hovered.top_contract)}</b>
            </span>
            <span>
              <i className={`${styles.swatch} ${styles.rest}`} /> Everything else: <b className="mono">{int(hovered.everything_else)}</b>
            </span>
          </div>
        ) : null}
      </div>
      <figcaption className={styles.legend}>
        <span>
          <i className={`${styles.swatch} ${styles.contract}`} aria-hidden="true" /> {contractLabel}
        </span>
        <span>
          <i className={`${styles.swatch} ${styles.rest}`} aria-hidden="true" /> Everything else
        </span>
        <span className={styles.axisNote}>Times in UTC · each bar is one 30-second window</span>
      </figcaption>
    </figure>
  );
}
