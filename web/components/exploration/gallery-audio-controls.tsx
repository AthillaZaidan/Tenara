"use client";

import { Volume2, VolumeX } from "lucide-react";
import type { GalleryAudio } from "./gallery-audio";

export function GalleryAudioControls({ audio }: { audio: GalleryAudio }) {
  return (
    <fieldset className="nx-audio-controls">
      <legend>Suara perjalanan</legend>
      <button
        type="button"
        className="nx-audio-switch"
        aria-pressed={audio.enabled}
        onClick={audio.toggle}
        data-audio="off"
      >
        {audio.enabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
        <span>{audio.enabled ? "Suara aktif" : "Aktifkan suara"}</span>
        <i aria-hidden="true" data-on={audio.enabled} />
      </button>
      {(
        [
          ["music", "Musik latar"],
          ["effects", "Efek suara"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="nx-audio-volume">
          <span>
            {label}
            <output>{Math.round(audio.preferences[key] * 100)}%</output>
          </span>
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            aria-label={`Volume ${label.toLowerCase()}`}
            value={Math.round(audio.preferences[key] * 100)}
            onChange={(event) =>
              audio.update({ [key]: Number(event.target.value) / 100 })
            }
          />
        </label>
      ))}
      {audio.status === "loading" && (
        <p className="nx-audio-status" role="status">
          Menyiapkan audio…
        </p>
      )}
      {audio.status === "unavailable" && (
        <p className="nx-audio-status" role="status">
          Audio belum sepenuhnya tersedia. Coba aktifkan kembali.
        </p>
      )}
      <details className="nx-audio-credit">
        <summary>Musik: Bali xylophone · kredit</summary>
        <p>
          <a
            href="https://freesound.org/people/qubodup/sounds/854334/"
            target="_blank"
            rel="noreferrer"
          >
            Bali Gamelan Xylophone Loop 2
          </a>{" "}
          — qubodup, dari rekaman thedialogueproject.{" "}
          <a
            href="https://creativecommons.org/publicdomain/zero/1.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC0
          </a>
          . Diolah untuk loop galeri.
        </p>
      </details>
    </fieldset>
  );
}
