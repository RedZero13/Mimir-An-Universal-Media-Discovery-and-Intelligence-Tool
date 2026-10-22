import Link from "next/link";
import { BasisTag } from "./BasisTag";
import { Feedback } from "./Feedback";
import { mediumLabel } from "@/lib/format";
import type { Result } from "@/lib/types";

export function ResultCard({ result, rank, eventId }: { result: Result; rank: number; eventId: string | null }) {
  const meta = [mediumLabel(result.medium), result.year, result.length, result.creators.slice(0, 2).join(", ")]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className="card">
      <div className="card-head">
        <span className="rank" aria-hidden>
          {rank}
        </span>
        <div>
          <h3>
            <Link href={`/works/${result.slug}`}>{result.title}</Link>
          </h3>
          <p className="meta">{meta}</p>
        </div>
      </div>
      <p className="headline">{result.headline}</p>
      {result.summary && <p className="summary">{result.summary}</p>}
      <details className="why">
        <summary>Why this fits</summary>
        <ul className="reasons">
          {result.reasons.map((r, i) => (
            <li key={i} title={r.definition}>
              <BasisTag basis={r.basis} /> {r.text}
            </li>
          ))}
        </ul>
        <details className="breakdown">
          <summary>Score breakdown</summary>
          <dl>
            {Object.entries(result.score_breakdown).map(([k, v]) => (
              <div key={k}>
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd>{v.toFixed(3)}</dd>
              </div>
            ))}
          </dl>
        </details>
      </details>
      {result.caveats.length > 0 && (
        <ul className="caveats">
          {result.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      <Feedback eventId={eventId} slug={result.slug} />
    </li>
  );
}
