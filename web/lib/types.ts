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

export interface TagRef {
  key: string;
  label: string;
}

export interface GuideFlag {
  group: string;
  label: string;
  severity: Severity;
}

export type Severity = "None" | "Mild" | "Moderate" | "Severe" | "Not assessed";

/** A work as shown in lists: browse results, tag pages, person pages. */
export interface WorkCard {
  slug: string;
  title: string;
  original_title: string | null;
  medium: string;
  year: number | null;
  length: string | null;
  creators: string[];
  summary: string | null;
  genres: TagRef[];
  tags: TagRef[];
  ratings: { system: string; rating: string }[];
  guide_flags: GuideFlag[];
  strength?: number; // tag pages
  roles?: string[]; // person pages
}

export interface FacetValue {
  value: string | number;
  label: string;
  count: number;
}

export interface BrowseResponse {
  total: number;
  results: WorkCard[];
  facets: Record<"medium" | "decade" | "language" | "genre" | "theme" | "mood", FacetValue[]>;
}

export interface TagIndexGroup {
  dimension: string;
  label: string;
  terms: (TagRef & { count: number })[];
}

export interface TagPage {
  key: string;
  label: string;
  definition: string;
  dimension: string;
  dimension_label: string;
  applies_to: string[];
  works: WorkCard[];
  related: (TagRef & { count: number })[];
}

export interface PersonSummary {
  slug: string;
  name: string;
  kind: "person" | "organisation";
  roles: string[];
  count: number;
}

export interface PersonPage {
  slug: string;
  name: string;
  kind: "person" | "organisation";
  roles: string[];
  works: WorkCard[];
  recurring_tags: (TagRef & { count: number })[];
}

export interface GuideItem {
  key: string;
  label: string;
  definition: string;
  assessed: boolean;
  level: number | null;
  severity: Severity;
  note: string | null;
  spoiler_note: string | null;
  basis: Basis | null;
}

export interface ParentsGuide {
  ratings: { system: string; rating: string; reason: string | null }[];
  assessed: boolean;
  groups: { slug: string; label: string; severity: Severity; partial: boolean; items: GuideItem[] }[];
}

export interface Work {
  slug: string;
  medium: string;
  title: string;
  original_title: string | null;
  original_language: string | null;
  countries: string[];
  year: number | null;
  summary: string | null;
  length: string | null;
  runtime_minutes: number | null;
  playtime_hours: number | null;
  length_is_estimate: boolean;
  popularity_tier: number | null;
  attributes: Record<string, unknown>;
  credits: { role: string; name: string; kind: string; slug: string }[];
  tags: {
    dimension: string;
    label: string;
    terms: { key: string; label: string; definition: string; strength: number; confidence: number; basis: Basis }[];
  }[];
  parents_guide: ParentsGuide;
  relationships: {
    label: string;
    type: string;
    factual: boolean;
    slug: string;
    title: string;
    medium: string;
    year: number | null;
    note: string | null;
    confidence: number;
  }[];
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
