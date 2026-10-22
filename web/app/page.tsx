import Link from "next/link";
import { Interpretation } from "@/components/Interpretation";
import { ResultCard } from "@/components/ResultCard";
import { SearchBox } from "@/components/SearchBox";
import { discover } from "@/lib/api";

const EXAMPLES = [
  "An intelligent sci-fi film with a strong atmosphere and very little violence, ideally under two hours, not something obvious",
  "Something comforting after a difficult day, no violence",
  "A book like Outer Wilds",
  "Something like Blade Runner but in a different medium",
  "A game I can finish in one evening, wordless and beautiful",
  "Stories about surveillance and complicity, any medium",
];

export default async function Home({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const query = q?.trim();

  if (!query) {
    return (
      <>
        <section className="hero">
          <p className="eyebrow">The well beneath the tree</p>
          <h1>
            Drawn from the well of <em>every story.</em>
          </h1>
          <p>
            Describe a feeling, an idea, a favourite or a time limit. Mimir finds the films, books, games and music that fit,
            and tells you why each one does.
          </p>
        </section>
        <SearchBox />
        <section className="examples">
          <h2>Try</h2>
          <ul>
            {EXAMPLES.map((e) => (
              <li key={e}>
                <Link href={`/?q=${encodeURIComponent(e)}`}>{e}</Link>
              </li>
            ))}
          </ul>
        </section>
      </>
    );
  }

  let data;
  try {
    data = await discover(query);
  } catch {
    return (
      <>
        <SearchBox initial={query} />
        <p className="error">The discovery service isn&apos;t reachable right now. Is the API running?</p>
      </>
    );
  }

  return (
    <>
      <SearchBox initial={query} />
      <Interpretation data={data} />
      {data.results.length === 0 ? (
        <p className="empty">{data.message}</p>
      ) : (
        <ol className="results">
          {data.results.map((r, i) => (
            <ResultCard key={r.slug} result={r} rank={i + 1} eventId={data.event_id} />
          ))}
        </ol>
      )}
    </>
  );
}
