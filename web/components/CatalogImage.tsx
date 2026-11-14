"use client";

import { useEffect, useRef, useState } from "react";

/** Keep the previous photo visible until its replacement has loaded and faded in. */
export function CatalogImage({ src, alt, priority = false }: { src: string; alt: string; priority?: boolean }) {
  const [displayed, setDisplayed] = useState(src);
  return <>
    <img className="catalog-image-base" src={displayed} alt={alt} fetchPriority={priority ? "high" : "auto"} loading={priority ? "eager" : "lazy"} />
    {src !== displayed && <IncomingImage key={src} src={src} onComplete={() => setDisplayed(src)} />}
  </>;
}

function IncomingImage({ src, onComplete }: { src: string; onComplete: () => void }) {
  const [ready, setReady] = useState(false);
  const frame = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; cancelAnimationFrame(frame.current); };
  }, []);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => { if (media.matches && ready) onComplete(); };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [ready, onComplete]);
  return <img className={`catalog-image-incoming${ready ? " is-ready" : ""}`} src={src} alt="" aria-hidden="true" onLoad={async (event) => {
    await event.currentTarget.decode().catch(() => {});
    if (!mounted.current) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { onComplete(); return; }
    // Paint the loaded replacement at opacity zero before beginning the blend, even from cache.
    frame.current = requestAnimationFrame(() => {
      frame.current = requestAnimationFrame(() => {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) onComplete();
        else setReady(true);
      });
    });
  }} onTransitionEnd={(event) => { if (event.propertyName === "opacity" && ready) onComplete(); }} />;
}
