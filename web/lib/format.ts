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
