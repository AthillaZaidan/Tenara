"use client";

import { ArrowLeft, ChevronLeft, ChevronRight, Map } from "lucide-react";
import { exploreRegions, type ExploreRegion } from "@/lib/exploration";
import { MapButton } from "./map-button";

function Flourish({ flip = false }: { flip?: boolean }) {
  return (
    <svg
      viewBox="0 0 100 78"
      className={`nx-preview-flourish ${flip ? "is-flipped" : ""}`}
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M83 67C44 59 28 36 20 12M81 66C55 60 39 58 12 63M65 57C62 40 58 29 40 23M49 46C42 32 42 18 50 8"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        d="M22 37C8 36 3 27 8 20c13-1 20 4 20 15ZM38 52C19 50 14 45 16 37c13-4 21 3 22 15Zm16 8C32 72 18 74 9 68c6-12 23-14 45-8Zm-7-37C37 11 40 1 48 1c8 8 10 14-1 22Zm16 18c-4-18 4-25 11-22 4 11-2 18-11 22Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function WorldPreview({
  region,
  percent,
  switching,
  onEnter,
  onCycle,
  onSelect,
  onMap,
}: {
  region: ExploreRegion;
  percent: number;
  switching: boolean;
  onEnter: () => void;
  onCycle: (direction: number) => void;
  onSelect: (id: string) => void;
  onMap: () => void;
}) {
  return (
    <>
      <MapButton
        className="nx-preview-back"
        icon={<ArrowLeft size={15} />}
        onClick={onMap}
        disabled={switching}
      >
        <Map size={15} />
        Peta Nusantara
      </MapButton>
      <div
        className={`nx-world-preview ${region.name.length > 10 ? "nx-preview-long" : ""}`}
        role="group"
        aria-roledescription="carrousel"
        aria-label={`Jelajahi ${region.name}`}
        onKeyDown={(event) => {
          if (
            !switching &&
            (event.key === "ArrowLeft" || event.key === "ArrowRight")
          ) {
            event.preventDefault();
            onCycle(event.key === "ArrowRight" ? 1 : -1);
          }
        }}
      >
        <span
          className={`nx-preview-progress ${percent === 100 ? "is-complete" : ""}`}
        >
          <i style={{ width: `${percent}%` }} />
          <b>{percent}% cerita dijelajahi</b>
        </span>
        <div className="nx-preview-name">
          <Flourish />
          <h1>{region.name}</h1>
          <Flourish flip />
        </div>
        <p>{region.tagline}</p>
        <svg
          className="nx-preview-divider"
          viewBox="0 0 230 20"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M0 10h85m60 0h85M115 1l9 9-9 9-9-9 9-9Zm-22 6 3 3-3 3-3-3 3-3Zm44 0 3 3-3 3-3-3 3-3Z"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path d="m115 6 4 4-4 4-4-4 4-4Z" fill="currentColor" />
        </svg>
        <div className="nx-preview-navigation">
          <MapButton
            variant="icon"
            icon={<ChevronLeft size={20} />}
            aria-label="Daerah sebelumnya"
            disabled={switching}
            onClick={() => onCycle(-1)}
          />
          <MapButton
            className="nx-enter-region"
            disabled={switching}
            onClick={onEnter}
          >
            Jelajahi daerah ini
          </MapButton>
          <MapButton
            variant="icon"
            icon={<ChevronRight size={20} />}
            aria-label="Daerah berikutnya"
            disabled={switching}
            onClick={() => onCycle(1)}
          />
        </div>
      </div>
      <nav className="nx-world-pagination" aria-label="Pilih daerah">
        {exploreRegions.map((item) => (
          <button
            key={item.id}
            aria-label={`Lihat ${item.name}`}
            aria-current={region.id === item.id ? "true" : undefined}
            disabled={switching}
            onClick={() => onSelect(item.id)}
          >
            <span />
          </button>
        ))}
      </nav>
    </>
  );
}
