"use client";

import { useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { RegionId } from "@/lib/exploration";
import { RegionalLand } from "./regional-land";
import { LandscapeGarden, RegionalArchitecture } from "./diorama-models";

function Ready({ onReady }: { onReady: () => void }) {
  useEffect(() => { onReady(); }, [onReady]);
  return null;
}

function ContextMonitor({ onFailure }: { onFailure: () => void }) {
  const canvas = useThree((state) => state.gl.domElement);
  useEffect(() => {
    const lost = (event: Event) => { event.preventDefault(); onFailure(); };
    canvas.addEventListener("webglcontextlost", lost);
    return () => canvas.removeEventListener("webglcontextlost", lost);
  }, [canvas, onFailure]);
  return null;
}

export default function RegionalDiorama({ region, rotation, onReady, onFailure }: { region: RegionId; rotation: number; onReady: () => void; onFailure: () => void }) {
  return <Canvas frameloop="demand" shadows dpr={[1, 1.5]} camera={{ position: [12, 12, 15], fov: 40, near: 0.1, far: 100 }} gl={{ alpha: true, antialias: true, powerPreference: "low-power" }} fallback={null} style={{ touchAction: "pan-y" }}>
    <ambientLight intensity={1.7} />
    <ContextMonitor onFailure={onFailure} />
    <directionalLight position={[5, 12, 8]} intensity={2.5} castShadow shadow-mapSize={[1024, 1024]} />
    <group rotation={[0, rotation, 0]}>
      <RegionalLand id={region} />
      <group position={[0, 0.9, 0]}><RegionalArchitecture id={region} lowGraphics /></group>
      <LandscapeGarden id={region} lowGraphics />
    </group>
    <OrbitControls target={[0, 0.6, 0]} enablePan={false} minDistance={12} maxDistance={28} maxPolarAngle={Math.PI / 2.15} />
    <Ready onReady={onReady} />
  </Canvas>;
}
