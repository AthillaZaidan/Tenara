import { exploreRegions } from "./exploration";

export const journeyChapters = ["culture", "weaving", "textiles"] as const;
export type JourneyChapter = (typeof journeyChapters)[number];
export type JourneyProgress = Record<string, JourneyChapter[]>;
export const chapterLabels: Record<JourneyChapter, string> = {
  culture: "Budaya",
  weaving: "Tradisi Tenun",
  textiles: "Kain Daerah",
};
export const journeyProgressKey = "tenara-journey-chapters-v1";
export const journeyVisitsKey = "tenara-journey-regions-v1";

export function parseJourneyProgress(value: unknown): JourneyProgress {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const result: JourneyProgress = {};
  for (const region of exploreRegions) {
    const chapters = (value as Record<string, unknown>)[region.id];
    if (Array.isArray(chapters))
      result[region.id] = journeyChapters.filter((id) => chapters.includes(id));
  }
  return result;
}

export function parseJourneyVisits(value: unknown): string[] {
  return Array.isArray(value)
    ? exploreRegions
        .filter((region) => value.includes(region.id))
        .map((region) => region.id)
    : [];
}

export const regionProgress = (progress: JourneyProgress, id: string) =>
  Math.round(((progress[id]?.length ?? 0) / journeyChapters.length) * 100);
