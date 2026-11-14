"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { findExploreRegion, regionHref } from "@/lib/exploration";

export type JourneyView = "preview" | "overview" | "free" | "detail";
export type WorldTransition = {
  phase: "idle" | "preparing" | "out" | "covered" | "in";
  direction: number;
  sequence: number;
  destination?: string;
  kind?: "cloud" | "slide";
  startedAt?: number;
};

export const CLOUD_CLOSE_MS = 640;
export const CLOUD_OPEN_MS = 850;
export const SLIDE_CLOSE_MS = 650;
export const SLIDE_OPEN_MS = 680;

export function useWorldNavigation(
  initialRegionId: string | undefined,
  instant: boolean,
) {
  const [regionId, setRegionId] = useState(() => {
    if (typeof window === "undefined") return initialRegionId;
    if (window.location.pathname === "/galeri") return undefined;
    const id = window.location.pathname.match(
      /^\/galeri\/daerah\/([^/]+)$/,
    )?.[1];
    return id && findExploreRegion(id) ? id : initialRegionId;
  });
  const [view, setView] = useState<JourneyView>(
    regionId ? "preview" : "overview",
  );
  const [transition, setTransition] = useState<WorldTransition>({
    phase: "idle",
    direction: 1,
    sequence: 0,
  });
  const current = useRef(regionId),
    busy = useRef(false),
    sequence = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const pending = useRef<{
    id?: string;
    serial: number;
    direction: number;
    kind: "cloud" | "slide";
    commit: () => void;
    started: boolean;
    completed: boolean;
  } | null>(null);
  const covered = useRef(false);
  const completeSlide = useCallback((serial: number) => {
    const journey = pending.current;
    if (
      !journey ||
      journey.serial !== serial ||
      journey.kind !== "slide" ||
      !journey.started ||
      journey.completed
    )
      return;
    journey.completed = true;
    journey.commit();
    setTransition({
      phase: "in",
      direction: journey.direction,
      sequence: journey.serial,
      destination: journey.id,
      kind: "slide",
    });
    timers.current.push(
      setTimeout(() => {
        if (sequence.current !== journey.serial) return;
        busy.current = false;
        pending.current = null;
        setTransition({
          phase: "idle",
          direction: journey.direction,
          sequence: journey.serial,
          kind: "slide",
        });
      }, SLIDE_OPEN_MS),
    );
  }, []);
  // The destination reports its first rendered frames, including SVG/error fallbacks.
  // Never reveal the new world merely because a fixed loading timeout elapsed.
  const sceneReady = useCallback((id?: string) => {
    const journey = pending.current;
    if (!journey || journey.id !== id) return;
    if (journey.kind === "slide") {
      if (journey.started) return;
      journey.started = true;
      setTransition({
        phase: "out",
        direction: journey.direction,
        sequence: journey.serial,
        destination: id,
        kind: "slide",
        startedAt: performance.now(),
      });
      return;
    }
    if (!covered.current) return;
    covered.current = false;
    timers.current.push(
      setTimeout(() => {
        if (sequence.current !== journey.serial) return;
        setTransition({
          phase: "in",
          direction: journey.direction,
          sequence: journey.serial,
          destination: id,
          kind: journey.kind,
        });
        timers.current.push(
          setTimeout(() => {
            if (sequence.current !== journey.serial) return;
            busy.current = false;
            pending.current = null;
            setTransition({
              phase: "idle",
              direction: journey.direction,
              sequence: journey.serial,
            });
          }, CLOUD_OPEN_MS),
        );
      }, 100),
    );
  }, []);
  const travelTo = useCallback(
    (
      id?: string,
      direction = 1,
      target: JourneyView = "preview",
      history = true,
      slideTransition = false,
    ) => {
      if (id && !findExploreRegion(id)) return;
      if (busy.current && history) return;
      timers.current.forEach(clearTimeout);
      timers.current = [];
      const serial = ++sequence.current;
      pending.current = null;
      covered.current = false;
      const commit = () => {
        current.current = id;
        setRegionId(id);
        setView(id ? target : "overview");
        if (history) {
          const state = {
            ...window.history.state,
            tenaraJourneyView: id ? target : "overview",
          };
          const url = id ? regionHref(id) : "/galeri";
          if (window.location.pathname === url)
            window.history.replaceState(state, "", url);
          else window.history.pushState(state, "", url);
        }
      };
      if (instant || id === current.current) {
        commit();
        busy.current = false;
        setTransition({ phase: "idle", direction, sequence: serial });
        return;
      }
      busy.current = true;
      const kind = slideTransition ? "slide" : "cloud";
      pending.current = {
        id,
        direction,
        serial,
        kind,
        commit,
        started: false,
        completed: false,
      };
      setTransition({
        phase: kind === "slide" ? "preparing" : "out",
        direction,
        sequence: serial,
        destination: id,
        kind,
      });
      if (kind === "slide") return;
      timers.current.push(
        setTimeout(() => {
          covered.current = true;
          commit();
          setTransition({
            phase: "covered",
            direction,
            sequence: serial,
            destination: id,
            kind,
          });
        }, CLOUD_CLOSE_MS),
      );
    },
    [instant],
  );
  const changeView = useCallback((next: JourneyView) => {
    if (busy.current) return;
    setView(next);
    window.history.replaceState(
      { ...window.history.state, tenaraJourneyView: next },
      "",
    );
  }, []);
  useEffect(() => {
    const back = (event: PopStateEvent) => {
      const match = window.location.pathname.match(
        /^\/galeri\/daerah\/([^/]+)$/,
      );
      if (window.location.pathname !== "/galeri" && !match) return;
      const saved = event.state?.tenaraJourneyView;
      travelTo(
        match?.[1],
        -1,
        ["preview", "overview", "free", "detail"].includes(saved)
          ? saved
          : "preview",
        false,
        !!match?.[1] && !!current.current && (!saved || saved === "preview"),
      );
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, [travelTo]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  return {
    regionId,
    view,
    setView: changeView,
    transition,
    travelTo,
    switching: transition.phase !== "idle",
    sceneReady,
    completeSlide,
  };
}
