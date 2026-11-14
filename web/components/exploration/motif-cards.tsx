"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, MapPin } from "lucide-react";
import { asset } from "@/lib/gallery-data";
import { catalogSamplesForTradition } from "@/lib/gallery-samples";
import { sampleKnowledge } from "@/lib/gallery-knowledge";
import {
  catalogHref,
  type ExploreRegion,
  type TextileTradition,
} from "@/lib/exploration";
import "./motif-cards.css";

function WovenEmblem({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="m20 2 6 7-6 7-6-7Zm18 18-7 6-7-6 7-6ZM20 38l-6-7 6-7 6 7ZM2 20l7-6 7 6-7 6Z" stroke="currentColor" strokeWidth="2.3" />
      <path d="m20 12 8 8-8 8-8-8Z" stroke="currentColor" strokeWidth="2" />
      <path d="m20 17 3 3-3 3-3-3Z" fill="currentColor" />
    </svg>
  );
}

function Landscape() {
  return (
    <svg
      className="nx-motif-landscape"
      viewBox="0 0 1536 190"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <pattern id="nx-motif-landscape-weave" width="80" height="40" patternUnits="userSpaceOnUse">
          <image href="/assets/exploration/motif-woven-border.svg" width="80" height="40" />
        </pattern>
      </defs>
      <path fill="#a3b093" d="M987 160c97-26 172-55 246-112 22-19 27-5 42-13 17-10 32 24 84 45 48 20 111 25 177 35v75H987Z" />
      <path fill="#8e9e7e" d="M0 141c141 8 235-32 366-44s164 56 291 58c277 7 393-68 494-50 72 13 89 31 160 13 109-28 145-21 225-6v78H0Z" />
      <path fill="#b75b2c" d="M0 155c137-56 233-35 344-11s200 32 325 0 123-28 227-4c210 49 403-22 640-52v102H0Z" />
      <path fill="#154d37" d="M0 85c68-36 172 12 279 49 142 49 187-28 308-12 137 18 210 65 354 20s178-45 278-8c138 51 211-10 317 4v52H0Z" />
      <path d="M0 155c137-56 233-35 344-11s200 32 325 0" stroke="#e6bd72" fill="none" />
      <g fill="#e9bf7d" opacity=".7">
        <path d="M1056 88c24 3 31-19 46-15 3-26 36-34 51-10 23-3 29 24 53 20-34 13-56-1-76 7-26 8-48-8-74-2Z" />
        <path d="M1331 53c30 3 34-20 56-16 9-28 41-27 51-6 21-2 31 27 68 23-48 14-65-6-83 2-31 13-57-9-92-3Z" />
      </g>
      <g stroke="#fff1cd" strokeWidth="1.5" fill="none" opacity=".9">
        <path d="M1131 79c-22 4-25-20-7-21 14-1 12 15 3 12M1414 47c-22 4-25-20-7-21 14-1 12 15 3 12" />
      </g>
      <rect y="150" width="1536" height="40" fill="url(#nx-motif-landscape-weave)" />
    </svg>
  );
}

export function MotifCards({
  region,
  traditions,
  onClose,
  reducedMotion,
}: {
  region: ExploreRegion;
  traditions: TextileTradition[];
  onClose: () => void;
  reducedMotion: boolean;
}) {
  const entries = useMemo(
    () =>
      traditions.flatMap((tradition) =>
        catalogSamplesForTradition(tradition.id).map((sample) => ({
          sample,
          tradition,
        })),
      ),
    [traditions],
  );
  const [selectedCode, setSelectedCode] = useState("");
  const [openedCodes, setOpenedCodes] = useState<Set<string>>(() => new Set());
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const rail = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const selectedIndex = entries.findIndex(
    ({ sample }) => sample.code === selectedCode,
  );
  const navigationIndex = Math.max(0, selectedIndex);
  const selectedEntry = entries[navigationIndex];

  useEffect(() => {
    close.current?.focus();
  }, []);

  const select = (index: number, focus = false) => {
    if (!entries.length) return;
    const nextIndex = (index + entries.length) % entries.length;
    const entry = entries[nextIndex];
    setSelectedCode(entry.sample.code);
    setOpenedCodes((previous) => new Set(previous).add(entry.sample.code));
    const card = cardRefs.current[entry.sample.code];
    if (card && rail.current) {
      const railBox = rail.current.getBoundingClientRect();
      const cardBox = card.getBoundingClientRect();
      rail.current.scrollTo({
        left:
          rail.current.scrollLeft +
          cardBox.left +
          cardBox.width / 2 -
          (railBox.left + railBox.width / 2),
        behavior: reducedMotion ? "auto" : "smooth",
      });
    }
    if (focus)
      requestAnimationFrame(() => card?.focus({ preventScroll: true }));
  };

  return (
    <div
      className={`nx-motif-overlay${reducedMotion ? " nx-motif-still" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="nx-motif-heading"
      ref={dialog}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          onClose();
          return;
        }
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          select(navigationIndex + (event.key === "ArrowRight" ? 1 : -1), true);
          return;
        }
        if (event.key !== "Tab") return;
        const nodes = [
          ...(dialog.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]),a[href],[tabindex="0"]',
          ) ?? []),
        ].filter(
          (node) => !node.closest("[inert]") && node.getClientRects().length,
        );
        if (!nodes.length) return;
        if (event.shiftKey && document.activeElement === nodes[0]) {
          event.preventDefault();
          nodes[nodes.length - 1].focus();
        } else if (
          !event.shiftKey &&
          document.activeElement === nodes[nodes.length - 1]
        ) {
          event.preventDefault();
          nodes[0].focus();
        }
      }}
    >
      <header className="nx-motif-header">
        <button
          type="button"
          ref={close}
          className="nx-motif-close"
          onClick={onClose}
        >
          <ArrowLeft size={20} /> Kembali ke cerita
        </button>
        <div className="nx-motif-brand" aria-hidden="true">
          <WovenEmblem /> tenara<span>.</span>
        </div>
        <span className="nx-motif-region">{region.province}</span>
      </header>
      <div className="nx-motif-content">
        <div className="nx-motif-intro">
          <span><WovenEmblem /> Koleksi {region.name} <WovenEmblem /></span>
          <h2 id="nx-motif-heading">
            Pilih <em>sehelai cerita.</em>
          </h2>
          <p>Pilih kartu untuk membaca kisah kain dan motifnya.</p>
        </div>
        {entries.length ? (
          <>
            <div
              className="nx-motif-rail"
              ref={rail}
              aria-label={`Kartu kain ${region.name}`}
            >
              {entries.map(({ sample, tradition }, index) => {
                const info = sampleKnowledge[sample.code];
                const isSelected = selectedCode === sample.code;
                const isOpen = openedCodes.has(sample.code);
                return (
                  <article
                    className={`nx-motif-card${isSelected ? " is-selected" : ""}${isOpen ? " is-open" : ""}`}
                    data-tone={index % 4}
                    key={sample.code}
                    style={{ "--nx-card-index": index } as React.CSSProperties}
                  >
                    <button
                      ref={(node) => {
                        cardRefs.current[sample.code] = node;
                      }}
                      className="nx-motif-card-select"
                      type="button"
                      aria-pressed={isOpen}
                      aria-label={`${isOpen ? "Tutup" : "Buka"} kartu ${sample.label}, ${tradition.name}`}
                      aria-describedby={isOpen ? `nx-motif-story-${sample.code}` : undefined}
                      onClick={() => {
                        if (!isOpen) select(index);
                        else {
                          setSelectedCode(sample.code);
                          setOpenedCodes((previous) => {
                            const next = new Set(previous);
                            next.delete(sample.code);
                            return next;
                          });
                        }
                      }}
                    >
                      <span className="nx-motif-card-turn">
                        <span className="nx-motif-card-face nx-motif-card-back" aria-hidden="true">
                          <span className="nx-motif-card-ornament" />
                          <span className="nx-motif-card-invitation">Ketuk untuk membuka</span>
                        </span>
                        <span className="nx-motif-card-face nx-motif-card-front" aria-hidden={!isOpen}>
                          <span className="nx-motif-card-art">
                            <img
                              src={asset(sample.images[2])}
                              alt={`Ilustrasi kain ${tradition.name}, pilihan ${sample.label}`}
                              loading="eager"
                              decoding="async"
                            />
                          </span>
                          <span className="nx-motif-card-copy">
                            <span className="nx-motif-kind"><WovenEmblem />{tradition.name}<WovenEmblem /></span>
                            <strong>{sample.label}</strong>
                            <span className="nx-motif-story" id={`nx-motif-story-${sample.code}`}>
                              {info?.story ??
                                "Sebuah kisah kain dari koleksi daerah ini."}
                            </span>
                          </span>
                          <span className="nx-motif-origin">
                            <MapPin size={13} fill="currentColor" />
                            {sample.origin.split(",")[0]}
                          </span>
                        </span>
                      </span>
                    </button>
                  </article>
                );
              })}
            </div>
            <div className="nx-motif-controls">
              <button
                type="button"
                onClick={() => select(navigationIndex - 1, true)}
                aria-label="Pilih kartu sebelumnya"
              >
                <ArrowLeft size={18} />
              </button>
              <span aria-live="polite">
                {selectedEntry
                  ? `${String(navigationIndex + 1).padStart(2, "0")} / ${String(entries.length).padStart(2, "0")} · ${selectedEntry.sample.label}`
                  : `${entries.length} pilihan · Pilih satu kartu`}
              </span>
              <button
                type="button"
                onClick={() => select(navigationIndex + 1, true)}
                aria-label="Pilih kartu berikutnya"
              >
                <ArrowRight size={18} />
              </button>
            </div>
            {selectedEntry ? (
              <Link
                className="nx-motif-continue"
                href={`${catalogHref(selectedEntry.tradition.id)}?pilihan=${encodeURIComponent(selectedEntry.sample.code)}`}
              >
                <WovenEmblem /> Lanjutkan ke katalog <WovenEmblem />
              </Link>
            ) : (
              <button className="nx-motif-continue" type="button" disabled>
                <WovenEmblem /> Pilih kartu untuk melanjutkan <WovenEmblem />
              </button>
            )}
          </>
        ) : (
          <p className="nx-motif-empty">
            Kartu kain untuk daerah ini sedang disiapkan.
          </p>
        )}
        <Landscape />
      </div>
    </div>
  );
}
