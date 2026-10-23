import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { MimirMark } from "@/components/MimirMark";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mimir · A Terratales Venture",
  description:
    "Mimir is a catalogue and discovery engine for films, books, games and music. Describe how you want to feel and it finds what fits, with the reasons for every pick.",
  openGraph: { title: "Mimir · Find what to watch, read, play or listen to next", siteName: "Mimir · A Terratales Venture" },
};

export const viewport: Viewport = { themeColor: "#131315" };

const FONTS =
  "https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- one shared stylesheet for the whole app */}
        <link rel="stylesheet" href={FONTS} />
      </head>
      <body>
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Mimir, home">
            <MimirMark />
            <span>
              <span className="brand-word">MIMIR</span>
              <span className="brand-sub">A TERRATALES VENTURE</span>
            </span>
          </Link>
          <nav className="site-nav" aria-label="Main">
            <Link href="/">Discover</Link>
            <Link href="/browse">Browse</Link>
            <Link href="/tags">Tags</Link>
            <Link href="/people">People</Link>
          </nav>
          <span className="pill">Pilot · 56 works</span>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <a className="endorse" href="https://terratalesmedia.world/" aria-label="A Terratales venture: visit Terratales">
            {/* eslint-disable-next-line @next/next/no-img-element -- tiny fixed-size brand seal */}
            <img src="/terratales-seal-64.png" alt="Terratales seal" width={32} height={32} />
            <span>A TERRATALES VENTURE</span>
          </a>
          <p>
            Mimir is in pilot. Facts, credits and official ratings are unverified, and every tag and parents&apos; guide level is
            an AI-assisted reading awaiting editorial review. Each is labelled where it appears.
          </p>
          <p className="legal">© 2026 Terratales Media Entertainment · All realms reserved</p>
        </footer>
      </body>
    </html>
  );
}
