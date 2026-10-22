import { mediumLabel, termLabel } from "@/lib/format";
import type { DiscoverResponse } from "@/lib/types";

export function Interpretation({ data }: { data: DiscoverResponse }) {
  const i = data.interpretation;
  const chips: { label: string; tone: "want" | "avoid" | "limit" }[] = [];
  i.media.forEach((m) => chips.push({ label: mediumLabel(m), tone: "limit" }));
  i.excluded_media.forEach((m) => chips.push({ label: `not ${mediumLabel(m).toLowerCase()}`, tone: "avoid" }));
  if (data.reference) chips.push({ label: `like ${data.reference.title}`, tone: "want" });
  i.preferences.forEach((p) => chips.push({ label: termLabel(p.term), tone: "want" }));
  i.avoid.forEach((a) => chips.push({ label: `${a.hard ? "no" : "less"} ${termLabel(a.term)}`, tone: "avoid" }));
  if (i.length) chips.push({ label: `${i.length.hard ? "≤" : "ideally ≤"} ${i.length.max_minutes} min`, tone: "limit" });
  if (i.novelty) chips.push({ label: i.novelty === "obscure" ? "lesser-known" : "well-known", tone: "want" });
  i.languages.forEach((l) => chips.push({ label: `language: ${l}`, tone: "limit" }));
  if (i.year_min || i.year_max) chips.push({ label: `${i.year_min ?? "…"}–${i.year_max ?? "…"}`, tone: "limit" });

  const excluded = Object.entries(data.excluded);
  return (
    <section className="interpretation" aria-label="How your request was read">
      <h2>How I read your request</h2>
      {chips.length > 0 ? (
        <ul className="chips">
          {chips.map((c) => (
            <li key={`${c.tone}-${c.label}`} className={`chip chip-${c.tone}`}>
              {c.label}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">I couldn&apos;t pick out any specific qualities, so these are broad matches.</p>
      )}
      {i.notes.length > 0 && (
        <ul className="notes">
          {i.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <p className="muted small">
        Searched {data.considered} works
        {excluded.length > 0 && <> · set aside {excluded.map(([r, n]) => `${n} (${r})`).join(", ")}</>}
        {data.weak_matches_hidden > 0 && <> · {data.weak_matches_hidden} weak matches hidden</>}
      </p>
    </section>
  );
}
