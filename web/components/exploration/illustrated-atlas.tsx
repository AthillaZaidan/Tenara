"use client";
/* SVG fallback camera hydrates geography and synchronizes pan/zoom interaction state. */
/* eslint-disable react-hooks/set-state-in-effect */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
  type CSSProperties,
} from "react";
import { ArrowLeftRight, RotateCcw } from "lucide-react";
import { exploreRegions } from "@/lib/exploration";
import { AtlasArt, AtlasOrnaments } from "./atlas-art";
import { MapButton, MapIcon } from "./map-button";

import {
  ATLAS_WIDTH as WIDTH,
  ATLAS_HEIGHT as HEIGHT,
  atlasProject as project,
  atlasRandom as random,
  atlasLabels as labels,
  atlasLabelNudge,
  atlasLandscape as buildLandscape,
  atlasIslands,
  type AtlasPoint as Point,
  type AtlasIsland as Island,
  type GeoDocument,
} from "./atlas-layout";
type AtlasProps = {
  selectedRegion: string;
  onSelectRegion: (id: string) => void;
  onHoverRegion: (id: string) => void;
  onReady: () => void;
  zoom: number;
  setZoom: (zoom: number) => void;
  reset: number;
  paused: boolean;
  reducedMotion: boolean;
  lowGraphics: boolean;
  timeOfDay: "day" | "sunset";
  visited: string[];
};

export function IllustratedAtlas(props: AtlasProps) {
  const { onReady, zoom, setZoom, reset, lowGraphics } = props;
  const [islands, setIslands] = useState<Island[]>([]),
    [error, setError] = useState(false),
    [retry, setRetry] = useState(0);
  const [pan, setPan] = useState({ x: 0, y: 0 }),
    [width, setWidth] = useState(1600),
    [dragging, setDragging] = useState(false),
    [hidden, setHidden] = useState(false);
  const svg = useRef<SVGSVGElement>(null),
    viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    id: number;
    x: number;
    y: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const suppressClickUntil = useRef(0);
  const baseZoom = Math.max(1, Math.min(2.8, 1000 / width));
  const scale = zoom * baseZoom;
  const bounded = useCallback(
    (x: number, y: number) => {
      const maxX = Math.max(30, WIDTH / 2 - WIDTH / (2 * scale) + 35);
      const maxY = Math.max(20, HEIGHT / 2 - HEIGHT / (2 * scale) + 20);
      return {
        x: Math.max(-maxX, Math.min(maxX, x)),
        y: Math.max(-maxY, Math.min(maxY, y)),
      };
    },
    [scale],
  );

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    fetch("/assets/exploration/indonesia.geo.json", {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Geography unavailable");
        const data = (await response.json()) as GeoDocument;
        const shapes = atlasIslands(data);
        if (!shapes.length) throw new Error("Empty geography");
        setIslands(shapes);
        onReady();
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          onReady();
        }
      });
    return () => controller.abort();
  }, [onReady, retry]);
  useEffect(() => {
    if (!viewport.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    observer.observe(viewport.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setPan({ x: 0, y: 0 });
  }, [reset]);
  useEffect(() => {
    setPan((p) => bounded(p.x, p.y));
  }, [bounded]);
  useEffect(() => {
    const visibility = () => setHidden(document.hidden);
    visibility();
    document.addEventListener("visibilitychange", visibility);
    return () => document.removeEventListener("visibilitychange", visibility);
  }, []);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom(Math.min(2.4, Math.max(0.7, zoom - event.deltaY * 0.0015)));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [zoom, setZoom]);

  const landscape = useMemo(
    () => buildLandscape(islands, lowGraphics),
    [islands, lowGraphics],
  );
  const landPath = useMemo(
    () => islands.map((island) => island.path).join(""),
    [islands],
  );
  const animate = !(props.paused || props.reducedMotion || hidden);
  const screenPoint = (clientX: number, clientY: number) => {
    const matrix = svg.current?.getScreenCTM();
    return matrix
      ? new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse())
      : null;
  };
  const startDrag = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 || (event.target as Element).closest("button"))
      return;
    const point = screenPoint(event.clientX, event.clientY);
    if (!point) return;
    // Capture only once a drag is established, preserving normal island clicks.
    drag.current = {
      id: event.pointerId,
      x: point.x,
      y: point.y,
      startX: pan.x,
      startY: pan.y,
      moved: false,
    };
  };
  const moveDrag = (event: PointerEvent<SVGSVGElement>) => {
    const current = drag.current;
    if (!current || current.id !== event.pointerId) return;
    const point = screenPoint(event.clientX, event.clientY);
    if (!point) return;
    if (Math.hypot(point.x - current.x, point.y - current.y) > 8) {
      current.moved = true;
      svg.current?.setPointerCapture(event.pointerId);
      setDragging(true);
    }
    if (current.moved)
      setPan(
        bounded(
          current.startX + (point.x - current.x) / scale,
          current.startY + (point.y - current.y) / scale,
        ),
      );
  };
  const endDrag = (event: PointerEvent<SVGSVGElement>) => {
    if (drag.current?.id !== event.pointerId) return;
    if (drag.current.moved) suppressClickUntil.current = Date.now() + 250;
    drag.current = null;
    setDragging(false);
    if (svg.current?.hasPointerCapture(event.pointerId))
      svg.current.releasePointerCapture(event.pointerId);
  };

  return (
    <div
      className="nx-illustrated-atlas"
      data-animated={animate}
      data-quality={lowGraphics ? "low" : "high"}
      data-light={props.timeOfDay}
    >
      <svg
        className="nx-atlas-ocean-texture"
        width="100%"
        height="100%"
        aria-hidden="true"
      >
        <filter id="atlas-ocean-grain">
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
          filter="url(#atlas-ocean-grain)"
          opacity=".2"
        />
      </svg>
      <AtlasOrnaments />
      <div
        className="nx-atlas-viewport"
        ref={viewport}
        data-dragging={dragging}
        tabIndex={0}
        role="group"
        aria-label="Peta Indonesia. Geser peta atau gunakan tombol panah. Pilih penanda untuk menjelajahi daerah."
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          const direction: Record<string, Point> = {
            ArrowLeft: [70, 0],
            ArrowRight: [-70, 0],
            ArrowUp: [0, 50],
            ArrowDown: [0, -50],
          };
          if (direction[event.key]) {
            event.preventDefault();
            const [x, y] = direction[event.key];
            setPan((p) => bounded(p.x + x, p.y + y));
          }
          if (event.key === "Home") {
            event.preventDefault();
            setPan({ x: 0, y: 0 });
            setZoom(1);
          }
        }}
      >
        <svg
          ref={svg}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio={width < 900 ? "xMidYMid meet" : "xMidYMin meet"}
          className="nx-atlas-scene"
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onLostPointerCapture={() => {
            drag.current = null;
            setDragging(false);
          }}
          role="group"
          aria-label="Kepulauan Nusantara"
        >
          <AtlasArt />
          <defs>
            <clipPath id="atlas-land-clip">
              <path d={landPath} />
            </clipPath>
          </defs>
          <g
            className="nx-atlas-camera"
            style={{
              transform: `translate(${WIDTH / 2}px, ${HEIGHT / 2}px) scale(${scale}) translate(${-WIDTH / 2 + pan.x}px, ${-HEIGHT / 2 + pan.y}px)`,
            }}
          >
            <g aria-hidden="true" className="nx-atlas-sea-life">
              <text
                className="nx-atlas-sea-name"
                x="405"
                y="535"
                transform="rotate(8 405 535)"
              >
                Samudra Hindia
              </text>
              <text
                className="nx-atlas-sea-name"
                x="1160"
                y="420"
                transform="rotate(7 1160 420)"
              >
                Laut Banda
              </text>
              {[
                [170, 400],
                [470, 500],
                [1030, 530],
                [1400, 510],
                [1150, 150],
                [400, 230],
                [680, 80],
              ].map(([x, y], i) => (
                <g key={i} transform={`translate(${x} ${y})`}>
                  <use
                    className="nx-atlas-wave"
                    href="#atlas-wave-shape"
                    style={{ animationDelay: `${i * -1.7}s` }}
                  />
                </g>
              ))}
              {[
                [270, 442, 0.88],
                [970, 346, 0.58],
                [670, 552, 0.62],
              ].map(([x, y, size], i) => (
                <g key={i} transform={`translate(${x} ${y}) scale(${size})`}>
                  <g className={`nx-atlas-boat nx-atlas-boat-${i}`}>
                    <path
                      className="nx-atlas-wake"
                      d="M-69 9q18 7 37 0M-80 14q25 10 54 0M-61 19q16 5 31 0"
                      fill="none"
                      stroke="#e6ecd0"
                      strokeWidth="1.5"
                      opacity=".65"
                    />
                    <use href="#atlas-boat-shape" />
                  </g>
                </g>
              ))}
              <g
                fill="none"
                stroke="#fff5d5"
                strokeWidth="2"
                strokeLinecap="round"
              >
                {[0, 1, 2, 3, 4].map((i) => (
                  <path
                    key={i}
                    className="nx-atlas-bird"
                    style={{ animationDelay: `${i * -0.8}s` }}
                    d={`m${550 + i * 17} ${140 - (i % 3) * 12}q3-7 8-3 3-7 8-6`}
                  />
                ))}
              </g>
              <g fill="#e6e6bc" opacity=".5">
                {Array.from({ length: 22 }, (_, i) => (
                  <ellipse
                    key={i}
                    cx={1230 + random(i, 21) * 100}
                    cy={510 + random(i, 22) * 35}
                    rx="3"
                    ry=".8"
                    transform={`rotate(-22 ${1230 + random(i, 21) * 100} ${510 + random(i, 22) * 35})`}
                  />
                ))}
              </g>
            </g>
            <g
              aria-hidden="true"
              filter={lowGraphics ? undefined : "url(#atlas-island-shadow)"}
            >
              <path
                d={landPath}
                transform="translate(0 16)"
                fill="#74c5b5"
                stroke="#a1d4b8"
                strokeWidth="9"
                opacity=".65"
              />
              <path
                d={landPath}
                transform="translate(0 11)"
                fill="url(#atlas-cliff)"
                stroke="#d5ac69"
                strokeWidth="3"
                strokeLinejoin="round"
              />
              <path
                d={landPath}
                transform="translate(0 5)"
                fill="#f4d598"
                stroke="#ffe5ac"
                strokeWidth="3"
                strokeLinejoin="round"
              />
              <path
                d={landPath}
                fill="url(#atlas-land)"
                stroke="#f8dfa0"
                strokeWidth="2.5"
                strokeLinejoin="round"
              />
            </g>
            <g
              clipPath="url(#atlas-land-clip)"
              aria-hidden="true"
              pointerEvents="none"
            >
              <rect width={WIDTH} height={HEIGHT} fill="url(#atlas-grass)" />
              {Array.from({ length: 46 }, (_, i) => (
                <ellipse
                  key={i}
                  cx={70 + random(i, 31) * 1450}
                  cy={70 + random(i, 32) * 430}
                  rx={35 + random(i, 33) * 65}
                  ry={12 + random(i, 34) * 20}
                  fill={
                    i % 3 === 0
                      ? "#ded181"
                      : i % 3 === 1
                        ? "#547f40"
                        : "#bed16d"
                  }
                  opacity=".24"
                />
              ))}
              <path
                d="M643 130q-40 35-15 70t-7 78q-18 15-11 29"
                stroke="#e5e8ba"
                strokeWidth="9"
                fill="none"
              />
              <path
                d="M643 130q-40 35-15 70t-7 78q-18 15-11 29"
                stroke="#71bfc0"
                strokeWidth="5"
                fill="none"
              />
              <path
                d="M328 294q-23 9-4 20t-3 23"
                stroke="#d2dc9e"
                strokeWidth="6"
                fill="none"
              />
              <path
                d={landPath}
                fill="none"
                stroke="#f0dc94"
                strokeWidth="6"
                opacity=".45"
              />
            </g>
            <g
              aria-hidden="true"
              pointerEvents="none"
              className="nx-atlas-landscape"
            >
              {landscape.map((item, i) => (
                <use
                  key={i}
                  href={`#atlas-${item.symbol}`}
                  transform={`translate(${item.x.toFixed(1)} ${item.y.toFixed(1)}) scale(${item.flip ? -item.scale : item.scale} ${item.scale})`}
                />
              ))}
            </g>
            <path
              d={landPath}
              fill="transparent"
              className="nx-atlas-land-hit"
              aria-hidden="true"
              onClick={(event) => {
                if (Date.now() < suppressClickUntil.current) return;
                const p = screenPoint(event.clientX, event.clientY);
                if (!p) return;
                const point = [
                  (p.x - WIDTH / 2) / scale + WIDTH / 2 - pan.x,
                  (p.y - HEIGHT / 2) / scale + HEIGHT / 2 - pan.y,
                ];
                const nearest = exploreRegions
                  .map((region) => ({
                    region,
                    distance: Math.hypot(
                      project(region.coordinates)[0] - point[0],
                      project(region.coordinates)[1] - point[1],
                    ),
                  }))
                  .sort((a, b) => a.distance - b.distance)[0];
                if (nearest.distance < 125)
                  props.onSelectRegion(nearest.region.id);
              }}
            />
            <g
              aria-hidden="true"
              pointerEvents="none"
              className="nx-atlas-clouds"
            >
              {[
                [320, 95, 1.05],
                [760, 65, 0.8],
                [1190, 102, 1],
                [1440, 480, 0.7],
                [330, 565, 0.65],
              ].map(([x, y, size], i) => (
                <g key={i} transform={`translate(${x} ${y}) scale(${size})`}>
                  <use
                    href="#atlas-cloud-shape"
                    className="nx-atlas-cloud"
                    style={{
                      animationDelay: `${i * -6}s`,
                      animationDuration: `${24 + i * 4}s`,
                    }}
                  />
                </g>
              ))}
            </g>
            <g className="nx-atlas-destinations">
              {exploreRegions.map((region, i) => {
                const [x, y] = project(region.coordinates),
                  label = labels[region.id];
                const [nudgeX, nudgeY] = atlasLabelNudge(
                  region.id,
                  width,
                  scale,
                );
                const centerX = x + label.dx + nudgeX / scale,
                  centerY = y + label.dy + 18 + nudgeY / scale;
                const labelX = centerX - label.width / 2,
                  labelY = centerY - 20 / scale;
                return (
                  <g key={region.id}>
                    <path
                      d={`M${x},${y} L${centerX},${centerY}`}
                      className="nx-atlas-label-line"
                      aria-hidden="true"
                    />
                    <circle
                      cx={x}
                      cy={y}
                      r="4"
                      fill="#fff1c3"
                      stroke="#7e8f45"
                      strokeWidth="1.5"
                      aria-hidden="true"
                    />
                    <foreignObject
                      x={labelX}
                      y={labelY}
                      width={label.width}
                      height={44 / scale}
                      overflow="visible"
                    >
                      <MapButton
                        variant="region"
                        className="map-fallback-destination"
                        icon={<MapIcon name="gem" />}
                        style={
                          {
                            fontSize: `${(width <= 900 ? 12 : 14) / scale}px`,
                            minHeight: `${40 / scale}px`,
                            height: `${40 / scale}px`,
                            padding: `0 ${16 / scale}px`,
                            left: "50%",
                            transform: "translateX(-50%)",
                            "--map-fallback-icon-scale": 1 / scale,
                            "--map-fallback-gap": `${9 / scale}px`,
                          } as CSSProperties
                        }
                        aria-label={`Jelajahi ${region.name}${props.visited.includes(region.id) ? ", sudah dikunjungi" : ""}`}
                        aria-pressed={props.selectedRegion === region.id}
                        onClick={() => {
                          if (Date.now() >= suppressClickUntil.current)
                            props.onSelectRegion(region.id);
                        }}
                        onMouseEnter={() => props.onHoverRegion(region.id)}
                        onFocus={(event) => {
                          props.onHoverRegion(region.id);
                          // Tab navigation brings off-screen destinations into view on phones.
                          if (event.currentTarget.matches(":focus-visible"))
                            setPan(bounded(WIDTH / 2 - x, HEIGHT / 2 - y));
                        }}
                      >
                        {label.name ?? region.name}
                        <span className="nx-sr-only">
                          , tujuan {i + 1} dari 9
                        </span>
                      </MapButton>
                    </foreignObject>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>
      </div>
      <div className="nx-atlas-navigation-hint">
        <ArrowLeftRight size={13} />
        <span>Geser untuk menjelajah · perbesar untuk melihat detail</span>
      </div>
      {error && (
        <div className="nx-atlas-error" role="status">
          <strong>Peta belum berhasil dimuat.</strong>
          <p>Kamu tetap bisa memilih daerah melalui daftar tujuan.</p>
          <button
            className="nx-game-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            <RotateCcw size={14} /> Muat ulang peta
          </button>
        </div>
      )}
      <div className="nx-atlas-sunset" aria-hidden="true" />
    </div>
  );
}
