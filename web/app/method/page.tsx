import type { Metadata } from "next";
import { EXPLORER, REPO, latestSnapshot, snapshotIndex } from "@/lib/snapshots";
import { int, pct, utcDateTime } from "@/lib/format";
import table from "@/components/table.module.css";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "Method" };

/** Set at build time once the registry is deployed on LiteForge. */
const REGISTRY = process.env.NEXT_PUBLIC_HEADCOUNT_REGISTRY ?? "";

export default function Method() {
  const s = latestSnapshot();
  const { summary } = s;
  const day = s.date.replaceAll("-", "");

  return (
    <main className="page">
      <section className={styles.head}>
        <p className="eyebrow">Method</p>
        <h1>How Headcount counts</h1>
        <p className={styles.dek}>
          Every label comes from a rule you can check, and every number links back to the chain.
        </p>
      </section>

      <section className="section" aria-labelledby="signals">
        <div className="section-head">
          <h2 id="signals">Four signals</h2>
          <p className="muted">
            A wallet with two or more signals is likely scripted. One is possibly scripted. None means no signals, which
            the leaderboard counts as a real-looking wallet.
          </p>
        </div>
        <div className={table.scroll}>
          <table className={table.table}>
            <thead>
              <tr>
                <th scope="col">Signal</th>
                <th scope="col">Rule</th>
                <th scope="col" className={table.num}>
                  Wallets in this snapshot
                </th>
              </tr>
            </thead>
            <tbody>
              {s.flags.map((f) => (
                <tr key={f.flag}>
                  <td>{f.signal}</td>
                  <td>{f.rule}</td>
                  <td className={`${table.num} mono`}>{int(f.wallets)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.prose} aria-labelledby="sampling">
        <h2 id="sampling">Sampling a day</h2>
        <p>
          Reading every block of a day through the public LiteForge RPC takes most of a day, so Headcount reads{" "}
          {summary.windows} windows of {summary.blocks_per_window} consecutive blocks, spread evenly over 24 hours:{" "}
          {pct(summary.sample_share_of_day)} of the day&apos;s blocks and {int(summary.sampled_txs)} transactions in this
          snapshot. Because the windows are spread evenly in time, the share of traffic per label is a fair estimate for
          the day. Daily totals are scaled up from the sample.
        </p>
        <p>
          Wallet counts lean busy. A wallet that sends every few seconds almost always lands in a 30-second window; a
          person who visits once a day usually does not. Read the traffic shares as the headline and real-looking wallet
          counts as a floor.
        </p>

        <h2 id="matching">Matching contracts to apps</h2>
        <p>
          Headcount reads the testnet hub&apos;s app directory, then scans each app&apos;s homepage, the pages it links to
          and their scripts for contract addresses. An address found in exactly one app&apos;s code belongs to that app.
          Contracts from the same deployer inherit it, and a matching contract or token name is the last resort.
          Addresses several apps embed, such as shared tokens, stay unmatched. Sites behind a bot check are not scanned.
          In this snapshot {summary.apps_frontend_scanned} of {summary.apps_listed} listed apps gave up contract
          addresses, and {pct(summary.share_attributed)} of traffic was matched.
        </p>

        <h2 id="limits">What this cannot tell you</h2>
        <p>
          There is no confirmed list of which wallets are bots, so these are behaviour labels, not verdicts. A careful
          script with random delays passes as no signals, and a person who batches many actions quickly can trip the
          burst signal. A shared funding wallet is not used as a signal, because nearly every wallet, person or script,
          is funded by the faucet. Scripted wallets calling an app do not mean the app runs them: airdrops, points and
          staking rewards attract farmers who script their own wallets.
        </p>
      </section>

      <section className="section" aria-labelledby="verify">
        <div className="section-head">
          <h2 id="verify">Check a snapshot yourself</h2>
          <p className="muted">
            Each daily snapshot&apos;s files are published in the{" "}
            <a href={`${REPO}/tree/main/snapshots`}>repository</a>, with a SHA-256 fingerprint over them.{" "}
            {REGISTRY ? (
              <>
                The fingerprint is recorded on LiteForge in the registry at{" "}
                <a className="mono" href={`${EXPLORER}/address/${REGISTRY}`}>
                  {REGISTRY}
                </a>
                , which never lets a day be changed.
              </>
            ) : (
              "Recording fingerprints on LiteForge starts once the registry contract is deployed."
            )}
          </p>
        </div>
        <pre className={styles.code}>
          {`git clone ${REPO}.git && cd headcount
python3 -c "from pathlib import Path; from headcount.snapshot import digest; print(digest(Path('snapshots/${s.date}')))"
${REGISTRY ? `cast call ${REGISTRY} "verify(uint32,bytes32)(bool)" ${day} ${s.digest} --rpc-url https://liteforge.rpc.caldera.xyz/http` : `# expected: ${s.digest}`}`}
        </pre>
        <div className={table.scroll}>
          <table className={table.table}>
            <thead>
              <tr>
                <th scope="col">Snapshot</th>
                <th scope="col">Window (UTC)</th>
                <th scope="col">Fingerprint</th>
              </tr>
            </thead>
            <tbody>
              {snapshotIndex().map((e) => (
                <tr key={e.date}>
                  <td className="mono">{e.date}</td>
                  <td>
                    {utcDateTime(e.window_start)} to {utcDateTime(e.window_end)}
                  </td>
                  <td className={`mono ${styles.digest}`}>{e.digest}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
