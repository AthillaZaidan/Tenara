"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { RegionId } from "@/lib/exploration";
import { useWorldMotion } from "./world-motion";
import {
  batakLake,
  batakLakeIsland,
  regionalTerrain,
  type CoastPoint,
} from "./regional-terrain";

function path(ring: CoastPoint[], target: THREE.Path) {
  ring.forEach(([x, z], i) =>
    i ? target.lineTo(x, -z) : target.moveTo(x, -z),
  );
  target.closePath();
  return target;
}
function shape(ring: CoastPoint[], holes: CoastPoint[][] = []) {
  const result = path(ring, new THREE.Shape()) as THREE.Shape;
  result.holes = holes.map((hole) => path(hole, new THREE.Path()));
  return result;
}
function surface(ring: CoastPoint[], holes: CoastPoint[][] = []) {
  const geometry = new THREE.ShapeGeometry(shape(ring, holes));
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}
function cliff(ring: CoastPoint[], holes: CoastPoint[][] = [], depth = 1) {
  const geometry = new THREE.ExtrudeGeometry(shape(ring, holes), {
    depth,
    bevelEnabled: true,
    bevelSize: 0.08,
    bevelThickness: 0.08,
    bevelSegments: 1,
    steps: 1,
  });
  geometry.rotateX(-Math.PI / 2);
  const positions = geometry.getAttribute("position"),
    colors = new Float32Array(positions.count * 3);
  const color = new THREE.Color();
  for (let i = 0; i < positions.count; i += 3) {
    const x =
      (positions.getX(i) + positions.getX(i + 1) + positions.getX(i + 2)) / 3;
    const z =
      (positions.getZ(i) + positions.getZ(i + 1) + positions.getZ(i + 2)) / 3;
    color
      .set("#e5c48a")
      .multiplyScalar(0.9 + Math.sin(x * 2.7 + z * 3.1) * 0.09);
    for (let j = 0; j < 3; j++) color.toArray(colors, (i + j) * 3);
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return geometry;
}
function coastRibbon(ring: CoastPoint[], inner: number, outer: number) {
  const points: number[] = [];
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i],
      b = ring[(i + 1) % ring.length];
    const vertex = (p: CoastPoint, s: number) => [p[0] * s, 0, p[1] * s];
    points.push(
      ...vertex(a, inner),
      ...vertex(b, inner),
      ...vertex(a, outer),
      ...vertex(b, inner),
      ...vertex(b, outer),
      ...vertex(a, outer),
    );
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(points, 3),
  );
  return geometry;
}

export function RegionalLand({ id }: { id: RegionId }) {
  const terrain = regionalTerrain[id];
  const lake = id === "sumatera-utara";
  const foam =
    useRef<THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>>(null);
  const motion = useWorldMotion();
  const art = useMemo(() => {
    const holes = lake ? [batakLake] : [];
    const inset = terrain.coast.map(
      ([x, z]) => [x * 0.969, z * 0.969] as CoastPoint,
    );
    const grassHoles = holes.map((ring) =>
      ring.map(
        ([x, z]) =>
          [1.65 + (x - 1.65) * 1.065, 1.7 + (z - 1.7) * 1.065] as CoastPoint,
      ),
    );
    return {
      base: cliff(terrain.coast, holes),
      grass: surface(inset, grassHoles),
      shallows: coastRibbon(terrain.coast, 1.015, 1.13),
      foam: coastRibbon(terrain.coast, 1.045, 1.053),
      lake: lake ? surface(batakLake) : null,
      island: lake ? cliff(batakLakeIsland, [], 0.18) : null,
      islandGrass: lake ? surface(batakLakeIsland) : null,
    };
  }, [terrain, lake]);
  useEffect(
    () => () => Object.values(art).forEach((geometry) => geometry?.dispose()),
    [art],
  );
  useFrame(() => {
    if (foam.current)
      foam.current.material.opacity =
        0.25 + Math.sin(motion.current.time * 0.65) * 0.1;
  });
  return (
    <group name={`regional-terrain-${id}`}>
      <mesh geometry={art.shallows} position={[0, -0.72, 0]}>
        <meshBasicMaterial
          color="#a1ded5"
          transparent
          opacity={0.23}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh ref={foam} geometry={art.foam} position={[0, -0.7, 0]}>
        <meshBasicMaterial
          color="#e1f5e9"
          transparent
          opacity={0.3}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh
        geometry={art.base}
        position={[0, -0.21, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          attach="material-0"
          color="#f3d99e"
          flatShading
          roughness={1}
        />
        <meshStandardMaterial
          attach="material-1"
          vertexColors
          flatShading
          roughness={1}
        />
      </mesh>
      <mesh geometry={art.grass} position={[0, 0.885, 0]} receiveShadow>
        <meshStandardMaterial color={terrain.grass} flatShading roughness={1} />
      </mesh>
      {art.lake && (
        <mesh geometry={art.lake} position={[0, 0.8, 0]} receiveShadow>
          <meshStandardMaterial
            color="#50b5c5"
            roughness={0.45}
            metalness={0.05}
          />
        </mesh>
      )}
      {art.island && (
        <mesh
          geometry={art.island}
          position={[0, 0.63, 0]}
          castShadow
          receiveShadow
        >
          <meshStandardMaterial color="#eed39a" roughness={1} flatShading />
        </mesh>
      )}
      {art.islandGrass && (
        <mesh geometry={art.islandGrass} position={[0, 0.9, 0]} receiveShadow>
          <meshStandardMaterial color="#a8bf57" roughness={1} />
        </mesh>
      )}
      {terrain.islets.map((islet, i) => (
        <Islet key={i} {...islet} grass={terrain.grass} index={i} />
      ))}
    </group>
  );
}

function Islet({
  center,
  radius,
  stretch,
  tree,
  grass,
  index,
}: {
  center: CoastPoint;
  radius: number;
  stretch: number;
  tree?: boolean;
  grass: string;
  index: number;
}) {
  return (
    <group
      position={[center[0], -0.15, center[1]]}
      rotation={[0, index * 0.7, 0]}
      scale={[1, 1, stretch]}
    >
      <mesh position={[0, 0.2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[radius * 0.87, radius, 0.65, 7]} />
        <meshStandardMaterial color="#e4c78d" flatShading roughness={1} />
      </mesh>
      <mesh position={[0, 0.54, 0]} receiveShadow>
        <cylinderGeometry args={[radius * 0.8, radius * 0.87, 0.07, 7]} />
        <meshStandardMaterial color={grass} flatShading roughness={1} />
      </mesh>
      {tree && (
        <group position={[0, 0.57, 0]}>
          <mesh position={[0, 0.25, 0]} castShadow>
            <cylinderGeometry args={[0.045, 0.065, 0.5, 5]} />
            <meshStandardMaterial color="#926039" />
          </mesh>
          <mesh position={[0, 0.58, 0]} scale={[1, 0.85, 1]} castShadow>
            <icosahedronGeometry args={[radius * 0.65, 0]} />
            <meshStandardMaterial color="#619445" flatShading />
          </mesh>
        </group>
      )}
    </group>
  );
}
