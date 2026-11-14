"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { OrbitControls, useTexture } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";

type TextileStudySceneProps = {
  imageUrl: string;
  zoom: number;
  rotation: number;
  reset: number;
  onReady: () => void;
  onFailure: () => void;
};

function SceneLifecycle({ onFailure }: { onFailure: () => void }) {
  const canvas = useThree((state) => state.gl.domElement);
  useEffect(() => {
    const handleLoss = (event: Event) => {
      event.preventDefault();
      onFailure();
    };
    canvas.addEventListener("webglcontextlost", handleLoss);
    return () => canvas.removeEventListener("webglcontextlost", handleLoss);
  }, [canvas, onFailure]);
  return null;
}

function SuspendedStudy({
  imageUrl,
  zoom,
  rotation,
  onReady,
  reducedMotion,
}: Pick<
  TextileStudySceneProps,
  "imageUrl" | "zoom" | "rotation" | "onReady"
> & { reducedMotion: boolean }) {
  const time = useRef(0);
  const display = useRef<THREE.Group>(null);
  const cloth = useRef<THREE.Mesh>(null);
  const original = useTexture(imageUrl);
  const invalidate = useThree((state) => state.invalidate);
  const texture = useMemo(() => {
    const copy = original.clone();
    copy.colorSpace = THREE.SRGBColorSpace;
    copy.anisotropy = 4;
    copy.needsUpdate = true;
    return copy;
  }, [original]);
  const geometry = useMemo(() => {
    const image = original.image as { width: number; height: number };
    const height = 3.3;
    const width = height * (image.width / image.height);
    const plane = new THREE.PlaneGeometry(width, height, 48, 64);
    const positions = plane.attributes.position;
    for (let index = 0; index < positions.count; index++) {
      const x = positions.getX(index);
      const y = positions.getY(index);
      const drop = (height / 2 - y) / height;
      // A gentle, static drape presents the photograph without simulating a weave.
      positions.setZ(index, Math.sin(x * 7.5) * (0.012 + drop * 0.043));
      positions.setY(index, y - Math.cos(x * 1.6) * drop * 0.035);
    }
    plane.computeVertexNormals();
    return plane;
  }, [original]);
  useFrame((_, delta) => {
    if (!document.hidden && !reducedMotion)
      time.current += Math.min(delta, 0.05);
    const currentGeometry = cloth.current?.geometry;
    if (!currentGeometry) return;
    const p = currentGeometry.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i),
        y = p.getY(i),
        free = (1.65 - y) / 3.3;
      p.setZ(
        i,
        Math.sin(x * 7.5) * (0.012 + free * 0.043) +
          Math.sin(x * 4 + time.current * 1.25) * 0.035 * free * free,
      );
    }
    p.needsUpdate = true;
    currentGeometry.computeVertexNormals();
    if (display.current) {
      const a = reducedMotion ? 1 : 1 - Math.exp(-Math.min(delta, 0.05) * 8);
      display.current.rotation.y = THREE.MathUtils.lerp(
        display.current.rotation.y,
        rotation,
        a,
      );
      display.current.scale.setScalar(
        THREE.MathUtils.lerp(display.current.scale.x, 1 + zoom * 0.15, a),
      );
    }
  });

  useEffect(
    () => () => {
      texture.dispose();
      geometry.dispose();
    },
    [texture, geometry],
  );
  useEffect(() => {
    invalidate();
    const frame = requestAnimationFrame(onReady);
    return () => cancelAnimationFrame(frame);
  }, [imageUrl, invalidate, onReady]);

  const width =
    3.3 *
    ((original.image as { width: number; height: number }).width /
      (original.image as { width: number; height: number }).height);
  return (
    <group ref={display} position={[0, 0.08, 0]}>
      <mesh ref={cloth} geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial
          map={texture}
          roughness={0.97}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh position={[0, 1.69, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.027, 0.027, width + 0.25, 20]} />
        <meshStandardMaterial
          color="#ad8b4c"
          metalness={0.65}
          roughness={0.32}
        />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side} position={[side * width * 0.44, 0, 0]}>
          <mesh position={[0, 2.03, 0]}>
            <cylinderGeometry args={[0.008, 0.008, 0.65, 8]} />
            <meshStandardMaterial color="#9a855e" roughness={0.8} />
          </mesh>
          <mesh position={[0, 1.64, 0.022]} castShadow>
            <boxGeometry args={[0.075, 0.13, 0.045]} />
            <meshStandardMaterial
              color="#b49a61"
              metalness={0.55}
              roughness={0.4}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function CameraControls({ reset }: { reset: number }) {
  const controls = useRef<OrbitControlsImpl>(null);
  useEffect(() => {
    controls.current?.reset();
  }, [reset]);
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      target={[0, 0.08, 0]}
      enablePan={false}
      enableZoom={false}
      enableDamping={false}
      minAzimuthAngle={-0.45}
      maxAzimuthAngle={0.45}
      minPolarAngle={Math.PI / 2 - 0.12}
      maxPolarAngle={Math.PI / 2 + 0.08}
      rotateSpeed={0.6}
    />
  );
}

export default function TextileStudyScene(props: TextileStudySceneProps) {
  const [reducedMotion, setReducedMotion] = useState(true);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      try {
        const saved = localStorage.getItem("tenara-reduced-motion");
        setReducedMotion(saved === null ? media.matches : saved === "true");
      } catch {
        setReducedMotion(media.matches);
      }
    };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return (
    <Canvas
      shadows
      frameloop={reducedMotion ? "demand" : "always"}
      dpr={[1, 1.5]}
      camera={{ position: [0, 0.35, 8.4], fov: 34, near: 0.1, far: 30 }}
      gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
      fallback={null}
      style={{ touchAction: "pan-y" }}
    >
      <SceneLifecycle onFailure={props.onFailure} />
      <ambientLight intensity={1.6} color="#fff7e7" />
      <directionalLight
        position={[-3, 5, 5]}
        intensity={2.4}
        color="#fff4dc"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-4}
        shadow-camera-right={4}
        shadow-camera-top={4}
        shadow-camera-bottom={-4}
        shadow-normalBias={0.04}
      />
      <directionalLight position={[3, 1, 2]} intensity={0.65} color="#e2eadb" />
      <Suspense fallback={null}>
        <SuspendedStudy
          imageUrl={props.imageUrl}
          zoom={props.zoom}
          rotation={props.rotation}
          onReady={props.onReady}
          reducedMotion={reducedMotion}
        />
      </Suspense>
      <mesh position={[0, -1.96, -0.1]} receiveShadow castShadow>
        <cylinderGeometry args={[1.85, 1.96, 0.2, 80]} />
        <meshStandardMaterial color="#e1d6bd" roughness={0.95} />
      </mesh>
      <mesh position={[0, -1.85, -0.1]} receiveShadow>
        <cylinderGeometry args={[1.84, 1.84, 0.035, 80]} />
        <meshStandardMaterial color="#f0e7d3" roughness={0.95} />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -2.07, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 20]} />
        <shadowMaterial transparent opacity={0.16} />
      </mesh>
      <CameraControls reset={props.reset} />
    </Canvas>
  );
}
