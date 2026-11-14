"use client";

import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { AtlasGpuWorld } from "./atlas-gpu-world";
import { AtlasGpuOverlay, type AtlasGpuBridge } from "./atlas-gpu-overlay";
import { WorldMotion } from "./world-motion";

class AtlasBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? null : this.props.children; }
}

export function AtlasMap({ selected, onSelect, onFailure }: { selected: string; onSelect: (id: string) => void; onFailure: () => void }) {
  const bridge = useRef<AtlasGpuBridge>({ buttons: Array(9).fill(null), lines: Array(9).fill(null), dots: Array(9).fill(null) });
  const [zoom, setZoom] = useState(1);
  const [reset, setReset] = useState(0);
  const [paused, setPaused] = useState(false);
  const [sunset, setSunset] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const onReady = useCallback(() => {}, []);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return <div className="grid gap-3">
    <div className="nx-atlas-gpu-stage relative h-[52vh] min-h-[340px] overflow-hidden rounded-2xl bg-[#86cbd2] sm:h-[64vh] sm:min-h-[460px]" style={{ "--atlas-safe-top": "3%", "--atlas-safe-bottom": "4%", "--atlas-safe-side": "2%" } as React.CSSProperties}>
      <AtlasBoundary onFailure={onFailure}>
        <Canvas orthographic frameloop={reducedMotion || paused ? "demand" : "always"} dpr={[1, 1.5]} camera={{ position: [0, 0, 1000], zoom: 1, near: 0.1, far: 2000 }} gl={{ alpha: true, antialias: true, powerPreference: "low-power" }} fallback={<div className="p-6">Tampilan interaktif tidak tersedia.</div>}>
          <WorldMotion enabled={!paused && !reducedMotion}>
            <AtlasGpuWorld lowGraphics={false} onReady={onReady} timeOfDay={sunset ? "sunset" : "day"} reducedMotion={reducedMotion} paused={paused} atlas2d={bridge} zoom={zoom} reset={reset} onZoomChange={setZoom} onSelectRegion={onSelect} />
          </WorldMotion>
        </Canvas>
      </AtlasBoundary>
      <AtlasGpuOverlay bridge={bridge} selected={selected} onSelect={onSelect} />
      <p className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-white/80 px-3 py-1 text-xs">Seret peta · scroll untuk zoom · pilih daerah untuk membuka diorama</p>
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <button className="btn btn-quiet" onClick={() => setZoom((value) => Math.max(0.7, value - 0.15))}>Perkecil peta</button>
      <button className="btn btn-quiet" onClick={() => setZoom((value) => Math.min(2.4, value + 0.15))}>Perbesar peta</button>
      <button className="btn btn-quiet" onClick={() => setReset((value) => value + 1)}>Atur posisi awal</button>
      <button className="btn btn-quiet" aria-pressed={paused} onClick={() => setPaused((value) => !value)}>{paused ? "Lanjutkan animasi" : "Jeda animasi"}</button>
      <button className="btn btn-quiet" aria-pressed={sunset} onClick={() => setSunset((value) => !value)}>{sunset ? "Tampilan siang" : "Tampilan senja"}</button>
    </div>
  </div>;
}
