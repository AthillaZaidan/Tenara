"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { WorldTransition } from "./use-world-navigation";
import {
  CLOUD_CLOSE_MS,
  CLOUD_OPEN_MS,
  SLIDE_CLOSE_MS,
  SLIDE_OPEN_MS,
} from "./use-world-navigation";

export function WorldTransitionStage({
  transition,
  instant,
  children,
}: {
  transition: WorldTransition;
  instant: boolean;
  children: ReactNode;
}) {
  const root = useRef<THREE.Group>(null),
    started = useRef(0);
  useLayoutEffect(() => {
    started.current = performance.now();
    if (root.current && transition.phase === "in" && !instant) {
      const slide = transition.kind === "slide";
      root.current.position.set(
        transition.direction * (slide ? 18 : 25),
        slide ? 0 : -1.1,
        0,
      );
      root.current.rotation.y = transition.direction * (slide ? 0.06 : 0.24);
      root.current.scale.setScalar(slide ? 0.96 : 0.78);
    }
  }, [transition.phase, transition.sequence, transition.direction, transition.kind, instant]);
  useFrame(() => {
    if (!root.current) return;
    root.current.visible = transition.phase !== "covered";
    if (instant || transition.phase === "idle") {
      root.current.position.set(0, 0, 0);
      root.current.rotation.y = 0;
      root.current.scale.setScalar(1);
      return;
    }
    const t = Math.min(
      1,
      (performance.now() - started.current) /
        (transition.phase === "out"
          ? transition.kind === "slide"
            ? SLIDE_CLOSE_MS
            : CLOUD_CLOSE_MS
          : transition.kind === "slide"
            ? SLIDE_OPEN_MS
            : CLOUD_OPEN_MS),
    );
    const slide = transition.kind === "slide";
    const ease =
      transition.phase === "out"
        ? slide
          ? t * t
          : t * t * t
        : 1 - Math.pow(1 - t, slide ? 3 : 4);
    const amount = transition.phase === "out" ? ease : 1 - ease;
    root.current.position.set(
      (transition.phase === "out" ? -1 : 1) *
        transition.direction *
        (slide ? 18 : 25) *
        amount,
      slide ? 0 : -1.1 * amount,
      0,
    );
    root.current.rotation.y =
      (transition.phase === "out" ? -1 : 1) *
      transition.direction *
      (slide ? 0.06 : 0.24) *
      amount;
    root.current.scale.setScalar(1 - amount * (slide ? 0.04 : 0.22));
  });
  return (
    <group ref={root} name="world-transition-stage">
      {children}
    </group>
  );
}
