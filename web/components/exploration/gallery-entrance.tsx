"use client";
/* Entrance timing synchronizes session storage and renderer readiness. */
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Volume2, VolumeX } from "lucide-react";
import { MapButton } from "./map-button";

const SESSION_KEY = "tenara-gallery-entered:v1";
type EntrancePhase =
  "loading" | "returning" | "welcome" | "leaving" | "entered";

export function useGalleryEntrance(
  ready: boolean,
  instant: boolean,
  skipWelcome = false,
) {
  const [phase, setPhase] = useState<EntrancePhase>(
    skipWelcome ? "returning" : "loading",
  );
  const [canContinue, setCanContinue] = useState(false);
  useEffect(() => {
    try {
      if (sessionStorage.getItem(SESSION_KEY) === "yes") setPhase("returning");
    } catch {
      /* Optional storage. */
    }
    const timer = setTimeout(() => setCanContinue(true), 1600);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!ready) return;
    if (phase === "returning") setPhase("entered");
    else if (phase === "loading" && canContinue) setPhase("welcome");
  }, [ready, canContinue, phase]);
  useEffect(() => {
    if (phase !== "leaving") return;
    const timer = setTimeout(() => setPhase("entered"), instant ? 0 : 950);
    return () => clearTimeout(timer);
  }, [phase, instant]);
  const enter = () => {
    if (!ready || phase !== "welcome") return;
    try {
      sessionStorage.setItem(SESSION_KEY, "yes");
    } catch {
      /* Optional storage. */
    }
    setPhase("leaving");
  };
  return { phase, active: phase !== "entered", enter };
}

function WovenSeal({ animated = false }: { animated?: boolean }) {
  return (
    <svg
      className={`nx-gate-seal ${animated ? "is-weaving" : ""}`}
      viewBox="0 0 120 120"
      fill="none"
      aria-hidden="true"
    >
      <path
        className="nx-gate-thread"
        d="M60 5 115 60 60 115 5 60ZM60 20 100 60 60 100 20 60ZM60 36 84 60 60 84 36 60ZM60 50 70 60 60 70 50 60ZM21 21 99 99M99 21 21 99"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <path
        d="M60 5v15M115 60h-15M60 115v-15M5 60h15"
        stroke="currentColor"
        strokeWidth="3"
      />
    </svg>
  );
}

function CloudBank({ side }: { side: "left" | "right" }) {
  return (
    <svg
      className={`nx-gate-cloud nx-gate-cloud-${side}`}
      viewBox="0 0 650 1000"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M0 0H320C510-30 570 60 480 160C610 180 650 310 515 355C650 445 610 560 500 600C625 710 600 810 470 850C550 950 450 1040 300 1000H0Z"
        fill="currentColor"
        opacity=".42"
      />
      <path
        d="M0 0H195C385 20 440 125 340 210C460 260 475 365 360 410C455 495 420 580 320 640C470 725 420 830 310 870C380 960 280 1010 170 1000H0Z"
        fill="currentColor"
        opacity=".45"
      />
    </svg>
  );
}

export function GalleryEntrance({
  phase,
  ready,
  onEnter,
  onLightMode,
}: {
  phase: EntrancePhase;
  ready: boolean;
  onEnter: (sound: boolean) => void;
  onLightMode: () => void;
}) {
  const primary = useRef<HTMLButtonElement>(null);
  const silent = useRef<HTMLButtonElement>(null);
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (phase === "welcome") primary.current?.focus({ preventScroll: true });
  }, [phase]);
  useEffect(() => {
    if (ready) return;
    const timer = setTimeout(() => setSlow(true), 12000);
    return () => clearTimeout(timer);
  }, [ready]);
  if (phase === "entered") return null;
  const welcome = phase === "welcome" || phase === "leaving";
  return (
    <section
      className="nx-gallery-entrance"
      data-phase={phase}
      role={welcome ? "dialog" : "region"}
      aria-modal={welcome || undefined}
      aria-labelledby={welcome ? "nx-gate-title" : "nx-loading-title"}
      onKeyDown={(event) => {
        if (!welcome || event.key !== "Tab") return;
        if (event.shiftKey && document.activeElement === primary.current) {
          event.preventDefault();
          silent.current?.focus();
        } else if (
          !event.shiftKey &&
          document.activeElement === silent.current
        ) {
          event.preventDefault();
          primary.current?.focus();
        }
      }}
    >
      <div className="nx-gate-grain" aria-hidden="true" />
      <CloudBank side="left" />
      <CloudBank side="right" />
      <div className="nx-gate-sparks" aria-hidden="true">
        {Array.from({ length: 14 }, (_, i) => (
          <i
            key={i}
            style={{
              left: `${7 + ((i * 37) % 87)}%`,
              top: `${10 + ((i * 23) % 77)}%`,
              animationDelay: `${-i * 0.7}s`,
            }}
          />
        ))}
      </div>
      <header className="nx-gate-header">
        <span className="nx-gate-brand">
          <WovenSeal />
          Tenara
        </span>
        <span>Galeri wastra · Indonesia</span>
      </header>
      {welcome ? (
        <>
          <div className="nx-gate-welcome">
            <span className="nx-gate-kicker">Pulau, benang, dan cerita</span>
            <h1 id="nx-gate-title">
              <em>Jelajah</em>
              <span>Nusantara</span>
            </h1>
            <div className="nx-gate-divider" aria-hidden="true">
              <i />
              <span>◇</span>
              <i />
            </div>
            <p>
              Kenali tempat. Temui budayanya.
              <br />
              Jelajahi cerita yang hidup di setiap helai kain.
            </p>
            <MapButton
              ref={primary}
              className="nx-gate-start"
              icon={<Volume2 size={18} />}
              trailing={<ArrowRight size={19} />}
              onClick={() => onEnter(true)}
              data-audio="off"
              disabled={phase === "leaving"}
            >
              Mulai perjalanan
            </MapButton>
            <small className="nx-gate-sound-hint">
              Dengan musik dan suara · paling nyaman memakai headphone
            </small>
          </div>
          <footer className="nx-gate-footer">
            <button
              ref={silent}
              className="nx-gate-silent"
              onClick={() => onEnter(false)}
              disabled={phase === "leaving"}
              data-audio="off"
            >
              <VolumeX size={15} />
              Masuk tanpa suara
            </button>
            <span>Sembilan daerah. Beragam tradisi. Satu perjalanan.</span>
          </footer>
        </>
      ) : (
        <>
          <div className="nx-gate-narrative">
            <WovenSeal animated />
            <span className="nx-gate-kicker">
              Sebuah perjalanan mengenal tenun
            </span>
            <h2 id="nx-loading-title">
              Di setiap helai,
              <br />
              <em>ada cerita.</em>
            </h2>
            <p>
              Melintasi pulau, mengenal budaya,
              <br />
              dan menemui tangan-tangan yang merawat tradisi.
            </p>
          </div>
          <footer className="nx-gate-loading" role="status" aria-live="polite">
            <div className="nx-gate-loading-line" data-ready={ready} />
            <span>
              {ready ? "Perjalananmu siap dimulai" : "Menyiapkan perjalananmu…"}
            </span>
            <small>
              {ready
                ? "Selamat datang di Tenara"
                : "Pulau, benang, dan cerita Nusantara"}
            </small>
            {slow && !ready && (
              <button onClick={onLightMode}>
                Gunakan mode ringan <ArrowRight size={14} />
              </button>
            )}
          </footer>
        </>
      )}
    </section>
  );
}
