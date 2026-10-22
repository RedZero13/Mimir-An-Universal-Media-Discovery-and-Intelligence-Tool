// Server-side API client. Only imported from server components and server actions.
import "server-only";
import type {
  BrowseResponse,
  DiscoverResponse,
  FeedbackKind,
  PersonPage,
  PersonSummary,
  TagIndexGroup,
  TagPage,
  Work,
} from "./types";

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

async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export const getWork = (slug: string) => orNull(request<Work>(`/api/works/${encodeURIComponent(slug)}`));

export interface BrowseParams {
  medium?: string[];
  tag?: string[];
  avoid?: string[];
  decade?: string;
  language?: string;
  max_minutes?: string;
  q?: string;
  sort?: string;
}

export function browse(params: BrowseParams): Promise<BrowseResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    for (const item of Array.isArray(v) ? v : [v]) if (item) qs.append(k, item);
  }
  return request(`/api/works?${qs}`);
}

export const getTags = () => request<TagIndexGroup[]>("/api/tags");
export const getTag = (key: string) => {
  const [dimension, slug] = key.split(":");
  return orNull(request<TagPage>(`/api/tags/${encodeURIComponent(dimension)}/${encodeURIComponent(slug ?? "")}`));
};
export const getPeople = () => request<PersonSummary[]>("/api/people");
export const getPerson = (slug: string) => orNull(request<PersonPage>(`/api/people/${encodeURIComponent(slug)}`));

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
