"use client";
/* Client-only local journey progress is hydrated from session storage. */
/* eslint-disable react-hooks/set-state-in-effect */

import { useCallback, useEffect, useState } from "react";
import {
  journeyProgressKey,
  journeyVisitsKey,
  parseJourneyProgress,
  parseJourneyVisits,
  type JourneyChapter,
  type JourneyProgress,
} from "@/lib/journey";

export function useJourneyProgress(regionId?: string) {
  const [progress, setProgress] = useState<JourneyProgress>({});
  const [visited, setVisited] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    try {
      setProgress(
        parseJourneyProgress(
          JSON.parse(localStorage.getItem(journeyProgressKey) ?? "{}"),
        ),
      );
      const visits = parseJourneyVisits(
        JSON.parse(localStorage.getItem(journeyVisitsKey) ?? "[]"),
      );
      setVisited(
        regionId && !visits.includes(regionId) ? [...visits, regionId] : visits,
      );
    } catch {
      if (regionId) setVisited([regionId]);
    }
    setLoaded(true);
    const sync = (event: StorageEvent) => {
      try {
        if (event.key === journeyProgressKey)
          setProgress(parseJourneyProgress(JSON.parse(event.newValue ?? "{}")));
        if (event.key === journeyVisitsKey)
          setVisited(parseJourneyVisits(JSON.parse(event.newValue ?? "[]")));
      } catch {
        /* Keep this tab's progress if another tab writes invalid data. */
      }
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [regionId]);
  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(journeyProgressKey, JSON.stringify(progress));
      localStorage.setItem(journeyVisitsKey, JSON.stringify(visited));
    } catch {
      /* Exploration also works without persistent storage. */
    }
  }, [progress, visited, loaded]);
  const visitChapter = useCallback((id: string, chapter: JourneyChapter) => {
    setProgress((current) =>
      current[id]?.includes(chapter)
        ? current
        : { ...current, [id]: [...(current[id] ?? []), chapter] },
    );
    setVisited((current) =>
      current.includes(id) ? current : [...current, id],
    );
  }, []);
  return { progress, visited, loaded, visitChapter };
}
