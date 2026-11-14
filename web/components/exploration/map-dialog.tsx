"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { exploreRegions, regionHref } from "@/lib/exploration";
import { regionProgress, type JourneyProgress } from "@/lib/journey";
import { MapIcon, MapSurface } from "./map-button";

/** Shared focus trap, Escape handling and focus restoration for map dialogs. */
export function MapDialog({
  title,
  children,
  onClose,
  className = "",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  className?: string;
}) {
  // Capture before the parent commits `inert` to the map, which blurs its trigger.
  const returnFocus = useRef(
    typeof document !== "undefined" &&
      document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null,
  );
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(
    () => () => {
      const target = returnFocus.current;
      requestAnimationFrame(() => {
        if (target?.isConnected && !target.closest("[inert]"))
          target.focus({ preventScroll: true });
      });
    },
    [],
  );
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current
      ?.querySelector<HTMLElement>("button,a,input,select,textarea,[tabindex]")
      ?.focus({ preventScroll: true });
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const nodes = [
        ...panel.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]),a[href],input,select,textarea,[tabindex="0"]',
        ),
      ].filter((node) => node.getClientRects().length);
      if (!nodes.length) return;
      if (event.shiftKey && document.activeElement === nodes[0]) {
        event.preventDefault();
        nodes[nodes.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) {
        event.preventDefault();
        nodes[0].focus();
      }
    };
    document.addEventListener("keydown", keydown);
    // Mount once: parent updates must not refocus the close button or reset scroll.
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keydown);
    };
  }, []);
  return (
    <div className={`map-dialog-theme${className ? ` ${className}-theme` : ""}`}>
      <div
        className="modal-backdrop"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) onClose();
        }}
      >
        <section ref={panel} className={`modal ${className}`} role="dialog" aria-modal="true" aria-label={title}>
          <header className="row-between">
            <h2>{title}</h2>
            <button className="icon-button" aria-label="Tutup" onClick={onClose}>
              <X size={19} />
            </button>
          </header>
          {children}
        </section>
      </div>
    </div>
  );
}

export function MapDestinationsDialog({
  progress,
  visited,
  selected,
  onSelect,
  onClose,
}: {
  progress: JourneyProgress;
  visited: string[];
  selected: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <MapDialog title="Pilih tujuan perjalanan" onClose={onClose} className="map-passport-dialog">
      <div className="map-passport-ornament map-passport-ornament--top" aria-hidden="true" />
      <div className="map-passport-ornament map-passport-ornament--bottom" aria-hidden="true" />
      <span className="map-passport-divider" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none"><path d="M16 3c-8 6-8 10 0 11 8-1 8-5 0-11Zm0 26c-8-6-8-10 0-11 8 1 8 5 0 11ZM3 16c6-8 10-8 11 0-1 8-5 8-11 0Zm26 0c-6-8-10-8-11 0 1 8 5 8 11 0Z" stroke="currentColor" strokeWidth="1.6" /></svg>
      </span>
      <div className="map-destination-intro">
        <p>Temukan cerita budaya dan tenun dari setiap daerah.</p>
        <span className="map-destination-count">
          {visited.length} / {exploreRegions.length} dikunjungi
        </span>
      </div>
      <div className="map-destination-grid">
        {exploreRegions.map((region) => {
          const percent = regionProgress(progress, region.id),
            hasVisited = visited.includes(region.id);
          return (
            // Navigation stays in the mounted world; native links avoid prefetching
            // nine regional pages when the passport opens or its cards scroll in.
            <a
              key={region.id}
              href={regionHref(region.id)}
              className="map-destination-card"
              data-selected={selected === region.id}
              onClick={(event) => {
                if (
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey
                )
                  return;
                event.preventDefault();
                onSelect(region.id);
              }}
            >
              <MapSurface />
              <span className="map-destination-copy">
                <strong>{region.name}</strong>
                <span className="map-destination-province">
                  {region.province}
                </span>
                <span className="map-destination-progress-label">
                  {percent}% cerita dijelajahi
                </span>
                <span className="map-destination-track" role="progressbar" aria-label={`Progres cerita ${region.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
                  <span style={{ width: `${percent}%` }} />
                </span>
              </span>
              <span
                className={`map-destination-status${hasVisited ? " is-visited" : ""}`}
                role="img"
                aria-label={hasVisited ? "Sudah dikunjungi" : "Jelajahi daerah"}
              >
                <MapIcon name={hasVisited ? "check" : "arrow"} />
              </span>
            </a>
          );
        })}
      </div>
      <div className="map-passport-landscape" aria-hidden="true" />
    </MapDialog>
  );
}
