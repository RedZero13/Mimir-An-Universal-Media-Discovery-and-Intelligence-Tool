const MEDIUM_LABELS: Record<string, string> = {
  film: "Film",
  series: "Series",
  episode: "Episode",
  book: "Book",
  comic: "Comic",
  game: "Game",
  album: "Album",
  track: "Track",
  podcast: "Podcast",
  online_video: "Video",
  channel: "Channel",
};

export const mediumLabel = (m: string) => MEDIUM_LABELS[m] ?? m;

export const BASIS_LABELS = {
  catalogue: { short: "Catalogue", title: "Recorded catalogue data (pilot data: not yet verified against primary sources)" },
  interpretation: { short: "Interpretation", title: "An AI-assisted interpretation that hasn't been reviewed by an editor yet" },
  reviewed_interpretation: { short: "Reviewed", title: "An interpretation reviewed by an editor" },
} as const;

export const DIMENSION_LABELS: Record<string, string> = {
  genre: "Genre",
  theme: "Themes",
  mood: "Mood & experience",
  pacing: "Pacing",
  complexity: "Complexity",
  narrative: "Narrative",
  world: "World & setting",
  style: "Style & craft",
  advisory: "Content advisories",
};

export function intensity(strength: number): string {
  if (strength >= 0.8) return "strong";
  if (strength >= 0.55) return "clear";
  if (strength >= 0.4) return "partial";
  if (strength > 0) return "slight";
  return "none";
}

export function termLabel(key: string): string {
  const slug = key.split(":")[1] ?? key;
  return slug.replace(/-/g, " ");
}

export const tagHref = (key: string) => `/tags/${key.replace(":", "/")}`;

/** Advisory filters offered on the browse page, in parents' guide order. */
export const AVOID_OPTIONS: { key: string; label: string }[] = [
  { key: "advisory:sexual-content", label: "Sex & nudity" },
  { key: "advisory:graphic-violence", label: "Graphic violence" },
  { key: "advisory:body-horror", label: "Body horror" },
  { key: "advisory:atrocity", label: "Atrocity" },
  { key: "advisory:strong-language", label: "Strong language" },
  { key: "advisory:substance-use", label: "Alcohol, drugs & smoking" },
  { key: "advisory:jump-scares", label: "Frightening scenes" },
  { key: "advisory:suicide-self-harm", label: "Suicide & self-harm" },
];

export const LANGUAGE_LABELS: Record<string, string> = {
  en: "English", ja: "Japanese", ru: "Russian", ko: "Korean", de: "German", pl: "Polish", it: "Italian", fr: "French",
  be: "Belarusian", es: "Spanish",
};
export const languageLabel = (code: string) => LANGUAGE_LABELS[code] ?? code;
