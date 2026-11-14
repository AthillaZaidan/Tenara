"use client";
/* Ported cinematic controller intentionally synchronizes imperative R3F/DOM APIs. */
/* eslint-disable react-hooks/exhaustive-deps, react-hooks/refs, react-hooks/set-state-in-effect */

import dynamic from "next/dynamic";
import {
  Component,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  Compass,
  House,
  Leaf,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import Link from "next/link";
import {
  exploreRegions,
  findExploreRegion,
  textileTraditions,
} from "@/lib/exploration";
import {
  chapterLabels,
  regionProgress,
  type JourneyChapter,
} from "@/lib/journey";
import { FabricDashboard } from "./fabric-dashboard";
import { RegionOverview, RegionStoryPanel } from "./journey-panels";
import { MotifCards } from "./motif-cards";
import { useJourneyProgress } from "./use-journey-progress";
import { SLIDE_CLOSE_MS, useWorldNavigation } from "./use-world-navigation";
import { ViewControls } from "./view-controls";
import { WorldPreview } from "./world-preview";
import { IllustratedAtlas } from "./illustrated-atlas";
import { AtlasFrame, AtlasFrameOverlay } from "./atlas-frame";
import { AtlasGpuOverlay, type AtlasGpuBridge } from "./atlas-gpu-overlay";
import { MapButton, MapButtonLink, MapIcon, MapPassport } from "./map-button";
import { MapDialog, MapDestinationsDialog } from "./map-dialog";
import { RegionSeascape } from "./region-seascape";
import { CloudTransition } from "./cloud-transition";
import { GalleryEntrance, useGalleryEntrance } from "./gallery-entrance";
import { useGalleryAudio } from "./gallery-audio";
import { GalleryAudioControls } from "./gallery-audio-controls";
import "./prototype-foundation.css";
import "./exploration.css";
import "./cinematic.css";
import "./interactions.css";
import "./world-selection.css";
import "./illustrated-atlas.css";
import "./atlas-gpu.css";
import "./map-button.css";
import "./map-dialog.css";
import "./region-seascape.css";
import "./cloud-transition.css";
import "./regional-controls.css";
import "./regional-motion.css";
import "./gallery-entrance.css";
import "./gallery-audio.css";
import "./region-playful.css";
import "./region-preview.css";
import "./region-story.css";

const WorldScene = dynamic(() => import("./world-scene"), { ssr: false });

class WorldBoundary extends Component<
  { children: ReactNode; onFailure: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function JourneyExperience({ regionId }: { regionId?: string }) {
  const atlasBridge = useRef<AtlasGpuBridge>({
    buttons: [],
    lines: [],
    dots: [],
  });
  const [selected, setSelected] = useState(regionId ?? "");
  const [chapter, setChapter] = useState<JourneyChapter>("culture");
  const [ready, setReady] = useState(false),
    [fallback, setFallback] = useState(false),
    [mounted, setMounted] = useState(false);
  const [lowGraphics, setLowGraphics] = useState(false),
    [reducedMotion, setReducedMotion] = useState(false);
  const [zoom, setZoom] = useState(1),
    [reset, setReset] = useState(0),
    [paused, setPaused] = useState(false),
    [greeting, setGreeting] = useState(0);
  const {
    regionId: displayRegionId,
    view: mode,
    setView: setMode,
    transition,
    travelTo,
    switching,
    sceneReady,
    completeSlide,
  } = useWorldNavigation(regionId, reducedMotion || paused);
  const transitionRef = useRef(transition);
  transitionRef.current = transition;
  const region = displayRegionId
    ? findExploreRegion(displayRegionId)
    : undefined;
  const isMap = !region;
  const [settings, setSettings] = useState(false),
    [list, setList] = useState(false),
    [cards, setCards] = useState(false);
  const [motifCards, setMotifCards] = useState(false);
  const motifReturnFocus = useRef<HTMLElement | null>(null);
  const [timeOfDay, setTimeOfDay] = useState<"day" | "sunset">("day");
  const [slideFrames, setSlideFrames] = useState<{
    sequence: number;
    from: string;
    to: string;
  } | null>(null);
  const hasSlideFrames =
    slideFrames?.sequence === transition.sequence &&
    transition.kind === "slide";
  const [discovery, setDiscovery] = useState<{
    text: string;
    key: number;
  } | null>(null);
  const audio = useGalleryAudio();
  const entrance = useGalleryEntrance(
    ready,
    reducedMotion || paused,
    !!regionId,
  );
  const hoveredControl = useRef<Element | null>(null);
  const { progress, visited, visitChapter } = useJourneyProgress(region?.id);
  const active = findExploreRegion(selected) ?? exploreRegions[0];
  const regionIndex = exploreRegions.findIndex(
    (item) => item.id === (region?.id ?? active.id),
  );
  const currentTraditions = textileTraditions.filter(
    (item) => item.regionId === (region?.id ?? active.id),
  );
  const read = region ? (progress[region.id] ?? []) : [];
  const modalOpen = settings || list || cards || motifCards;
  const rightPanel =
    !!region && (mode === "overview" || mode === "detail") && !cards;

  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const motion = () => {
      try {
        const value = localStorage.getItem("tenara-reduced-motion");
        setReducedMotion(value === null ? media.matches : value === "true");
      } catch {
        setReducedMotion(media.matches);
      }
    };
    motion();
    media.addEventListener("change", motion);
    try {
      setLowGraphics(localStorage.getItem("tenara-low-graphics") === "true");
    } catch {
      /* Optional preference. */
    }
    try {
      const canvas = document.createElement("canvas"),
        gl = canvas.getContext("webgl2");
      if (!gl) setFallback(true);
      else gl.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      setFallback(true);
    }
    setMounted(true);
    return () => media.removeEventListener("change", motion);
  }, []);
  const onReady = useCallback(() => {
    setReady(true);
    sceneReady(displayRegionId);
  }, [sceneReady, displayRegionId]);
  const onSlidePrepared = useCallback(
    (id: string, sequence: number, frames: { from: string; to: string }) => {
      setSlideFrames({ sequence, ...frames });
      // Give the compositor a painted starting position before starting the slide.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          if (
            transitionRef.current.sequence === sequence &&
            transitionRef.current.phase === "preparing"
          )
            sceneReady(id);
        }),
      );
    },
    [sceneReady],
  );
  const onSlidePresented = useCallback((sequence: number) => {
    setSlideFrames((current) =>
      current?.sequence === sequence ? null : current,
    );
  }, []);
  useEffect(() => {
    if (slideFrames && slideFrames.sequence !== transition.sequence)
      setSlideFrames(null);
  }, [slideFrames, transition.sequence]);
  useEffect(() => {
    if (transition.kind !== "slide") setReady(false);
  }, [displayRegionId]);
  useEffect(() => {
    if (fallback && !isMap) onReady();
  }, [fallback, isMap, onReady]);
  useEffect(() => {
    if (
      fallback &&
      transition.kind === "slide" &&
      transition.phase === "preparing" &&
      transition.destination
    )
      sceneReady(transition.destination);
  }, [
    fallback,
    transition.kind,
    transition.phase,
    transition.destination,
    sceneReady,
  ]);
  useEffect(() => {
    if (
      (!fallback && !hasSlideFrames) ||
      transition.kind !== "slide" ||
      transition.phase !== "out"
    )
      return;
    const timer = setTimeout(
      () => completeSlide(transition.sequence),
      SLIDE_CLOSE_MS + (hasSlideFrames ? 250 : 0),
    );
    return () => clearTimeout(timer);
  }, [
    fallback,
    hasSlideFrames,
    transition.kind,
    transition.phase,
    transition.sequence,
    completeSlide,
  ]);
  const onFailure = useCallback(() => {
    setFallback(true);
    if (!isMap) onReady();
  }, [isMap, onReady]);
  const onDiscover = useCallback(
    (text: string) => {
      setDiscovery({ text, key: Date.now() });
      audio.play("discover", true);
    },
    [audio.play],
  );
  useEffect(() => {
    if (transition.phase === "out") audio.play("travel");
  }, [transition.phase, transition.sequence, audio.play]);
  useEffect(() => {
    if (entrance.phase === "leaving") audio.play("select");
  }, [entrance.phase, audio.play]);
  const openChapter = useCallback(
    (id: JourneyChapter) => {
      setChapter(id);
      setMode("detail");
      window.history.replaceState(
        { ...window.history.state, tenaraJourneyChapter: id },
        "",
      );
      if (region) visitChapter(region.id, id);
    },
    [region, visitChapter, setMode],
  );
  const closeDetail = useCallback(() => {
    setMode("overview");
    setTimeout(() => {
      (
        document.querySelector<HTMLButtonElement>(
          `button[data-chapter="${chapter}"]`,
        ) ?? document.querySelector<HTMLButtonElement>(".nx-overview-primary")
      )?.focus({ preventScroll: true });
    }, 100);
  }, [chapter, setMode]);
  const openCards = useCallback(() => setCards(true), []);
  const closeCards = useCallback(() => setCards(false), []);
  useEffect(() => {
    if (!discovery) return;
    const timer = setTimeout(() => setDiscovery(null), 4200);
    return () => clearTimeout(timer);
  }, [discovery]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || modalOpen || isMap || entrance.active)
        return;
      if (mode === "detail") closeDetail();
      else if (mode === "free") setMode("overview");
      else if (mode === "overview") setMode("preview");
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [
    mode,
    modalOpen,
    closeDetail,
    isMap,
    setMode,
    entrance.active,
    region?.id,
  ]);
  useEffect(() => {
    const restore = (event: PopStateEvent) => {
      const id = event.state?.tenaraJourneyChapter;
      if (id === "culture" || id === "weaving" || id === "textiles")
        setChapter(id);
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  const selectRegion = useCallback(
    (id: string) => {
      if (!findExploreRegion(id) || switching) return;
      setSelected(id);
      setZoom(1);
      travelTo(id, 1, "preview", true, !isMap && mode === "preview");
    },
    [travelTo, switching, isMap, mode],
  );
  const cycle = (direction: number) => {
    const next =
      exploreRegions[
        (regionIndex + direction + exploreRegions.length) %
          exploreRegions.length
      ].id;
    if (isMap) {
      setSelected(next);
      return;
    }
    setSelected(next);
    setZoom(1);
    travelTo(next, direction, "preview", true, mode === "preview");
  };
  const returnToMap = () => {
    setZoom(1);
    travelTo(undefined, -1);
  };

  return (
    <section
      className={`nx-journey nx-art-v2 nx-reference-ui nx-refined-journey ${isMap ? "nx-is-map" : "nx-is-region"} ${region && region.name.length > 10 ? "nx-long-region" : ""} ${isMap && !fallback ? "nx-has-atlas-2d" : ""} ${!isMap && mode === "preview" ? "nx-is-preview" : ""} ${!isMap && mode === "overview" ? "nx-overview-visible" : ""} ${!isMap && mode === "free" ? "nx-free-explore" : ""} ${mode === "detail" ? "nx-detail-open" : ""} ${rightPanel ? "nx-has-panel" : ""} ${cards ? "nx-dashboard-open" : ""} ${motifCards ? "nx-motif-open" : ""}`}
      data-transition={transition.phase}
      data-transition-kind={transition.kind}
      data-transition-direction={transition.direction}
      data-region={region?.id ?? "indonesia"}
      data-motion={reducedMotion ? "reduced" : paused ? "paused" : "live"}
      data-light={timeOfDay}
      data-entry={entrance.phase}
      data-audio={audio.enabled ? "on" : "off"}
      data-modal-open={modalOpen || undefined}
      onClickCapture={(event) => {
        if (entrance.active || !(event.target instanceof Element)) return;
        const control = event.target.closest(
          'button,a[href],input[type="checkbox"],summary',
        );
        if (
          !control ||
          control.closest('[data-audio="off"]:not(.nx-journey),[inert]') ||
          control.matches(':disabled,[aria-disabled="true"]')
        )
          return;
        const label = control.getAttribute("aria-label")?.toLowerCase() ?? "";
        audio.play(
          control.matches(
            ".nx-gpu-atlas-destination,.map-destination-card,.nx-location-card",
          )
            ? "select"
            : control.matches(
                  ".nx-topic-close,.nx-close-dashboard,.icon-button",
                ) || /^(tutup|kembali)/.test(label)
              ? "close"
              : control.closest(
                    ".nx-topic-stepper,.nx-region-pagination,.nx-world-pagination",
                  )
                ? "step"
                : control.matches(
                      ".map-control--passport,.nx-panel-cards,.nx-open-cards",
                    ) || /^(buka|pilih)/.test(label)
                  ? "open"
                  : "click",
          true,
        );
      }}
      onPointerOverCapture={(event) => {
        if (
          entrance.active ||
          event.pointerType !== "mouse" ||
          !(event.target instanceof Element)
        )
          return;
        const control = event.target.closest("button,a[href],summary");
        if (control === hoveredControl.current) return;
        hoveredControl.current = control;
        if (
          control &&
          !control.closest('[data-audio="off"]:not(.nx-journey),[inert]') &&
          !control.matches(':disabled,[aria-disabled="true"]')
        )
          audio.play("hover");
      }}
      onPointerOutCapture={(event) => {
        if (
          hoveredControl.current &&
          event.relatedTarget instanceof Node &&
          hoveredControl.current.contains(event.relatedTarget)
        )
          return;
        hoveredControl.current = null;
      }}
      onFocusCapture={(event) => {
        if (
          !entrance.active &&
          event.target.matches("button:focus-visible,a:focus-visible") &&
          !event.target.closest('[data-audio="off"]:not(.nx-journey),[inert]')
        )
          audio.play("hover");
      }}
      aria-label={
        isMap
          ? "Jelajah Nusantara — peta interaktif Indonesia"
          : `Jelajah budaya ${region.name}`
      }
    >
      <div
        className="nx-play-surface"
        inert={modalOpen || switching || entrance.active}
        aria-hidden={modalOpen || entrance.active || undefined}
      >
        {!isMap && <RegionSeascape />}
        <div className="nx-world">
          {isMap && !fallback && <AtlasFrame timeOfDay={timeOfDay} />}
          {isMap && fallback ? (
            <IllustratedAtlas
              selectedRegion={selected}
              onSelectRegion={selectRegion}
              onHoverRegion={setSelected}
              onReady={onReady}
              zoom={zoom}
              setZoom={setZoom}
              reset={reset}
              paused={paused || modalOpen || entrance.active}
              reducedMotion={reducedMotion}
              lowGraphics={lowGraphics}
              timeOfDay={timeOfDay}
              visited={visited}
            />
          ) : fallback ? (
            <div className="nx-region-fallback" aria-hidden="true">
              <span>✦</span>
            </div>
          ) : (
            mounted && (
              <div
                className={isMap ? "nx-atlas-gpu-stage" : "nx-region-3d-stage"}
              >
                <WorldBoundary onFailure={onFailure}>
                  <WorldScene
                    mode={isMap ? "map" : "region"}
                    regionId={region?.id}
                    selectedRegion={selected}
                    onSelectRegion={selectRegion}
                    onHoverRegion={setSelected}
                    onHotspot={openChapter}
                    onReady={onReady}
                    onSlideReady={sceneReady}
                    onSlideComplete={completeSlide}
                    onSlidePrepared={onSlidePrepared}
                    onSlidePresented={onSlidePresented}
                    snapshotTransition={!!hasSlideFrames}
                    lowGraphics={lowGraphics}
                    reducedMotion={reducedMotion}
                    zoom={zoom}
                    reset={reset}
                    activeHotspot={chapter}
                    paused={
                      paused ||
                      settings ||
                      list ||
                      entrance.active ||
                      (isMap && cards)
                    }
                    renderingSuspended={modalOpen}
                    departing={false}
                    timeOfDay={timeOfDay}
                    onDiscover={onDiscover}
                    greeting={greeting}
                    presentation={
                      mode === "preview"
                        ? "preview"
                        : cards || mode === "overview"
                          ? "intro"
                          : "explore"
                    }
                    panelOpen={rightPanel}
                    readChapters={read}
                    dashboardOpen={cards}
                    transition={transition}
                    onZoomChange={setZoom}
                    atlas2d={isMap ? atlasBridge : undefined}
                  />
                </WorldBoundary>
                {isMap && (
                  <AtlasGpuOverlay
                    bridge={atlasBridge}
                    selected={selected}
                    visited={visited}
                    onSelect={selectRegion}
                    onHover={setSelected}
                  />
                )}
              </div>
            )
          )}
          {isMap && !fallback && <AtlasFrameOverlay />}
        </div>
        {hasSlideFrames && slideFrames && (
          <div
            className="nx-slide-frames"
            data-phase={transition.phase}
            data-direction={transition.direction}
            aria-hidden="true"
          >
            <img
              className="nx-slide-frame-from"
              src={slideFrames.from}
              alt=""
              draggable={false}
            />
            <img
              className="nx-slide-frame-to"
              src={slideFrames.to}
              alt=""
              draggable={false}
              onTransitionEnd={(event) => {
                if (
                  event.propertyName === "transform" &&
                  transition.phase === "out"
                )
                  completeSlide(transition.sequence);
              }}
            />
          </div>
        )}
        <div className="nx-atmosphere" aria-hidden="true" />
        <header className="nx-hud">
          <div className="nx-hud-brand">
            <Link href="/galeri" className="brand" aria-label="Tenara — galeri Nusantara"><svg viewBox="0 0 36 36" fill="none" aria-hidden="true"><path d="M18 2 34 18 18 34 2 18Z" stroke="currentColor" strokeWidth="1.4" /><path d="m18 8 10 10-10 10L8 18Zm0 6 4 4-4 4-4-4ZM7 7l22 22M29 7 7 29" stroke="currentColor" strokeWidth="1.2" /></svg><span>Tenara</span></Link>
            <span className="nx-brand-divider" />
            <span className="nx-brand-caption">
              Galeri
              <br />
              <strong>{region?.name ?? "Nusantara"}</strong>
            </span>
          </div>
          <nav className="map-hud" aria-label="Menu penjelajahan">
            {isMap && (
              <MapButtonLink
                href="/katalog"
                icon={<MapIcon name="catalog" />}
                trailing={<MapIcon name="arrow" />}
                aria-label="Katalog kain"
              >
                Katalog Kain
              </MapButtonLink>
            )}
            {isMap && (
              <MapButton
                className="nx-open-cards"
                icon={<MapIcon name="book" />}
                badge={currentTraditions.length}
                aria-label={`Kartu kain, ${currentTraditions.length} koleksi`}
                aria-haspopup="dialog"
                aria-expanded={cards}
                aria-controls="nx-card-dashboard"
                onClick={openCards}
              >
                Kartu Kain
              </MapButton>
            )}
            {isMap && (
              <MapButton
                variant="icon"
                className="nx-audio-toggle"
                icon={
                  audio.enabled ? <Volume2 size={18} /> : <VolumeX size={18} />
                }
                aria-label={
                  audio.enabled
                    ? "Matikan suara galeri"
                    : "Aktifkan suara galeri"
                }
                aria-pressed={audio.enabled}
                onClick={audio.toggle}
                data-audio="off"
              />
            )}
            <MapButton
              variant="icon"
              icon={<MapIcon name="settings" />}
              aria-label="Pengaturan penjelajahan"
              onClick={() => setSettings(true)}
            />
            {!isMap && mode !== "preview" ? (
              <MapButton
                variant="icon"
                icon={<MapIcon name="close" />}
                aria-label="Kembali ke daerah"
                onClick={() => setMode("preview")}
              />
            ) : isMap || mode === "preview" ? (
              <MapButtonLink
                variant="icon"
                href="/katalog"
                icon={<MapIcon name="close" />}
                aria-label="Tutup penjelajahan dan buka katalog kain"
              />
            ) : null}
          </nav>
        </header>

        {isMap ? (
          <>
            <div className="nx-map-title">
              <svg
                className="nx-atlas-title-ornament"
                viewBox="0 0 210 45"
                aria-hidden="true"
              >
                <path
                  d="M4 23h58m86 0h58m-135 0 4-4 4 4-4 4Zm60 0 4-4 4 4-4 4Z"
                  fill="currentColor"
                  stroke="currentColor"
                />
                <g
                  transform="translate(105 23) scale(.8)"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  {[0, 60, 120, 180, 240, 300].map((a) => (
                    <path
                      key={a}
                      transform={`rotate(${a})`}
                      d="M0 0Q-15-14 0-25 15-14 0 0Zm0-7-4-7 4-6 4 6Z"
                    />
                  ))}
                  <circle r="5" fill="#f3dfab" />
                </g>
              </svg>
              <span className="nx-eyebrow">
                <span />
                Sebuah perjalanan mengenal tenun
              </span>
              <h1>
                Ribuan pulau.
                <br />
                <em>Sejuta cerita.</em>
              </h1>
              <p>
                Pilih daerah. Temui budayanya.
                <br /> Kenali kain yang menyimpan ceritanya.
              </p>
            </div>
            <span className="nx-map-step">
              01 / Pilih daerah <span>02 / Kenali budaya</span>
              <span>03 / Temukan kain</span>
            </span>
            <div className="nx-compass" aria-hidden="true">
              <span>U</span>
              <Compass size={43} strokeWidth={0.8} />
            </div>
          </>
        ) : (
          <>
            {!cards && (
              <div
                className="nx-preview-layer"
                data-active={mode === "preview"}
                inert={mode !== "preview"}
                aria-hidden={mode !== "preview"}
              >
                <WorldPreview
                  region={region}
                  percent={regionProgress(progress, region.id)}
                  switching={switching || (!ready && !fallback)}
                  onEnter={() => {
                    setMode("overview");
                    setReset((value) => value + 1);
                  }}
                  onCycle={cycle}
                  onSelect={selectRegion}
                  onMap={returnToMap}
                />
              </div>
            )}
            {!cards && (
              <div
                className="nx-overview-layer"
                data-active={mode === "overview"}
                inert={mode !== "overview"}
                aria-hidden={mode !== "overview"}
              >
                <RegionOverview
                  region={region}
                  read={read}
                  onChapter={openChapter}
                  onFreeExplore={() => setMode("free")}
                  onCards={openCards}
                  simplified
                  fallback={fallback}
                />
              </div>
            )}
            {!cards && mode === "detail" && (
              <>
                <h1 className="nx-sr-only">
                  {region.name} — {chapterLabels[chapter]}
                </h1>
                <RegionStoryPanel
                  key={`${region.id}:${chapter}`}
                  region={region}
                  chapter={chapter}
                  onChapter={openChapter}
                  onClose={closeDetail}
                  motifCardsOpen={motifCards}
                  onCards={() => {
                    motifReturnFocus.current =
                      document.activeElement as HTMLElement;
                    setMotifCards(true);
                  }}
                />
              </>
            )}
            {!cards && mode === "free" && (
              <>
                <div className="nx-region-heading">
                  <span className="nx-eyebrow">{region.province}</span>
                  <h1>{region.name}</h1>
                  <MapButton
                    variant="text"
                    trailing={<ArrowRight size={14} />}
                    onClick={() => setMode("overview")}
                  >
                    Buka pengantar
                  </MapButton>
                </div>
                <nav
                  className="nx-explore-dock"
                  aria-label="Pilih cerita daerah"
                >
                  <span>Pilih penanda pada diorama atau mulai dari sini</span>
                  <div>
                    <MapButton
                      icon={<House size={16} />}
                      onClick={() => openChapter("culture")}
                    >
                      Budaya
                    </MapButton>
                    <MapButton
                      icon={<Leaf size={16} />}
                      onClick={() => openChapter("weaving")}
                    >
                      Tradisi Tenun
                    </MapButton>
                    <MapButton
                      icon={<MapIcon name="catalog" />}
                      onClick={() => openChapter("textiles")}
                    >
                      Kain Daerah
                    </MapButton>
                  </div>
                </nav>
              </>
            )}
          </>
        )}

        {isMap && (
          <div className="nx-bottom-hud">
            <MapPassport
              visited={visited.length}
              total={exploreRegions.length}
              onClick={() => setList(true)}
            />
            <ViewControls
              zoom={zoom}
              setZoom={setZoom}
              onReset={() => {
                setZoom(1);
                setReset((value) => value + 1);
              }}
              paused={paused}
              setPaused={setPaused}
              timeOfDay={timeOfDay}
              setTimeOfDay={setTimeOfDay}
              illustratedMap={isMap}
              audio={audio}
            />
          </div>
        )}
        {!isMap && (
          <div className="nx-region-passport">
            <MapPassport
              visited={visited.length}
              total={exploreRegions.length}
              onClick={() => setList(true)}
            />
          </div>
        )}
        {region && mode === "free" && !fallback && (
          <button
            className="nx-life-hint"
            onClick={() => {
              setGreeting((value) => value + 1);
              onDiscover("Halo! Selamat datang di kampung tenun.");
            }}
          >
            Sapa warga · atau klik penghuni di diorama
          </button>
        )}
        {discovery && (
          <output
            key={discovery.key}
            className="nx-discovery"
            aria-live="polite"
          >
            <Sparkles size={17} />
            {discovery.text}
          </output>
        )}
        {!ready && !switching && !entrance.active && (isMap || !fallback) && (
          <div className="nx-loading" role="status">
            <div className="nx-loading-compass">
              <Compass size={35} />
            </div>
            <span>Menyiapkan perjalananmu…</span>
            <small>Pulau, benang, dan cerita Nusantara</small>
          </div>
        )}
      </div>

      <GalleryEntrance
        phase={entrance.phase}
        ready={ready}
        onEnter={(enabled) => {
          audio.start(enabled);
          entrance.enter();
        }}
        onLightMode={() => setFallback(true)}
      />
      <CloudTransition transition={transition} />
      {switching && (
        <span className="nx-sr-only" role="status">
          Melintasi kepulauan menuju{" "}
          {findExploreRegion(transition.destination ?? "")?.name ?? "Nusantara"}
          …
        </span>
      )}

      {region && motifCards && (
        <MotifCards
          region={region}
          traditions={currentTraditions}
          reducedMotion={reducedMotion || paused}
          onClose={() => {
            setMotifCards(false);
            setTimeout(() => {
              const target = motifReturnFocus.current;
              (target?.isConnected
                ? target
                : document.querySelector<HTMLElement>(
                    ".nx-topic-stepper button:last-child",
                  )
              )?.focus({ preventScroll: true });
            }, 50);
          }}
        />
      )}
      {cards && (
        <FabricDashboard
          regionId={region?.id ?? active.id}
          progress={progress}
          onClose={closeCards}
          reducedMotion={reducedMotion}
        />
      )}
      {settings && (
        <MapDialog title="Atur perjalananmu" onClose={() => setSettings(false)}>
          <div className="nx-settings">
            <p>Sesuaikan pengalaman penjelajahan agar nyaman di perangkatmu.</p>
            <GalleryAudioControls audio={audio} />
            {!isMap && (
              <div className="nx-region-view-settings">
                <strong>Tampilan diorama</strong>
                <div>
                  <button
                    onClick={() => setZoom(Math.max(0.7, zoom - 0.2))}
                    disabled={zoom <= 0.7}
                    aria-label="Perkecil diorama"
                  >
                    −
                  </button>
                  <output aria-label="Jarak pandang">
                    {Math.round(zoom * 100)}%
                  </output>
                  <button
                    onClick={() => setZoom(Math.min(2.4, zoom + 0.2))}
                    disabled={zoom >= 2.4}
                    aria-label="Perbesar diorama"
                  >
                    +
                  </button>
                  <button
                    onClick={() => {
                      setZoom(1);
                      setReset((value) => value + 1);
                    }}
                  >
                    Reset
                  </button>
                </div>
                <label>
                  <span>
                    <strong>Jeda animasi</strong>
                  </span>
                  <input
                    type="checkbox"
                    checked={paused}
                    onChange={(event) => setPaused(event.target.checked)}
                  />
                </label>
                <label>
                  <span>
                    <strong>Suasana senja</strong>
                  </span>
                  <input
                    type="checkbox"
                    checked={timeOfDay === "sunset"}
                    onChange={(event) =>
                      setTimeOfDay(event.target.checked ? "sunset" : "day")
                    }
                  />
                </label>
              </div>
            )}
            <label>
              <span>
                <strong>Grafis ringan</strong>
                <small>Kurangi detail pohon dan bayangan.</small>
              </span>
              <input
                type="checkbox"
                checked={lowGraphics}
                onChange={(event) => {
                  setLowGraphics(event.target.checked);
                  try {
                    localStorage.setItem(
                      "tenara-low-graphics",
                      String(event.target.checked),
                    );
                  } catch {}
                }}
              />
            </label>
            <label>
              <span>
                <strong>Kurangi gerakan</strong>
                <small>Hentikan gerakan awan dan transisi kamera.</small>
              </span>
              <input
                type="checkbox"
                checked={reducedMotion}
                onChange={(event) => {
                  setReducedMotion(event.target.checked);
                  try {
                    localStorage.setItem(
                      "tenara-reduced-motion",
                      String(event.target.checked),
                    );
                  } catch {}
                }}
              />
            </label>
            <button
              className="map-dialog-primary"
              onClick={() => setSettings(false)}
            >
              Lanjutkan menjelajah <ArrowRight size={17} />
            </button>
          </div>
        </MapDialog>
      )}
      {list && (
        <MapDestinationsDialog
          progress={progress}
          visited={visited}
          selected={selected}
          onClose={() => setList(false)}
          onSelect={(id) => {
            setList(false);
            selectRegion(id);
          }}
        />
      )}
    </section>
  );
}
