import Link from "next/link";
import { SeverityPill } from "./SeverityPill";
import { mediumLabel, tagHref } from "@/lib/format";
import type { WorkCard as Card } from "@/lib/types";

export function WorkCard({ work, extra }: { work: Card; extra?: React.ReactNode }) {
  const meta = [mediumLabel(work.medium), work.year, work.length, work.creators.slice(0, 2).join(", ")]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className="work-card">
      <div className="work-card-head">
        <h3>
          <Link href={`/works/${work.slug}`}>{work.title}</Link>
        </h3>
        {work.ratings.map((r) => (
          <span key={r.system} className="rating" title={`${r.system} rating`}>
            {r.rating}
          </span>
        ))}
      </div>
      <p className="meta">{meta}</p>
      {extra}
      {work.summary && <p className="summary">{work.summary}</p>}
      <ul className="tag-list" aria-label="Tags">
        {[...work.genres, ...work.tags].map((t) => (
          <li key={t.key}>
            <Link href={tagHref(t.key)} className="tag-chip">
              {t.label}
            </Link>
          </li>
        ))}
      </ul>
      {work.guide_flags.length > 0 && (
        <p className="guide-flags">
          {work.guide_flags.map((f) => (
            <span key={f.group}>
              <SeverityPill severity={f.severity} /> {f.label}
            </span>
          ))}
        </p>
      )}
    </li>
  );
}
