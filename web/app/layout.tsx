import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import Link from "next/link";
import { REPO, latestSnapshot } from "@/lib/snapshots";
import { longDate, shortHex } from "@/lib/format";
import styles from "./layout.module.css";
import "./globals.css";

const display = Newsreader({ subsets: ["latin"], variable: "--font-newsreader", display: "swap" });
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-sans", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Headcount", template: "%s · Headcount" },
  description: "Real users, counted: how much of each LitVM testnet app's traffic looks scripted.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  const snapshot = latestSnapshot();
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <header className={styles.header}>
          <div className={styles.bar}>
            <Link href="/" className={styles.brand}>
              Headcount
            </Link>
            <nav aria-label="Main" className={styles.nav}>
              <Link href="/">Leaderboard</Link>
              <Link href="/method/">Method</Link>
              <a href={REPO}>Source</a>
            </nav>
          </div>
        </header>
        {children}
        <footer className={styles.footer}>
          <div className={styles.bar}>
            <p className="small muted">
              Snapshot of {longDate(snapshot.date)} from the LitVM LiteForge testnet. Fingerprint{" "}
              <span className="mono" title={snapshot.digest}>
                {shortHex(snapshot.digest, 10, 6)}
              </span>
              .
            </p>
            <p className="small muted">Labels describe wallet behaviour, not who runs a wallet.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
