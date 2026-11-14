"use client";

import { createContext, useContext } from "react";

// The regional preview is rendered on demand; the decorative scene stays still.
const motion = { current: { time: 0, delta: 0, enabled: false } };
const MotionContext = createContext(motion);
export const useWorldMotion = () => useContext(MotionContext);
