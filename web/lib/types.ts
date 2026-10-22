// Data contracts mirroring the API (api/mde/app.py). Keep in sync when the API changes.

export type Basis = "catalogue" | "interpretation" | "reviewed_interpretation";

export interface Reason {
  kind: "match" | "relationship" | "constraint" | "novelty";
  text: string;
  basis: Basis;
  term?: string;
  definition?: string;
  strength?: number;
  confidence?: number;
}

export interface Result {
  slug: string;
  title: string;
  original_title: string | null;
  medium: string;
  year: number | null;
  creators: string[];
  length: string | null;
  summary: string | null;
  headline: string;
  reasons: Reason[];
  caveats: string[];
  score: number;
  score_breakdown: Record<string, number>;
}

export interface Interpretation {
  query: string;
  media: string[];
  excluded_media: string[];
  preferences: { term: string; weight: number; phrase: string }[];
  avoid: { term: string; hard: boolean; threshold: number; phrase: string }[];
  length: { max_minutes: number; hard: boolean; phrase: string } | null;
  languages: string[];
  excluded_languages: string[];
  year_min: number | null;
  year_max: number | null;
  novelty: "obscure" | "popular" | null;
  reference_phrase: string | null;
  reference_slug: string | null;
  reference_other_medium: boolean;
  keywords: string[];
  notes: string[];
}

export interface DiscoverResponse {
  event_id: string | null;
  interpretation: Interpretation;
  results: Result[];
  excluded: Record<string, number>;
  weak_matches_hidden: number;
  considered: number;
  reference: { slug: string; title: string; medium: string } | null;
  parser: string;
  ranker: string;
  message: string | null;
}

export interface Classification {
  dimension: string;
  slug: string;
  label: string;
  definition: string;
  strength: number;
  confidence: number;
  origin: string;
  review_status: string;
  is_interpretation: boolean;
  is_spoiler: boolean;
  taxonomy_version: string;
  source: string;
}

export interface WorkRelationship {
  label: string;
  type: string;
  factual: boolean;
  slug: string;
  title: string;
  medium: string;
  release_year: number | null;
  note: string | null;
  confidence: number;
  origin: string;
  review_status: string;
  is_spoiler: boolean;
}

export interface Work {
  slug: string;
  medium: string;
  title: string;
  original_title: string | null;
  original_language: string | null;
  countries: string[];
  release_year: number | null;
  summary: string | null;
  summary_spoiler: string | null;
  runtime_minutes: number | null;
  page_count: number | null;
  playtime_hours: number | null;
  length_is_estimate: boolean;
  popularity_tier: number | null;
  attributes: Record<string, unknown>;
  advisories_assessed: boolean;
  updated_at: string;
  credits: { role: string; name: string; kind: string; source: string }[];
  classifications: Classification[];
  relationships: WorkRelationship[];
  provenance: { field: string; value: unknown; source: string; source_name: string; observed: string }[];
  sources: { slug: string; name: string; kind: string; notes: string | null }[];
}

export type FeedbackKind =
  | "relevant"
  | "irrelevant"
  | "too_long"
  | "wrong_mood"
  | "already_experienced"
  | "not_what_i_meant"
  | "will_try";
