"use client";

import { useEffect, useRef } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  House,
  Layers3,
  Leaf,
  MapPin,
} from "lucide-react";
import { type ExploreRegion } from "@/lib/exploration";
import { regionStories } from "@/lib/region-stories";
import { catalogSamplesForTradition } from "@/lib/gallery-samples";
import { asset } from "@/lib/gallery-data";
import { textileTraditions } from "@/lib/exploration";
import {
  chapterLabels,
  journeyChapters,
  type JourneyChapter,
} from "@/lib/journey";
import { MapButton, MapIcon } from "./map-button";

const chapterIcons = { culture: House, weaving: Leaf, textiles: Layers3 };

function WovenMark() {
  return (
    <svg
      className="nx-woven-watermark"
      viewBox="0 0 180 260"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="m90 10 72 72-72 72L18 82 90 10Zm0 72 72 72-72 72-72-72 72-72Zm0 72 42 42-42 42-42-42 42-42Z"
        stroke="currentColor"
        strokeWidth="14"
      />
      <path
        d="m90 46 36 36-36 36-36-36 36-36Zm0 72 36 36-36 36-36-36 36-36Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function RegionOverview({
  region,
  read,
  onChapter,
  onFreeExplore,
  onCards,
  simplified = false,
  fallback = false,
}: {
  region: ExploreRegion;
  read: JourneyChapter[];
  onChapter: (chapter: JourneyChapter) => void;
  onFreeExplore: () => void;
  onCards: () => void;
  simplified?: boolean;
  fallback?: boolean;
}) {
  return (
    <aside
      className="nx-world-overview"
      aria-label={`Pengantar ${region.name}`}
    >
      <div className="nx-overview-scroll">
        <span className="nx-region-tag">
          <MapPin size={12} />
          {region.province}
        </span>
        <span className="nx-small-label">Kenali tempat, temui tenunnya</span>
        <h1>{region.name}</h1>
        <h2>{region.tagline}</h2>
        <p>{region.introduction}</p>
        {simplified ? (
          <>
            <p className="nx-region-prompt">
              {fallback
                ? "Pilih cerita untuk mulai menjelajah."
                : "Pilih penanda pada pulau untuk membuka cerita."}
            </p>
            {fallback && (
              <div
                className="nx-region-fallback-stories"
                aria-label="Pilih cerita Bali"
              >
                {journeyChapters.map((item) => (
                  <MapButton
                    key={item}
                    onClick={() => onChapter(item)}
                    trailing={<ArrowRight size={16} />}
                  >
                    {chapterLabels[item]}{" "}
                    {read.includes(item) ? "· Sudah dibaca" : ""}
                  </MapButton>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <MapButton
              variant="text"
              className="nx-overview-read"
              trailing={<ArrowRight size={15} />}
              onClick={() => onChapter("culture")}
            >
              Baca cerita budaya
            </MapButton>
            <div
              className="nx-overview-route"
              aria-label="Cerita yang dapat dijelajahi"
            >
              {journeyChapters.map((chapter, index) => (
                <MapButton
                  variant="text"
                  key={chapter}
                  data-chapter-link={chapter}
                  icon={
                    <span className="nx-route-number">
                      {read.includes(chapter) ? (
                        <Check size={13} />
                      ) : (
                        `0${index + 1}`
                      )}
                    </span>
                  }
                  trailing={<ArrowUpRight size={14} />}
                  onClick={() => onChapter(chapter)}
                >
                  {chapterLabels[chapter]}
                </MapButton>
              ))}
            </div>
          </>
        )}
      </div>
      {!simplified && (
        <div className="nx-overview-actions">
          <MapButton
            className="nx-overview-primary"
            trailing={<ArrowRight size={17} />}
            onClick={onFreeExplore}
          >
            Jelajahi diorama
          </MapButton>
          <MapButton icon={<MapIcon name="catalog" />} onClick={onCards}>
            Kain daerah ini
          </MapButton>
        </div>
      )}
    </aside>
  );
}

export function RegionStoryPanel({
  region,
  chapter,
  onChapter,
  onClose,
  onCards,
  motifCardsOpen = false,
}: {
  region: ExploreRegion;
  chapter: JourneyChapter;
  onChapter: (chapter: JourneyChapter) => void;
  onClose: () => void;
  onCards: () => void;
  motifCardsOpen?: boolean;
}) {
  const index = journeyChapters.indexOf(chapter);
  const previous = journeyChapters[index - 1];
  const next = journeyChapters[index + 1];
  const Icon = chapterIcons[chapter];
  const story = regionStories[region.id];
  const [opening, continuation] = story.chapters[chapter];
  const regionTraditions = textileTraditions.filter(
    (item) => item.regionId === region.id,
  );
  const images = regionTraditions.flatMap((item) =>
    catalogSamplesForTradition(item.id),
  );
  const illustration = images[index % Math.max(images.length, 1)];
  const title = useRef<HTMLHeadingElement>(null),
    scroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroll.current?.scrollTo({ top: 0 });
    title.current?.focus({ preventScroll: true });
  }, [region.id, chapter]);
  return (
    <aside
      className="nx-region-panel nx-topic-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="nx-topic-title"
      aria-hidden={motifCardsOpen || undefined}
      inert={motifCardsOpen}
    >
      <WovenMark />
      <header className="nx-topic-header">
        <span className="nx-topic-emblem">
          <Icon size={30} strokeWidth={1.5} />
        </span>
        <MapButton
          className="nx-topic-close"
          trailing={<MapIcon name="close" />}
          onClick={onClose}
        >
          Tutup
        </MapButton>
      </header>
      <div className="nx-panel-scroll nx-topic-scroll" ref={scroll}>
        <span className="nx-small-label">
          {region.name} / {chapterLabels[chapter]}
        </span>
        {illustration && (
          <div className="nx-story-visual">
            <img src={asset(illustration.images[2])} alt="" />
            <span>
              <small>CATATAN PERJALANAN · {region.name}</small>
              <strong>{chapterLabels[chapter]}</strong>
              <i>Ilustrasi koleksi tenun</i>
            </span>
          </div>
        )}
        <h2 id="nx-topic-title" ref={title} tabIndex={-1}>
          {opening.title}
        </h2>
        <p className="nx-topic-lead">{opening.lead}</p>
        <p>{opening.detail}</p>
        <h3 className="nx-story-subheading">{continuation.title}</h3>
        <p>{continuation.lead}</p>
        <p>{continuation.detail}</p>
        <div className="nx-story-question">
          <span aria-hidden="true">✳</span>
          <p>{continuation.question}</p>
        </div>
      </div>
      <footer className="nx-topic-footer">
        <nav className="nx-topic-stepper" aria-label="Navigasi cerita daerah">
          <button
            aria-label={previous ? `Kembali ke ${chapterLabels[previous]}` : "Kembali ke diorama"}
            onClick={previous ? () => onChapter(previous) : onClose}
          >
            <ChevronLeft size={19} />
            <span>{previous ? chapterLabels[previous] : "Diorama"}</span>
          </button>
          <span className="nx-chapter-position">0{index + 1} / 03</span>
          <button
            aria-label={
              next ? `Buka ${chapterLabels[next]}` : "Jelajahi kartu kain"
            }
            onClick={next ? () => onChapter(next) : onCards}
          >
            <span>
              {next ? chapterLabels[next] : "Kartu kain"}
            </span>
            <ChevronRight size={19} />
          </button>
        </nav>
      </footer>
    </aside>
  );
}
