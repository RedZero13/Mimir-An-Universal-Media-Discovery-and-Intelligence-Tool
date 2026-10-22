import { BasisTag } from "./BasisTag";
import { SeverityPill } from "./SeverityPill";
import type { ParentsGuide as Guide } from "@/lib/types";

export function ParentsGuide({ guide }: { guide: Guide }) {
  return (
    <section id="parents-guide" aria-labelledby="pg-heading">
      <h2 id="pg-heading">Parents&apos; guide</h2>
      {guide.ratings.length > 0 ? (
        <ul className="ratings">
          {guide.ratings.map((r) => (
            <li key={r.system}>
              <span className="rating big">{r.rating}</span> <strong>{r.system}</strong>
              {r.reason && <span className="muted">: rated {r.rating} for {r.reason.toLowerCase()}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">No official rating recorded.</p>
      )}
      {!guide.assessed && (
        <p className="notice">This work&apos;s content hasn&apos;t been assessed yet. Absence of a warning here does not mean it is suitable.</p>
      )}
      <div className="guide-groups">
        {guide.groups.map((g) => (
          <div key={g.slug} className="guide-group">
            <h3>
              {g.label} <SeverityPill severity={g.severity} />
              {g.partial && <span className="muted small"> (partly assessed)</span>}
            </h3>
            <ul>
              {g.items.map((i) => (
                <li key={i.key} title={i.definition}>
                  <span className="guide-item-label">{i.label}</span>: {i.severity}
                  {i.basis && <BasisTag basis={i.basis} />}
                  {i.note && <p className="guide-note">{i.note}</p>}
                  {i.spoiler_note && (
                    <details className="spoiler">
                      <summary>Show spoiler detail</summary>
                      <p>{i.spoiler_note}</p>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="muted small">
        Severity: None, Mild, Moderate or Severe. &ldquo;Not assessed&rdquo; means nobody has reviewed that category for this
        work yet. Ratings and notes in the pilot are unverified.
      </p>
    </section>
  );
}
