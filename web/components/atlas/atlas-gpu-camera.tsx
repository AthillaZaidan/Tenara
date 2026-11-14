"use client";
/* Three.js camera, DOM canvas and render-loop state are deliberately imperative. */
/* eslint-disable react-hooks/immutability, react-hooks/refs */
/* Event listeners intentionally reuse the camera's stable state refs. */
/* eslint-disable react-hooks/exhaustive-deps */

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type RefObject,
} from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { exploreRegions } from "@/lib/exploration";
import {
  ATLAS_WIDTH as W,
  ATLAS_HEIGHT as H,
  atlasLabels,
  atlasLabelNudge,
  atlasProject,
} from "./atlas-layout";
import type { AtlasGpuBridge } from "./atlas-gpu-overlay";

type Props = {
  bridge: RefObject<AtlasGpuBridge>;
  zoom: number;
  reset: number;
  paused: boolean;
  reducedMotion: boolean;
  landPath: string;
  onZoomChange?: (zoom: number) => void;
  onSelectRegion: (id: string) => void;
};
type Pointer = { x: number; y: number };
const clamp = THREE.MathUtils.clamp;

/** A fixed-view 2.5D camera: no React state writes during drag, inertia or pinch. */
export function AtlasGpuCamera(props: Props) {
  const { camera, size, gl, invalidate } = useThree();
  const latest = useRef(props);
  latest.current = props;
  const state = useRef({
    factor: props.zoom,
    target: props.zoom,
    base: 1,
    vx: 0,
    vy: 0,
    moved: false,
    originX: 0,
    originY: 0,
    lastTime: 0,
  });
  const pointers = useRef(new Map<number, Pointer>());
  const rect = useRef({ left: 0, top: 0 });
  // Safe insets determine the home composition, never the drawing boundary.
  const frame = useRef({
    width: size.width,
    height: size.height,
    centerX: size.width / 2,
    centerY: size.height / 2,
    offsetY: 0,
  });
  const reported = useRef(props.zoom),
    reportTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const previousProjection = useRef("");
  const hitTest = useMemo(
    () => ({
      path: new Path2D(props.landPath),
      context: document.createElement("canvas").getContext("2d")!,
    }),
    [props.landPath],
  );

  const bounds = () => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    // Leave navigable ocean around the artwork, including at the home zoom.
    // Tight image-edge clamping makes an otherwise direct drag feel unresponsive.
    const maxX = Math.max(
      140,
      W / 2 - (frame.current.width / (2 * camera.zoom)) * 0.35,
    );
    const maxY = Math.max(
      70,
      H / 2 - (frame.current.height / (2 * camera.zoom)) * 0.45,
    );
    const homeY = frame.current.offsetY / camera.zoom;
    const x = clamp(camera.position.x, -maxX, maxX),
      y = clamp(camera.position.y, homeY - maxY, homeY + maxY);
    if (x !== camera.position.x) state.current.vx = 0;
    if (y !== camera.position.y) state.current.vy = 0;
    camera.position.set(x, y, 1000);
  };
  const applyZoom = (
    factor: number,
    point: Pointer = { x: frame.current.centerX, y: frame.current.centerY },
  ) => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const s = state.current,
      next = clamp(factor, 0.7, 2.4),
      zoom = s.base * next;
    const dx = point.x - size.width / 2,
      dy = size.height / 2 - point.y;
    camera.position.x += dx / camera.zoom - dx / zoom;
    camera.position.y += dy / camera.zoom - dy / zoom;
    s.factor = next;
    camera.zoom = zoom;
    camera.updateProjectionMatrix();
    bounds();
    invalidate();
  };
  const report = () => {
    const value = Math.round(state.current.factor * 100) / 100;
    if (Math.abs(value - reported.current) < 0.005) return;
    reported.current = value;
    latest.current.onZoomChange?.(value);
  };

  useLayoutEffect(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const previousHomeY = frame.current.offsetY / camera.zoom;
    const style = getComputedStyle(
      gl.domElement.closest(".nx-atlas-gpu-stage") ?? gl.domElement,
    );
    const inset = (name: string, total: number) => {
      const value = style.getPropertyValue(name).trim();
      return (parseFloat(value) || 0) * (value.endsWith("%") ? total / 100 : 1);
    };
    const top = inset("--atlas-safe-top", size.height),
      bottom = inset("--atlas-safe-bottom", size.height),
      side = inset("--atlas-safe-side", size.width);
    const width = Math.max(1, size.width - side * 2),
      height = Math.max(1, size.height - top - bottom);
    frame.current = {
      width,
      height,
      centerX: size.width / 2,
      centerY: top + height / 2,
      offsetY: (top - bottom) / 2,
    };
    state.current.base =
      size.width < 600
        ? width / 640
        : size.width < 900
          ? width / 1250
          : Math.min(width / W, height / H);
    camera.left = -size.width / 2;
    camera.right = size.width / 2;
    camera.top = size.height / 2;
    camera.bottom = -size.height / 2;
    camera.near = 0.1;
    camera.far = 2000;
    camera.rotation.set(0, 0, 0);
    camera.up.set(0, 1, 0);
    camera.position.z = 1000;
    camera.zoom = state.current.base * state.current.factor;
    camera.position.y += frame.current.offsetY / camera.zoom - previousHomeY;
    camera.updateProjectionMatrix();
    const box = gl.domElement.getBoundingClientRect();
    rect.current = { left: box.left, top: box.top };
    previousProjection.current = "";
    bounds();
    invalidate();
  }, [camera, size.width, size.height, gl, invalidate]);

  useLayoutEffect(() => {
    state.current.vx = 0;
    state.current.vy = 0;
    state.current.factor = props.zoom;
    state.current.target = props.zoom;
    if (camera instanceof THREE.OrthographicCamera) {
      camera.zoom = state.current.base * props.zoom;
      camera.position.set(0, frame.current.offsetY / camera.zoom, 1000);
      camera.updateProjectionMatrix();
    }
    invalidate();
  }, [props.reset, camera, invalidate]);
  useEffect(() => {
    if (Math.abs(props.zoom - reported.current) > 0.001) {
      state.current.target = props.zoom;
      reported.current = props.zoom;
      state.current.vx = 0;
      state.current.vy = 0;
    }
  }, [props.zoom]);

  useEffect(() => {
    const canvas = gl.domElement;
    canvas.tabIndex = 0;
    canvas.style.cursor = "grab";
    canvas.setAttribute(
      "aria-label",
      "Peta interaktif Indonesia. Seret untuk menjelajah, scroll atau cubit dua jari untuk memperbesar. Gunakan tombol panah untuk bergeser dan Home untuk mengatur ulang.",
    );
    const point = (event: { clientX: number; clientY: number }): Pointer => ({
      x: event.clientX - rect.current.left,
      y: event.clientY - rect.current.top,
    });
    const down = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && event.button > 0) return;
      const box = canvas.getBoundingClientRect();
      rect.current = { left: box.left, top: box.top };
      const p = point(event),
        s = state.current;
      if (!pointers.current.size) {
        s.moved = false;
        s.originX = p.x;
        s.originY = p.y;
      } else s.moved = true;
      s.vx = 0;
      s.vy = 0;
      s.lastTime = performance.now();
      pointers.current.set(event.pointerId, p);
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = "grabbing";
    };
    const move = (event: PointerEvent) => {
      const previous = pointers.current.get(event.pointerId);
      if (!previous) return;
      const p = point(event),
        s = state.current;
      if (pointers.current.size > 1) {
        const old = [...pointers.current.values()];
        pointers.current.set(event.pointerId, p);
        const next = [...pointers.current.values()];
        const center = (points: Pointer[]) => ({
          x: (points[0].x + points[1].x) / 2,
          y: (points[0].y + points[1].y) / 2,
        });
        const a = center(old),
          b = center(next);
        const distance = (points: Pointer[]) =>
          Math.max(
            10,
            Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y),
          );
        applyZoom((s.factor * distance(next)) / distance(old), a);
        s.target = s.factor;
        camera.position.x -=
          (b.x - a.x) / (camera as THREE.OrthographicCamera).zoom;
        camera.position.y +=
          (b.y - a.y) / (camera as THREE.OrthographicCamera).zoom;
        s.moved = true;
        s.vx = 0;
        s.vy = 0;
      } else {
        pointers.current.set(event.pointerId, p);
        if (Math.hypot(p.x - s.originX, p.y - s.originY) > 4) s.moved = true;
        if (!s.moved) return;
        const dx =
          -(p.x - previous.x) / (camera as THREE.OrthographicCamera).zoom;
        const dy =
          (p.y - previous.y) / (camera as THREE.OrthographicCamera).zoom;
        camera.position.x += dx;
        camera.position.y += dy;
        const now = performance.now(),
          dt = Math.max(0.008, (now - s.lastTime) / 1000);
        s.vx = s.vx * 0.35 + clamp(dx / dt, -1800, 1800) * 0.65;
        s.vy = s.vy * 0.35 + clamp(dy / dt, -1800, 1800) * 0.65;
        s.lastTime = now;
      }
      bounds();
      invalidate();
    };
    const end = (event: PointerEvent) => {
      if (!pointers.current.has(event.pointerId)) return;
      pointers.current.delete(event.pointerId);
      if (canvas.hasPointerCapture(event.pointerId))
        canvas.releasePointerCapture(event.pointerId);
      const s = state.current;
      if (!pointers.current.size) {
        canvas.style.cursor = "grab";
        report();
        if (!s.moved && event.type === "pointerup") {
          const p = point(event),
            zoom = (camera as THREE.OrthographicCamera).zoom;
          const x = camera.position.x + (p.x - size.width / 2) / zoom + W / 2;
          const y = H / 2 - camera.position.y + (p.y - size.height / 2) / zoom;
          if (hitTest.context.isPointInPath(hitTest.path, x, y)) {
            const nearest = exploreRegions
              .map((region) => {
                const position = atlasProject(region.coordinates);
                return {
                  id: region.id,
                  distance: Math.hypot(position[0] - x, position[1] - y),
                };
              })
              .sort((a, b) => a.distance - b.distance)[0];
            if (nearest.distance < 125)
              latest.current.onSelectRegion(nearest.id);
          }
        }
        if (
          latest.current.reducedMotion ||
          latest.current.paused ||
          event.type !== "pointerup"
        ) {
          s.vx = 0;
          s.vy = 0;
        }
      }
    };
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const s = state.current;
      s.vx = 0;
      s.vy = 0;
      const delta =
        event.deltaY *
        (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.height : 1);
      applyZoom(s.factor * Math.exp(-delta * 0.0015), point(event));
      s.target = s.factor;
      clearTimeout(reportTimer.current);
      reportTimer.current = setTimeout(report, 120);
    };
    const key = (event: KeyboardEvent) => {
      const directions: Record<string, [number, number]> = {
        ArrowLeft: [-80, 0],
        ArrowRight: [80, 0],
        ArrowUp: [0, 65],
        ArrowDown: [0, -65],
      };
      if (directions[event.key]) {
        event.preventDefault();
        const [x, y] = directions[event.key];
        camera.position.x += x;
        camera.position.y += y;
        state.current.vx = 0;
        state.current.vy = 0;
        bounds();
        invalidate();
      } else if (event.key === "Home") {
        event.preventDefault();
        state.current.vx = 0;
        state.current.vy = 0;
        if (camera instanceof THREE.OrthographicCamera) {
          camera.zoom = state.current.base;
          camera.position.set(0, frame.current.offsetY / camera.zoom, 1000);
          camera.updateProjectionMatrix();
        }
        state.current.factor = 1;
        state.current.target = 1;
        bounds();
        invalidate();
        report();
      }
    };
    const cancel = () => {
      state.current.vx = 0;
      state.current.vy = 0;
      pointers.current.clear();
      canvas.style.cursor = "grab";
    };
    const visibility = () => {
      if (document.hidden) cancel();
    };
    latest.current.bridge.current.focus = (x, y) => {
      camera.position.x = x - W / 2;
      camera.position.y =
        H / 2 -
        y +
        frame.current.offsetY / (camera as THREE.OrthographicCamera).zoom;
      state.current.vx = 0;
      state.current.vy = 0;
      bounds();
      invalidate();
    };
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    canvas.addEventListener("lostpointercapture", end);
    canvas.addEventListener("wheel", wheel, { passive: false });
    canvas.addEventListener("keydown", key);
    window.addEventListener("blur", cancel);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      clearTimeout(reportTimer.current);
      latest.current.bridge.current.focus = undefined;
      pointers.current.clear();
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", end);
      canvas.removeEventListener("pointercancel", end);
      canvas.removeEventListener("lostpointercapture", end);
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("keydown", key);
      window.removeEventListener("blur", cancel);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [camera, gl, size.width, size.height, hitTest, invalidate]);

  useFrame((_, delta) => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const s = state.current,
      dt = Math.min(delta, 0.035);
    if (latest.current.paused || latest.current.reducedMotion) {
      s.vx = 0;
      s.vy = 0;
    }
    if (!pointers.current.size) {
      if (
        !latest.current.paused &&
        !latest.current.reducedMotion &&
        (Math.abs(s.vx) > 1 || Math.abs(s.vy) > 1)
      ) {
        camera.position.x += s.vx * dt;
        camera.position.y += s.vy * dt;
        s.vx *= Math.exp(-12 * dt);
        s.vy *= Math.exp(-12 * dt);
        bounds();
      }
      if (Math.abs(s.factor - s.target) > 0.0001)
        applyZoom(
          latest.current.reducedMotion
            ? s.target
            : THREE.MathUtils.damp(s.factor, s.target, 15, dt),
        );
    }
    // Only nine DOM markers move. The illustrated world stays entirely on GPU.
    const projection = `${camera.position.x.toFixed(2)},${camera.position.y.toFixed(2)},${camera.zoom.toFixed(4)},${size.width},${size.height}`;
    if (projection === previousProjection.current) return;
    previousProjection.current = projection;
    const bridge = latest.current.bridge.current;
    exploreRegions.forEach((region, i) => {
      const [x, y] = atlasProject(region.coordinates),
        label = atlasLabels[region.id];
      const sx = (x - W / 2 - camera.position.x) * camera.zoom + size.width / 2;
      const sy =
        (y - H / 2 + camera.position.y) * camera.zoom + size.height / 2;
      const [nudgeX, nudgeY] = atlasLabelNudge(
        region.id,
        size.width,
        camera.zoom,
      );
      const lx = sx + label.dx * camera.zoom + nudgeX,
        ly = sy + (label.dy + 18) * camera.zoom + nudgeY;
      const visible =
        sx > -20 && sx < size.width + 20 && sy > -20 && sy < size.height + 20;
      const button = bridge.buttons[i];
      if (button) {
        button.style.transform = `translate3d(${lx.toFixed(1)}px,${ly.toFixed(1)}px,0) translate(-50%,-50%)`;
        button.style.visibility = visible ? "visible" : "hidden";
      }
      const line = bridge.lines[i],
        dot = bridge.dots[i];
      if (line) {
        line.setAttribute("x1", String(sx));
        line.setAttribute("y1", String(sy));
        line.setAttribute("x2", String(lx));
        line.setAttribute("y2", String(ly));
        line.style.visibility = visible ? "visible" : "hidden";
      }
      if (dot) {
        dot.setAttribute("cx", String(sx));
        dot.setAttribute("cy", String(sy));
        dot.style.visibility = visible ? "visible" : "hidden";
      }
    });
  }, -2);
  return null;
}
