import { ArrowLeftRight } from "lucide-react";
import { AtlasOrnaments } from "./atlas-art";

/** Screen-space illustration frame; the world itself is rendered in WebGL. */
export function AtlasFrame({ timeOfDay }: { timeOfDay: "day" | "sunset" }) {
  return (
    <div
      className="nx-illustrated-atlas nx-atlas-gpu-frame"
      data-light={timeOfDay}
    >
      <svg
        className="nx-atlas-ocean-texture"
        width="100%"
        height="100%"
        aria-hidden="true"
      >
        <filter id="atlas-frame-grain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency=".018 .045"
            numOctaves="3"
            stitchTiles="stitch"
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect
          width="100%"
          height="100%"
          filter="url(#atlas-frame-grain)"
          opacity=".2"
        />
      </svg>
      <div className="nx-atlas-sunset" aria-hidden="true" />
    </div>
  );
}

/** Keep the cloth and navigation hint above the full-screen painted world. */
export function AtlasFrameOverlay() {
  return (
    <>
      <AtlasOrnaments />
      <div className="nx-atlas-navigation-hint">
        <ArrowLeftRight size={14} />
        <span className="nx-atlas-desktop-hint">
          Geser untuk menjelajah · scroll untuk melihat lebih dekat
        </span>
        <span className="nx-atlas-touch-hint">
          Geser untuk menjelajah · cubit dua jari untuk zoom
        </span>
      </div>
    </>
  );
}
