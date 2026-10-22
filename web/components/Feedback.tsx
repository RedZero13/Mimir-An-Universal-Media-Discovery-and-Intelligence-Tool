"use client";

import { useState, useTransition } from "react";
import { sendFeedback } from "@/app/actions";
import type { FeedbackKind } from "@/lib/types";

const OPTIONS: { kind: FeedbackKind; label: string }[] = [
  { kind: "relevant", label: "Good fit" },
  { kind: "will_try", label: "I'll try this" },
  { kind: "already_experienced", label: "Already know it" },
  { kind: "wrong_mood", label: "Wrong mood" },
  { kind: "too_long", label: "Too long" },
  { kind: "not_what_i_meant", label: "Not what I meant" },
];

export function Feedback({ eventId, slug }: { eventId: string | null; slug: string }) {
  const [sent, setSent] = useState<FeedbackKind | null>(null);
  const [failed, setFailed] = useState(false);
  const [pending, startTransition] = useTransition();

  if (sent) {
    return <p className="feedback-done">Thanks, noted.</p>;
  }
  return (
    <div className="feedback" role="group" aria-label={`Feedback on this recommendation`}>
      {OPTIONS.map((o) => (
        <button
          key={o.kind}
          type="button"
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              const res = await sendFeedback(eventId, slug, o.kind);
              if (res.ok) setSent(o.kind);
              else setFailed(true);
            })
          }
        >
          {o.label}
        </button>
      ))}
      {failed && <span className="feedback-error">Couldn&apos;t save that. Try again?</span>}
    </div>
  );
}
