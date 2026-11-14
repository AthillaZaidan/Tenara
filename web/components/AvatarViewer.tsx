"use client";

import { useEffect, useState } from "react";
import type { DetailedHTMLProps, HTMLAttributes } from "react";

type ModelViewerProps = DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
  src: string; alt: string; "camera-controls"?: boolean; "camera-orbit"?: string; "shadow-intensity"?: string;
  exposure?: string; "touch-action"?: string; "interaction-prompt"?: string;
};

declare module "react" {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements { "model-viewer": ModelViewerProps }
  }
}

/** A GLB the viewer can turn and zoom. model-viewer registers a custom element that needs the browser, so it loads here. */
export function AvatarViewer({ src, alt }: { src: string; alt: string }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { import("@google/model-viewer").then(() => setReady(true)); }, []);
  if (!ready) return <div className="grid h-[min(70vh,560px)] place-items-center bg-surface text-base text-muted">Memuat penampil 3D…</div>;
  return (
    <model-viewer src={src} alt={alt} camera-controls camera-orbit="20deg 80deg auto" shadow-intensity="0.6"
      exposure="1.05" touch-action="pan-y" interaction-prompt="none" className="block h-[min(70vh,560px)] w-full bg-surface" />
  );
}
