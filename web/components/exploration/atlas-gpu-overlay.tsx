"use client";
/* Marker refs are positioned by the atlas camera render loop. */
/* eslint-disable react-hooks/immutability */

import type { RefObject } from "react";
import { exploreRegions } from "@/lib/exploration";
import { atlasLabels, atlasProject } from "./atlas-layout";
import { MapButton, MapIcon } from "./map-button";

export type AtlasGpuBridge = {
  buttons: (HTMLButtonElement | null)[];
  lines: (SVGLineElement | null)[];
  dots: (SVGCircleElement | null)[];
  focus?: (x: number, y: number) => void;
};
export function AtlasGpuOverlay({
  bridge,
  selected,
  visited,
  onSelect,
  onHover,
}: {
  bridge: RefObject<AtlasGpuBridge>;
  selected: string;
  visited: string[];
  onSelect: (id: string) => void;
  onHover: (id: string) => void;
}) {
  return (
    <div
      className="nx-gpu-atlas-labels"
      aria-label="Daerah tujuan di peta Indonesia"
    >
      <svg
        className="nx-gpu-atlas-connectors"
        width="100%"
        height="100%"
        aria-hidden="true"
      >
        {exploreRegions.map((region, i) => (
          <g key={region.id}>
            <line
              ref={(node) => {
                bridge.current.lines[i] = node;
              }}
            />
            <circle
              r="3"
              ref={(node) => {
                bridge.current.dots[i] = node;
              }}
            />
          </g>
        ))}
      </svg>
      {exploreRegions.map((region, i) => (
        <MapButton
          key={region.id}
          ref={(node) => {
            bridge.current.buttons[i] = node;
          }}
          variant="region"
          className="nx-gpu-atlas-destination"
          icon={<MapIcon name="gem" />}
          aria-label={`Jelajahi ${region.name}${visited.includes(region.id) ? ", sudah dikunjungi" : ""}`}
          aria-pressed={selected === region.id}
          onClick={() => onSelect(region.id)}
          onMouseEnter={() => onHover(region.id)}
          onFocus={(event) => {
            onHover(region.id);
            if (event.currentTarget.matches(":focus-visible")) {
              const [x, y] = atlasProject(region.coordinates);
              bridge.current.focus?.(x, y);
            }
          }}
        >
          {atlasLabels[region.id].name ?? region.name}
        </MapButton>
      ))}
    </div>
  );
}
