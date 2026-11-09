import Link from "next/link";
import { DayChart } from "@/components/DayChart";
import { Figures } from "@/components/Figures";
import { Leaderboard } from "@/components/Leaderboard";
import { ShareBar, ShareLegend } from "@/components/ShareBar";
import { EXPLORER, latestSnapshot } from "@/lib/snapshots";
import { compact, int, longDate, pct, shortHex } from "@/lib/format";
import table from "@/components/table.module.css";
import styles from "./page.module.css";

export default function Home() {
  const s = latestSnapshot();
  const { summary } = s;
  const anySignal = summary.share_likely_scripted + summary.share_possibly_scripted;
  const withTraffic = s.apps.filter((a) => a.sampled_txs > 0);
  const quiet = s.apps.filter((a) => a.sampled_txs === 0);
  const busiestApp = s.apps.find((a) => a.app === summary.top_contract_app);
  const [callers, everyoneElse] = [
    s.cohorts.find((c) => c.cohort === "top_contract"),
    s.cohorts.find((c) => c.cohort === "everyone_else"),
  ];

  return (
    <main className="page">
      <section className={styles.lede}>
        <p className="eyebrow">
          LiteForge testnet · {longDate(s.date)}
        </p>
        <h1>
          {pct(anySignal)} of LitVM testnet transactions come from wallets with at least one scripted signal.
        </h1>
        <p className={styles.dek}>
          Headcount reads the chain and counts the wallets behind each app. Here is who sent the traffic over 24 hours,
          and which apps have real-looking users.
        </p>
        <div className={styles.census}>
          <ShareBar shares={summary} size="lg" />
          <ShareLegend shares={summary} />
        </div>
      </section>

      <Figures
        items={[
          { label: "Transactions a day", value: compact(summary.est_daily_txs), note: "estimated from the sample" },
          {
            label: "Real-looking wallets",
            value: int(summary.wallets_none),
            note: `of ${int(summary.wallets)} wallets seen`,
            tone: "real",
          },
          {
            label: `Traffic to ${summary.top_contract_app}'s busiest contract`,
            value: pct(summary.top_contract_share),
            note: "one contract, all day",
            tone: "scripted",
          },
          {
            label: "Hub apps with traffic",
            value: `${summary.apps_seen} of ${summary.apps_listed}`,
            note: `${pct(summary.share_attributed)} of traffic matched to an app`,
          },
        ]}
      />

      <section className="section" aria-labelledby="leaderboard">
        <div className="section-head">
          <h2 id="leaderboard">Leaderboard</h2>
          <p className="muted">
            Apps on the LitVM testnet hub, ranked by wallets that show none of the four scripted signals. The bar shows
            who each app&apos;s traffic comes from.{" "}
            <Link href="/method/">How the signals work</Link>.
          </p>
        </div>
        <Leaderboard apps={withTraffic} />
        {quiet.length ? (
          <details className={styles.quiet}>
            <summary>
              {quiet.length} listed apps had no traffic in the sample
            </summary>
            <p className="small muted">
              Either nobody used them in the sampled windows, or Headcount could not find their contracts. Each app&apos;s
              page says which.
            </p>
            <ul className={styles.quietList}>
              {quiet.map((a) => (
                <li key={a.app_id}>
                  <Link href={`/apps/${a.app_id}/`}>{a.app}</Link>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <section className="section" aria-labelledby="around-the-clock">
        <div className="section-head">
          <h2 id="around-the-clock">One contract, around the clock</h2>
          <p className="muted">
            {busiestApp ? <Link href={`/apps/${busiestApp.app_id}/`}>{summary.top_contract_app}</Link> : summary.top_contract_app}
            &apos;s contract{" "}
            <a className="mono" href={`${EXPLORER}/address/${summary.top_contract}`} title={summary.top_contract}>
              {shortHex(summary.top_contract)}
            </a>{" "}
            ({summary.top_contract_call}, source code {summary.top_contract_source.toLowerCase()}) took {pct(summary.top_contract_share)}{" "}
            of all transactions. Its calls hold steady at every hour, while everything else rises and falls with the day.
          </p>
        </div>
        <DayChart windows={s.windows} contractLabel={`${summary.top_contract_app}'s contract`} />
        {callers && everyoneElse ? (
          <div className={styles.compare}>
            <div>
              <p className="eyebrow">Wallets calling it</p>
              <p className={styles.compareValue}>{int(callers.median_lifetime_txs)}</p>
              <p className="small muted">median lifetime transactions, across {int(callers.wallets)} wallets</p>
            </div>
            <div>
              <p className="eyebrow">Every other wallet</p>
              <p className={styles.compareValue}>{int(everyoneElse.median_lifetime_txs)}</p>
              <p className="small muted">median lifetime transactions, across {int(everyoneElse.wallets)} wallets</p>
            </div>
            <p className={`small muted ${styles.compareNote}`}>
              Its callers take turns: each shows up in a median of {callers.median_windows_active} of {summary.windows}{" "}
              windows, which is why the per-wallet round-the-clock signal rarely fires. Scripted wallets calling an app do
              not mean the app runs them; airdrops and staking rewards attract farmers.
            </p>
          </div>
        ) : null}
      </section>

      <section className="section" aria-labelledby="unmatched">
        <div className="section-head">
          <h2 id="unmatched">Busy contracts not matched to an app</h2>
          <p className="muted">The rest of the traffic, by contract. Unverified means the explorer has no published source code.</p>
        </div>
        <div className={table.scroll}>
          <table className={table.table}>
            <thead>
              <tr>
                <th scope="col">Contract</th>
                <th scope="col">Most common call</th>
                <th scope="col">Source code</th>
                <th scope="col" className={table.num}>
                  Wallets
                </th>
                <th scope="col" className={table.num}>
                  Transactions a day
                </th>
                <th scope="col">Who sends it</th>
              </tr>
            </thead>
            <tbody>
              {s.groups.slice(0, 8).map((g) => (
                <tr key={g.group}>
                  <td>
                    <a className="mono" href={`${EXPLORER}/address/${g.top_contract}`} title={g.top_contract}>
                      {shortHex(g.top_contract)}
                    </a>
                    {g.top_name ? <span className={table.sub}>{g.top_name}</span> : null}
                  </td>
                  <td className="mono">{g.top_call || "unknown"}</td>
                  <td>{g.source_code}</td>
                  <td className={`${table.num} mono`}>{int(g.wallets)}</td>
                  <td className={`${table.num} mono`}>{compact(g.est_daily_txs)}</td>
                  <td className={table.barCell}>
                    <ShareBar shares={g} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
