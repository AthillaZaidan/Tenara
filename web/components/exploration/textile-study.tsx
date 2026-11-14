"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Component,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Box,
  ChevronRight,
  Diamond,
  Focus,
  ImageIcon,
  Layers3,
  MapPin,
  Minus,
  MoveHorizontal,
  Plus,
  RotateCcw,
  RotateCw,
  Scan,
  Sparkles,
} from "lucide-react";
import { asset } from "@/lib/gallery-data";
import { catalogSamplesForTradition } from "@/lib/gallery-samples";
import { collectionKnowledge, sampleKnowledge } from "@/lib/gallery-knowledge";
import {
  catalogHref,
  exploreRegions,
  regionHref,
  type TextileTradition,
} from "@/lib/exploration";
import "./prototype-foundation.css";
import "./textile-study.css";

const TextileScene = dynamic(() => import("./textile-study-scene"), {
  ssr: false,
  loading: () => null,
});

const views = [
  {
    id: "kain",
    label: "Kain",
    short: "Lihat keseluruhan",
    image: 0,
    photo: "Tampilan utama",
    icon: Layers3,
  },
  {
    id: "motif",
    label: "Motif & tekstur",
    short: "Amati lebih dekat",
    image: 2,
    photo: "Detail tekstur",
    icon: Scan,
  },
  {
    id: "teknik",
    label: "Teknik",
    short: "Kenali tenunannya",
    image: 1,
    photo: "Tampilan alternatif",
    icon: Sparkles,
  },
] as const;

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

function StudyImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? (
    <div className="nx-study-image-unavailable" role="img" aria-label={alt}>
      <ImageIcon size={36} aria-hidden="true" />
      <span>Gambar belum dapat ditampilkan.</span>
      <span>Kamu tetap bisa menjelajahi cerita kain di sini.</span>
    </div>
  ) : (
    <img
      src={src}
      alt={alt}
      width={1000}
      height={1250}
      fetchPriority="high"
      draggable={false}
      onError={() => setFailed(true)}
    />
  );
}

/** A self-contained exhibit. Route ownership stays with the parent. */
export function TextileStudy({
  tradition,
  initialSampleCode,
}: {
  tradition: TextileTradition;
  initialSampleCode?: string;
}) {
  return (
    <StudyRoom
      key={`${tradition.id}:${initialSampleCode ?? ""}`}
      tradition={tradition}
      initialSampleCode={initialSampleCode}
    />
  );
}

function StudyRoom({
  tradition,
  initialSampleCode,
}: {
  tradition: TextileTradition;
  initialSampleCode?: string;
}) {
  const region = exploreRegions.find((item) => item.id === tradition.regionId);
  const regionName = region?.name ?? tradition.gallery.region;
  const samples = catalogSamplesForTradition(tradition.id);
  const [sampleCode, setSampleCode] = useState(
    () =>
      samples.find((sample) => sample.code === initialSampleCode)?.code ??
      samples[0]?.code ??
      "",
  );
  const sample = samples.find((item) => item.code === sampleCode) ?? samples[0];
  const knowledge = collectionKnowledge[tradition.id];
  const motif = sample ? sampleKnowledge[sample.code] : undefined;
  const [selected, setSelected] = useState(0);
  const [mode, setMode] = useState<"3d" | "image">("image");
  const [sceneReady, setSceneReady] = useState(false);
  const [sceneFailed, setSceneFailed] = useState(false);
  const [zoom, setZoom] = useState(0);
  const [rotation, setRotation] = useState(0);
  const [reset, setReset] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();
  const view = views[selected];
  const source =
    sample?.images[view.image] ??
    tradition.gallery.images?.[view.image] ??
    tradition.gallery.image;
  const imageUrl = asset(source);
  const sceneEnabled = mode === "3d" && !sceneFailed;
  const showScene = sceneEnabled && sceneReady;
  const onSceneReady = useCallback(() => setSceneReady(true), []);
  const onSceneFailure = useCallback(() => {
    setSceneFailed(true);
    setSceneReady(false);
  }, []);

  // The real image stays visible during loading, including on slow GPUs.
  useEffect(() => {
    if (!sceneEnabled || sceneReady) return;
    const timeout = window.setTimeout(onSceneFailure, 15000);
    return () => window.clearTimeout(timeout);
  }, [sceneEnabled, sceneReady, imageUrl, onSceneFailure]);

  const selectView = (index: number) => {
    if (index === selected) return;
    setSelected(index);
    setSceneReady(false);
    setZoom(0);
    setRotation(0);
    setReset((value) => value + 1);
  };

  const resetView = () => {
    setZoom(0);
    setRotation(0);
    setReset((value) => value + 1);
  };

  const heading =
    selected === 0
      ? `Mengenal ${tradition.name}`
      : selected === 1
        ? (sample?.label ?? "Ragam pada kain")
        : "Dari benang menjadi kain";
  const copy =
    selected === 0
      ? (knowledge?.introduction ?? tradition.description)
      : selected === 1
        ? (motif?.story ?? "Amati susunan bentuk dan warna pada kain ini.")
        : (knowledge?.technique ??
          region?.stories[2]?.text ??
          tradition.description);
  const catalogUrl = `${catalogHref(tradition.id)}${sample ? `?pilihan=${encodeURIComponent(sample.code)}` : ""}`;

  return (
    <div
      className="nx-study"
      style={{ "--nx-study-accent": tradition.gallery.color } as CSSProperties}
    >
      <header className="nx-study-header">
        <Link
          className="nx-study-back nx-study-raised"
          href={regionHref(tradition.regionId)}
        >
          <ArrowLeft size={18} aria-hidden="true" />
          <span>Kembali ke daerah</span>
        </Link>
        <Link
          className="nx-study-brand"
          href="/galeri"
          aria-label="Tenara — jelajahi galeri Nusantara"
        >
          <Diamond size={15} aria-hidden="true" />
          <span>
            tenara<span className="nx-study-brand-dot">.</span>
          </span>
          <Diamond size={15} aria-hidden="true" />
        </Link>
        <Link className="nx-study-catalog nx-study-raised" href={catalogUrl}>
          <span>Lihat katalog</span>
          <ArrowUpRight size={18} aria-hidden="true" />
        </Link>
      </header>

      <div className="nx-study-body">
        <nav className="nx-study-breadcrumb" aria-label="Jejak penjelajahan">
          <Link href={regionHref(tradition.regionId)}>
            <MapPin size={14} aria-hidden="true" />
            {regionName}
          </Link>
          <ChevronRight size={13} aria-hidden="true" />
          <span aria-current="page">{tradition.name}</span>
          <span className="nx-study-breadcrumb-note">
            Galeri wastra Nusantara
          </span>
        </nav>

        <div className="nx-study-layout">
          <section
            className="nx-study-exhibit"
            aria-label={`Pengamatan visual ${tradition.name}`}
          >
            <div className="nx-study-stage">
              <div className="nx-study-stage-top">
                <span className="nx-study-kicker">
                  <Diamond size={10} aria-hidden="true" />
                  Ruang pengamatan
                </span>
                <span className="nx-study-view-number">
                  0{selected + 1}
                  <span> / 03</span>
                </span>
              </div>
              <div className="nx-study-arch" aria-hidden="true">
                <span>W A S T R A &nbsp; N U S A N T A R A</span>
              </div>
              <div className="nx-study-floor" aria-hidden="true" />

              <figure
                className="nx-study-artwork"
                aria-describedby={`${id}-caption`}
              >
                <div
                  className={`nx-study-photo${showScene ? " nx-study-photo-hidden" : ""}`}
                >
                  <div
                    className="nx-study-photo-frame"
                    style={{ transform: `scale(${1 + zoom * 0.15})` }}
                  >
                    <StudyImage
                      key={imageUrl}
                      src={imageUrl}
                      alt={`${tradition.name}${sample ? ` ${sample.label}` : ""} — ${view.photo.toLocaleLowerCase("id-ID")}`}
                    />
                  </div>
                  <div className="nx-study-photo-plinth" aria-hidden="true" />
                </div>
                {sceneEnabled && (
                  <div
                    className={`nx-study-scene${showScene ? " nx-study-scene-ready" : ""}`}
                    aria-hidden="true"
                  >
                    <SceneBoundary onFailure={onSceneFailure}>
                      <TextileScene
                        imageUrl={imageUrl}
                        zoom={zoom}
                        rotation={rotation}
                        reset={reset}
                        onReady={onSceneReady}
                        onFailure={onSceneFailure}
                      />
                    </SceneBoundary>
                  </div>
                )}
                <figcaption className="nx-study-sr-only" id={`${id}-caption`}>
                  {view.photo} {tradition.name}
                  {sample ? `, ${sample.label}` : ""}.
                </figcaption>
              </figure>

              <div className="nx-study-stage-bottom">
                <div className="nx-study-art-label">
                  <span className="nx-study-swatch" aria-hidden="true" />
                  <span>
                    {view.photo}
                    <small>
                      {sample?.label ?? tradition.technique} · {regionName}
                    </small>
                  </span>
                </div>
                <div
                  className="nx-study-mode"
                  role="group"
                  aria-label="Tampilan pameran"
                >
                  <button
                    type="button"
                    aria-pressed={!sceneEnabled}
                    onClick={() => {
                      setMode("image");
                      setSceneReady(false);
                    }}
                  >
                    <ImageIcon size={15} aria-hidden="true" />
                    Foto
                  </button>
                  <button
                    type="button"
                    aria-pressed={sceneEnabled}
                    disabled={sceneFailed}
                    onClick={() => setMode("3d")}
                  >
                    <Box size={15} aria-hidden="true" />
                    3D
                  </button>
                </div>
              </div>
            </div>

            <div className="nx-study-tools-row">
              <p className="nx-study-help" role="status" aria-live="polite">
                {sceneFailed ? (
                  <>
                    <ImageIcon size={15} aria-hidden="true" />
                    Mode foto · ruang 3D tidak tersedia
                  </>
                ) : showScene ? (
                  <>
                    <MoveHorizontal size={17} aria-hidden="true" />
                    Geser untuk melihat sudut lain
                  </>
                ) : (
                  <>
                    <Focus size={16} aria-hidden="true" />
                    {sceneEnabled
                      ? "Menyiapkan ruang 3D · foto tetap tersedia"
                      : "Dekatkan untuk mengamati detail"}
                  </>
                )}
              </p>
              <div
                className="nx-study-tools"
                role="group"
                aria-label="Kontrol pengamatan"
              >
                {showScene && (
                  <button
                    className="nx-study-tool nx-study-raised"
                    type="button"
                    aria-label="Putar kain ke kiri"
                    onClick={() =>
                      setRotation((value) => Math.max(-0.6, value - 0.15))
                    }
                    disabled={rotation <= -0.6}
                  >
                    <RotateCcw size={17} aria-hidden="true" />
                  </button>
                )}
                <button
                  className="nx-study-tool nx-study-raised"
                  type="button"
                  aria-label="Perkecil tampilan"
                  disabled={zoom === 0}
                  onClick={() => setZoom((value) => Math.max(0, value - 1))}
                >
                  <Minus size={17} aria-hidden="true" />
                </button>
                <output
                  className="nx-study-zoom"
                  aria-label="Perbesaran"
                  aria-live="polite"
                >
                  {100 + zoom * 15}%
                </output>
                <button
                  className="nx-study-tool nx-study-raised"
                  type="button"
                  aria-label="Perbesar tampilan"
                  disabled={zoom === 3}
                  onClick={() => setZoom((value) => Math.min(3, value + 1))}
                >
                  <Plus size={17} aria-hidden="true" />
                </button>
                {showScene && (
                  <button
                    className="nx-study-tool nx-study-raised"
                    type="button"
                    aria-label="Putar kain ke kanan"
                    onClick={() =>
                      setRotation((value) => Math.min(0.6, value + 0.15))
                    }
                    disabled={rotation >= 0.6}
                  >
                    <RotateCw size={17} aria-hidden="true" />
                  </button>
                )}
                <button
                  className="nx-study-tool nx-study-raised"
                  type="button"
                  aria-label="Atur ulang tampilan"
                  onClick={resetView}
                >
                  <Focus size={17} aria-hidden="true" />
                </button>
              </div>
            </div>

            <div
              className="nx-study-tabs"
              role="tablist"
              aria-label="Jelajahi kain"
            >
              {views.map((item, index) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    ref={(node) => {
                      tabRefs.current[index] = node;
                    }}
                    id={`${id}-tab-${item.id}`}
                    className="nx-study-tab nx-study-raised"
                    type="button"
                    role="tab"
                    aria-selected={selected === index}
                    aria-controls={`${id}-panel`}
                    tabIndex={selected === index ? 0 : -1}
                    onClick={() => selectView(index)}
                    onKeyDown={(event) => {
                      const next =
                        event.key === "ArrowRight"
                          ? (index + 1) % views.length
                          : event.key === "ArrowLeft"
                            ? (index + views.length - 1) % views.length
                            : event.key === "Home"
                              ? 0
                              : event.key === "End"
                                ? views.length - 1
                                : -1;
                      if (next < 0) return;
                      event.preventDefault();
                      selectView(next);
                      tabRefs.current[next]?.focus();
                    }}
                  >
                    <Icon size={23} strokeWidth={1.5} aria-hidden="true" />
                    <span>
                      {item.label}
                      <small>{item.short}</small>
                    </span>
                    <Diamond
                      className="nx-study-tab-diamond"
                      size={9}
                      aria-hidden="true"
                    />
                  </button>
                );
              })}
            </div>
          </section>

          <aside
            className="nx-study-story"
            aria-label="Catatan pengamatan kain"
          >
            {samples.length > 0 && (
              <section className="nx-study-samples" aria-label="Pilih kain">
                <div className="nx-study-samples-heading">
                  <span className="nx-study-kicker">Koleksi kain</span>
                  <span>{samples.length} pilihan</span>
                </div>
                <div className="nx-study-sample-list">
                  {samples.map((item) => (
                    <button
                      key={item.code}
                      type="button"
                      className="nx-study-sample"
                      aria-pressed={sample?.code === item.code}
                      onClick={() => {
                        setSampleCode(item.code);
                        setSceneReady(false);
                        setZoom(0);
                        setRotation(0);
                        setReset((value) => value + 1);
                      }}
                    >
                      <img
                        src={asset(item.thumbnails[0])}
                        alt=""
                        loading="lazy"
                      />
                      <span>
                        <strong>{item.label}</strong>
                        <small>{item.code}</small>
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            )}
            <div className="nx-study-title-block">
              <span className="nx-study-kicker">
                <span className="nx-study-dot" />
                Mengenal warisan tenun
              </span>
              <h1>{tradition.name}</h1>
              <p className="nx-study-subtitle">
                Pilih kain untuk mengenal ragam dalam koleksi ini.
              </p>
              <dl className="nx-study-facts">
                <div>
                  <dt>Asal koleksi</dt>
                  <dd>{sample?.origin ?? tradition.gallery.region}</dd>
                </div>
                <div>
                  <dt>Teknik tercatat</dt>
                  <dd>{tradition.technique}</dd>
                </div>
              </dl>
            </div>

            <div
              className="nx-study-panel"
              id={`${id}-panel`}
              role="tabpanel"
              aria-labelledby={`${id}-tab-${view.id}`}
              tabIndex={0}
              aria-live="polite"
            >
              <div className="nx-study-chapter">
                <span>0{selected + 1}</span>
                <span>{view.label}</span>
                <span className="nx-study-chapter-line" />
                <Diamond size={9} aria-hidden="true" />
              </div>
              <h2>{heading}</h2>
              <p>{copy}</p>
              <div className="nx-study-observe">
                <Focus size={18} strokeWidth={1.5} aria-hidden="true" />
                <p>
                  {selected === 0
                    ? "Pilih kain untuk mengamati bidang, warna, dan tepinya sebelum beralih ke detail."
                    : selected === 1
                      ? "Cerita motif dapat berbeda mengikuti tradisi, komunitas, dan pembuatnya."
                      : "Amati permukaan kain. Bahan dan rincian proses tercantum pada informasi produk."}
                </p>
              </div>
            </div>

            {tradition.id === "hinggi-sumba" && (
              <Link
                className="nx-study-museum"
                href="/galeri/kain/hinggi-sumba?museum=1"
              >
                Jelajahi diorama Hinggi 3D <ArrowUpRight size={15} />
              </Link>
            )}

            {region && (
              <details className="nx-study-context">
                <summary>
                  <MapPin size={15} aria-hidden="true" />
                  <span>Tentang {regionName}</span>
                  <Plus
                    size={15}
                    className="nx-study-context-plus"
                    aria-hidden="true"
                  />
                </summary>
                <p>{region.introduction}</p>
                <Link href={regionHref(tradition.regionId)}>
                  Jelajahi daerah
                  <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </details>
            )}

            <div className="nx-study-catalog-card">
              <span className="nx-study-kicker">
                Dari mengenal, menjadi dekat.
              </span>
              <p>Pilih ragam untuk menelusuri koleksi dan penawaran terkait.</p>
              <Link
                className="nx-study-catalog-button nx-study-raised"
                href={catalogUrl}
              >
                Lihat {sample?.label ?? tradition.name} di katalog
                <ArrowUpRight size={18} aria-hidden="true" />
              </Link>
            </div>
          </aside>
        </div>

        <footer className="nx-study-footer">
          <span>
            <Diamond size={9} aria-hidden="true" />
            Pelan-pelan melihat, lebih dalam mengenal.
          </span>
        </footer>
      </div>
    </div>
  );
}
