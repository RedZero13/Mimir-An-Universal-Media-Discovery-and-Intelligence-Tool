// Helpers for filter state that lives in the URL query string.

export type SearchParams = Record<string, string | string[] | undefined>;

export const asArray = (v: string | string[] | undefined): string[] => (v === undefined ? [] : Array.isArray(v) ? v : [v]);
export const asString = (v: string | string[] | undefined): string => (Array.isArray(v) ? v[0] ?? "" : v ?? "");

/** Returns a /browse URL with one parameter value added, replaced or removed. */
export function browseHref(params: SearchParams, key: string, value: string | null, mode: "add" | "set" | "remove"): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    for (const item of asArray(v)) {
      if (k === key && (mode === "set" || (mode === "remove" && item === value))) continue;
      qs.append(k, item);
    }
  }
  if (value !== null && mode !== "remove" && !(mode === "add" && asArray(params[key]).includes(value))) {
    qs.append(key, value);
  }
  const s = qs.toString();
  return s ? `/browse?${s}` : "/browse";
}
