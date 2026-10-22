import Link from "next/link";

export default function NotFound() {
  return (
    <section>
      <h1>Not in the catalogue</h1>
      <p>
        That work isn&apos;t in the pilot catalogue. <Link href="/">Back to discovery</Link>
      </p>
    </section>
  );
}
