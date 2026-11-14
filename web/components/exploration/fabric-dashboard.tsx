"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Heart,
  Layers3,
  MapPin,
  X,
} from "lucide-react";
import { asset } from "@/lib/gallery-data";
import { featuredCatalogSample } from "@/lib/gallery-samples";
import {
  catalogHref,
  exploreRegions,
  textileHref,
  textileTraditions,
  type TextileTradition,
} from "@/lib/exploration";
import {
  chapterLabels,
  journeyChapters,
  regionProgress,
  type JourneyProgress,
} from "@/lib/journey";
import { useGalleryFavorites } from "@/lib/gallery-favorites";

function FabricCard({ tradition }: { tradition: TextileTradition }) {
  const { favorites, toggleFavorite } = useGalleryFavorites();
  const saved = favorites.includes(tradition.id);
  return (
    <article className="nx-fabric-collectible">
      <Link
        className="nx-collectible-image"
        href={textileHref(tradition.id)}
        aria-label={`Jelajahi galeri ${tradition.name}`}
      >
        <img
          src={asset(
            featuredCatalogSample(tradition.id)?.thumbnails[0] ??
              tradition.gallery.thumbnails?.[0] ??
              tradition.gallery.image,
          )}
          alt={tradition.name}
          loading="lazy"
        />
        <span>{tradition.technique}</span>
      </Link>
      <button
        className={`nx-save-card ${saved ? "is-saved" : ""}`}
        aria-label={`${saved ? "Hapus" : "Simpan"} ${tradition.name}`}
        aria-pressed={saved}
        onClick={() => toggleFavorite(tradition.id)}
      >
        <Heart size={16} fill={saved ? "currentColor" : "none"} />
      </button>
      <div className="nx-collectible-copy">
        <h3>{tradition.name}</h3>
        <div className="nx-collectible-actions">
          <Link href={textileHref(tradition.id)}>
            <BookOpen size={13} />
            Galeri
          </Link>
          <Link href={catalogHref(tradition.id)}>
            Katalog
            <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>
    </article>
  );
}

export function FabricDashboard({
  regionId,
  progress,
  onClose,
  reducedMotion = false,
}: {
  regionId?: string;
  progress: JourneyProgress;
  onClose: () => void;
  reducedMotion?: boolean;
}) {
  const [scope, setScope] = useState<"related" | "all">("all");
  const dialog = useRef<HTMLDivElement>(null),
    closeButton = useRef<HTMLButtonElement>(null),
    rail = useRef<HTMLDivElement>(null);
  const { favorites } = useGalleryFavorites();
  const regions = exploreRegions
    .filter((region) => scope === "all" || region.id === regionId)
    .sort((a, b) => Number(b.id === regionId) - Number(a.id === regionId));
  const count = textileTraditions.filter(
    (tradition) => scope === "all" || tradition.regionId === regionId,
  ).length;
  const saved = textileTraditions.filter((tradition) =>
    favorites.includes(tradition.id),
  ).length;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key !== "Tab") return;
      const nodes = [
        ...(dialog.current?.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),[tabindex="0"]',
        ) ?? []),
      ].filter((node) => node.getClientRects().length);
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !dialog.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      requestAnimationFrame(() => {
        if (previous?.isConnected) previous.focus();
        else
          document.querySelector<HTMLButtonElement>(".nx-open-cards")?.focus();
      });
    };
  }, [onClose]);
  return (
    <div
      id="nx-card-dashboard"
      className="nx-card-dashboard"
      role="dialog"
      aria-modal="true"
      aria-labelledby="nx-dashboard-heading"
      ref={dialog}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="nx-dashboard-tray">
        <button
          ref={closeButton}
          className="nx-game-button nx-close-dashboard"
          onClick={onClose}
        >
          Tutup kartu <X size={17} />
        </button>
        <div className="nx-dashboard-paper">
          <header className="nx-dashboard-intro">
            <span className="nx-small-label">
              <Layers3 size={15} />
              Koleksi Nusantara
            </span>
            <h2 id="nx-dashboard-heading">
              Temukan
              <br />
              kain ceritamu.
            </h2>
            <p>
              {count} kain tersedia untuk dijelajahi.
              <br />
              {saved} koleksi kamu simpan.
            </p>
            {regionId && (
              <div className="nx-dashboard-scopes" aria-label="Cakupan kartu">
                <button
                  aria-pressed={scope === "related"}
                  onClick={() => {
                    setScope("related");
                    rail.current?.scrollTo({ left: 0 });
                  }}
                >
                  Daerah ini
                </button>
                <button
                  aria-pressed={scope === "all"}
                  onClick={() => setScope("all")}
                >
                  Semua daerah
                </button>
              </div>
            )}
            <Link
              className="nx-dashboard-catalog"
              href={
                regionId && scope === "related"
                  ? `/katalog?daerah=${regionId}`
                  : "/katalog"
              }
            >
              Buka katalog <ArrowRight size={14} />
            </Link>
          </header>
          <div className="nx-dashboard-main">
            <div className="nx-dashboard-toolbar">
              <span>
                {scope === "related"
                  ? "Kain dari daerah yang sedang kamu jelajahi"
                  : "Ragam kain dari seluruh tujuan perjalanan"}
              </span>
              <div>
                <button
                  aria-label="Geser kartu ke kiri"
                  onClick={() =>
                    rail.current?.scrollBy({
                      left: -380,
                      behavior: reducedMotion ? "auto" : "smooth",
                    })
                  }
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  aria-label="Geser kartu ke kanan"
                  onClick={() =>
                    rail.current?.scrollBy({
                      left: 380,
                      behavior: reducedMotion ? "auto" : "smooth",
                    })
                  }
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
            <div
              className="nx-dashboard-rail"
              ref={rail}
              tabIndex={0}
              aria-label="Kartu kain menurut daerah"
            >
              {regions.map((region) => {
                const traditions = textileTraditions.filter(
                  (tradition) => tradition.regionId === region.id,
                );
                const percent = regionProgress(progress, region.id);
                return (
                  <section
                    className={`nx-region-card-group ${region.id === regionId ? "is-current-region" : ""}`}
                    key={region.id}
                  >
                    <div className="nx-group-card-list">
                      {traditions.map((tradition) => (
                        <FabricCard tradition={tradition} key={tradition.id} />
                      ))}
                    </div>
                    <footer>
                      <div>
                        <strong>
                          <MapPin size={12} />
                          {region.name}
                        </strong>
                        <span className={percent === 100 ? "is-complete" : ""}>
                          {percent === 100 && <Check size={10} />} {percent}%
                          cerita dijelajahi
                        </span>
                      </div>
                      <div
                        className="nx-mini-chapters"
                        aria-label={`Progres cerita ${region.name}`}
                      >
                        {journeyChapters.map((chapter) => (
                          <span
                            key={chapter}
                            className={
                              progress[region.id]?.includes(chapter)
                                ? "is-read"
                                : ""
                            }
                            title={`${chapterLabels[chapter]}: ${progress[region.id]?.includes(chapter) ? "sudah dibuka" : "belum dibuka"}`}
                          >
                            <Check size={10} />
                          </span>
                        ))}
                      </div>
                    </footer>
                  </section>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
