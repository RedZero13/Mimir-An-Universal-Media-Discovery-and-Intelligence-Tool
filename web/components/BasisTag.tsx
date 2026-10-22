import { BASIS_LABELS } from "@/lib/format";
import type { Basis } from "@/lib/types";

export function BasisTag({ basis }: { basis: Basis }) {
  const b = BASIS_LABELS[basis];
  return (
    <span className={`basis basis-${basis}`} title={b.title}>
      {b.short}
    </span>
  );
}
