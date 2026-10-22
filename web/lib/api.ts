// Server-side API client. Only imported from server components and server actions.
import "server-only";
import type { DiscoverResponse, FeedbackKind, Work } from "./types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export function discover(query: string): Promise<DiscoverResponse> {
  return request(`/api/discover?q=${encodeURIComponent(query)}`);
}

export async function getWork(slug: string): Promise<Work | null> {
  try {
    return await request<Work>(`/api/works/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function postFeedback(body: {
  event_id: string | null;
  work_slug: string;
  kind: FeedbackKind;
}): Promise<{ ok: boolean }> {
  return request("/api/feedback", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}
