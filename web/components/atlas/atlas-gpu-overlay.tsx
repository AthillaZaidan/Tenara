"use client";
/* Bridge refs connect imperative DOM marker positioning to the GPU camera. */
/* eslint-disable react-hooks/immutability */

import { atlasLabels, atlasProject } from "./atlas-layout";
import { exploreRegions } from "@/lib/exploration";

export type AtlasBridgeRef = { current: AtlasGpuBridge };
export type AtlasGpuBridge = {
  buttons: (HTMLButtonElement | null)[];
  lines: (SVGLineElement | null)[];
  dots: (SVGCircleElement | null)[];
  focus?: (x: number, y: number) => void;
};

export function AtlasGpuOverlay({ bridge, selected, onSelect }: { bridge: AtlasBridgeRef; selected: string; onSelect: (id: string) => void }) {
  return <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-label="Daerah tujuan di peta Indonesia">
    <svg className="absolute inset-0 h-full w-full" aria-hidden="true">{exploreRegions.map((region, i) => <g key={region.id}><line ref={(node) => { bridge.current.lines[i] = node; }} stroke="#304729" strokeOpacity=".65" strokeWidth="1" /><circle ref={(node) => { bridge.current.dots[i] = node; }} r="3" fill="#5f4228" /></g>)}</svg>
    {exploreRegions.map((region, i) => <button key={region.id} ref={(node) => { bridge.current.buttons[i] = node; }} className={`pointer-events-auto absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 px-3 py-2 text-xs font-semibold shadow-md transition-colors sm:text-sm ${selected === region.id ? "bg-[#5f4228] text-white" : "bg-[#3d5a33] text-white hover:bg-[#5f4228]"}`} aria-pressed={selected === region.id} aria-label={`Jelajahi ${region.name}`} onClick={() => onSelect(region.id)} onFocus={(event) => { if (event.currentTarget.matches(":focus-visible")) { const [x, y] = atlasProject(region.coordinates); bridge.current.focus?.(x, y); } }}>{atlasLabels[region.id]?.name ?? region.name}</button>)}
  </div>;
}
