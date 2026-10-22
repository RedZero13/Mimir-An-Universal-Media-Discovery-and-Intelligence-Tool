import Link from "next/link";
import { getTags } from "@/lib/api";
import { tagHref } from "@/lib/format";

export const metadata = { title: "Tags · Media Discovery" };

export default async function TagsPage() {
  const groups = await getTags();
  return (
    <>
      <h1>Tags</h1>
      <p className="muted">
        Every quality in the catalogue&apos;s controlled taxonomy that at least one work carries. Each has a definition; open
        one to see the works it applies to, strongest first.
      </p>
      {groups.map((g) => (
        <section key={g.dimension}>
          <h2>{g.label}</h2>
          <ul className="tag-cloud">
            {g.terms.map((t) => (
              <li key={t.key}>
                <Link href={tagHref(t.key)} className="tag-chip">
                  {t.label} <span className="count">{t.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
