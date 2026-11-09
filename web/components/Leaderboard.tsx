"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { App } from "@/lib/snapshots";
import { compact, int, pct } from "@/lib/format";
import { ShareBar } from "./ShareBar";
import styles from "./Leaderboard.module.css";

type SortKey = "wallets_none" | "share_no_signals" | "est_daily_txs" | "app";

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "app", label: "App", numeric: false },
  { key: "wallets_none", label: "Real-looking wallets", numeric: true },
  { key: "share_no_signals", label: "Traffic with no signals", numeric: true },
  { key: "est_daily_txs", label: "Transactions a day", numeric: true },
];

/** Hub apps with sampled traffic, ranked by wallets that show no scripted signals. */
export function Leaderboard({ apps }: { apps: App[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "wallets_none", dir: -1 });

  const ranked = useMemo(
    () => [...apps].sort((a, b) => b.wallets_none - a.wallets_none || b.sampled_txs - a.sampled_txs),
    [apps],
  );
  const rankOf = useMemo(() => new Map(ranked.map((a, i) => [a.app_id, i + 1])), [ranked]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = ranked.filter((a) => !q || `${a.app} ${a.category}`.toLowerCase().includes(q));
    return filtered.sort((a, b) => {
      const va = a[sort.key];
      const vb = b[sort.key];
      const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return c * sort.dir || (rankOf.get(a.app_id) ?? 0) - (rankOf.get(b.app_id) ?? 0);
    });
  }, [ranked, rankOf, query, sort]);

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "app" ? 1 : -1 }));

  return (
    <div className={styles.wrap}>
      <div className={styles.tools}>
        <label htmlFor="app-search" className="sr-only">
          Search apps
        </label>
        <input
          id="app-search"
          type="search"
          className={styles.search}
          placeholder="Search apps or categories"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="small muted" aria-live="polite">
          {rows.length === apps.length ? `${apps.length} apps` : `${rows.length} of ${apps.length} apps`}
        </span>
      </div>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" className={styles.rank}>
                <span className="sr-only">Rank</span>#
              </th>
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={c.numeric ? styles.num : undefined}
                  aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : undefined}
                >
                  <button type="button" onClick={() => toggle(c.key)} className={styles.sortButton}>
                    {c.label}
                    <span aria-hidden="true" className={styles.arrow}>
                      {sort.key === c.key ? (sort.dir === 1 ? "↑" : "↓") : ""}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.app_id}>
                <td className={`${styles.rank} mono`}>{rankOf.get(a.app_id)}</td>
                <td>
                  <Link href={`/apps/${a.app_id}/`} className={styles.appLink}>
                    {a.app}
                  </Link>
                  <span className={styles.category}>{a.category}</span>
                </td>
                <td className={`${styles.num} mono`}>
                  {int(a.wallets_none)}
                  <span className={styles.of}> of {int(a.wallets)}</span>
                </td>
                <td>
                  <div className={styles.shareCell}>
                    <span className="mono">{pct(a.share_no_signals)}</span>
                    <ShareBar shares={a} />
                  </div>
                </td>
                <td className={`${styles.num} mono`}>{compact(a.est_daily_txs)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <p className={`${styles.empty} muted`}>No apps match “{query}”.</p> : null}
      </div>
    </div>
  );
}
