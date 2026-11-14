"use client";
/* Browser audio preference restoration is client-only state hydration. */
/* eslint-disable react-hooks/set-state-in-effect */

import { useCallback, useEffect, useRef, useState } from "react";

const MUSIC_URL = "/assets/exploration/audio/bali-xylophone-loop-2.mp3";
const PREFERENCE_KEY = "tenara-gallery-audio:v1";
type AudioPreferences = { muted: boolean; music: number; effects: number };
export type GallerySound =
  | "hover"
  | "click"
  | "select"
  | "open"
  | "close"
  | "step"
  | "travel"
  | "discover";
type AudioStatus = "idle" | "loading" | "ready" | "unavailable";
const defaults: AudioPreferences = { muted: false, music: 0.28, effects: 0.45 };
let musicRequest: Promise<ArrayBuffer> | undefined;

function loadMusic() {
  return (musicRequest ??= fetch(MUSIC_URL)
    .then((response) => {
      if (!response.ok) throw new Error("Soundtrack unavailable");
      return response.arrayBuffer();
    })
    .catch((error) => {
      musicRequest = undefined;
      throw error;
    }));
}

/** One context per gallery visit. The short decoded recording loops without
 * creating a new media element on every region or depending on a remote CDN. */
class GalleryAudioEngine {
  context: AudioContext;
  master: GainNode;
  music: GainNode;
  effects: GainNode;
  source: AudioBufferSourceNode | null = null;
  noise: AudioBuffer;
  disposed = false;
  preparing = false;
  preferences = defaults;
  lastEffect = new Map<GallerySound, number>();

  constructor() {
    const Context =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    this.context = new Context();
    this.master = this.context.createGain();
    this.music = this.context.createGain();
    this.effects = this.context.createGain();
    this.master.gain.value = 0;
    this.music.gain.value = 0;
    this.effects.gain.value = 0;
    this.music.connect(this.master);
    this.effects.connect(this.master);
    this.master.connect(this.context.destination);
    this.noise = this.context.createBuffer(
      1,
      this.context.sampleRate,
      this.context.sampleRate,
    );
    const samples = this.noise.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
  }

  async unlock() {
    if (!this.disposed && this.context.state !== "running")
      await this.context.resume();
  }

  async prepare() {
    this.preparing = true;
    try {
      const data = await loadMusic();
      if (this.disposed) return;
      const buffer = await this.context.decodeAudioData(data.slice(0));
      if (this.disposed || this.source) return;
      const source = this.context.createBufferSource();
      source.buffer = buffer;
      source.loop = true;
      source.connect(this.music);
      const now = this.context.currentTime;
      this.music.gain.cancelScheduledValues(now);
      this.music.gain.setValueAtTime(0, now);
      this.music.gain.linearRampToValueAtTime(
        this.preferences.music,
        now + 1.2,
      );
      source.start();
      this.source = source;
    } finally {
      this.preparing = false;
    }
  }

  apply(preferences: AudioPreferences, fade = 0.15) {
    this.preferences = preferences;
    if (this.disposed) return;
    const now = this.context.currentTime;
    for (const [node, value] of [
      [this.master, preferences.muted || document.hidden ? 0 : 0.85],
      [this.music, preferences.music],
      [this.effects, preferences.effects * 0.6],
    ] as const) {
      node.gain.cancelScheduledValues(now);
      node.gain.setValueAtTime(node.gain.value, now);
      node.gain.linearRampToValueAtTime(value, now + fade);
    }
  }

  visibility() {
    if (this.disposed) return;
    if (document.hidden) {
      void this.context.suspend().catch(() => {});
    } else if (this.context.state === "suspended") {
      void this.context
        .resume()
        .then(() => this.apply(this.preferences))
        .catch(() => {});
    }
  }

  play(sound: GallerySound) {
    if (
      this.disposed ||
      this.preferences.muted ||
      this.preferences.effects === 0 ||
      document.hidden ||
      this.context.state !== "running"
    )
      return;
    const now = this.context.currentTime;
    if (
      now - (this.lastEffect.get(sound) ?? -10) <
      (sound === "hover" ? 0.1 : 0.07)
    )
      return;
    this.lastEffect.set(sound, now);
    const tone = (
      frequency: number,
      delay: number,
      duration: number,
      volume: number,
      end = frequency,
      shape: OscillatorType = "sine",
    ) => {
      const oscillator = this.context.createOscillator(),
        envelope = this.context.createGain();
      oscillator.type = shape;
      oscillator.frequency.setValueAtTime(frequency, now + delay);
      oscillator.frequency.exponentialRampToValueAtTime(
        end,
        now + delay + duration,
      );
      envelope.gain.setValueAtTime(0.0001, now + delay);
      envelope.gain.exponentialRampToValueAtTime(volume, now + delay + 0.006);
      envelope.gain.exponentialRampToValueAtTime(
        0.0001,
        now + delay + duration,
      );
      oscillator.connect(envelope);
      envelope.connect(this.effects);
      oscillator.start(now + delay);
      oscillator.stop(now + delay + duration + 0.01);
      oscillator.onended = () => {
        oscillator.disconnect();
        envelope.disconnect();
      };
    };
    if (sound === "hover") tone(740, 0, 0.07, 0.07, 610, "triangle");
    else if (sound === "click") {
      tone(520, 0, 0.11, 0.22, 300, "triangle");
      tone(1040, 0.012, 0.07, 0.07, 780);
    } else if (sound === "select") {
      tone(523, 0, 0.18, 0.18, 560, "triangle");
      tone(784, 0.065, 0.24, 0.13, 820);
    } else if (sound === "open") {
      tone(392, 0, 0.16, 0.16, 470, "triangle");
      tone(659, 0.055, 0.22, 0.12, 710);
    } else if (sound === "close") {
      tone(570, 0, 0.12, 0.14, 350, "triangle");
      tone(350, 0.045, 0.14, 0.08, 260);
    } else if (sound === "step") {
      tone(620, 0, 0.12, 0.16, 710, "triangle");
      tone(930, 0.025, 0.1, 0.07, 980);
    } else if (sound === "discover")
      [523, 659, 784].forEach((note, i) => tone(note, i * 0.1, 0.4, 0.13));
    else {
      const source = this.context.createBufferSource(),
        filter = this.context.createBiquadFilter(),
        envelope = this.context.createGain();
      source.buffer = this.noise;
      filter.type = "bandpass";
      filter.Q.value = 0.65;
      filter.frequency.setValueAtTime(350, now);
      filter.frequency.linearRampToValueAtTime(1500, now + 0.4);
      filter.frequency.linearRampToValueAtTime(500, now + 0.9);
      envelope.gain.setValueAtTime(0, now);
      envelope.gain.linearRampToValueAtTime(0.12, now + 0.3);
      envelope.gain.linearRampToValueAtTime(0, now + 0.95);
      source.connect(filter);
      filter.connect(envelope);
      envelope.connect(this.effects);
      source.start();
      source.stop(now + 0.96);
      source.onended = () => {
        source.disconnect();
        filter.disconnect();
        envelope.disconnect();
      };
    }
  }

  dispose() {
    this.disposed = true;
    this.source?.stop();
    this.source?.disconnect();
    void this.context.close().catch(() => {});
  }
}

export function useGalleryAudio() {
  const [preferences, setPreferences] = useState(defaults);
  const current = useRef(defaults);
  const engine = useRef<GalleryAudioEngine | null>(null);
  const alive = useRef(false);
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState<AudioStatus>("idle");
  useEffect(() => {
    alive.current = true;
    try {
      const stored = JSON.parse(localStorage.getItem(PREFERENCE_KEY) ?? "null");
      if (stored && typeof stored.muted === "boolean") {
        const restored = {
          muted: stored.muted,
          music:
            typeof stored.music === "number" && Number.isFinite(stored.music)
              ? Math.min(1, Math.max(0, stored.music))
              : defaults.music,
          effects:
            typeof stored.effects === "number" &&
            Number.isFinite(stored.effects)
              ? Math.min(1, Math.max(0, stored.effects))
              : defaults.effects,
        };
        current.current = restored;
        setPreferences(restored);
      }
    } catch {
      /* Preferences are optional. */
    }
    void loadMusic().catch(() => {});
    const visibility = () => engine.current?.visibility();
    document.addEventListener("visibilitychange", visibility);
    return () => {
      alive.current = false;
      document.removeEventListener("visibilitychange", visibility);
      engine.current?.dispose();
      engine.current = null;
    };
  }, []);

  const update = useCallback((change: Partial<AudioPreferences>) => {
    const next = { ...current.current, ...change };
    current.current = next;
    setPreferences(next);
    engine.current?.apply(next);
    try {
      localStorage.setItem(PREFERENCE_KEY, JSON.stringify(next));
    } catch {
      /* Optional storage. */
    }
  }, []);
  const start = useCallback(
    (enabled: boolean, initialSound?: GallerySound) => {
      update({ muted: !enabled });
      if (!enabled) return;
      try {
        if (!engine.current) {
          const audio = new GalleryAudioEngine();
          engine.current = audio;
          audio.apply(current.current);
          setStatus("loading");
          // Resume synchronously from the initiating click, before fetching/decoding.
          void audio
            .unlock()
            .then(() => {
              if (alive.current && engine.current === audio) {
                setActive(true);
                if (initialSound) audio.play(initialSound);
              }
            })
            .catch(() => {
              if (alive.current) {
                setActive(false);
                setStatus("unavailable");
              }
            });
          void audio
            .prepare()
            .then(() => {
              if (alive.current && engine.current === audio) setStatus("ready");
            })
            .catch(() => {
              if (alive.current && engine.current === audio)
                setStatus("unavailable");
            });
        } else {
          const audio = engine.current;
          void audio
            .unlock()
            .then(() => {
              if (alive.current && engine.current === audio) {
                setActive(true);
                if (initialSound) audio.play(initialSound);
              }
            })
            .catch(() => {
              if (alive.current) {
                setActive(false);
                setStatus("unavailable");
              }
            });
          if (!audio.source && !audio.preparing) {
            setStatus("loading");
            void audio
              .prepare()
              .then(() => {
                if (alive.current && engine.current === audio)
                  setStatus("ready");
              })
              .catch(() => {
                if (alive.current && engine.current === audio)
                  setStatus("unavailable");
              });
          }
        }
      } catch {
        setActive(false);
        setStatus("unavailable");
      }
    },
    [update],
  );
  const play = useCallback(
    (sound: GallerySound, userGesture = false) => {
      if (current.current.muted) return;
      if (!engine.current || engine.current.context.state !== "running") {
        // Only a direct user gesture can reliably unlock audio after returning.
        if (userGesture) start(true, sound);
        return;
      }
      engine.current.play(sound);
    },
    [start],
  );
  const enabled = active && !preferences.muted;
  const toggle = useCallback(() => {
    if (active && !current.current.muted) update({ muted: true });
    else start(true);
  }, [active, start, update]);
  return { preferences, active, enabled, status, start, toggle, update, play };
}

export type GalleryAudio = ReturnType<typeof useGalleryAudio>;
