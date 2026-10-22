import Link from "next/link";
import { getPeople } from "@/lib/api";

export const metadata = { title: "People & studios · Mimir" };

export default async function PeoplePage() {
  const people = await getPeople();
  return (
    <>
      <h1>People &amp; studios</h1>
      <p className="muted">Directors, authors, developers, artists, cinematographers and studios credited in the catalogue.</p>
      <ul className="people-list">
        {people.map((p) => (
          <li key={p.slug}>
            <Link href={`/people/${p.slug}`}>{p.name}</Link>{" "}
            <span className="muted small">
              {p.roles.join(", ")} · {p.count === 1 ? "1 work" : `${p.count} works`}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
