"use client";

import { createContext, useContext, useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";

type MotionState = { time: number; delta: number; enabled: boolean };
const MotionContext = createContext<{ current: MotionState }>({ current: { time: 0, delta: 0, enabled: false } });

export function WorldMotion({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const motion = useRef<MotionState>({ time: 0, delta: 0, enabled });
  useFrame((_, delta) => {
    motion.current.enabled = enabled && !document.hidden;
    motion.current.delta = motion.current.enabled ? Math.min(delta, 0.05) : 0;
    motion.current.time += motion.current.delta;
  }, -100);
  return <MotionContext.Provider value={motion}>{children}</MotionContext.Provider>;
}

export const useWorldMotion = () => useContext(MotionContext);
