"use server";

import { postFeedback } from "@/lib/api";
import type { FeedbackKind } from "@/lib/types";

const KINDS: FeedbackKind[] = [
  "relevant",
  "irrelevant",
  "too_long",
  "wrong_mood",
  "already_experienced",
  "not_what_i_meant",
  "will_try",
];

export async function sendFeedback(eventId: string | null, workSlug: string, kind: FeedbackKind) {
  if (!KINDS.includes(kind)) return { ok: false };
  try {
    return await postFeedback({ event_id: eventId, work_slug: workSlug, kind });
  } catch {
    return { ok: false };
  }
}
