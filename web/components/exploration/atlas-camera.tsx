"use client";
/* R3F camera and controls intentionally mutate Three.js objects in callbacks. */
/* eslint-disable react-hooks/exhaustive-deps, react-hooks/immutability, react-hooks/refs */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
} from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";

/** Camera motion stays in Three.js refs. Pointer movement never updates React state. */
export function AtlasCamera({
  zoom,
  reset,
  reducedMotion,
  onZoomChange,
}: {
  zoom: number;
  reset: number;
  reducedMotion: boolean;
  onZoomChange?: (value: number) => void;
}) {
  const controls = useRef<OrbitControlsImpl>(null);
  const {
    camera,
    size,
    gl,
    invalidate,
    performance: renderPerformance,
  } = useThree();
  const requested = useRef(zoom),
    base = useRef(1),
    interacting = useRef(false);
  const lastReported = useRef(zoom),
    zoomCallback = useRef(onZoomChange);
  const offset = useMemo(() => new THREE.Vector3(), []);
  zoomCallback.current = onZoomChange;
  // On phones, start closer and allow navigation across the archipelago.
  const visibleWidth =
    size.width <= 600
      ? 23
      : size.width <= 900
        ? 43
        : Math.max(49, (size.width / size.height) * 18);
  const home = useMemo(() => new THREE.Vector3(0, 0.25, 0.4), []);

  useLayoutEffect(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    base.current = size.width / visibleWidth;
    camera.left = -size.width / 2;
    camera.right = size.width / 2;
    camera.top = size.height / 2;
    camera.bottom = -size.height / 2;
    camera.zoom = base.current * zoom;
    camera.updateProjectionMatrix();
    invalidate();
    // Resize changes framing, never the user's orbit or target.
  }, [camera, size.width, size.height, visibleWidth, invalidate]);

  useLayoutEffect(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    camera.position.set(home.x, home.y + 38, home.z + 29);
    camera.up.set(0, 1, 0);
    camera.lookAt(home);
    controls.current?.target.copy(home);
    camera.zoom = base.current * zoom;
    camera.updateProjectionMatrix();
    controls.current?.update();
    invalidate();
  }, [camera, reset, home, invalidate]);

  useEffect(() => {
    if (Math.abs(zoom - lastReported.current) > 0.001) requested.current = zoom;
    lastReported.current = zoom;
  }, [zoom]);

  const reportZoom = useCallback(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const value =
      Math.round(
        THREE.MathUtils.clamp(camera.zoom / base.current, 0.7, 2.4) * 100,
      ) / 100;
    requested.current = value;
    if (Math.abs(value - lastReported.current) < 0.005) return;
    lastReported.current = value;
    zoomCallback.current?.(value);
  }, [camera]);

  useEffect(() => {
    const canvas = gl.domElement;
    canvas.tabIndex = 0;
    canvas.setAttribute(
      "aria-label",
      "Atlas 3D Indonesia. Seret untuk memutar, Shift dan seret untuk menggeser. Dua jari untuk geser dan zoom. Tombol panah untuk menggeser, Home untuk reset.",
    );
    const keyboard = (event: KeyboardEvent) => {
      const orbit = controls.current;
      if (!orbit) return;
      const directions: Record<string, [number, number]> = {
        ArrowLeft: [-1, 0],
        ArrowRight: [1, 0],
        ArrowUp: [0, -1],
        ArrowDown: [0, 1],
      };
      if (directions[event.key]) {
        event.preventDefault();
        const [x, z] = directions[event.key];
        offset.set(x * 1.3, 0, z * 1.3);
        camera.position.add(offset);
        orbit.target.add(offset);
        orbit.update();
        invalidate();
      } else if (event.key === "Home") {
        event.preventDefault();
        camera.position.set(home.x, home.y + 38, home.z + 29);
        orbit.target.copy(home);
        requested.current = 1;
        if (camera instanceof THREE.OrthographicCamera) {
          camera.zoom = base.current;
          camera.updateProjectionMatrix();
        }
        orbit.update();
        reportZoom();
        invalidate();
      }
    };
    canvas.addEventListener("keydown", keyboard);
    const menu = (event: Event) => event.preventDefault();
    canvas.addEventListener("contextmenu", menu);
    return () => {
      canvas.removeEventListener("keydown", keyboard);
      canvas.removeEventListener("contextmenu", menu);
    };
  }, [camera, gl, home, invalidate, offset, reportZoom]);

  useFrame((_, delta) => {
    const orbit = controls.current;
    if (!orbit || !(camera instanceof THREE.OrthographicCamera)) return;
    // HUD zoom uses a brief camera-only interpolation. Direct wheel/pinch inputs
    // are owned entirely by OrbitControls until the gesture ends.
    if (!interacting.current) {
      const target = base.current * requested.current;
      if (Math.abs(camera.zoom - target) > 0.001) {
        camera.zoom = reducedMotion
          ? target
          : THREE.MathUtils.damp(
              camera.zoom,
              target,
              14,
              Math.min(delta, 0.05),
            );
        camera.updateProjectionMatrix();
      }
    }
    const x = THREE.MathUtils.clamp(orbit.target.x, -19, 19);
    const z = THREE.MathUtils.clamp(orbit.target.z, -6, 9);
    offset.set(x - orbit.target.x, home.y - orbit.target.y, z - orbit.target.z);
    if (offset.lengthSq() > 0.000001) {
      camera.position.add(offset);
      orbit.target.add(offset);
    }
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping={!reducedMotion}
      dampingFactor={0.16}
      rotateSpeed={0.48}
      panSpeed={0.85}
      zoomSpeed={0.65}
      screenSpacePanning={false}
      minPolarAngle={0.44}
      maxPolarAngle={1.06}
      minAzimuthAngle={-0.32}
      maxAzimuthAngle={0.32}
      minZoom={(size.width / visibleWidth) * 0.7}
      maxZoom={(size.width / visibleWidth) * 2.4}
      mouseButtons={{
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
      }}
      touches={{ ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN }}
      onStart={() => {
        interacting.current = true;
        renderPerformance.regress();
        gl.domElement.style.cursor = "grabbing";
      }}
      onEnd={() => {
        interacting.current = false;
        gl.domElement.style.cursor = "grab";
        reportZoom();
      }}
    />
  );
}
