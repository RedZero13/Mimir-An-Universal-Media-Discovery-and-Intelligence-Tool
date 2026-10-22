export function SearchBox({ initial }: { initial?: string }) {
  return (
    <form className="search" action="/" method="get" role="search">
      <label htmlFor="q" className="visually-hidden">
        Describe what you want to watch, read, play or listen to
      </label>
      <textarea
        id="q"
        name="q"
        rows={2}
        defaultValue={initial}
        placeholder="e.g. an atmospheric, thought-provoking sci-fi film under two hours with little violence"
        required
        minLength={2}
        maxLength={500}
      />
      <button type="submit">Find</button>
    </form>
  );
}
