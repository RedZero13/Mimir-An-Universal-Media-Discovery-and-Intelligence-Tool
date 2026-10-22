import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Media Discovery",
  description: "Describe what you want to experience. Find films, books, games and music that fit, and see why.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            Media Discovery
          </Link>
          <span className="pill">pilot catalogue</span>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          Pilot: a small, hand-curated catalogue. Facts are unverified; classifications are AI-assisted and awaiting
          editorial review. Both are labelled wherever they appear.
        </footer>
      </body>
    </html>
  );
}
