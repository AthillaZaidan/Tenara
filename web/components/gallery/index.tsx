"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Component,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Grid2X2,
  List,
  Map,
  Mouse,
  RotateCcw,
  X,
  Plus,
  Minus,
} from "lucide-react";
import {
  galleryAssets,
  galleryProgressKey,
  galleryStories,
  passportTabs,
  rooms,
  type GalleryView,
  type PassportTab,
} from "@/lib/gallery";
import { Brand, Breadcrumb, Button } from "./primitives";
import { MapSurface } from "@/components/exploration/map-button";
import { MapDialog } from "@/components/exploration/map-dialog";
import {
  HinggiAnatomy,
  HinggiColors,
  HinggiMotifs,
} from "./collection-content";
import "../exploration/prototype-foundation.css";
import "./museum-foundation.css";
import "./gallery.css";
import "../exploration/hinggi-game.css";
import "../exploration/map-button.css";
import "../exploration/map-dialog.css";
import "./gallery-map-theme.css";

const Scene = dynamic(() => import("./scene"), { ssr: false });

class SceneBoundary extends Component<
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

function PassportContent() {
  const [tab, setTab] = useState<PassportTab>("asal");
  const tabRef = useRef<HTMLDivElement>(null);
  return (
    <div className="gallery-passport">
      <div className="gallery-passport-image">
        <img
          src={galleryAssets.textile}
          alt="Tenun ikat Sumba"
          width={700}
          height={1536}
        />
        <span>Hinggi Sumba</span>
      </div>
      <div className="gallery-passport-copy">
        <span className="gallery-eyebrow">Sumba, Nusa Tenggara Timur</span>
        <h3>Hinggi Sumba</h3>
        <div
          className="gallery-passport-tabs"
          role="tablist"
          aria-label="Informasi kain dan sumber"
          ref={tabRef}
        >
          {passportTabs.map((item, index) => (
            <button
              key={item.id}
              id={`passport-tab-${item.id}`}
              role="tab"
              aria-selected={tab === item.id}
              aria-controls={`passport-panel-${item.id}`}
              tabIndex={tab === item.id ? 0 : -1}
              onClick={() => setTab(item.id)}
              onKeyDown={(event) => {
                const next =
                  event.key === "ArrowRight"
                    ? (index + 1) % passportTabs.length
                    : event.key === "ArrowLeft"
                      ? (index + passportTabs.length - 1) % passportTabs.length
                      : event.key === "Home"
                        ? 0
                        : event.key === "End"
                          ? passportTabs.length - 1
                          : -1;
                if (next < 0) return;
                event.preventDefault();
                setTab(passportTabs[next].id);
                tabRef.current
                  ?.querySelectorAll<HTMLButtonElement>("button")
                  [next].focus();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div
          className="gallery-passport-panel"
          id={`passport-panel-${tab}`}
          role="tabpanel"
          aria-labelledby={`passport-tab-${tab}`}
          tabIndex={0}
        >
          {tab === "asal" && (
            <>
              <p>
                Hinggi disusun dalam tujuh panel atau pita horizontal. Bidang
                tengah dan badan kain diapit oleh pita-pita yang membentuk batas
                visualnya.
              </p>
              <p>
                Pilih bagian pada skema untuk membaca fungsi dan ragam motifnya.
              </p>
              <HinggiAnatomy />
            </>
          )}
          {tab === "motif" && (
            <>
              <p>
                Motif Hinggi menyampaikan strata sosial dan kepercayaan lokal
                Marapu.
              </p>
              <HinggiMotifs />
            </>
          )}
          {tab === "teknik" && (
            <>
              <h4>Teknik ikat</h4>
              <p>
                Motif terbentuk dari benang yang diikat dan diwarnai sebelum
                ditenun.
              </p>
              <p>
                Bagian yang diikat membatasi masuknya warna. Benang kemudian
                disusun dan ditenun, mempertemukan bidang-bidang warna menjadi
                pola kain.
              </p>
              <HinggiColors />
            </>
          )}
          {tab === "referensi" && (
            <>
              <h4>Materi koleksi</h4>
              <p>
                Anatomi Hinggi, motif figuratif, dan pewarnaan Kombu–Kawuru
                mengikuti materi koleksi yang disiapkan untuk Gallery Tenara.
              </p>
              <a
                href="https://www.metmuseum.org/art/collection/search?q=Sumba"
                target="_blank"
                rel="noreferrer"
              >
                Telusuri koleksi Sumba · The Met <ArrowUpRight size={14} />
              </a>
              <a
                href="https://www.britishmuseum.org/collection/search?keyword=ikat"
                target="_blank"
                rel="noreferrer"
              >
                Telusuri ikat · British Museum <ArrowUpRight size={14} />
              </a>
              <small>Penelusuran koleksi museum untuk bacaan lanjutan.</small>
            </>
          )}
        </div>
        <Button
          href="/katalog/hinggi-sumba"
          className="gallery-passport-cta"
          arrow
        >
          Temukan Penyedia Kain
        </Button>
        <span className="gallery-passport-note">
          Lihat bahan, ukuran, harga, dan stok penjual.
        </span>
      </div>
    </div>
  );
}

export function CulturalPassportPage() {
  return (
    <div className="container page gallery-passport-page">
      <Breadcrumb
        items={[
          { label: "Gallery", href: "/galeri" },
          { label: "Tentang kain" },
        ]}
      />
      <header>
        <span className="gallery-eyebrow">Koleksi Sumba</span>
        <h1>Tentang kain</h1>
      </header>
      <PassportContent />
      <Link className="gallery-text-link" href="/galeri/kain/hinggi-sumba?museum=1">
        <ArrowLeft size={17} /> Kembali ke Gallery 3D
      </Link>
    </div>
  );
}

export function GalleryWorkspace() {
  const [view, setView] = useState<GalleryView>("overview");
  const [selected, setSelected] = useState<string | null>(null);
  const [visited, setVisited] = useState<string[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [passport, setPassport] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [storyList, setStoryList] = useState(false);
  const [reset, setReset] = useState(0);
  const [zoom, setZoom] = useState(0);
  const [ready, setReady] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const story = galleryStories.find((s) => s.id === selected);
  const activeRoom = rooms.find((r) => r.id === view);
  const previousFocus = useRef<HTMLElement | null>(null);
  const panelTitle = useRef<HTMLHeadingElement>(null);

  /* The prototype hydrates browser-only progress, motion preference and WebGL
     capability after mount; its initial server render must stay deterministic. */
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      try {
        const preference = localStorage.getItem("tenara-reduced-motion");
        setReducedMotion(
          preference === null ? media.matches : preference === "true",
        );
      } catch {
        setReducedMotion(media.matches);
      }
    };
    update();
    media.addEventListener("change", update);
    try {
      const saved: unknown = JSON.parse(
        localStorage.getItem(galleryProgressKey) || "[]",
      );
      if (Array.isArray(saved))
        setVisited([
          ...new Set(
            saved.filter(
              (id): id is string =>
                typeof id === "string" &&
                galleryStories.some((s) => s.id === id),
            ),
          ),
        ]);
    } catch {
      /* Exploration also works without storage. */
    }
    try {
      const probe = document.createElement("canvas");
      const context = probe.getContext("webgl2");
      if (!context) setFallback(true);
      context?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      setFallback(true);
    }
    setStorageReady(true);
    return () => media.removeEventListener("change", update);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!storageReady) return;
    try {
      localStorage.setItem(galleryProgressKey, JSON.stringify(visited));
    } catch {
      /* Private browsing can disable storage. */
    }
  }, [visited, storageReady]);

  const onReady = useCallback(() => setReady(true), []);
  const onFailure = useCallback(() => {
    setFallback(true);
    setReady(true);
  }, []);
  const openRoom = useCallback((room: GalleryView) => {
    setView(room);
    setSelected(null);
    setStoryList(false);
    setMapOpen(false);
  }, []);
  const openStory = useCallback((id: string) => {
    const entry = galleryStories.find((s) => s.id === id);
    if (!entry) return;
    previousFocus.current = document.activeElement as HTMLElement;
    setView(entry.room);
    setSelected(id);
    setStoryList(false);
    setMapOpen(false);
    setVisited((ids) => (ids.includes(id) ? ids : [...ids, id]));
  }, []);
  const closeStory = useCallback(() => {
    setSelected(null);
    requestAnimationFrame(() => {
      if (previousFocus.current?.isConnected) previousFocus.current.focus();
      else
        document
          .querySelector<HTMLButtonElement>(
            ".gallery-room-nav button[aria-pressed=true]",
          )
          ?.focus();
    });
  }, []);

  useEffect(() => {
    if (selected) panelTitle.current?.focus();
  }, [selected]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || passport || mapOpen) return;
      if (selected) closeStory();
      else setStoryList(false);
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [selected, passport, mapOpen, closeStory]);

  return (
    <section
      className={`gallery-workspace ${story ? "has-story" : ""} ${view === "overview" ? "is-overview" : ""}`}
      aria-label="Gallery interaktif Koleksi Sumba"
    >
      <div
        className="gallery-canvas"
        aria-hidden={passport || mapOpen || undefined}
        inert={passport || mapOpen}
      >
        {fallback ? (
          <div className="gallery-scene-fallback">
            <img src={galleryAssets.preview} alt="Diorama Sumba" />
            <span>Mode cerita · Jelajahi melalui menu ruang</span>
          </div>
        ) : (
          storageReady && (
            <SceneBoundary onFailure={onFailure}>
              <Scene
                view={view}
                selected={selected}
                visited={visited}
                reset={reset}
                zoom={zoom}
                reducedMotion={reducedMotion}
                onRoom={openRoom}
                onStory={openStory}
                onReady={onReady}
                onFailure={onFailure}
              />
            </SceneBoundary>
          )
        )}
      </div>
      {!ready && !fallback && (
        <div className="gallery-loading" role="status">
          <Brand light />
          <span>Memuat Gallery…</span>
          <small>Koleksi Sumba</small>
        </div>
      )}
      <header className="gallery-workspace-header">
        <div className="gallery-workspace-brand">
          <Brand />
          <span />
          <p>
            Gallery <span>/ Hinggi Sumba</span>
          </p>
        </div>
        <div className="gallery-workspace-actions">
          <Link href="/galeri/daerah/sumba" className="gallery-header-catalog">
            <ArrowLeft size={15} /> Landscape Sumba
          </Link>
          <Link href="/katalog/hinggi-sumba" className="gallery-header-catalog">
            Katalog Kain <ArrowUpRight size={15} />
          </Link>
          <button
            className="gallery-map-trigger"
            onClick={() => setMapOpen(true)}
          >
            <MapSurface />
            <span>
              <Map size={16} /> Peta Galeri
            </span>
          </button>
          <Link
            className="gallery-exit"
            href="/galeri/daerah/sumba"
            aria-label="Kembali ke landscape Sumba"
          >
            <X size={21} />
          </Link>
        </div>
      </header>
      <div className="gallery-workspace-intro">
        <span className="gallery-eyebrow">
          {view === "overview"
            ? "Galeri kain / Sumba"
            : `RUANG ${activeRoom?.number} / 03`}
        </span>
        <h1>{view === "overview" ? "Hinggi Sumba" : activeRoom?.name}</h1>
        {view === "overview" && (
          <div className="gallery-intro-ornament" aria-hidden="true">
            <span>◇◇◇</span>
          </div>
        )}
        <p>
          {view === "overview"
            ? "Anatomi Hinggi, ragam motif, dan pewarnaan alami."
            : activeRoom?.caption}
        </p>
        {view === "overview" && (
          <button
            className="gallery-enter-button"
            onClick={() => openRoom("kain")}
          >
            <MapSurface />
            <span>
              Jelajahi Kain <ArrowRight size={19} />
            </span>
          </button>
        )}
      </div>
      {story && (
        <aside
          className="gallery-story-panel"
          aria-labelledby="gallery-story-title"
        >
          <header>
            <span className="gallery-eyebrow">{activeRoom?.name}</span>
            <button aria-label="Tutup cerita" onClick={closeStory}>
              <X size={21} />
            </button>
          </header>
          <div className="gallery-story-scroll">
            <h2 id="gallery-story-title" ref={panelTitle} tabIndex={-1}>
              {story.title}
            </h2>
            {story.study !== "anatomy" && story.study !== "colors" && (
              <img
                src={story.image}
                alt={story.imageAlt}
                className={
                  story.id === "sehelai-sumba" || story.id === "irama-motif"
                    ? "is-textile"
                    : ""
                }
              />
            )}
            <p className="gallery-story-intro">{story.intro}</p>
            {story.paragraphs.map((p) => (
              <p key={p}>{p}</p>
            ))}
            {story.study === "anatomy" && <HinggiAnatomy />}
            {story.study === "colors" && <HinggiColors />}
            {story.study === "motifs" && <HinggiMotifs />}
            <button
              className="gallery-text-link"
              onClick={() => setPassport(true)}
            >
              Tentang kain <ArrowRight size={18} />
            </button>
          </div>
          <footer>
            <span>
              <Check size={14} /> Cerita dijelajahi
            </span>
            <button
              onClick={() => {
                const index = galleryStories.findIndex(
                  (s) => s.id === selected,
                );
                openStory(
                  galleryStories[(index + 1) % galleryStories.length].id,
                );
              }}
            >
              Cerita berikutnya <ArrowRight size={16} />
            </button>
          </footer>
        </aside>
      )}
      <div className="gallery-explore-tools">
        {!fallback && (
          <>
            <button
              className="gallery-tool-button gallery-zoom-button"
              onClick={() => setZoom((n) => n + 1)}
              aria-label="Perbesar pandangan"
              title="Perbesar"
            >
              <MapSurface />
              <Plus size={18} />
            </button>
            <button
              className="gallery-tool-button gallery-zoom-button"
              onClick={() => setZoom((n) => n - 1)}
              aria-label="Perkecil pandangan"
              title="Perkecil"
            >
              <MapSurface />
              <Minus size={18} />
            </button>
            <button
              className="gallery-tool-button"
              onClick={() => {
                setSelected(null);
                setReset((n) => n + 1);
              }}
              aria-label="Reset pandangan kamera"
              title="Reset pandangan"
            >
              <MapSurface />
              <RotateCcw size={18} />
            </button>
          </>
        )}
        <button
          className={`gallery-tool-button ${storyList ? "is-active" : ""}`}
          onClick={() => setStoryList((open) => !open)}
          aria-label="Daftar cerita"
          aria-expanded={storyList}
          aria-controls="gallery-story-list"
          title="Daftar cerita"
        >
          <MapSurface />
          <List size={19} />
        </button>
        <span className="gallery-drag-hint">
          <Mouse size={20} /> Geser untuk melihat · Gulir untuk zoom
        </span>
      </div>
      <nav className="gallery-room-nav" aria-label="Navigasi ruang Gallery">
        <button
          onClick={() => openRoom("overview")}
          className="gallery-overview-button"
          aria-label="Lihat seluruh diorama"
          aria-pressed={view === "overview"}
        >
          <MapSurface />
          <Grid2X2 size={18} />
        </button>
        {rooms.map((room) => (
          <button
            key={room.id}
            onClick={() => openRoom(room.id)}
            aria-pressed={view === room.id}
          >
            <MapSurface />
            <span>{room.number}</span>
            {room.name}
          </button>
        ))}
      </nav>
      <div className="gallery-progress">
        <button
          onClick={() => setStoryList((open) => !open)}
          aria-label={`${visited.length} dari ${galleryStories.length} cerita dijelajahi. Buka daftar cerita.`}
        >
          <span className="gallery-progress-count">
            {String(visited.length).padStart(2, "0")}
            <small> / {galleryStories.length}</small>
          </span>
          <span>Cerita dibuka</span>
          <span className="gallery-progress-track">
            <i
              style={{
                width: `${(visited.length / galleryStories.length) * 100}%`,
              }}
            />
          </span>
        </button>
        <button
          className="gallery-passport-trigger"
          onClick={() => setPassport(true)}
        >
          <BookOpen size={17} /> Tentang kain
        </button>
      </div>
      {storyList && (
        <div className="gallery-story-list" id="gallery-story-list">
          <header>
            <div>
              <h2>Daftar cerita</h2>
            </div>
            <button
              aria-label="Tutup daftar cerita"
              onClick={() => setStoryList(false)}
            >
              <X size={20} />
            </button>
          </header>
          <p>Pilih cerita untuk mendekati objeknya.</p>
          {rooms.map((room) => (
            <div key={room.id}>
              <h3>
                {room.number} · {room.name}
              </h3>
              {galleryStories
                .filter((s) => s.room === room.id)
                .map((s) => (
                  <button key={s.id} onClick={() => openStory(s.id)}>
                    <span>{s.label}</span>
                    {visited.includes(s.id) ? (
                      <Check size={16} />
                    ) : (
                      <ArrowUpRight size={16} />
                    )}
                  </button>
                ))}
            </div>
          ))}
        </div>
      )}
      {view !== "overview" && !story && (
        <div
          className="gallery-room-story-links"
          aria-label={`Cerita ${activeRoom?.name}`}
        >
          {galleryStories
            .filter((s) => s.room === view)
            .map((s) => (
              <button key={s.id} onClick={() => openStory(s.id)}>
                {visited.includes(s.id) ? (
                  <Check size={14} />
                ) : (
                  <span className="gallery-small-dot" />
                )}
                {s.label}
                <ArrowUpRight size={14} />
              </button>
            ))}
        </div>
      )}
      {fallback && view === "overview" && (
        <div className="gallery-fallback-notice">
          Tampilan 3D tidak tersedia di perangkat ini. Semua cerita tetap dapat
          dijelajahi melalui menu ruang.
        </div>
      )}
      <span className="gallery-sr-only" role="status" aria-live="polite">
        {story
          ? `Cerita: ${story.title}`
          : view === "overview"
            ? "Peta diorama Sumba"
            : `Memasuki ${activeRoom?.name}`}
      </span>
      {passport && (
        <MapDialog title="Tentang kain" onClose={() => setPassport(false)}>
          <PassportContent />
        </MapDialog>
      )}
      {mapOpen && (
        <MapDialog title="Peta Galeri" onClose={() => setMapOpen(false)}>
          <div className="gallery-map">
            <p>
              Satu kain, tiga cara untuk mengenalinya. Pilih ruang untuk
              melanjutkan.
            </p>
            <button
              className="gallery-map-overview"
              onClick={() => openRoom("overview")}
            >
              <Map size={20} />
              <span>Lihat seluruh diorama</span>
              <ArrowUpRight size={18} />
            </button>
            {rooms.map((room) => (
              <button key={room.id} onClick={() => openRoom(room.id)}>
                <span className="gallery-map-number">{room.number}</span>
                <span>
                  <strong>{room.name}</strong>
                  <small>{room.caption}</small>
                </span>
                <span className="gallery-map-progress">
                  {
                    galleryStories.filter(
                      (s) => s.room === room.id && visited.includes(s.id),
                    ).length
                  }
                  /2
                </span>
                <ArrowRight size={18} />
              </button>
            ))}
            <Link className="gallery-text-link" href="/katalog/hinggi-sumba">
              Langsung ke Katalog Hinggi Sumba <ArrowRight size={16} />
            </Link>
          </div>
        </MapDialog>
      )}
    </section>
  );
}
