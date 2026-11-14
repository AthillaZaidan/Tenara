"use client";

import { Canvas, useThree, useFrame } from "@react-three/fiber";
import {
  WorldMotion,
  useWorldMotion,
} from "@/components/exploration/world-motion";
import {
  CameraControls,
  ContactShadows,
  Html,
  RoundedBox,
  useTexture,
} from "@react-three/drei";
import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentRef,
} from "react";
import * as THREE from "three";
import { MapSurface } from "@/components/exploration/map-button";
import {
  galleryAssets,
  galleryStories,
  rooms,
  type GalleryView,
  type Point3,
} from "@/lib/gallery";

export type SceneProps = {
  view: GalleryView;
  selected: string | null;
  visited: string[];
  reset: number;
  zoom: number;
  reducedMotion: boolean;
  onRoom: (room: GalleryView) => void;
  onStory: (id: string) => void;
  onReady: () => void;
  onFailure: () => void;
};

const palette = {
  plaster: "#d9c4a4",
  edge: "#bda685",
  wood: "#69472e",
  terracotta: "#ac593c",
  olive: "#606044",
  indigo: "#202f3a",
  cream: "#e5d8b8",
};

function grainTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const data = ctx.createImageData(128, 128);
  let seed = 29;
  for (let i = 0; i < data.data.length; i += 4) {
    seed = (seed * 16807) % 2147483647;
    const n = 204 + (seed % 48);
    data.data[i] = data.data[i + 1] = data.data[i + 2] = n;
    data.data[i + 3] = 255;
  }
  ctx.putImageData(data, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(5, 5);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function Box({
  position,
  size,
  color = palette.plaster,
  radius = 0.035,
  material,
}: {
  position: Point3;
  size: Point3;
  color?: string;
  radius?: number;
  material?: THREE.Material;
}) {
  return (
    <RoundedBox
      position={position}
      args={size}
      radius={radius}
      smoothness={2}
      castShadow
      receiveShadow
      material={material}
    >
      {!material && <meshStandardMaterial color={color} roughness={0.87} />}
    </RoundedBox>
  );
}

function Rod({
  start,
  end,
  radius = 0.035,
  color = palette.wood,
}: {
  start: Point3;
  end: Point3;
  radius?: number;
  color?: string;
}) {
  const { middle, quaternion, length } = useMemo(() => {
    const a = new THREE.Vector3(...start),
      b = new THREE.Vector3(...end);
    const direction = b.clone().sub(a);
    return {
      middle: a.clone().add(b).multiplyScalar(0.5),
      length: direction.length(),
      quaternion: new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        direction.normalize(),
      ),
    };
  // Coordinate values deliberately key the geometry, not fresh JSX tuple identities.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start[0], start[1], start[2], end[0], end[1], end[2]]);
  return (
    <mesh position={middle} quaternion={quaternion} castShadow>
      <cylinderGeometry args={[radius, radius, length, 10]} />
      <meshStandardMaterial color={color} roughness={0.8} />
    </mesh>
  );
}

function Arch({ material }: { material: THREE.Material }) {
  const shape = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-2.12, 0);
    s.lineTo(2.12, 0);
    s.lineTo(2.12, 2.65);
    s.absarc(0, 2.65, 2.12, 0, Math.PI, false);
    s.lineTo(-2.12, 0);
    const hole = new THREE.Path();
    hole.moveTo(-1.78, 0);
    hole.lineTo(-1.78, 2.65);
    hole.absarc(0, 2.65, 1.78, Math.PI, 0, true);
    hole.lineTo(1.78, 0);
    hole.closePath();
    s.holes.push(hole);
    return s;
  }, []);
  return (
    <mesh
      position={[0, 0.16, -0.6]}
      material={material}
      castShadow
      receiveShadow
    >
      <extrudeGeometry
        args={[
          shape,
          {
            depth: 0.3,
            bevelEnabled: true,
            bevelSize: 0.04,
            bevelThickness: 0.04,
            bevelSegments: 2,
            steps: 1,
            curveSegments: 36,
          },
        ]}
      />
    </mesh>
  );
}

function Textile({
  position,
  size = [1.65, 3.42],
  rotation = [0, 0, 0],
  highlight = false,
}: {
  position: Point3;
  size?: [number, number];
  rotation?: Point3;
  highlight?: boolean;
}) {
  const texture = useTexture(galleryAssets.textile);
  const motion = useWorldMotion();
  const geometry = useMemo(() => {
    const g = new THREE.PlaneGeometry(size[0], size[1], 32, 48);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++)
      p.setZ(
        i,
        Math.sin(p.getX(i) * 15) * 0.017 + Math.sin(p.getY(i) * 2.5) * 0.02,
      );
    g.computeVertexNormals();
    return g;
  // Preserve geometry across renders when the source dimensions are unchanged.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size[0], size[1]]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useFrame(() => {
    if (!motion.current.enabled) return;
    const p = geometry.attributes.position,
      t = motion.current.time;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i),
        y = p.getY(i),
        free = (size[1] / 2 - y) / size[1];
      p.setZ(
        i,
        Math.sin(x * 15) * 0.017 +
          Math.sin(y * 2.5) * 0.02 +
          Math.sin(x * 6 + t * 1.4) * 0.045 * free * free,
      );
    }
    // R3F's imperative frame loop updates the owned Three.js vertex buffer.
    // eslint-disable-next-line react-hooks/immutability
    p.needsUpdate = true;
    geometry.computeVertexNormals();
  });
  // useTexture returns a Three.js resource; preserve the prototype's sRGB setup.
  // eslint-disable-next-line react-hooks/immutability
  texture.colorSpace = THREE.SRGBColorSpace;
  return (
    <group position={position} rotation={rotation}>
      <mesh geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial
          map={texture}
          transparent
          alphaTest={0.2}
          side={THREE.DoubleSide}
          roughness={1}
          emissive={highlight ? "#b87b36" : "#000"}
          emissiveIntensity={0.14}
        />
      </mesh>
      <Rod
        start={[-size[0] / 2 - 0.12, size[1] / 2 + 0.02, -0.02]}
        end={[size[0] / 2 + 0.12, size[1] / 2 + 0.02, -0.02]}
        radius={0.055}
      />
    </group>
  );
}

function MotifFrame({
  x,
  alternate = false,
  highlight = false,
}: {
  x: number;
  alternate?: boolean;
  highlight?: boolean;
}) {
  const texture = useTexture(
    alternate ? galleryAssets.textile : galleryAssets.motif,
  );
  // The exhibit texture is an imperative Three.js resource, not React state.
  // eslint-disable-next-line react-hooks/immutability
  texture.colorSpace = THREE.SRGBColorSpace;
  return (
    <group position={[x, 2.72, -1.63]}>
      <Box position={[0, 0, 0]} size={[1.55, 1.48, 0.1]} color="#a67846" />
      <mesh position={[0, 0, 0.061]}>
        <planeGeometry args={[1.37, 1.3]} />
        <meshStandardMaterial
          map={texture}
          roughness={0.95}
          emissive={highlight ? "#bd8e47" : "#000"}
          emissiveIntensity={0.28}
        />
      </mesh>
      <Box position={[0, -0.84, 0]} size={[0.5, 0.04, 0.12]} color="#d0ba8a" />
    </group>
  );
}

function Pot({
  position,
  scale = 1,
  plant = true,
}: {
  position: Point3;
  scale?: number;
  plant?: boolean;
}) {
  const profile = useMemo(
    () => [
      new THREE.Vector2(0.16, 0),
      new THREE.Vector2(0.27, 0.05),
      new THREE.Vector2(0.34, 0.28),
      new THREE.Vector2(0.29, 0.55),
      new THREE.Vector2(0.16, 0.68),
      new THREE.Vector2(0.16, 0.73),
      new THREE.Vector2(0.13, 0.73),
      new THREE.Vector2(0.13, 0.66),
    ],
    [],
  );
  return (
    <group position={position} scale={scale}>
      <mesh castShadow receiveShadow>
        <latheGeometry args={[profile, 24]} />
        <meshStandardMaterial color="#9c754d" roughness={1} />
      </mesh>
      {plant &&
        Array.from({ length: 7 }, (_, i) => {
          const a = i * 2.4;
          const end: Point3 = [
            Math.cos(a) * 0.43,
            1.25 + (i % 3) * 0.22,
            Math.sin(a) * 0.4,
          ];
          return (
            <group key={i}>
              <Rod
                start={[0, 0.6, 0]}
                end={end}
                radius={0.012}
                color="#665d35"
              />
              {[0.55, 0.8, 1].map((t, j) => (
                <mesh
                  key={j}
                  position={[
                    end[0] * t + 0.06,
                    0.6 + (end[1] - 0.6) * t,
                    end[2] * t,
                  ]}
                  rotation={[0, a, 0.7]}
                  scale={[0.14, 0.045, 0.065]}
                  castShadow
                >
                  <sphereGeometry args={[1, 8, 6]} />
                  <meshStandardMaterial
                    color={i % 2 ? "#71764b" : "#858756"}
                    roughness={1}
                  />
                </mesh>
              ))}
            </group>
          );
        })}
    </group>
  );
}

function Cushion({ position }: { position: Point3 }) {
  return (
    <group position={position}>
      <mesh castShadow receiveShadow>
        <cylinderGeometry args={[0.4, 0.43, 0.15, 32]} />
        <meshStandardMaterial color="#ad9162" roughness={1} />
      </mesh>
      {[0.12, 0.21, 0.3, 0.38].map((r) => (
        <mesh key={r} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.08, 0]}>
          <torusGeometry args={[r, 0.009, 4, 40]} />
          <meshStandardMaterial color="#ccb080" />
        </mesh>
      ))}
    </group>
  );
}

function Yarn({ x, color }: { x: number; color: string }) {
  const loops = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => {
        const offset = i * 0.034;
        return new THREE.CatmullRomCurve3([
          new THREE.Vector3(x + offset, 3.48, -1.4),
          new THREE.Vector3(x + offset - 0.015, 3.25, -1.32),
          new THREE.Vector3(x + offset - 0.03, 2.25 - (i % 3) * 0.045, -1.34),
          new THREE.Vector3(x + offset + 0.11, 2.12 - (i % 3) * 0.045, -1.35),
          new THREE.Vector3(x + offset + 0.15, 2.3, -1.42),
          new THREE.Vector3(x + offset + 0.12, 3.5, -1.45),
        ]);
      }),
    [x],
  );
  return (
    <group>
      {loops.map((curve, i) => (
        <mesh key={i} castShadow>
          <tubeGeometry args={[curve, 24, 0.018, 5, false]} />
          <meshStandardMaterial color={color} roughness={1} />
        </mesh>
      ))}
    </group>
  );
}

function Loom({ selected }: { selected: string | null }) {
  const threadGeometry = useMemo(() => {
    const positions: number[] = [],
      colors: number[] = [];
    for (let i = 0; i < 100; i++) {
      const x = -1.18 + i * 0.0238;
      positions.push(x, 0.48, 1.68, x, 1.02, -0.64);
      const c = new THREE.Color(
        i % 11 < 2
          ? palette.terracotta
          : i % 11 === 3
            ? palette.cream
            : palette.indigo,
      );
      colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return g;
  }, []);
  useEffect(() => () => threadGeometry.dispose(), [threadGeometry]);
  return (
    <group position={[4.3, 0.2, 0.1]}>
      <Box
        position={[0, -0.015, 0.5]}
        size={[3.2, 0.04, 3.25]}
        color="#a58a5e"
        radius={0.015}
      />
      {[-1.15, 1.15].map((x) => (
        <Rod
          key={x}
          start={[x, 0.15, 1.68]}
          end={[x, 0.7, -0.64]}
          radius={0.055}
        />
      ))}
      <lineSegments geometry={threadGeometry}>
        <lineBasicMaterial vertexColors />
      </lineSegments>
      <mesh
        position={[0, 0.65, 0.94]}
        rotation={[-Math.PI / 2 + 0.23, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[2.38, 1.42]} />
        <meshStandardMaterial color={palette.indigo} roughness={1} />
      </mesh>
      {[-0.64, 1.68].map((z, i) => (
        <Rod
          key={z}
          start={[-1.4, i ? 0.48 : 1.02, z]}
          end={[1.4, i ? 0.48 : 1.02, z]}
          radius={0.075}
        />
      ))}
      <Rod
        start={[-1.4, 0.8, 0.3]}
        end={[1.4, 0.8, 0.3]}
        radius={0.05}
        color={selected === "loop-heddle" ? "#d5b36d" : palette.wood}
      />
      {Array.from({ length: 46 }, (_, i) => (
        <mesh
          key={i}
          position={[-1.14 + i * 0.05, 0.81, 0.3]}
          rotation={[0, Math.PI / 2, 0]}
        >
          <torusGeometry args={[0.075, 0.011, 4, 12]} />
          <meshStandardMaterial color={palette.cream} roughness={1} />
        </mesh>
      ))}
      <Rod start={[-1.3, 0.1, -0.7]} end={[-1.3, 0.95, -0.7]} radius={0.045} />
      <Rod start={[1.3, 0.1, -0.7]} end={[1.3, 0.95, -0.7]} radius={0.045} />
    </group>
  );
}

/* The carved timber facade frames all three rooms as one exhibition house. */
function HouseFacade() {
  const gable = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(-3.4, 4.15);
    shape.lineTo(0, 6.77);
    shape.lineTo(3.4, 4.15);
    shape.closePath();
    return shape;
  }, []);
  const roof = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(-6.85, 4.05);
    shape.lineTo(-2.85, 5.12);
    shape.lineTo(0, 6.95);
    shape.lineTo(2.85, 5.12);
    shape.lineTo(6.85, 4.05);
    shape.lineTo(6.85, 3.72);
    shape.lineTo(2.72, 4.77);
    shape.lineTo(0, 6.54);
    shape.lineTo(-2.72, 4.77);
    shape.lineTo(-6.85, 3.72);
    shape.closePath();
    return shape;
  }, []);
  const roofline: Point3[] = [
    [-6.85, 4.05, -0.2],
    [-2.85, 5.12, -0.2],
    [0, 6.95, -0.2],
    [2.85, 5.12, -0.2],
    [6.85, 4.05, -0.2],
  ];
  return (
    <group>
      <mesh position={[0, 0, -1.7]} receiveShadow>
        <shapeGeometry args={[gable]} />
        <meshStandardMaterial color="#713719" roughness={1} />
      </mesh>
      <mesh position={[0, 0, -1.3]} castShadow receiveShadow>
        <extrudeGeometry args={[roof, { depth: 1.15, bevelEnabled: false }]} />
        <meshStandardMaterial color="#85401c" roughness={0.9} />
      </mesh>
      {roofline.slice(0, -1).map((point, i) => (
        <group key={i}>
          <Rod
            start={point}
            end={roofline[i + 1]}
            radius={0.14}
            color="#f3c883"
          />
          <Rod
            start={[point[0], point[1] - 0.29, point[2]]}
            end={[
              roofline[i + 1][0],
              roofline[i + 1][1] - 0.29,
              roofline[i + 1][2],
            ]}
            radius={0.12}
            color="#9d4c1d"
          />
        </group>
      ))}
      <Rod
        start={[-0.55, 7.2, -0.35]}
        end={[0.45, 6.48, -0.35]}
        radius={0.13}
        color="#b76025"
      />
      <Rod
        start={[0.55, 7.2, -0.35]}
        end={[-0.45, 6.48, -0.35]}
        radius={0.13}
        color="#b76025"
      />
      {[-6.1, -2.18, 2.18, 6.1].map((x) => (
        <group key={x}>
          <Box
            position={[x, 2.05, -0.4]}
            size={[0.34, 3.9, 0.4]}
            color="#8e431b"
          />
          <Box
            position={[x, 0.38, -0.35]}
            size={[0.52, 0.52, 0.5]}
            color="#9d4d1e"
          />
          <Box
            position={[x, 3.75, -0.35]}
            size={[0.55, 0.3, 0.52]}
            color="#a45320"
          />
          {Math.abs(x) < 3 &&
            Array.from({ length: 6 }, (_, i) => (
              <mesh
                key={i}
                position={[x, 0.95 + i * 0.43, -0.18]}
                rotation={[0, 0, Math.PI / 4]}
              >
                <ringGeometry args={[0.09, 0.15, 4]} />
                <meshBasicMaterial color="#f3c789" side={THREE.DoubleSide} />
              </mesh>
            ))}
        </group>
      ))}
      <Box
        position={[0, 4.25, -1.2]}
        size={[5.8, 0.22, 0.35]}
        color="#793a1a"
      />
      <Textile position={[0, 5.55, -0.05]} size={[0.9, 1.45]} />
      <group position={[0, 4.15, -1.75]}>
        {[-0.42, -0.21, 0, 0.21, 0.42].map((x, i) => (
          <mesh
            key={x}
            position={[x, i % 2 ? 0.15 : 0, 0]}
            rotation={[0, 0, Math.PI / 4]}
          >
            <ringGeometry args={[0.08, 0.14, 4]} />
            <meshBasicMaterial color="#f4ca88" side={THREE.DoubleSide} />
          </mesh>
        ))}
      </group>
      <pointLight
        position={[-4.2, 4, 0]}
        color="#ffb458"
        intensity={24}
        distance={6}
      />
      <pointLight
        position={[4.2, 4, 0]}
        color="#ffb458"
        intensity={24}
        distance={6}
      />
      <pointLight
        position={[0, 4.6, -0.5]}
        color="#ffae49"
        intensity={18}
        distance={6}
      />
    </group>
  );
}

function Diorama({ selected }: { selected: string | null }) {
  const texture = useMemo(() => grainTexture(), []);
  const archMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#99501f", roughness: 0.9 }),
    [],
  );
  const plaster = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: palette.plaster,
        map: texture,
        bumpMap: texture,
        bumpScale: 0.035,
        roughness: 1,
      }),
    [texture],
  );
  useEffect(
    () => () => {
      plaster.dispose();
      archMaterial.dispose();
      texture.dispose();
    },
    [plaster, archMaterial, texture],
  );
  return (
    <group>
      <Box
        position={[0, -0.13, 0.1]}
        size={[13.3, 0.5, 5.8]}
        radius={0.22}
        material={plaster}
      />
      <Box
        position={[0, -0.35, 3.07]}
        size={[2.6, 0.18, 0.75]}
        material={plaster}
      />
      <Box
        position={[0, -0.46, 3.4]}
        size={[3, 0.12, 0.6]}
        material={plaster}
      />
      <Box
        position={[-4.3, 2.4, -1.94]}
        size={[4.18, 4.6, 0.3]}
        radius={0.1}
        material={plaster}
      />
      <Box
        position={[0, 2.2, -1.97]}
        size={[4.2, 4.2, 0.25]}
        color={palette.olive}
      />
      <Box
        position={[4.3, 2.15, -1.97]}
        size={[4.18, 4.1, 0.25]}
        material={plaster}
      />
      <Arch material={archMaterial} />
      <HouseFacade />
      <Textile
        position={[-4.3, 2.55, -1.69]}
        highlight={selected === "sehelai-sumba"}
      />
      <Box
        position={[-4.3, 0.42, -0.75]}
        size={[3.15, 0.55, 1.2]}
        material={plaster}
      />
      <Textile
        position={[-4.85, 0.71, -0.4]}
        size={[0.65, 0.85]}
        rotation={[-Math.PI / 2, 0, 0]}
      />
      <Pot position={[-3.18, 0.7, -0.75]} scale={0.6} />
      <Pot position={[-5.7, 0.15, 1.5]} scale={0.95} plant={false} />
      <mesh position={[-5.4, 0.78, -0.78]} castShadow>
        <sphereGeometry args={[0.21, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#b59663" roughness={1} />
      </mesh>
      {Array.from({ length: 6 }, (_, i) => (
        <mesh
          key={i}
          position={[
            -5.57 + (i % 3) * 0.14,
            0.84 + Math.floor(i / 3) * 0.1,
            -0.77,
          ]}
          castShadow
        >
          <sphereGeometry args={[0.09, 10, 8]} />
          <meshStandardMaterial color="#ede3cc" roughness={1} />
        </mesh>
      ))}
      <MotifFrame x={-0.87} highlight={selected === "motif-rusa"} />
      <MotifFrame x={0.92} alternate highlight={selected === "irama-motif"} />
      <Box
        position={[0, 0.19, 0.2]}
        size={[3.35, 0.035, 2.4]}
        color="#b29769"
        radius={0.01}
      />
      <Box
        position={[0, 0.82, -0.35]}
        size={[2.95, 0.17, 0.95]}
        color={palette.wood}
      />
      {[-1.17, 1.17].map((x) => (
        <Box
          key={x}
          position={[x, 0.46, -0.35]}
          size={[0.17, 0.65, 0.65]}
          color={palette.wood}
        />
      ))}
      <Box
        position={[0.12, 0.94, -0.32]}
        size={[0.72, 0.055, 0.47]}
        color="#d8c99f"
      />
      <Box
        position={[-0.06, 0.98, -0.32]}
        size={[0.32, 0.025, 0.42]}
        color="#e9ddbd"
      />
      <Pot position={[-1, 0.91, -0.4]} scale={0.35} />
      <Cushion position={[-0.68, 0.27, 0.8]} />
      <Cushion position={[0.68, 0.27, 0.8]} />
      <Rod start={[2.8, 3.5, -1.48]} end={[5.8, 3.5, -1.48]} radius={0.07} />
      <Yarn x={3} color={palette.indigo} />
      <Yarn x={3.85} color={palette.terracotta} />
      <Yarn x={4.7} color={palette.cream} />
      <Box
        position={[4.3, 1.23, -1.15]}
        size={[3.2, 0.15, 0.82]}
        color={palette.wood}
      />
      {[3, 5.6].map((x) => (
        <Box
          key={x}
          position={[x, 0.68, -1.15]}
          size={[0.14, 1.05, 0.6]}
          color={palette.wood}
        />
      ))}
      <Pot position={[5.7, 1.31, -1.15]} scale={0.4} plant={false} />
      <Loom selected={selected} />
      <Pot position={[2.7, 0.15, 1.75]} scale={0.75} />
      <Pot position={[6, 0.15, 2.2]} scale={0.55} />
      {/* Warm inset path lights guide the eye between rooms. */}
    </group>
  );
}

function CameraRig({
  view,
  selected,
  reset,
  zoom,
  reducedMotion,
}: Pick<SceneProps, "view" | "selected" | "reset" | "zoom" | "reducedMotion">) {
  const ref = useRef<ComponentRef<typeof CameraControls>>(null);
  const previousZoom = useRef(zoom);
  const { size } = useThree();
  useEffect(() => {
    const delta = zoom - previousZoom.current;
    previousZoom.current = zoom;
    if (delta) ref.current?.dolly(delta * 0.9, !reducedMotion);
  }, [zoom, reducedMotion]);
  useEffect(() => {
    const controls = ref.current;
    if (!controls) return;
    const mobile = size.width < 760;
    const story = galleryStories.find((s) => s.id === selected);
    const x = view === "kain" ? -4.3 : view === "proses" ? 4.3 : 0;
    let target: Point3, position: Point3;
    if (view === "overview") {
      target = [0, 3.1, 0];
      const distance = mobile
        ? Math.max(25, 18 / (size.width / size.height))
        : Math.max(14.5, 25.6 / (size.width / size.height));
      position = [0, 3.1 + distance * 0.11, distance];
    } else if (story) {
      const shift = mobile ? 0 : 1.15;
      target = [
        story.focus[0] + shift,
        story.focus[1] + (mobile ? -0.6 : 0),
        story.focus[2],
      ];
      position = [
        story.focus[0] + shift + 0.3,
        story.focus[1] + 1.05,
        story.focus[2] + (mobile ? 7.9 : 6.2),
      ];
    } else {
      target = [x, 1.8, -0.5];
      position = [x + 0.6, 3.6, mobile ? 11 : 8];
    }
    controls.minDistance = view === "overview" ? 13 : 4;
    controls.maxDistance = view === "overview" ? 44 : 14;
    controls.setLookAt(...position, ...target, !reducedMotion);
  }, [view, selected, reset, reducedMotion, size.width, size.height]);
  return (
    <CameraControls
      ref={ref}
      makeDefault
      smoothTime={reducedMotion ? 0 : 0.65}
      minPolarAngle={0.5}
      maxPolarAngle={Math.PI / 2 - 0.05}
      minAzimuthAngle={-0.55}
      maxAzimuthAngle={0.65}
      truckSpeed={0}
      dollySpeed={0.45}
    />
  );
}

function Markers({
  view,
  selected,
  visited,
  onRoom,
  onStory,
}: Pick<SceneProps, "view" | "selected" | "visited" | "onRoom" | "onStory">) {
  return (
    <group>
      {view === "overview"
        ? rooms.map((room) => (
            <Html
              key={room.id}
              position={room.position}
              center
              zIndexRange={[20, 10]}
            >
              <button
                className="gallery-hotspot gallery-room-hotspot"
                onClick={() => onRoom(room.id)}
                aria-label={`Masuk ${room.name}`}
              >
                <MapSurface />
                <span className="gallery-hotspot-dot">{room.number}</span>
                <span>{room.name}</span>
              </button>
            </Html>
          ))
        : galleryStories
            .filter((s) => s.room === view && s.id !== selected)
            .map((story) => (
              <Html
                key={story.id}
                position={story.position}
                center
                zIndexRange={[20, 10]}
              >
                <button
                  className={`gallery-hotspot ${visited.includes(story.id) ? "is-visited" : ""}`}
                  onClick={() => onStory(story.id)}
                  aria-label={`Buka cerita ${story.label}`}
                >
                  <MapSurface />
                  <span className="gallery-hotspot-dot">
                    {visited.includes(story.id) ? "✓" : "+"}
                  </span>
                  <span>{story.label}</span>
                </button>
              </Html>
            ))}
    </group>
  );
}

function Ready({ onReady }: { onReady: () => void }) {
  useEffect(onReady, [onReady]);
  return null;
}

export default function GalleryScene(props: SceneProps) {
  const [contextLost, setContextLost] = useState(false);
  const { onFailure } = props;
  useEffect(() => {
    if (contextLost) onFailure();
  }, [contextLost, onFailure]);
  return (
    <Canvas
      shadows
      frameloop={props.reducedMotion ? "demand" : "always"}
      dpr={[1, 1.5]}
      camera={{ position: [6, 9, 21], fov: 40, near: 0.1, far: 100 }}
      gl={{ antialias: true, powerPreference: "default" }}
      onCreated={({ gl }) => {
        gl.domElement.setAttribute(
          "aria-label",
          "Diorama 3D Koleksi Sumba. Gunakan menu ruang dan daftar cerita untuk navigasi keyboard.",
        );
        gl.domElement.addEventListener(
          "webglcontextlost",
          () => setContextLost(true),
          { once: true },
        );
      }}
      fallback={<span>Tampilan 3D tidak tersedia.</span>}
    >
      <color attach="background" args={["#494735"]} />
      <fog attach="fog" args={["#494735", 28, 65]} />
      <ambientLight intensity={1.25} color="#fff0d3" />
      <hemisphereLight args={["#e7e2cb", "#797455", 1.3]} />
      <directionalLight
        position={[-5, 10, 6]}
        intensity={3.4}
        color="#ffe2b0"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-10}
        shadow-camera-right={10}
        shadow-camera-top={9}
        shadow-camera-bottom={-7}
        shadow-normalBias={0.035}
        shadow-bias={-0.0001}
      />
      <directionalLight position={[7, 6, -4]} intensity={0.8} color="#e7dfc6" />
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.56, 0]}
        receiveShadow
      >
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#494735" roughness={1} />
      </mesh>
      <WorldMotion enabled={!props.reducedMotion}>
        <Suspense fallback={null}>
          <Diorama selected={props.selected} />
          <ContactShadows
            position={[0, -0.53, 0]}
            scale={25}
            opacity={0.45}
            blur={2.5}
            far={12}
            resolution={256}
            frames={1}
          />
          <Markers {...props} />
          <Ready onReady={props.onReady} />
        </Suspense>
      </WorldMotion>
      <CameraRig {...props} />
    </Canvas>
  );
}
