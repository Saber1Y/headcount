import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Figures } from "@/components/Figures";
import { ShareBar, ShareLegend } from "@/components/ShareBar";
import { EXPLORER, appHistory, latestSnapshot } from "@/lib/snapshots";
import { compact, int, longDate, pct, shortHex } from "@/lib/format";
import table from "@/components/table.module.css";
import styles from "./page.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return latestSnapshot().apps.map((a) => ({ id: a.app_id }));
}

export async function generateMetadata({ params }: PageProps<"/apps/[id]">): Promise<Metadata> {
  const { id } = await params;
  const app = latestSnapshot().apps.find((a) => a.app_id === id);
  return { title: app ? app.app : "App" };
}

const RULES: Record<string, string> = {
  frontend: "Found in the app's own website code",
  deployer: "Same deployer as one of the app's contracts",
  name: "Contract or token name matches the app",
};

export default async function AppPage({ params }: PageProps<"/apps/[id]">) {
  const { id } = await params;
  const s = latestSnapshot();
  const app = s.apps.find((a) => a.app_id === id);
  if (!app) notFound();

  const evidence = s.evidence.filter((e) => e.app_id === id);
  const history = appHistory(id).filter((h) => h.app && h.app.sampled_txs > 0);
  const hasTraffic = app.sampled_txs > 0;

  return (
    <main className="page">
      <section className={styles.head}>
        <p className="eyebrow">
          {app.category || "App"} · {longDate(s.date)}
        </p>
        <h1>{app.app}</h1>
        {hasTraffic ? (
          <p className={styles.dek}>
            {pct(app.share_no_signals)} of {app.app}&apos;s sampled traffic came from wallets with no scripted signals, from{" "}
            {int(app.wallets_none)} real-looking wallets out of {int(app.wallets)} seen.
          </p>
        ) : (
          <p className={styles.dek}>
            {app.app} had no traffic in this sample.{" "}
            {app.contracts === 0
              ? "Headcount could not match any contracts to it, so its traffic may be uncounted rather than absent."
              : "Its matched contracts were not called in the sampled windows."}
          </p>
        )}
        <p className="small">
          <a href={app.url}>{app.url.replace(/^https?:\/\//, "").replace(/\/$/, "")}</a>
        </p>
      </section>

      {hasTraffic ? (
        <>
          <section className="section" aria-label="Who sends the traffic">
            <ShareBar shares={app} size="lg" />
            <ShareLegend shares={app} />
          </section>

          <Figures
            items={[
              { label: "Real-looking wallets", value: int(app.wallets_none), note: `of ${int(app.wallets)} seen`, tone: "real" },
              { label: "Likely scripted traffic", value: pct(app.share_likely_scripted), tone: "scripted" },
              { label: "Transactions a day", value: compact(app.est_daily_txs), note: `${int(app.sampled_txs)} sampled` },
              { label: "Most common call", value: app.top_call || "unknown" },
            ]}
          />
        </>
      ) : null}

      {history.length > 1 ? (
        <section className="section" aria-labelledby="trend">
          <div className="section-head">
            <h2 id="trend">Day by day</h2>
          </div>
          <ol className={styles.trend}>
            {history.map(({ date, app: day }) =>
              day ? (
                <li key={date}>
                  <span className="mono small">{date}</span>
                  <ShareBar shares={day} />
                  <span className="mono small">{int(day.wallets_none)} real-looking</span>
                </li>
              ) : null,
            )}
          </ol>
        </section>
      ) : hasTraffic ? (
        <p className="small muted">This is the first snapshot for {app.app}. A day-by-day trend appears as daily scans add up.</p>
      ) : null}

      {evidence.length ? (
        <section className="section" aria-labelledby="examples">
          <div className="section-head">
            <h2 id="examples">Example wallets</h2>
            <p className="muted">
              The busiest likely scripted wallets and wallets with no signals, each with one transaction to {app.app}.
            </p>
          </div>
          <div className={table.scroll}>
            <table className={table.table}>
              <thead>
                <tr>
                  <th scope="col">Wallet</th>
                  <th scope="col">Label</th>
                  <th scope="col">Signals</th>
                  <th scope="col" className={table.num}>
                    Lifetime txs
                  </th>
                  <th scope="col" className={table.num}>
                    Most in 30 s
                  </th>
                  <th scope="col">Transaction</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((e) => (
                  <tr key={e.key}>
                    <td>
                      <a className="mono" href={`${EXPLORER}/address/${e.wallet}`} title={e.wallet}>
                        {shortHex(e.wallet)}
                      </a>
                    </td>
                    <td>
                      <span className={`${table.pill} ${table[e.label]}`}>{e.label_name}</span>
                    </td>
                    <td className={styles.signals}>{e.flags}</td>
                    <td className={`${table.num} mono`}>{e.lifetime_txs === null ? "unknown" : int(e.lifetime_txs)}</td>
                    <td className={`${table.num} mono`}>{int(e.max_in_window)}</td>
                    <td>
                      <a className="mono" href={`${EXPLORER}/tx/${e.tx}`} title={e.tx}>
                        {shortHex(e.tx)}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="section" aria-labelledby="contracts">
        <div className="section-head">
          <h2 id="contracts">Contracts counted</h2>
          <p className="muted">
            {app.contracts
              ? "The contracts whose traffic counts toward this app, and how each was matched."
              : app.frontend === "ok"
                ? "No contracts found. The app's website code did not name any contract seen on LiteForge in the sample."
                : `No contracts found. Its website could not be scanned (${app.frontend}).`}
          </p>
        </div>
        {app.contract_list.length ? (
          <div className={table.scroll}>
            <table className={table.table}>
              <thead>
                <tr>
                  <th scope="col">Contract</th>
                  <th scope="col">Matched by</th>
                  <th scope="col" className={table.num}>
                    Sampled txs
                  </th>
                </tr>
              </thead>
              <tbody>
                {app.contract_list.map((c) => (
                  <tr key={c.address}>
                    <td>
                      <a className="mono" href={`${EXPLORER}/address/${c.address}`} title={c.address}>
                        {shortHex(c.address)}
                      </a>
                      {c.name ? <span className={table.sub}>{c.name}</span> : null}
                    </td>
                    <td>{RULES[c.rule] ?? c.rule}</td>
                    <td className={`${table.num} mono`}>{int(c.sampled_txs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <p className="small muted">
        Labels describe wallet behaviour, not who runs a wallet. Scripted wallets calling {app.app} do not mean {app.app}{" "}
        runs them. <Link href="/method/">How Headcount counts</Link> · <Link href="/">Back to the leaderboard</Link>
      </p>
    </main>
  );
}
