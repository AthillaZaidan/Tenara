"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Minus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Sun,
  Sunset,
  X,
} from "lucide-react";
import { MapButton, MapIcon } from "./map-button";
import { GalleryAudioControls } from "./gallery-audio-controls";
import type { GalleryAudio } from "./gallery-audio";

export function ViewControls({
  zoom,
  setZoom,
  onReset,
  paused,
  setPaused,
  timeOfDay,
  setTimeOfDay,
  illustratedMap = false,
  atlas3d = false,
  audio,
}: {
  zoom: number;
  setZoom: (value: number) => void;
  onReset: () => void;
  paused: boolean;
  setPaused: (value: boolean) => void;
  timeOfDay: "day" | "sunset";
  setTimeOfDay: (value: "day" | "sunset") => void;
  illustratedMap?: boolean;
  atlas3d?: boolean;
  audio?: GalleryAudio;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null),
    trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const click = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", click);
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("pointerdown", click);
      document.removeEventListener("keydown", key, true);
    };
  }, [open]);
  return (
    <div className="nx-view-controls" ref={root}>
      <MapButton
        ref={trigger}
        variant="menu"
        className="map-view-trigger"
        icon={<MapIcon name="display" />}
        trailing={<MapIcon name="chevron" />}
        aria-expanded={open}
        aria-controls="nx-view-options"
        onClick={() => setOpen((value) => !value)}
      >
        Tampilan
      </MapButton>
      {open && (
        <div
          className="nx-view-options"
          id="nx-view-options"
          role="region"
          aria-label="Atur tampilan dunia"
        >
          <header>
            <strong>Tampilan dunia</strong>
            <button
              aria-label="Tutup kontrol tampilan"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              <X size={15} />
            </button>
          </header>
          <div className="nx-view-zoom">
            <span>Jarak pandang</span>
            <div>
              <button
                aria-label="Perkecil peta"
                disabled={zoom <= 0.7}
                onClick={() => setZoom(Math.max(0.7, zoom - 0.2))}
              >
                <Minus size={16} />
              </button>
              <output>{Math.round(zoom * 100)}%</output>
              <button
                aria-label="Perbesar peta"
                disabled={zoom >= 2.4}
                onClick={() => setZoom(Math.min(2.4, zoom + 0.2))}
              >
                <Plus size={16} />
              </button>
            </div>
          </div>
          <button className="nx-view-row" onClick={onReset}>
            <RotateCcw size={15} />
            <span>Reset pandangan</span>
          </button>
          <button
            className="nx-view-row"
            aria-pressed={paused}
            onClick={() => setPaused(!paused)}
          >
            {paused ? <Play size={15} /> : <Pause size={15} />}
            <span>{paused ? "Lanjutkan animasi" : "Jeda animasi"}</span>
            {paused && <Check size={14} />}
          </button>
          <div className="nx-view-light">
            <span>Suasana</span>
            <div>
              <button
                aria-pressed={timeOfDay === "day"}
                onClick={() => setTimeOfDay("day")}
              >
                <Sun size={14} />
                Siang
              </button>
              <button
                aria-pressed={timeOfDay === "sunset"}
                onClick={() => setTimeOfDay("sunset")}
              >
                <Sunset size={14} />
                Senja
              </button>
            </div>
          </div>
          {audio && <GalleryAudioControls audio={audio} />}
          <p>
            {atlas3d
              ? "Seret untuk memutar. Shift + seret atau klik kanan untuk menggeser. Scroll / cubit dua jari untuk zoom."
              : illustratedMap
                ? "Geser untuk menjelajah. Scroll atau cubit dua jari untuk zoom; Reset mengembalikan pandangan."
                : "Geser untuk melihat dari sudut lain."}
          </p>
        </div>
      )}
    </div>
  );
}
