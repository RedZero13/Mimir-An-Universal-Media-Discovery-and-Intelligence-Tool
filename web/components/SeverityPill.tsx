import type { Severity } from "@/lib/types";

export function SeverityPill({ severity }: { severity: Severity }) {
  const cls = severity === "Not assessed" ? "unknown" : severity.toLowerCase();
  return <span className={`severity severity-${cls}`}>{severity}</span>;
}
