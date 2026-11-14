"use client";
/* Lighting and shadow-map updates are renderer lifecycle operations. */
/* eslint-disable react-hooks/immutability */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import * as THREE from "three";
import { useWorldMotion } from "./world-motion";

type V3 = [number, number, number];

export function AtlasSeaNames() {
  const labels = useMemo(
    () =>
      ["Samudra Hindia", "Laut Banda"].map((name) => {
        const canvas = document.createElement("canvas");
        canvas.width = 640;
        canvas.height = 96;
        const context = canvas.getContext("2d")!;
        context.font = "italic 34px Georgia, serif";
        context.fillStyle = "#2f7071";
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.letterSpacing = "6px";
        context.fillText(name, 320, 48);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        return texture;
      }),
    [],
  );
  useEffect(
    () => () => labels.forEach((texture) => texture.dispose()),
    [labels],
  );
  return (
    <group name="atlas-sea-names">
      {labels.map((texture, i) => (
        <mesh
          key={i}
          position={i ? [14, -0.12, 4.4] : [-8.5, -0.12, 9]}
          rotation={[-Math.PI / 2, 0, -0.05]}
        >
          <planeGeometry args={[6.5, 1]} />
          <meshBasicMaterial
            map={texture}
            transparent
            opacity={0.65}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

/** Soft sculpted clouds, including raised spiral ornament — all actual geometry. */
export function AtlasClouds({ lowGraphics }: { lowGraphics: boolean }) {
  const root = useRef<THREE.Group>(null);
  const motion = useWorldMotion();
  const positions: V3[] = [
    [-15, 3.2, -5.8],
    [-3.3, 3.4, -5.1],
    [13.2, 3.3, -5.7],
    [19.7, 2.3, 5.1],
    [-13.5, 2.1, 9.2],
  ];
  const geometry = useMemo(() => {
    const parts = [
      [-1.05, -0.05, 0, 0.72, 0.38, 0.48],
      [-0.45, 0.2, 0, 0.86, 0.59, 0.62],
      [0.25, 0.38, -0.03, 0.84, 0.75, 0.69],
      [1, 0.09, 0, 0.74, 0.48, 0.55],
      [1.55, -0.13, 0.04, 0.55, 0.28, 0.4],
      [-1.6, -0.15, 0.08, 0.53, 0.26, 0.38],
      [0.2, -0.14, 0.3, 1.3, 0.32, 0.55],
    ].map(([x, y, z, sx, sy, sz]) => {
      const part = new THREE.SphereGeometry(1, 12, 8);
      part.scale(sx, sy, sz);
      part.translate(x, y, z);
      return part;
    });
    const body = mergeGeometries(parts)!;
    parts.forEach((part) => part.dispose());
    const points = Array.from({ length: 55 }, (_, i) => {
      const t = i / 54,
        a = t * Math.PI * 3.5,
        r = 0.03 + t * 0.46;
      return new THREE.Vector3(
        Math.cos(a) * r + 0.2,
        Math.sin(a) * r + 0.22,
        0.63 - t * 0.025,
      );
    });
    const spiral = new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3(points),
      52,
      0.035,
      5,
      false,
    );
    return { body, spiral };
  }, []);
  useEffect(
    () => () => {
      geometry.body.dispose();
      geometry.spiral.dispose();
    },
    [geometry],
  );
  useFrame(() => {
    if (!root.current || !motion.current.enabled) return;
    const t = motion.current.time;
    root.current.children.forEach((cloud, i) => {
      const p = positions[i];
      cloud.position.set(
        p[0] + Math.sin(t * 0.07 + i * 2) * 0.65,
        p[1] + Math.sin(t * 0.22 + i) * 0.08,
        p[2] + Math.cos(t * 0.06 + i) * 0.18,
      );
    });
  });
  return (
    <group ref={root} name="atlas-sculpted-clouds">
      {positions.slice(0, lowGraphics ? 3 : 5).map((p, i) => (
        <group
          key={i}
          position={p}
          rotation={[-0.65, 0, 0]}
          scale={i === 4 ? 0.68 : 1}
        >
          <mesh geometry={geometry.body}>
            <meshStandardMaterial color="#fff0cf" roughness={1} />
          </mesh>
          <mesh geometry={geometry.spiral}>
            <meshStandardMaterial color="#d9b77f" roughness={1} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Static atlas lighting lets shadows be cached while the camera is manipulated. */
export function AtlasLighting({
  evening,
  lowGraphics,
  ready,
}: {
  evening: boolean;
  lowGraphics: boolean;
  ready: boolean;
}) {
  const { gl } = useThree();
  const warmup = useRef(0);
  useEffect(() => {
    warmup.current = 0;
    gl.shadowMap.autoUpdate = false;
    gl.shadowMap.needsUpdate = true;
    return () => {
      gl.shadowMap.autoUpdate = true;
      gl.shadowMap.needsUpdate = true;
    };
  }, [gl, evening, lowGraphics, ready]);
  useFrame(() => {
    if (ready && warmup.current++ < 3) gl.shadowMap.needsUpdate = true;
  });
  return (
    <>
      <ambientLight
        intensity={evening ? 0.55 : 0.65}
        color={evening ? "#ffe3bf" : "#fff5df"}
      />
      <hemisphereLight args={["#fff2d6", "#6f8c65", 0.9]} />
      <directionalLight
        position={[12, 14, -8]}
        color="#c5e4d7"
        intensity={0.6}
      />
      <directionalLight
        position={evening ? [-17, 17, 12] : [-14, 26, 16]}
        color={evening ? "#ffbd7c" : "#fff0ca"}
        intensity={evening ? 1.8 : 2.05}
        castShadow={!lowGraphics}
        shadow-mapSize-width={1536}
        shadow-mapSize-height={1536}
        shadow-camera-left={-29}
        shadow-camera-right={29}
        shadow-camera-top={18}
        shadow-camera-bottom={-18}
        shadow-camera-near={1}
        shadow-camera-far={85}
        shadow-normalBias={0.045}
        shadow-bias={-0.00015}
        shadow-radius={3}
      />
    </>
  );
}
