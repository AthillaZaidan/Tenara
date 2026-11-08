"use client";

import { useEffect, useState } from "react";

/** A run-on sentence of real region names; one is lit at a time. */
export function LitNames({ names }: { names: string[] }) {
  const [on, setOn] = useState(0);
  useEffect(() => {
    if (names.length < 2 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setOn((i) => (i + 1) % names.length), 2000);
    return () => clearInterval(t);
  }, [names.length]);
  return (
    <>
      {names.map((n, i) => (
        <span key={n} style={{ transition: "color .4s", color: i === on ? "var(--ink)" : "var(--muted)" }}>
          {n}
          {i < names.length - 1 ? ", " : "."}{" "}
        </span>
      ))}
    </>
  );
}
