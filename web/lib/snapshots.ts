import { readFileSync } from "node:fs";
import path from "node:path";

/** Snapshots live at the repo root, written by `python3 -m headcount snapshot`. */
const ROOT = path.join(process.cwd(), "..", "snapshots");

export type Label = "likely_scripted" | "possibly_scripted" | "no_signals";

export type Shares = {
  share_likely_scripted: number;
  share_possibly_scripted: number;
  share_no_signals: number;
};

export type Summary = Shares & {
  window_start: string;
  window_end: string;
  span_hours: number;
  windows: number;
  blocks_per_window: number;
  sampled_blocks: number;
  est_blocks_per_day: number;
  sample_share_of_day: number;
  sampled_txs: number;
  est_daily_txs: number;
  wallets: number;
  wallets_likely: number;
  wallets_possible: number;
  wallets_none: number;
  attributed_txs: number;
  share_attributed: number;
  apps_listed: number;
  apps_seen: number;
  apps_frontend_scanned: number;
  head_block: number;
  top_contract: string;
  top_contract_share: number;
  top_contract_sampled_txs: number;
  top_contract_call: string;
  top_contract_source: string;
  top_contract_app: string;
};

export type App = Shares & {
  app: string;
  app_id: string;
  category: string;
  url: string;
  sampled_txs: number;
  est_daily_txs: number;
  wallets: number;
  wallets_none: number;
  contracts: number;
  contract_list: { address: string; rule: string; name: string; sampled_txs: number }[];
  matched_by: string;
  frontend: string;
  top_call: string;
};

export type Group = Shares & {
  group: string;
  kind: string;
  top_contract: string;
  top_name: string;
  source_code: string;
  contracts: number;
  sampled_txs: number;
  est_daily_txs: number;
  wallets: number;
  top_call: string;
};

export type Evidence = {
  key: string;
  app_id: string;
  app: string;
  wallet: string;
  label: Label;
  label_name: string;
  flags: string;
  lifetime_txs: number | null;
  sampled_txs: number;
  hours_active: number;
  max_in_window: number;
  tx: string;
};

export type Flag = { flag: string; signal: string; rule: string; wallets: number };

export type Window = {
  window: number;
  start: string;
  likely_scripted: number;
  possibly_scripted: number;
  no_signals: number;
  top_contract: number;
  everything_else: number;
};

export type Cohort = {
  cohort: string;
  group: string;
  wallets: number;
  median_lifetime_txs: number;
  median_sampled_txs: number;
  median_windows_active: number;
  wallets_likely_scripted: number;
  wallets_possibly_scripted: number;
  wallets_no_signals: number;
};

export type IndexEntry = { date: string; digest: string; window_start: string; window_end: string };

export type Snapshot = {
  date: string;
  digest: string;
  summary: Summary;
  apps: App[];
  groups: Group[];
  evidence: Evidence[];
  flags: Flag[];
  windows: Window[];
  cohorts: Cohort[];
};

function readJson<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(path.join(ROOT, ...parts), "utf8")) as T;
}

/** Every published snapshot, newest first. */
export function snapshotIndex(): IndexEntry[] {
  return readJson<IndexEntry[]>("index.json");
}

export function loadSnapshot(date: string): Snapshot {
  const meta = readJson<{ date: string; digest: string }>(date, "meta.json");
  return {
    date: meta.date,
    digest: meta.digest,
    summary: readJson<Summary[]>(date, "summary.json")[0],
    apps: readJson<App[]>(date, "apps.json"),
    groups: readJson<Group[]>(date, "groups.json"),
    evidence: readJson<Evidence[]>(date, "evidence.json"),
    flags: readJson<Flag[]>(date, "flags.json"),
    windows: readJson<Window[]>(date, "windows.json"),
    cohorts: readJson<Cohort[]>(date, "cohorts.json"),
  };
}

export function latestSnapshot(): Snapshot {
  const [latest] = snapshotIndex();
  if (!latest) throw new Error("No snapshots found. Run `python3 -m headcount all` first.");
  return loadSnapshot(latest.date);
}

/** One app's numbers across every snapshot, oldest first, for its trend. */
export function appHistory(appId: string): { date: string; app: App | undefined }[] {
  return snapshotIndex()
    .map((entry) => ({ date: entry.date, app: loadSnapshot(entry.date).apps.find((a) => a.app_id === appId) }))
    .reverse();
}

export const EXPLORER = "https://liteforge.explorer.caldera.xyz";
export const REPO = "https://github.com/Saber1Y/headcount";
