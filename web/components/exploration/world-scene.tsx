"use client";
/* Three/R3F scene code intentionally mutates cameras, geometries and uniforms in render hooks. */
/* eslint-disable react-hooks/exhaustive-deps, react-hooks/immutability, @typescript-eslint/no-unused-vars */

import {
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { AdaptiveDpr, OrbitControls } from "@react-three/drei";
import { createRoot, type Root } from "react-dom/client";
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import {
  Check as CheckIcon,
  House as HomeIcon,
  Leaf as LeafIcon,
  Layers3 as LayersIcon,
} from "lucide-react";
import type { JourneyChapter } from "@/lib/journey";
import {
  exploreRegions,
  findExploreRegion,
  type ExploreRegion,
} from "@/lib/exploration";
import {
  LivingWorld,
  RiverRipples,
  WorldEntrance,
  WorldMotion,
  useWorldMotion,
} from "./world-motion";
import {
  AtlasLandscape,
  GrazingHorse,
  LandscapeGarden,
  MiniatureLandmarks,
  MapWaveAccents,
  RegionalArchitecture,
} from "./diorama-models";
import { WorldTransitionStage } from "./world-transitions";
import { SLIDE_CLOSE_MS, type WorldTransition } from "./use-world-navigation";
import { AtlasCamera } from "./atlas-camera";
import { AtlasClouds, AtlasLighting, AtlasSeaNames } from "./atlas-three-art";
import { AtlasGpuWorld } from "./atlas-gpu-world";
import type { AtlasGpuBridge } from "./atlas-gpu-overlay";
import { RegionalLand } from "./regional-land";
import { isRegionalGround } from "./regional-terrain";
import { MapButton } from "./map-button";

export type WorldSceneProps = {
  mode: "map" | "region";
  regionId?: string;
  selectedRegion: string;
  onSelectRegion: (id: string) => void;
  onHoverRegion?: (id: string) => void;
  onHotspot: (id: "culture" | "weaving" | "textiles") => void;
  onReady: () => void;
  onSlideReady: (id: string) => void;
  onSlideComplete: (sequence: number) => void;
  onSlidePrepared: (
    id: string,
    sequence: number,
    frames: { from: string; to: string },
  ) => void;
  onSlidePresented: (sequence: number) => void;
  snapshotTransition: boolean;
  lowGraphics: boolean;
  reducedMotion: boolean;
  zoom: number;
  reset: number;
  activeHotspot: "culture" | "weaving" | "textiles";
  paused: boolean;
  /** Stop drawing while a modal covers the world, without disposing the scene. */
  renderingSuspended?: boolean;
  departing: boolean;
  timeOfDay: "day" | "sunset";
  onDiscover: (message: string) => void;
  greeting: number;
  presentation: "preview" | "intro" | "explore";
  panelOpen: boolean;
  readChapters?: JourneyChapter[];
  dashboardOpen?: boolean;
  transition: WorldTransition;
  onZoomChange?: (value: number) => void;
  atlas2d?: RefObject<AtlasGpuBridge>;
};

type Point = [number, number, number];
type Ring = number[][];
type Geography =
  | { type: "Polygon"; coordinates: Ring[] }
  | { type: "MultiPolygon"; coordinates: Ring[][] };
type GeoDocument =
  | Geography
  | { type: "Feature"; geometry: GeoDocument | null }
  | { type: "FeatureCollection"; features: GeoDocument[] };
type TreeSpec = { position: Point; scale: number; rotation: number };

// Project labels into a DOM overlay. Defer root disposal so StrictMode does not
// synchronously unmount React DOM while the Three reconciler is rendering.
function Html({
  children,
  position,
  style,
  zIndexRange = [30, 20],
  calculatePosition,
}: {
  children: ReactNode;
  position?: Point;
  center?: boolean;
  style?: CSSProperties;
  zIndexRange?: number[];
  calculatePosition?: (
    object: THREE.Object3D,
    camera: THREE.Camera,
    size: { width: number; height: number },
  ) => number[];
}) {
  const group = useRef<THREE.Group>(null);
  const root = useRef<Root | null>(null);
  const node = useRef<HTMLDivElement | null>(null);
  const { gl } = useThree();
  const projected = useMemo(() => new THREE.Vector3(), []);
  const lastProjection = useRef("");
  useEffect(() => {
    const element = document.createElement("div");
    Object.assign(element.style, {
      position: "absolute",
      left: "0",
      top: "0",
      pointerEvents: "none",
      zIndex: String(zIndexRange[0]),
    });
    gl.domElement.parentElement?.appendChild(element);
    node.current = element;
    const mountedRoot = createRoot(element);
    root.current = mountedRoot;
    return () => {
      node.current = null;
      root.current = null;
      queueMicrotask(() => {
        mountedRoot.unmount();
        element.remove();
      });
    };
  }, [gl]);
  useEffect(() => {
    root.current?.render(
      <div style={{ transform: "translate(-50%, -50%)", ...style }}>
        {children}
      </div>,
    );
  }, [children, style]);
  useFrame(({ camera, size }) => {
    if (!group.current || !node.current) return;
    let x: number, y: number;
    if (calculatePosition) {
      [x, y] = calculatePosition(group.current, camera, size);
    } else {
      projected
        .setFromMatrixPosition(group.current.matrixWorld)
        .project(camera);
      x = ((projected.x + 1) * size.width) / 2;
      y = ((1 - projected.y) * size.height) / 2;
    }
    const transform = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0)`;
    if (lastProjection.current !== transform) {
      node.current.style.transform = transform;
      lastProjection.current = transform;
    }
    node.current.style.zIndex = String(zIndexRange[0]);
    node.current.style.visibility =
      x < 0 || y < 0 || x > size.width || y > size.height
        ? "hidden"
        : "visible";
  });
  return <group ref={group} position={position} />;
}

const C = {
  green: "#79a644",
  light: "#a6bf4b",
  dark: "#244d3c",
  sea: "#68bdcd",
  sand: "#e5cf99",
  cliff: "#9caa7c",
  cream: "#fff9e9",
  wood: "#87502d",
  roof: "#7d6142",
  clay: "#b86647",
  gold: "#edba55",
};

// Every procedural placement is stable, including across hydration and quality changes.
function noise(index: number, seed = 1) {
  const n = Math.sin(index * 127.1 + seed * 311.7) * 43758.5453;
  return n - Math.floor(n);
}

function project(lon: number, lat: number): [number, number] {
  return [(lon - 118) * 0.98, -(lat + 2.3) * 1.04];
}

function polygons(document: GeoDocument): Ring[][] {
  if (document.type === "FeatureCollection")
    return document.features.flatMap(polygons);
  if (document.type === "Feature")
    return document.geometry ? polygons(document.geometry) : [];
  return document.type === "Polygon"
    ? [document.coordinates]
    : document.coordinates;
}

function islandShape(rings: Ring[]) {
  const shape = new THREE.Shape();
  rings.forEach((ring, i) => {
    const path = i === 0 ? shape : new THREE.Path();
    ring.forEach(([lon, lat], j) => {
      const [x, z] = project(lon, lat);
      if (j === 0) path.moveTo(x, -z);
      else path.lineTo(x, -z);
    });
    path.closePath();
    if (i > 0) shape.holes.push(path as THREE.Path);
  });
  return shape;
}

function useGeography(enabled: boolean) {
  const [data, setData] = useState<GeoDocument | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    if (!enabled || data) return;
    const controller = new AbortController();
    fetch("/assets/exploration/indonesia.geo.json", {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            `Indonesia geography could not load (${response.status}).`,
          );
        const json = (await response.json()) as GeoDocument;
        if (
          !json ||
          !["FeatureCollection", "Feature", "Polygon", "MultiPolygon"].includes(
            json.type,
          ) ||
          !polygons(json).length
        ) {
          throw new Error(
            "Indonesia geography contains no supported island polygons.",
          );
        }
        setError(null);
        setData(json);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason
              : new Error("Unable to load Indonesia geography."),
          );
      });
    return () => controller.abort();
  }, [enabled, data]);
  // Render errors propagate to the controller's React error boundary.
  if (enabled && error) throw error;
  return data;
}

function Geography({
  data,
  lowGraphics,
  onSelectRegion,
}: {
  data: GeoDocument;
  lowGraphics: boolean;
  onSelectRegion: (id: string) => void;
}) {
  const geometry = useMemo(() => {
    const pieces = polygons(data)
      .filter((rings) => {
        const r = rings[0];
        if (!r || r.length < 4) return false;
        let area = 0;
        for (let i = 0; i < r.length - 1; i++)
          area += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
        return Math.abs(area) > 0.025;
      })
      .map((rings) => {
        const part = new THREE.ExtrudeGeometry(islandShape(rings), {
          depth: 0.48,
          bevelEnabled: true,
          bevelSegments: 1,
          steps: 1,
          bevelSize: 0.025,
          bevelThickness: 0.045,
          curveSegments: 1,
        });
        part.rotateX(-Math.PI / 2);
        return part;
      });
    // Preserve cap/side materials while batching all islands into one draw per material.
    const tops: THREE.BufferGeometry[] = [];
    const sides: THREE.BufferGeometry[] = [];
    pieces.forEach((part) => {
      part.groups.forEach((group) => {
        const slice = new THREE.BufferGeometry();
        for (const name of ["position", "normal", "uv"]) {
          const attribute = part.getAttribute(name);
          slice.setAttribute(
            name,
            new THREE.BufferAttribute(
              (attribute.array as Float32Array).slice(
                group.start * attribute.itemSize,
                (group.start + group.count) * attribute.itemSize,
              ),
              attribute.itemSize,
            ),
          );
        }
        (group.materialIndex === 0 ? tops : sides).push(slice);
      });
      part.dispose();
    });
    const top = tops.length ? mergeGeometries(tops) : null;
    const side = sides.length ? mergeGeometries(sides) : null;
    [...tops, ...sides].forEach((part) => part.dispose());
    if (top) {
      const p = top.getAttribute("position"),
        colors = new Float32Array(p.count * 3);
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i),
          z = p.getZ(i);
        const blend =
          (Math.sin(x * 0.75 + z * 0.48) + Math.cos(x * 0.38 - z * 0.7) + 2) /
          4;
        new THREE.Color("#779e49")
          .lerp(new THREE.Color("#a6bc63"), blend * 0.7)
          .toArray(colors, i * 3);
      }
      top.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    }
    if (side) {
      const p = side.getAttribute("position"),
        colors = new Float32Array(p.count * 3);
      for (let i = 0; i < p.count; i++) {
        const h = THREE.MathUtils.clamp(p.getY(i) / 0.48, 0, 1);
        const color = new THREE.Color(
          h > 0.82
            ? "#efcd81"
            : h > 0.56
              ? "#ce9d5d"
              : h > 0.24
                ? "#e1b46f"
                : "#b8874e",
        );
        color
          .multiplyScalar(
            0.97 + Math.sin(p.getX(i) * 11 + p.getZ(i) * 8) * 0.035,
          )
          .toArray(colors, i * 3);
      }
      side.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    }
    return { top, side };
  }, [data]);
  useEffect(
    () => () => {
      geometry.top?.dispose();
      geometry.side?.dispose();
    },
    [geometry],
  );
  return (
    <group>
      {geometry.top && (
        <mesh
          geometry={geometry.top}
          name="indonesia-land"
          receiveShadow
          castShadow={!lowGraphics}
          onClick={(event) => {
            if (event.delta > 5) return;
            const lon = event.point.x / 0.98 + 118,
              lat = -event.point.z / 1.04 - 2.3;
            const ranked = exploreRegions
              .map((region) => ({
                region,
                distance: Math.hypot(
                  region.coordinates[0] - lon,
                  region.coordinates[1] - lat,
                ),
              }))
              .sort((a, b) => a.distance - b.distance);
            if (ranked[0].distance < 4) {
              event.stopPropagation();
              onSelectRegion(ranked[0].region.id);
            }
          }}
        >
          <meshStandardMaterial
            color="#ffffff"
            vertexColors
            roughness={0.98}
            flatShading
          />
        </mesh>
      )}
      {geometry.side && (
        <mesh geometry={geometry.side} receiveShadow>
          <meshStandardMaterial
            color="#ffffff"
            vertexColors
            roughness={1}
            flatShading
          />
        </mesh>
      )}
      {/* A submerged second silhouette makes the shallow coastal shelf dimensional. */}
      {geometry.top && (
        <mesh
          geometry={geometry.top}
          position={[0, -0.53, 0]}
          scale={[1.004, 1, 1.012]}
        >
          <meshStandardMaterial
            color="#a1d6bc"
            transparent
            opacity={0.4}
            depthWrite={false}
          />
        </mesh>
      )}
    </group>
  );
}

const oceanVertex = `
  varying vec2 vWorld;
  varying vec2 vScreen;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xz;
    gl_Position = projectionMatrix * viewMatrix * world;
    vScreen = gl_Position.xy / gl_Position.w;
  }
`;
const oceanFragment = `
  varying vec2 vWorld;
  varying vec2 vScreen;
  uniform float time;
  uniform float sunset;
  void main() {
    float distanceToCenter = length(vWorld * vec2(.022, .036));
    vec3 shallow = vec3(.20, .49, .48);
    vec3 deep = vec3(.16, .42, .45);
    shallow = mix(shallow, vec3(.30,.46,.41), sunset);
    deep = mix(deep, vec3(.25,.39,.38), sunset);
    vec3 water = mix(shallow, deep, smoothstep(.08, 1.6, distanceToCenter));
    float wave = sin(vWorld.x * 1.4 + vWorld.y * 2.1 + time * .48);
    float crossWave = sin(vWorld.x * 2.5 - vWorld.y * 1.2 - time * .3);
    float ripple = smoothstep(.94, 1., wave) * smoothstep(.2, .9, crossWave);
    float grain = fract(sin(dot(floor(vWorld * 55.), vec2(12.9898,78.233))) * 43758.5453);
    water += ripple * .009 + sin(vWorld.x * .3 + time * .12) * .004 + grain * .006;
    float edge = min(1. - abs(vScreen.x), 1. - abs(vScreen.y));
    gl_FragColor = vec4(water, smoothstep(0., .22, edge));
    #include <colorspace_fragment>
  }
`;

function Ocean({
  timeOfDay,
  reducedMotion,
  paused,
}: Pick<WorldSceneProps, "timeOfDay" | "reducedMotion" | "paused">) {
  const material = useRef<THREE.ShaderMaterial>(null);
  const motion = useWorldMotion();
  const uniforms = useMemo(
    () => ({
      time: { value: 0 },
      sunset: { value: timeOfDay === "sunset" ? 1 : 0 },
    }),
    [],
  );
  useFrame((_, delta) => {
    if (material.current) {
      material.current.uniforms.time.value = motion.current.time;
      material.current.uniforms.sunset.value =
        reducedMotion || paused
          ? timeOfDay === "sunset"
            ? 1
            : 0
          : THREE.MathUtils.damp(
              material.current.uniforms.sunset.value,
              timeOfDay === "sunset" ? 1 : 0,
              3,
              Math.min(delta, 0.05),
            );
    }
  });
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.16, 0]}>
      <planeGeometry args={[450, 450]} />
      <shaderMaterial
        ref={material}
        uniforms={uniforms}
        vertexShader={oceanVertex}
        fragmentShader={oceanFragment}
        transparent
        toneMapped={false}
      />
    </mesh>
  );
}

function Forest({
  trees,
  dry = false,
  illustrated = false,
}: {
  trees: TreeSpec[];
  dry?: boolean;
  illustrated?: boolean;
}) {
  const trunks = useRef<THREE.InstancedMesh>(null);
  const crowns = useRef<THREE.InstancedMesh>(null);
  const motion = useWorldMotion();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const windTime = useMemo(() => ({ value: 0 }), []);
  const canopy = useMemo(() => {
    const blobs = illustrated
      ? [
          [-0.3, 0, 0.05, 0.5],
          [0.32, 0.07, 0.08, 0.46],
          [0, 0.36, -0.13, 0.52],
          [-0.18, 0.31, 0.2, 0.38],
          [0.1, -0.04, 0.3, 0.4],
        ]
      : [
          [-0.3, 0, 0.05, 0.65],
          [0.32, 0.07, 0.08, 0.6],
          [0, 0.36, -0.13, 0.68],
        ];
    const pieces = blobs.map(([x, y, z, s]) => {
      const g = illustrated
        ? new THREE.SphereGeometry(s, 8, 6)
        : new THREE.IcosahedronGeometry(s, 0);
      g.translate(x, y, z);
      return g;
    });
    const result = mergeGeometries(pieces)!;
    pieces.forEach((g) => g.dispose());
    return result;
  }, [illustrated]);
  useEffect(() => () => canopy.dispose(), [canopy]);
  useFrame(() => {
    if (!crowns.current || !motion.current.enabled) return;
    if (illustrated) {
      windTime.value = motion.current.time;
      return;
    }
    const t = motion.current.time;
    trees.forEach(({ position: [x, y, z], scale, rotation }, i) => {
      const wind =
        Math.sin(t * 1.4 + x * 0.6 + z * 0.2) * 0.035 +
        Math.sin(t * 0.6 + i) * 0.018;
      dummy.position.set(x + wind * scale * 0.4, y + scale * 0.98, z);
      dummy.rotation.set(wind * 0.4, rotation, wind);
      dummy.scale.set(scale * 0.64, scale * (dry ? 0.64 : 1.05), scale * 0.64);
      dummy.updateMatrix();
      crowns.current!.setMatrixAt(i, dummy.matrix);
    });
    crowns.current.instanceMatrix.needsUpdate = true;
  });
  useLayoutEffect(() => {
    const dummy = new THREE.Object3D();
    trees.forEach(({ position: [x, y, z], scale, rotation }, i) => {
      dummy.position.set(x, y + scale * 0.32, z);
      dummy.rotation.set(0, rotation, 0);
      dummy.scale.set(scale * 0.12, scale * 0.8, scale * 0.12);
      dummy.updateMatrix();
      trunks.current?.setMatrixAt(i, dummy.matrix);
      dummy.position.y = y + scale * 0.98;
      dummy.scale.set(scale * 0.64, scale * (dry ? 0.64 : 1.05), scale * 0.64);
      dummy.updateMatrix();
      crowns.current?.setMatrixAt(i, dummy.matrix);
      crowns.current?.setColorAt(
        i,
        new THREE.Color(
          dry
            ? i % 2
              ? "#92a337"
              : "#728c2d"
            : illustrated
              ? i % 11 === 0
                ? "#c47a36"
                : ["#597f30", "#75943b", "#426d38", "#94a545"][i % 4]
              : i % 3
                ? "#55912e"
                : "#8db73b",
        ),
      );
    });
    for (const mesh of [trunks.current, crowns.current]) {
      if (!mesh) continue;
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
  }, [trees, dry, illustrated]);
  return (
    <group>
      <instancedMesh
        ref={trunks}
        args={[undefined, undefined, trees.length]}
        castShadow
      >
        <cylinderGeometry args={[0.65, 1, 1, 5]} />
        <meshStandardMaterial color={C.wood} flatShading />
      </instancedMesh>
      <instancedMesh
        ref={crowns}
        args={[undefined, undefined, trees.length]}
        castShadow
        geometry={canopy}
      >
        <meshStandardMaterial
          roughness={1}
          flatShading={!illustrated}
          onBeforeCompile={(shader) => {
            if (!illustrated) return;
            shader.uniforms.atlasWindTime = windTime;
            shader.vertexShader =
              `uniform float atlasWindTime;\n${shader.vertexShader}`.replace(
                "#include <begin_vertex>",
                `#include <begin_vertex>\n#ifdef USE_INSTANCING\ntransformed.x += sin(atlasWindTime * 1.2 + instanceMatrix[3].x * .7 + instanceMatrix[3].z) * .035 * max(position.y, 0.);\n#endif`,
              );
          }}
          customProgramCacheKey={() =>
            illustrated ? "atlas-foliage-wind" : "regional-foliage"
          }
        />
      </instancedMesh>
    </group>
  );
}

function Palm({ position, scale = 1 }: { position: Point; scale?: number }) {
  const crown = useRef<THREE.Group>(null);
  const motion = useWorldMotion();
  useFrame(() => {
    if (crown.current) {
      const t = motion.current.time;
      crown.current.rotation.z = Math.sin(t * 1.2 + position[0]) * 0.065;
      crown.current.rotation.x = Math.cos(t * 0.8 + position[2]) * 0.035;
    }
  });
  return (
    <group position={position} scale={scale} rotation={[0, position[0], -0.1]}>
      <mesh position={[0.06, 0.85, 0]} rotation={[0, 0, -0.08]} castShadow>
        <cylinderGeometry args={[0.055, 0.11, 1.7, 6]} />
        <meshStandardMaterial color="#a28b5e" flatShading />
      </mesh>
      <group ref={crown} position={[0.13, 1.68, 0]}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <group key={i} rotation={[0, (i * Math.PI) / 3, 0]}>
            <mesh
              position={[0.4, 0.06, 0]}
              scale={[0.72, 0.055, 0.17]}
              rotation={[0, 0, -0.24]}
              castShadow
            >
              <sphereGeometry args={[1, 5, 3]} />
              <meshStandardMaterial
                color={i % 2 ? "#6f9858" : "#426e48"}
                flatShading
              />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}

function Boat({
  position,
  rotation = 0,
  scale = 1,
  sail = false,
  woven = false,
}: {
  position: Point;
  rotation?: number;
  scale?: number;
  sail?: boolean;
  woven?: boolean;
}) {
  const sailTexture = useMemo(() => {
    if (!woven) return null;
    const bytes = new Uint8Array(64 * 64 * 4);
    for (let y = 0; y < 64; y++)
      for (let x = 0; x < 64; x++) {
        const diamond = Math.abs((x % 32) - 16) + Math.abs((y % 32) - 16);
        const line =
          Math.abs(diamond - 13) < 1.3 ||
          Math.abs(diamond - 6) < 1 ||
          y % 32 < 2;
        const i = (y * 64 + x) * 4;
        bytes.set(line ? [242, 207, 145, 255] : [159, 73, 43, 255], i);
      }
    const texture = new THREE.DataTexture(bytes, 64, 64);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    texture.needsUpdate = true;
    return texture;
  }, [woven]);
  useEffect(() => () => sailTexture?.dispose(), [sailTexture]);
  const vessel = useRef<THREE.Group>(null),
    wake = useRef<THREE.Mesh>(null);
  const motion = useWorldMotion();
  const phase = position[0] * 0.3 + position[2];
  useFrame(() => {
    if (!vessel.current) return;
    const t = motion.current.time,
      a = t * 0.085 + phase;
    // Local loops stay in the sea/river corridor; the hull turns into its path.
    const river = position[1] > 0.5;
    const range = river ? 0.14 : sail ? 1.5 : 0.6;
    const dx = Math.sin(a) * range,
      dz = Math.sin(a * 2) * range * 0.27;
    vessel.current.position.set(
      position[0] + Math.cos(rotation) * dx + Math.sin(rotation) * dz,
      position[1] - (river ? 0 : 0.05) + Math.sin(t * 1.9 + phase) * 0.035,
      position[2] - Math.sin(rotation) * dx + Math.cos(rotation) * dz,
    );
    vessel.current.rotation.set(
      Math.sin(t * 1.3 + phase) * 0.025,
      rotation +
        (river
          ? Math.sin(a) * 0.12
          : Math.atan2(-Math.cos(a), -Math.cos(a * 2) * 0.54)),
      Math.sin(t * 1.8 + phase) * 0.045,
    );
    if (wake.current) {
      wake.current.position.y =
        (river ? 0.927 : -0.15) - vessel.current.position.y;
      const pulse = (((t * 0.5 + phase) % 1) + 1) % 1;
      wake.current.scale.set(0.6 + pulse * 0.18, 1.8 + pulse * 0.5, 1);
      (wake.current.material as THREE.MeshBasicMaterial).opacity =
        0.45 - pulse * 0.25;
    }
  });
  return (
    <group
      ref={vessel}
      name="animated-boat"
      position={position}
      rotation={[0, rotation, 0]}
      scale={scale}
    >
      <mesh scale={[0.28, 0.18, 0.8]} position={[0, 0.1, 0]} castShadow>
        <sphereGeometry args={[1, 5, 3]} />
        <meshStandardMaterial color="#805b3d" flatShading />
      </mesh>
      <mesh position={[0, 0.19, 0]}>
        <boxGeometry args={[0.27, 0.035, 0.85]} />
        <meshStandardMaterial color={C.sand} />
      </mesh>
      {sail ? (
        <>
          <mesh position={[0, 0.72, 0]}>
            <cylinderGeometry args={[0.018, 0.025, 1.2, 5]} />
            <meshStandardMaterial color={C.wood} />
          </mesh>
          <mesh
            position={[0.02, 0.82, 0.2]}
            rotation={[0, 0, -0.07]}
            scale={[0.65, 1, 1]}
          >
            <circleGeometry args={[0.5, 3, 0]} />
            <meshStandardMaterial
              color={woven ? "#ffffff" : C.cream}
              map={sailTexture}
              side={THREE.DoubleSide}
              roughness={1}
            />
          </mesh>
        </>
      ) : (
        <mesh position={[0, 0.5, -0.15]}>
          <boxGeometry args={[0.45, 0.12, 0.65]} />
          <meshStandardMaterial color={C.clay} />
        </mesh>
      )}
      <mesh
        ref={wake}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.015, 1.1]}
        scale={[0.6, 1.8, 1]}
      >
        <ringGeometry args={[0.36, 0.375, 20, 1, 0, Math.PI]} />
        <meshBasicMaterial
          color="#b5e0cb"
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function Clouds({
  map,
  reducedMotion,
  lowGraphics,
}: {
  map: boolean;
  reducedMotion: boolean;
  lowGraphics: boolean;
}) {
  const cloud = useRef<THREE.Group>(null);
  const motion = useWorldMotion();
  useFrame(() => {
    if (!cloud.current) return;
    const t = motion.current.time;
    cloud.current.children.forEach((child, i) => {
      const p = positions[i];
      child.position.x = p[0] + Math.sin(t * 0.075 + i * 2) * (map ? 1.6 : 0.8);
      child.position.y = p[1] + Math.sin(t * 0.22 + i) * 0.12;
      child.position.z = p[2] + Math.cos(t * 0.045 + i) * 0.3;
    });
  });
  const positions: Point[] = map
    ? [
        [-17, 3.5, -6.7],
        [-6, 4, -5.5],
        [15, 3.2, -7.5],
        [18, 3.5, 5.5],
        [-14, 2.5, 10],
      ]
    : [
        [-6.7, 2.7, -3.2],
        [5.7, 3, -4.8],
        [7, 1.8, 2.9],
      ];
  return (
    <group ref={cloud}>
      {positions.slice(0, lowGraphics ? 2 : undefined).map((position, i) => (
        <group key={i} position={position} scale={map ? 1.1 : 0.75}>
          {[
            [-0.7, 0, 0],
            [0, 0.3, 0],
            [0.8, 0.05, 0.1],
            [0.15, -0.12, 0.4],
          ].map((p, j) => (
            <mesh
              key={j}
              position={p as Point}
              scale={[1.1, 0.55 + j * 0.06, 0.7]}
            >
              <icosahedronGeometry args={[0.8, 1]} />
              <meshStandardMaterial
                color="#fffdf0"
                roughness={1}
                transparent
                opacity={0.91}
                depthWrite={false}
              />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
}

const badge: CSSProperties = {
  fontFamily: "var(--font-manrope), Manrope, sans-serif",
  fontSize: 11,
  fontWeight: 650,
  border: "1px solid rgba(44,77,55,.22)",
  borderRadius: 999,
  padding: "8px 12px",
  background: C.cream,
  color: C.dark,
  boxShadow: "0 3px 0 rgba(35,76,57,.17), 0 6px 18px rgba(28,64,53,.12)",
  whiteSpace: "nowrap",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  gap: 7,
  minHeight: 36,
  touchAction: "manipulation",
  pointerEvents: "auto",
};

// Screen-space offsets separate the small, closely-spaced Lesser Sunda islands.
const pinOffsets: Record<string, [number, number]> = {
  "sumatera-utara": [-5, -42],
  "sumatera-barat": [-70, 6],
  "sumatera-selatan": [36, -25],
  "jawa-tengah": [-30, 36],
  bali: [-48, -42],
  lombok: [22, 40],
  sumba: [28, 32],
  flores: [64, -29],
  "sulawesi-tengah": [26, -36],
};

function PulseBeacon({
  active,
  scale = 1,
}: {
  active: boolean;
  scale?: number;
}) {
  const ring = useRef<THREE.Mesh>(null);
  const motion = useWorldMotion();
  useFrame(() => {
    if (!ring.current) return;
    const progress = (motion.current.time * 0.45) % 1;
    ring.current.scale.setScalar((1 + progress * 1.8) * scale);
    (ring.current.material as THREE.MeshBasicMaterial).opacity = active
      ? (1 - progress) * 0.55
      : 0;
  });
  return (
    <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
      <ringGeometry args={[0.22, 0.25, 32]} />
      <meshBasicMaterial
        color="#f5d286"
        transparent
        opacity={0.5}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

function RegionPins({
  selectedRegion,
  onSelectRegion,
  onHoverRegion,
}: Pick<
  WorldSceneProps,
  "selectedRegion" | "onSelectRegion" | "onHoverRegion"
>) {
  const mobile = useThree((state) => state.size.width <= 900);
  const projected = useMemo(() => new THREE.Vector3(), []);
  return (
    <group>
      {exploreRegions.map((region, regionIndex) => {
        const [x, z] = project(...region.coordinates);
        const selected = selectedRegion === region.id;
        const mobileOffsets: Record<string, [number, number]> = {
          "sumatera-utara": [-12, -25],
          "sumatera-barat": [-20, 18],
          "sumatera-selatan": [10, -24],
          "jawa-tengah": [-24, 28],
          bali: [-19, -17],
          lombok: [7, 33],
          sumba: [38, 28],
          flores: [35, -18],
          "sulawesi-tengah": [12, -25],
        };
        const [dx, dy] = (mobile
          ? mobileOffsets[region.id]
          : pinOffsets[region.id]) ?? [0, -20];
        const offsetX = dx;
        return (
          <group key={region.id} position={[x, 0.66, z]}>
            {selected && <PulseBeacon active scale={2} />}
            <mesh rotation={[-Math.PI / 2, 0, 0]}>
              <ringGeometry args={[0.12, selected ? 0.26 : 0.19, 24]} />
              <meshBasicMaterial
                color={selected ? C.gold : C.cream}
                side={THREE.DoubleSide}
              />
            </mesh>
            <Html
              center
              zIndexRange={selected ? [35, 30] : [25, 20]}
              style={{ pointerEvents: "none" }}
              calculatePosition={(object, camera, size) => {
                projected
                  .setFromMatrixPosition(object.matrixWorld)
                  .project(camera);
                const x = ((projected.x + 1) * size.width) / 2;
                const y = ((1 - projected.y) * size.height) / 2;
                return [x, y];
              }}
            >
              <div
                style={{
                  position: "relative",
                  transform: `translate(${offsetX}px, ${dy}px)`,
                }}
              >
                <svg
                  width="1"
                  height="1"
                  aria-hidden="true"
                  style={{
                    overflow: "visible",
                    position: "absolute",
                    left: "50%",
                    top: "50%",
                    pointerEvents: "none",
                  }}
                >
                  <line
                    x1={0}
                    y1={0}
                    x2={-offsetX}
                    y2={-dy}
                    stroke={selected ? "#e5bc69" : "#fff9e9"}
                    strokeWidth={1.3}
                  />
                </svg>
                <button
                  type="button"
                  className="nx-map-pin"
                  aria-pressed={selected}
                  aria-label={`Pilih daerah ${region.name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectRegion(region.id);
                  }}
                  onMouseEnter={() => onHoverRegion?.(region.id)}
                  onFocus={() => onHoverRegion?.(region.id)}
                  style={{
                    ...badge,
                    position: "relative",
                    fontSize: mobile ? 10 : 11,
                    padding: mobile
                      ? selected
                        ? "7px 10px"
                        : "0"
                      : "8px 12px",
                    minWidth: mobile && !selected ? 29 : undefined,
                    minHeight: mobile ? 29 : 36,
                    justifyContent: "center",
                    background: selected ? C.clay : C.cream,
                    color: selected ? C.cream : C.dark,
                    borderColor: selected ? "#985037" : "rgba(44,77,55,.22)",
                  }}
                >
                  {(!mobile || selected) && (
                    <span
                      aria-hidden="true"
                      style={{
                        width: 6,
                        height: 6,
                        background: selected ? "#f0d69b" : C.green,
                        transform: "rotate(45deg)",
                        flexShrink: 0,
                      }}
                    />
                  )}
                  {mobile
                    ? ((
                        {
                          "sumatera-utara": "Batak",
                          "sumatera-barat": "Minang",
                          "sumatera-selatan": "Palembang",
                          "jawa-tengah": "Jateng",
                          "sulawesi-tengah": "Donggala",
                          flores: "Flores",
                        } as Record<string, string>
                      )[region.id] ?? region.name)
                    : region.name}
                </button>
              </div>
            </Html>
          </group>
        );
      })}
    </group>
  );
}

function MapWorld({
  data,
  lowGraphics,
  selectedRegion,
  onSelectRegion,
  onHoverRegion,
}: Pick<
  WorldSceneProps,
  "lowGraphics" | "selectedRegion" | "onSelectRegion" | "onHoverRegion"
> & { data: GeoDocument }) {
  const trees = useMemo(() => {
    const inside = (lon: number, lat: number, ring: Ring) => {
      let hit = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [x, y] = ring[i],
          [xj, yj] = ring[j];
        if (y > lat !== yj > lat && lon < ((xj - x) * (lat - y)) / (yj - y) + x)
          hit = !hit;
      }
      return hit;
    };
    const rings = polygons(data).map((p) => ({
      ring: p[0],
      minX: Math.min(...p[0].map((p) => p[0])),
      maxX: Math.max(...p[0].map((p) => p[0])),
      minY: Math.min(...p[0].map((p) => p[1])),
      maxY: Math.max(...p[0].map((p) => p[1])),
    }));
    const result: TreeSpec[] = [];
    const landmarks = exploreRegions.map((region) =>
      project(...region.coordinates),
    );
    for (
      let i = 0;
      i < 6500 && result.length < (lowGraphics ? 135 : 410);
      i++
    ) {
      const lon = 95 + noise(i, 5) * 46,
        lat = -10 + noise(i, 9) * 16;
      if (
        !rings.some(
          ({ ring, minX, maxX, minY, maxY }) =>
            lon >= minX &&
            lon <= maxX &&
            lat >= minY &&
            lat <= maxY &&
            inside(lon, lat, ring),
        )
      )
        continue;
      const [x, z] = project(lon, lat);
      if (landmarks.some(([lx, lz]) => Math.hypot(x - lx, z - lz) < 1))
        continue;
      if (noise(Math.floor(lon * 1.3) + Math.floor(lat) * 7, 8) < 0.25)
        continue;
      result.push({
        position: [x, 0.53, z],
        scale: 0.34 + noise(i, 2) * 0.24,
        rotation: noise(i, 8) * 6,
      });
    }
    return result;
  }, [lowGraphics, data]);
  return (
    <>
      <Geography
        data={data}
        lowGraphics={lowGraphics}
        onSelectRegion={onSelectRegion}
      />
      <Forest trees={trees} illustrated />
      <MiniatureLandmarks lowGraphics={lowGraphics} />
      <AtlasLandscape lowGraphics={lowGraphics} />
      <AtlasSeaNames />
      <MapWaveAccents />
      <Boat position={[-17, 0, 8]} rotation={-0.7} scale={1.8} sail woven />
      <Boat position={[1, 0, 10]} rotation={1.3} scale={1.2} sail woven />
      <Boat position={[14, 0, 1.6]} rotation={0.5} scale={1.0} />
      {[0, 1, 2].slice(0, lowGraphics ? 1 : 3).map((i) => (
        <mesh
          key={`isobath-${i}`}
          position={[0, -0.14, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          scale={[1.65, 0.66, 1]}
        >
          <ringGeometry args={[8 + i * 1.4, 8.025 + i * 1.4, 72]} />
          <meshBasicMaterial
            color="#d0ead1"
            transparent
            opacity={0.13 - i * 0.025}
            depthWrite={false}
          />
        </mesh>
      ))}
      <RegionPins
        selectedRegion={selectedRegion}
        onSelectRegion={onSelectRegion}
        onHoverRegion={onHoverRegion}
      />
    </>
  );
}

function House({
  position,
  rotation = 0,
  scale = 1,
  landscape,
}: {
  position: Point;
  rotation?: number;
  scale?: number;
  landscape: ExploreRegion["landscape"];
}) {
  const peaked = landscape === "savanna";
  const pavilion = landscape === "terraces";
  const river = landscape === "river";
  return (
    <group position={position} rotation={[0, rotation, 0]} scale={scale}>
      {[-0.52, 0.52].flatMap((x) =>
        [-0.4, 0.4].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 0.37, z]} castShadow>
            <boxGeometry args={[0.09, 0.75, 0.09]} />
            <meshStandardMaterial color={C.wood} />
          </mesh>
        )),
      )}
      <mesh position={[0, 0.6, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.4, 0.12, 1.15]} />
        <meshStandardMaterial color="#a88658" />
      </mesh>
      <mesh position={[0, 1.03, 0]} castShadow>
        <boxGeometry args={[1.12, 0.75, 0.9]} />
        <meshStandardMaterial
          color={peaked ? "#c5ac78" : river ? "#c5a26e" : "#ddc99d"}
          flatShading
        />
      </mesh>
      <mesh position={[0, 0.92, 0.459]}>
        <boxGeometry args={[0.27, 0.57, 0.035]} />
        <meshStandardMaterial color="#4f4c35" />
      </mesh>
      {[-0.37, 0.37].map((x) => (
        <mesh key={x} position={[x, 1.12, 0.46]}>
          <boxGeometry args={[0.19, 0.22, 0.035]} />
          <meshStandardMaterial color="#6a7354" />
        </mesh>
      ))}
      <mesh
        position={[0, 1.62, 0]}
        rotation={[0, Math.PI / 4, 0]}
        scale={[1.15, 0.5, 1]}
        castShadow
      >
        <coneGeometry args={[1.12, 1.05, 4]} />
        <meshStandardMaterial
          color={pavilion ? "#635d43" : C.roof}
          flatShading
          roughness={1}
        />
      </mesh>
      {peaked && (
        <>
          <mesh
            position={[0, 2.35, 0]}
            rotation={[0, Math.PI / 4, 0]}
            scale={[0.63, 1, 0.6]}
            castShadow
          >
            <coneGeometry args={[1, 1.95, 4]} />
            <meshStandardMaterial color="#8b724e" flatShading />
          </mesh>
          {[0, 1, 2, 3].map((i) => (
            <mesh
              key={i}
              position={[0, 1.87 + i * 0.24, 0]}
              rotation={[0, Math.PI / 4, 0]}
            >
              <cylinderGeometry
                args={[0.52 - i * 0.11, 0.55 - i * 0.11, 0.035, 4]}
              />
              <meshStandardMaterial color="#b49b6b" />
            </mesh>
          ))}
        </>
      )}
      {pavilion && (
        <mesh
          position={[0, 2.03, 0]}
          rotation={[0, Math.PI / 4, 0]}
          scale={[0.68, 0.55, 0.62]}
          castShadow
        >
          <coneGeometry args={[1.1, 0.9, 4]} />
          <meshStandardMaterial color="#555c40" flatShading />
        </mesh>
      )}
      {[0, 1, 2].map((i) => (
        <mesh
          key={i}
          position={[0, 0.16 + i * 0.13, 0.85 - i * 0.13]}
          receiveShadow
        >
          <boxGeometry args={[0.45, 0.13, 0.35]} />
          <meshStandardMaterial color="#b7a27a" />
        </mesh>
      ))}
    </group>
  );
}

function Hills({ landscape }: { landscape: ExploreRegion["landscape"] }) {
  if (landscape === "terraces")
    return (
      <group position={[-2.3, 0.8, -2.1]} rotation={[0, -0.2, 0]}>
        {[0, 1, 2, 3, 4].map((i) => (
          <group key={i} position={[i * 0.24, i * 0.28, -i * 0.14]}>
            <mesh scale={[1, 1, 0.63]} receiveShadow castShadow>
              <cylinderGeometry
                args={[2.35 - i * 0.34, 2.55 - i * 0.34, 0.31, 12]}
              />
              <meshStandardMaterial color="#638748" flatShading />
            </mesh>
            <mesh
              position={[0, 0.162, 0]}
              rotation={[-Math.PI / 2, 0, 0]}
              scale={[1, 0.63, 1]}
            >
              <ringGeometry args={[1.92 - i * 0.31, 2.3 - i * 0.34, 24]} />
              <meshStandardMaterial
                color={i % 2 ? "#b6c77b" : "#8fae5f"}
                roughness={0.7}
              />
            </mesh>
          </group>
        ))}
      </group>
    );
  return (
    <group>
      {[
        [0, -3.5, 2.2, 1.65],
        [-3.7, -3, 1.7, 1.2],
        [3.5, -2.9, 1.9, 1.5],
      ].map(([x, z, radius, height], i) => (
        <mesh
          key={i}
          position={[x, 0.76, z]}
          scale={[1, height / radius, 0.65]}
          rotation={[0, i * 0.8, 0]}
          castShadow
          receiveShadow
        >
          <sphereGeometry
            args={[radius, 7, 3, 0, Math.PI * 2, 0, Math.PI / 2]}
          />
          <meshStandardMaterial
            color={
              landscape === "savanna"
                ? ["#b7b575", "#cdbe83", "#a1a267"][i]
                : ["#658951", "#90a665", "#72965b"][i]
            }
            flatShading
          />
        </mesh>
      ))}
    </group>
  );
}

function River() {
  const geometry = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(0.3, -4.3);
    shape.bezierCurveTo(-0.4, -2, 0.8, 0, 0.2, 2.3);
    shape.lineTo(-0.25, 4.3);
    shape.lineTo(3.3, 4);
    shape.bezierCurveTo(4.3, 0.7, 3.6, -1.4, 3.7, -3.7);
    shape.closePath();
    const result = new THREE.ShapeGeometry(shape, 20);
    result.rotateX(-Math.PI / 2);
    return result;
  }, []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <group>
      <RiverRipples />
      <mesh geometry={geometry} position={[0, 0.915, 0]} receiveShadow>
        <meshStandardMaterial
          color="#4baabb"
          roughness={0.4}
          metalness={0.12}
        />
      </mesh>
      <Boat position={[2.1, 0.95, 0.4]} scale={0.8} rotation={0.15} />
      <group position={[1.4, 0.98, -0.8]} rotation={[0, -0.2, 0]}>
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <mesh key={i} position={[i * 0.18, 0, 0]} castShadow>
            <boxGeometry args={[0.15, 0.12, 0.7]} />
            <meshStandardMaterial color="#b99c6d" />
          </mesh>
        ))}
        {[-0.32, 0.32].map((z) => (
          <mesh key={z} position={[0.63, 0.43, z]}>
            <boxGeometry args={[1.8, 0.07, 0.06]} />
            <meshStandardMaterial color={C.wood} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

function Cloth({
  position,
  rotation = 0,
  color = C.clay,
}: {
  position: Point;
  rotation?: number;
  color?: string;
}) {
  const motion = useWorldMotion();
  const geometry = useMemo(
    () => new THREE.PlaneGeometry(1.05, 0.9, 18, 18),
    [],
  );
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 160;
    const context = canvas.getContext("2d")!;
    context.fillStyle = color;
    context.fillRect(0, 0, 128, 160);
    context.fillStyle = C.sand;
    [18, 27, 98, 107].forEach((x) => context.fillRect(x, 0, 4, 160));
    [24, 64, 104, 144].forEach((y) => {
      context.save();
      context.translate(64, y);
      context.rotate(Math.PI / 4);
      context.fillRect(-8, -8, 16, 16);
      context.restore();
    });
    const result = new THREE.CanvasTexture(canvas);
    result.colorSpace = THREE.SRGBColorSpace;
    return result;
  }, [color]);
  useEffect(
    () => () => {
      geometry.dispose();
      texture.dispose();
    },
    [geometry, texture],
  );
  useFrame(() => {
    const t = motion.current.time;
    const p = geometry.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const free = (0.45 - p.getY(i)) / 0.9;
      p.setZ(
        i,
        (Math.sin(p.getX(i) * 8 + t * 2.1 + position[0]) * 0.06 +
          Math.sin(t * 1.1) * 0.055) *
          free *
          free,
      );
    }
    p.needsUpdate = true;
    geometry.computeVertexNormals();
  });
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      {[-0.64, 0.64].map((x) => (
        <mesh key={x} position={[x, 0.65, 0]} castShadow>
          <cylinderGeometry args={[0.025, 0.035, 1.45, 5]} />
          <meshStandardMaterial color={C.wood} />
        </mesh>
      ))}
      <mesh position={[0, 1.26, 0]}>
        <boxGeometry args={[1.48, 0.045, 0.045]} />
        <meshStandardMaterial color={C.wood} />
      </mesh>
      <mesh
        name="animated-cloth"
        geometry={geometry}
        position={[0, 0.81, 0.025]}
        castShadow
      >
        <meshStandardMaterial
          map={texture}
          roughness={1}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function Loom({ position }: { position: Point }) {
  const shuttle = useRef<THREE.Mesh>(null);
  const motion = useWorldMotion();
  useFrame(() => {
    if (shuttle.current)
      shuttle.current.position.z =
        0.12 + Math.sin(motion.current.time * 3) * 0.12;
  });
  return (
    <group position={position} rotation={[0, -0.25, 0]}>
      {[-0.55, 0.55].flatMap((x) =>
        [-0.5, 0.5].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 0.5, z]}>
            <boxGeometry args={[0.065, 1, 0.065]} />
            <meshStandardMaterial color={C.wood} />
          </mesh>
        )),
      )}
      {[-0.5, 0.5].map((z) => (
        <mesh key={z} position={[0, 0.85, z]}>
          <boxGeometry args={[1.2, 0.07, 0.07]} />
          <meshStandardMaterial color={C.wood} />
        </mesh>
      ))}
      <mesh position={[0, 0.68, 0]} rotation={[0.25, 0, 0]}>
        <boxGeometry args={[0.85, 0.022, 1.05]} />
        <meshStandardMaterial color="#d1b183" />
      </mesh>
      {Array.from({ length: 12 }, (_, i) => (
        <mesh
          key={i}
          position={[-0.39 + i * 0.07, 0.7, 0]}
          rotation={[0.25, 0, 0]}
        >
          <boxGeometry args={[0.012, 0.016, 1.06]} />
          <meshStandardMaterial color={i % 3 ? C.cream : C.clay} />
        </mesh>
      ))}
      <mesh ref={shuttle} position={[0, 0.8, 0.12]}>
        <boxGeometry args={[1.12, 0.06, 0.08]} />
        <meshStandardMaterial color="#654b35" />
      </mesh>
      <mesh position={[0.1, 0.29, 0.9]}>
        <boxGeometry args={[0.8, 0.13, 0.35]} />
        <meshStandardMaterial color={C.wood} />
      </mesh>
    </group>
  );
}

function VillageDetails({
  regionId,
  lowGraphics,
  savanna,
  river = false,
}: {
  regionId: ExploreRegion["id"];
  lowGraphics: boolean;
  savanna: boolean;
  river?: boolean;
}) {
  return (
    <group>
      {Array.from({ length: river ? 8 : 13 }, (_, i) => i)
        .filter((i) =>
          isRegionalGround(
            regionId,
            -3 + i * 0.4,
            0.5 + Math.sin(i * 0.48) * 0.37,
            0.2,
          ),
        )
        .map((i) => (
          <mesh
            key={`path-${i}`}
            position={[-3 + i * 0.4, 0.91, 0.5 + Math.sin(i * 0.48) * 0.37]}
            rotation={[0, noise(i, 5), 0]}
            receiveShadow
          >
            <cylinderGeometry args={[0.15 + noise(i) * 0.06, 0.2, 0.06, 5]} />
            <meshStandardMaterial color="#d0bf94" flatShading />
          </mesh>
        ))}
      {Array.from({ length: lowGraphics ? 7 : 14 }, (_, i) => (
        <group key={`fence-${i}`} position={[-4.3 + i * 0.27, 0.85, 2.85]}>
          <mesh position={[0, 0.27, 0]} castShadow>
            <boxGeometry args={[0.055, 0.54, 0.055]} />
            <meshStandardMaterial color="#9b8054" />
          </mesh>
          <mesh position={[0.12, 0.33, 0]}>
            <boxGeometry args={[0.3, 0.045, 0.05]} />
            <meshStandardMaterial color="#b5a06e" />
          </mesh>
        </group>
      ))}
      {Array.from({ length: lowGraphics ? 8 : 18 }, (_, i) => {
        const angle = i * 2.399;
        const x = Math.cos(angle) * (4.8 + noise(i) * 0.6),
          z = Math.sin(angle) * 3.65;
        if (!isRegionalGround(regionId, x, z, 0.2)) return null;
        return (
          <mesh
            key={`rock-${i}`}
            position={[x, 0.95, z]}
            scale={[0.12 + noise(i) * 0.2, 0.1 + noise(i + 4) * 0.2, 0.16]}
            rotation={[0, i, 0]}
            castShadow
          >
            <dodecahedronGeometry args={[1, 0]} />
            <meshStandardMaterial
              color={i % 2 ? "#b1b094" : "#8b9678"}
              flatShading
            />
          </mesh>
        );
      })}
      <group position={[-3.3, 0.9, 1.65]} rotation={[0, 0.1, 0]}>
        {[0, 1, 2, 3, 4].map((i) => (
          <mesh key={i} position={[i * 0.25, 0.035, 0]} receiveShadow>
            <boxGeometry args={[0.16, 0.07, 1.15]} />
            <meshStandardMaterial color={savanna ? "#c5aa66" : "#9bb66b"} />
          </mesh>
        ))}
      </group>
      {[
        [-0.75, 2.1],
        [-0.3, 2.2],
        [0.15, 2],
      ]
        .filter(([x, z]) => isRegionalGround(regionId, x, z, 0.2))
        .map(([x, z], i) => (
          <mesh key={i} position={[x, 1.05, z]} castShadow>
            <cylinderGeometry args={[0.11, 0.17, 0.3 + i * 0.06, 7]} />
            <meshStandardMaterial
              color={i % 2 ? "#bca27b" : C.clay}
              flatShading
            />
          </mesh>
        ))}
    </group>
  );
}

function Hotspots({
  onHotspot,
  activeHotspot,
  readChapters = [],
  river = false,
  lake = false,
  playful = false,
  visible = true,
}: Pick<WorldSceneProps, "onHotspot" | "activeHotspot" | "readChapters"> & {
  river?: boolean;
  lake?: boolean;
  playful?: boolean;
  visible?: boolean;
}) {
  const projected = useMemo(() => new THREE.Vector3(), []);
  const spots = [
    {
      id: "culture",
      label: "Budaya",
      Icon: HomeIcon,
      position: [-0.4, 3.5, -1.3],
    },
    {
      id: "weaving",
      label: "Tradisi Tenun",
      Icon: LeafIcon,
      position: [-2.8, 2, 1.5],
    },
    {
      id: "textiles",
      label: "Kain Daerah",
      Icon: LayersIcon,
      position: (river || lake ? [4.4, 2.4, 2.8] : [2.5, 2.4, 2.2]) as Point,
    },
  ] as const;
  return (
    <group>
      {spots.map((spot, index) => (
        <Html
          key={spot.id}
          center
          position={[...spot.position]}
          calculatePosition={(object, camera, size) => {
            projected.setFromMatrixPosition(object.matrixWorld).project(camera);
            let x = ((projected.x + 1) * size.width) / 2;
            let y = ((1 - projected.y) * size.height) / 2;
            if (size.width <= 900) {
              if (spot.id === "culture") y -= 18;
              if (spot.id === "weaving") {
                x -= 12;
                y += 4;
              }
              if (spot.id === "textiles") {
                x += 14;
                y += 16;
              }
              const half = size.width <= 360 ? 68.5 : 77.5;
              x = THREE.MathUtils.clamp(x, half + 10, size.width - half - 10);
            }
            return [x, y];
          }}
          zIndexRange={[40, 36]}
          style={{ pointerEvents: "none" }}
        >
          <MapButton
            className={`nx-hotspot nx-location-card ${readChapters.includes(spot.id) ? "is-read" : "is-unread"}`}
            aria-hidden={!visible}
            tabIndex={visible ? 0 : -1}
            data-visible={visible}
            data-chapter={spot.id}
            type="button"
            aria-label={`Jelajahi ${spot.label.toLowerCase()}`}
            aria-describedby={`nx-location-progress-${spot.id}`}
            onClick={(event) => {
              event.stopPropagation();
              onHotspot(spot.id);
            }}
            style={
              {
                pointerEvents: visible ? "auto" : "none",
                "--hotspot-delay": `${400 + index * 120}ms`,
              } as CSSProperties
            }
          >
            <span className="nx-location-icon" aria-hidden="true">
              <spot.Icon size={26} strokeWidth={1.7} />
            </span>
            <span className="nx-location-copy">
              <strong>{spot.label}</strong>
              <span
                className="nx-location-progress"
                id={`nx-location-progress-${spot.id}`}
              >
                <i
                  style={{
                    width: readChapters.includes(spot.id) ? "100%" : "0%",
                  }}
                />
                <b>
                  {playful
                    ? readChapters.includes(spot.id)
                      ? "Sudah dibaca"
                      : "Mulai cerita"
                    : `${readChapters.includes(spot.id) ? "100" : "0"}% dijelajahi`}
                </b>
              </span>
            </span>
            <span className="nx-location-status" aria-hidden="true">
              {readChapters.includes(spot.id) ? <CheckIcon size={15} /> : "!"}
            </span>
          </MapButton>
          <div
            aria-hidden="true"
            style={{
              width: 1,
              height: 18,
              margin: "3px auto 0",
              background: visible ? "rgba(255,249,233,.8)" : "transparent",
            }}
          />
        </Html>
      ))}
    </group>
  );
}

function LandscapeWorld({
  region,
  lowGraphics,
  onHotspot,
  activeHotspot,
  presentation,
  panelOpen,
  readChapters,
  dashboardOpen,
}: { region: ExploreRegion } & Pick<
  WorldSceneProps,
  | "lowGraphics"
  | "onHotspot"
  | "activeHotspot"
  | "presentation"
  | "panelOpen"
  | "readChapters"
  | "dashboardOpen"
>) {
  const { landscape } = region;
  const savanna = landscape === "savanna";
  const lake = region.id === "sumatera-utara";
  const river = region.id === "sumatera-selatan";
  const trees = useMemo(
    () =>
      Array.from({ length: lowGraphics ? 12 : 25 }, (_, i) => {
        const angle = 0.15 + noise(i, 7) * Math.PI * 2;
        const x = Math.cos(angle) * (4.2 + noise(i, 3));
        const z = Math.sin(angle) * 3.3;
        return {
          position: [x, 0.9, z] as Point,
          scale: (savanna ? 0.55 : 0.72) + noise(i, 8) * 0.45,
          rotation: noise(i, 2) * 6.28,
        };
      }).filter(
        ({ position: [x, , z] }) =>
          isRegionalGround(region.id, x, z, 0.45) &&
          !(z > 2.2 && Math.abs(x) < 3.8) &&
          (!river || x < 0 || z < -2.8),
      ),
    [region.id, river, lowGraphics, savanna],
  );
  return (
    <>
      <RegionalLand id={region.id} />
      {!["bali", "jawa-tengah", "sumatera-selatan"].includes(region.id) && (
        <Hills landscape={landscape} />
      )}
      {river && <River />}
      {lake && (
        <>
          <Forest
            trees={[
              { position: [1.35, 0.92, 1.55], scale: 0.44, rotation: 0.3 },
              { position: [1.8, 0.92, 1.85], scale: 0.34, rotation: 1.1 },
            ]}
          />
          <Boat position={[2.8, 0.83, 2.25]} scale={0.33} rotation={-0.6} />
          {[0, 1, 2].map((i) => (
            <mesh
              key={i}
              position={[0.5 + i * 0.85, 0.815, 2.8 + i * 0.04]}
              rotation={[-Math.PI / 2, 0, 0.2]}
              scale={[1, 0.4, 1]}
            >
              <ringGeometry args={[0.16, 0.175, 16, 1, 0, Math.PI]} />
              <meshBasicMaterial
                color="#d8f3e9"
                transparent
                opacity={0.65}
                side={THREE.DoubleSide}
              />
            </mesh>
          ))}
        </>
      )}
      <Forest trees={trees} dry={savanna} />
      <group position={[0, 0.9, 0]}>
        <RegionalArchitecture id={region.id} lowGraphics={lowGraphics} />
      </group>
      <LandscapeGarden id={region.id} lowGraphics={lowGraphics} />
      {savanna && (
        <>
          <GrazingHorse position={[-3.6, 0.94, 2.6]} scale={0.72} />
          {!lowGraphics && (
            <GrazingHorse
              position={[-4.3, 0.94, 0.15]}
              scale={0.6}
              coat="#f1dfb9"
            />
          )}
        </>
      )}
      <Loom position={[-2.15, 0.9, 1.5]} />
      <Cloth
        position={river || lake ? [4, 0.9, 2.7] : [2.2, 0.9, 2]}
        rotation={-0.2}
        color={region.color}
      />
      <Cloth
        position={river || lake ? [4.9, 0.9, 2.7] : [3.5, 0.9, 2.6]}
        rotation={-0.35}
        color="#405d62"
      />
      <VillageDetails
        regionId={region.id}
        lowGraphics={lowGraphics}
        savanna={savanna}
        river={river}
      />
      {!river && (
        <Boat position={[6.6, -0.48, 1.8]} scale={0.5} rotation={0.5} sail />
      )}
      {!dashboardOpen && (presentation !== "explore" || !panelOpen) && (
        <Hotspots
          visible={presentation !== "preview"}
          onHotspot={onHotspot}
          activeHotspot={activeHotspot}
          river={river}
          lake={lake}
          playful
          readChapters={readChapters}
        />
      )}
    </>
  );
}

function CameraRig({
  mode,
  regionId,
  zoom,
  reset,
  reducedMotion,
  activeHotspot,
  selectedRegion,
  departing,
  paused,
  presentation,
  panelOpen,
  dashboardOpen,
}: Pick<
  WorldSceneProps,
  | "mode"
  | "regionId"
  | "zoom"
  | "reset"
  | "reducedMotion"
  | "activeHotspot"
  | "selectedRegion"
  | "departing"
  | "paused"
  | "presentation"
  | "panelOpen"
  | "dashboardOpen"
>) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, size, invalidate } = useThree();
  const requestedZoom = useRef(1);
  const home = useRef(new THREE.Vector3());
  const framing = useRef({ x: 0, y: 0 });
  const flight = useMemo(
    () => ({
      started: 0,
      position: new THREE.Vector3(),
      target: new THREE.Vector3(),
      zoom: 1,
    }),
    [],
  );
  const pose = useMemo(
    () => ({ position: new THREE.Vector3(), target: new THREE.Vector3() }),
    [],
  );
  const transitioning = useRef(true);
  const initialized = useRef(false);
  const interacting = useRef(false);
  const lastInput = useRef(0);
  useEffect(() => {
    const touch = () => {
      lastInput.current = performance.now();
    };
    touch();
    window.addEventListener("pointermove", touch, { passive: true });
    window.addEventListener("keydown", touch);
    return () => {
      window.removeEventListener("pointermove", touch);
      window.removeEventListener("keydown", touch);
    };
  }, []);
  const motion = useWorldMotion();
  const mobile = size.width <= 900;
  useLayoutEffect(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const map = mode === "map";
    // Reproduce the safe preview/story area inside a full-screen canvas. Changing
    // views must never resize the WebGL renderer or reset its projection mid-flight.
    const top = map
      ? 0
      : mobile
        ? presentation === "preview"
          ? 92
          : panelOpen
            ? 68
            : 90
        : presentation === "preview"
          ? 63
          : 76;
    const bottom = map
      ? 0
      : mobile
        ? presentation === "preview"
          ? 285
          : panelOpen
            ? size.height * (presentation === "intro" ? 0.28 : 0.46)
            : 115
        : presentation === "preview"
          ? size.height <= 760
            ? 230
            : 255
          : 76;
    const viewHeight = Math.max(180, size.height - top - bottom);
    const panel =
      !map && !mobile && panelOpen && !dashboardOpen
        ? presentation === "intro"
          ? Math.min(400, size.width * 0.34)
          : Math.min(500, size.width * 0.38)
        : 0;
    const visibleWidth = map
      ? Math.max(52, (28 * size.width) / Math.max(size.height, 1))
      : ((dashboardOpen
          ? 19.5
          : presentation === "preview"
            ? Math.max(
                mobile ? 17.4 : regionId === "bali" ? 20.7 : 19.3,
                (10 * size.width) / viewHeight,
              )
            : mobile
              ? 16.4
              : Math.max(
                  presentation === "intro" ? 16.4 : 16.8,
                  (9 * (size.width - panel)) / viewHeight,
                )) *
          size.width) /
        Math.max(size.width - panel, 1);
    const baseZoom = size.width / visibleWidth;
    // zoom is a multiplicative HUD value: 1 is home; invalid inputs use home.
    const zoomFactor = Number.isFinite(zoom)
      ? THREE.MathUtils.clamp(zoom, 0.65, 2.8)
      : 1;
    requestedZoom.current = baseZoom * zoomFactor;
    framing.current = {
      x: panel / (2 * baseZoom),
      y: (top - bottom) / (2 * baseZoom),
    };
    home.current.set(
      0,
      map ? 0 : presentation === "preview" ? 1.45 : 1.15,
      map ? -1.1 : presentation === "preview" ? 0.45 : 0.2,
    );
    camera.left = -size.width / 2;
    camera.right = size.width / 2;
    camera.top = size.height / 2;
    camera.bottom = -size.height / 2;
    camera.near = 0.1;
    camera.far = 550;
    camera.updateProjectionMatrix();
    invalidate();
  }, [
    camera,
    size.width,
    size.height,
    mode,
    mobile,
    zoom,
    invalidate,
    presentation,
    panelOpen,
    dashboardOpen,
    regionId,
  ]);

  useLayoutEffect(() => {
    const map = mode === "map";
    pose.target.copy(home.current);
    if (map) {
      const region = findExploreRegion(selectedRegion);
      if (region) {
        const [x, z] = project(...region.coordinates);
        pose.target.x += x * (departing ? 0.65 : 0.045);
        pose.target.z += z * (departing ? 0.65 : 0.045);
      }
    } else if (panelOpen && presentation === "explore" && !dashboardOpen) {
      const focus =
        activeHotspot === "weaving"
          ? [-2.2, 1.5]
          : activeHotspot === "textiles"
            ? regionId === "sumatera-utara" || regionId === "sumatera-selatan"
              ? [4.4, 2.8]
              : [2.5, 2.2]
            : [0, -1.3];
      pose.target.x += focus[0] * 0.65;
      pose.target.z += focus[1] * 0.5;
      pose.target.y += activeHotspot === "culture" ? 0.75 : 0.25;
    }
    const orbit = map
      ? [0, 38, 30]
      : presentation === "intro" || presentation === "preview"
        ? [9, 17, 28]
        : activeHotspot === "weaving"
          ? [8, 18, 25]
          : activeHotspot === "textiles"
            ? [12, 18, 23]
            : [10, 19, 24];
    const forward = new THREE.Vector3(...orbit).normalize();
    const right = new THREE.Vector3(forward.z, 0, -forward.x).normalize();
    const up = new THREE.Vector3().crossVectors(forward, right).normalize();
    pose.target
      .addScaledVector(right, framing.current.x)
      .addScaledVector(up, framing.current.y);
    pose.position.set(
      pose.target.x + orbit[0],
      pose.target.y + orbit[1],
      pose.target.z + orbit[2],
    );
    if (!initialized.current) {
      camera.position.set(
        pose.position.x + (map ? 0 : 2),
        pose.position.y + 5,
        pose.position.z + 4,
      );
      camera.lookAt(pose.target);
      controls.current?.target.copy(pose.target);
      if (camera instanceof THREE.OrthographicCamera) {
        camera.zoom = requestedZoom.current * (reducedMotion ? 1 : 0.86);
        camera.updateProjectionMatrix();
      }
      initialized.current = true;
    }
    flight.started = performance.now();
    flight.position.copy(camera.position);
    flight.target.copy(controls.current?.target ?? pose.target);
    flight.zoom = camera instanceof THREE.OrthographicCamera ? camera.zoom : 1;
    interacting.current = false;
    transitioning.current = true;
    invalidate();
  }, [
    camera,
    mode,
    regionId,
    reset,
    mobile,
    size.width,
    size.height,
    invalidate,
    activeHotspot,
    selectedRegion,
    departing,
    reducedMotion,
    pose,
    presentation,
    panelOpen,
    dashboardOpen,
    zoom,
    flight,
  ]);

  useFrame((_, delta) => {
    const orbit = controls.current;
    if (!orbit) return;
    const targetZoom =
      requestedZoom.current *
      (dashboardOpen
        ? mobile
          ? 0.94
          : 0.78
        : departing
          ? 1.9
          : mode === "region" && panelOpen && presentation === "explore"
            ? mobile
              ? 1.14
              : 1.45
            : presentation === "intro" && !mobile
              ? 1.12
              : 1);
    if (transitioning.current && !interacting.current) {
      const progress =
        reducedMotion || paused
          ? 1
          : Math.min(1, (performance.now() - flight.started) / 1600);
      const eased = 1 - Math.pow(1 - progress, 4);
      camera.position.lerpVectors(flight.position, pose.position, eased);
      orbit.target.lerpVectors(flight.target, pose.target, eased);
      if (camera instanceof THREE.OrthographicCamera) {
        camera.zoom = THREE.MathUtils.lerp(flight.zoom, targetZoom, eased);
        camera.updateProjectionMatrix();
      }
      orbit.update();
      if (progress === 1) transitioning.current = false;
    }
    if (
      !transitioning.current &&
      camera instanceof THREE.OrthographicCamera &&
      Math.abs(camera.zoom - targetZoom) > 0.001
    ) {
      camera.zoom =
        reducedMotion || paused
          ? targetZoom
          : THREE.MathUtils.damp(
              camera.zoom,
              targetZoom,
              8,
              Math.min(delta, 0.05),
            );
      camera.updateProjectionMatrix();
    }
    orbit.autoRotate =
      !transitioning.current &&
      !interacting.current &&
      !paused &&
      !dashboardOpen &&
      !panelOpen &&
      !reducedMotion &&
      performance.now() - lastInput.current > 5000;
    orbit.autoRotateSpeed = Math.sin(motion.current.time * 0.12) * 0.16;
    if (transitioning.current || departing) return;
    const max = mode === "map" ? 7 : 1.4;
    const x = THREE.MathUtils.clamp(
      orbit.target.x,
      pose.target.x - max,
      pose.target.x + max,
    );
    const z = THREE.MathUtils.clamp(
      orbit.target.z,
      pose.target.z - max * 0.5,
      pose.target.z + max * 0.5,
    );
    camera.position.x += x - orbit.target.x;
    camera.position.z += z - orbit.target.z;
    camera.position.y += pose.target.y - orbit.target.y;
    orbit.target.set(x, pose.target.y, z);
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping={!reducedMotion && !paused}
      dampingFactor={0.09}
      enablePan
      screenSpacePanning={false}
      panSpeed={0.55}
      rotateSpeed={0.4}
      enableZoom={false}
      onStart={() => {
        interacting.current = true;
        transitioning.current = false;
      }}
      onEnd={() => {
        interacting.current = false;
      }}
      minPolarAngle={0.35}
      maxPolarAngle={Math.PI / 2.65}
      minAzimuthAngle={mode === "map" ? -0.22 : 0.05}
      maxAzimuthAngle={mode === "map" ? 0.22 : 0.75}
      mouseButtons={{
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.PAN,
        RIGHT: THREE.MOUSE.PAN,
      }}
      touches={{ ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.PAN }}
    />
  );
}

function Ready({ onReady }: Pick<WorldSceneProps, "onReady">) {
  const callback = useRef(onReady);
  const frames = useRef(0);
  const done = useRef(false);
  useEffect(() => {
    callback.current = onReady;
  }, [onReady]);
  useFrame(() => {
    if (!done.current && ++frames.current >= 2) {
      done.current = true;
      callback.current();
    }
  });
  return null;
}

function SceneLighting({
  timeOfDay,
  reducedMotion,
  lowGraphics,
  mode,
  paused,
}: Pick<
  WorldSceneProps,
  "timeOfDay" | "reducedMotion" | "lowGraphics" | "mode" | "paused"
>) {
  const sun = useRef<THREE.DirectionalLight>(null),
    ambient = useRef<THREE.AmbientLight>(null);
  const colors = useMemo(
    () => ({
      day: new THREE.Color("#fff1ce"),
      sunset: new THREE.Color("#ffb36e"),
    }),
    [],
  );
  const target = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, delta) => {
    if (!sun.current || !ambient.current) return;
    const evening = timeOfDay === "sunset",
      alpha =
        reducedMotion || paused ? 1 : 1 - Math.exp(-Math.min(delta, 0.05) * 2);
    sun.current.color.lerp(evening ? colors.sunset : colors.day, alpha);
    target.set(...((evening ? [-18, 11, 7] : [-12, 24, 12]) as Point));
    sun.current.position.lerp(target, alpha);
    ambient.current.intensity = THREE.MathUtils.lerp(
      ambient.current.intensity,
      evening ? 0.4 : 0.6,
      alpha,
    );
  });
  return (
    <>
      <ambientLight ref={ambient} intensity={0.6} />
      <hemisphereLight args={["#ffeaca", "#687d47", 1.15]} />
      <directionalLight position={[9, 6, -5]} intensity={0.6} color="#bde4df" />
      <directionalLight
        ref={sun}
        position={[-12, 24, 12]}
        color="#fff1ce"
        intensity={3.1}
        castShadow={!lowGraphics}
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={mode === "map" ? -27 : -10}
        shadow-camera-right={mode === "map" ? 27 : 10}
        shadow-camera-top={mode === "map" ? 24 : 10}
        shadow-camera-bottom={mode === "map" ? -24 : -10}
        shadow-camera-far={85}
        shadow-normalBias={0.04}
        shadow-bias={-0.0002}
      />
    </>
  );
}

/** A stable, soft contact shadow travels with each island instead of being
 * recomputed on an overlapping shadow-receiving plane during scene swaps. */
function IslandShadow() {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const context = canvas.getContext("2d");
    if (!context) return null;
    const gradient = context.createRadialGradient(128, 128, 20, 128, 128, 125);
    gradient.addColorStop(0, "rgba(24, 76, 78, 0.36)");
    gradient.addColorStop(0.48, "rgba(24, 76, 78, 0.25)");
    gradient.addColorStop(1, "rgba(24, 76, 78, 0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 256);
    const result = new THREE.CanvasTexture(canvas);
    result.colorSpace = THREE.SRGBColorSpace;
    return result;
  }, []);
  useEffect(() => () => texture?.dispose(), [texture]);
  if (!texture) return null;
  return (
    <mesh position={[0.5, -1.04, 0.65]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[18, 13]} />
      <meshBasicMaterial
        map={texture}
        transparent
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

function SlidingRegion({
  region,
  incoming,
  transition,
  onSlideReady,
  slideClock,
  ...props
}: WorldSceneProps & {
  region: ExploreRegion;
  incoming: boolean;
  slideClock: RefObject<{ sequence: number; startedAt: number }>;
}) {
  const ref = useRef<THREE.Group>(null);
  const { gl, scene, camera, size } = useThree();
  const completionRequested = useRef(false);
  const presentationRequested = useRef(false);
  useEffect(() => {
    completionRequested.current = false;
    presentationRequested.current = false;
  }, [transition.sequence]);
  useLayoutEffect(() => {
    if (!ref.current) return;
    if (incoming && transition.phase === "preparing") {
      ref.current.position.x = transition.direction * 22;
      ref.current.visible = false;
    } else {
      ref.current.visible = true;
    }
  }, [incoming, transition.phase, transition.direction]);
  useEffect(() => {
    const group = ref.current;
    if (
      !incoming ||
      transition.kind !== "slide" ||
      transition.phase !== "preparing" ||
      !group
    )
      return;
    let cancelled = false;
    let frame = 0;
    const prepare = async () => {
      try {
        await gl.compileAsync(group, camera, scene);
        if (cancelled) return;
        const source = scene.getObjectByName(
          `region-diorama-${props.regionId}`,
        );
        if (!source) throw new Error("Source diorama unavailable");
        const scale = Math.min(1, 1440 / Math.max(size.width, 1));
        const width = Math.max(1, Math.round(size.width * scale));
        const height = Math.max(1, Math.round(size.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("Snapshot canvas unavailable");
        const previousTarget = gl.getRenderTarget();
        const sourceVisible = source.visible;
        const incomingVisible = group.visible;
        const incomingX = group.position.x;
        const capture = () => {
          gl.render(scene, camera);
          // Capture the actual display buffer: render targets use linear colour
          // and do not apply the same output transform as the visible canvas.
          ctx.clearRect(0, 0, width, height);
          ctx.drawImage(gl.domElement, 0, 0, width, height);
          return canvas.toDataURL("image/png");
        };
        let from: string, to: string;
        try {
          gl.setRenderTarget(null);
          group.visible = false;
          from = capture();
          source.visible = false;
          group.visible = true;
          group.position.x = 0;
          group.updateMatrixWorld(true);
          to = capture();
        } finally {
          source.visible = sourceVisible;
          group.visible = incomingVisible;
          group.position.x = incomingX;
          group.updateMatrixWorld(true);
          // Both captures happen in one task; restore the visible frame before
          // the browser can paint the prepared destination.
          gl.render(scene, camera);
          gl.setRenderTarget(previousTarget);
        }
        await Promise.all(
          [from, to].map(async (src) => {
            const image = new Image();
            image.src = src;
            await image.decode();
          }),
        );
        if (!cancelled)
          props.onSlidePrepared(region.id, transition.sequence, { from, to });
        return;
      } catch {
        // Navigation remains available if a device cannot precompile the scene.
      }
      if (!cancelled)
        frame = requestAnimationFrame(() => {
          frame = requestAnimationFrame(() => onSlideReady(region.id));
        });
    };
    void prepare();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [
    incoming,
    transition.kind,
    transition.phase,
    transition.direction,
    region.id,
    onSlideReady,
    gl,
    scene,
    camera,
    size.width,
    size.height,
    props.regionId,
    props.onSlidePrepared,
    transition.sequence,
  ]);
  useFrame(() => {
    if (!ref.current) return;
    if (
      !incoming &&
      props.snapshotTransition &&
      transition.kind === "slide" &&
      transition.phase === "in" &&
      !presentationRequested.current
    ) {
      presentationRequested.current = true;
      const sequence = transition.sequence;
      requestAnimationFrame(() => props.onSlidePresented(sequence));
    }
    if (
      transition.kind !== "slide" ||
      transition.phase === "idle" ||
      transition.phase === "in"
    ) {
      ref.current.position.x = 0;
      return;
    }
    if (slideClock.current.sequence !== transition.sequence) {
      slideClock.current.sequence = transition.sequence;
      slideClock.current.startedAt = 0;
    }
    if (transition.phase === "out" && !slideClock.current.startedAt)
      slideClock.current.startedAt = performance.now();
    const progress =
      transition.phase === "out" && slideClock.current.startedAt
        ? Math.min(
            1,
            Math.max(
              0,
              (performance.now() - slideClock.current.startedAt) /
                SLIDE_CLOSE_MS,
            ),
          )
        : 0;
    const eased = progress * progress * (3 - 2 * progress);
    ref.current.position.x =
      transition.direction * 22 * (incoming ? 1 - eased : -eased);
    if (
      incoming &&
      transition.phase === "out" &&
      progress >= 1 &&
      !completionRequested.current
    ) {
      completionRequested.current = true;
      const sequence = transition.sequence;
      requestAnimationFrame(() => props.onSlideComplete(sequence));
    }
  });
  return (
    <group ref={ref} name={`region-diorama-${region.id}`}>
      <LandscapeWorld
        region={region}
        lowGraphics={props.lowGraphics}
        onHotspot={props.onHotspot}
        activeHotspot={props.activeHotspot}
        presentation={props.presentation}
        panelOpen={props.panelOpen}
        readChapters={incoming ? [] : props.readChapters}
        dashboardOpen={props.dashboardOpen}
      />
      <LivingWorld
        map={false}
        lowGraphics={props.lowGraphics}
        onDiscover={props.onDiscover}
        savanna={region.landscape === "savanna"}
        greeting={props.greeting}
        regionId={region.id}
      />
      <IslandShadow />
    </group>
  );
}

function World({
  data,
  ...props
}: WorldSceneProps & { data: GeoDocument | null }) {
  const slideClock = useRef({ sequence: -1, startedAt: 0 });
  if (props.mode === "map" && props.atlas2d)
    return <AtlasGpuWorld {...props} />;
  const region =
    findExploreRegion(props.regionId ?? props.selectedRegion) ??
    exploreRegions[0];
  const ready = props.mode === "region" || data !== null;
  const nextRegion =
    props.transition.kind === "slide" &&
    ["preparing", "out"].includes(props.transition.phase)
      ? findExploreRegion(props.transition.destination ?? "")
      : undefined;
  return (
    <>
      {props.mode === "map" ? (
        <AtlasLighting
          evening={props.timeOfDay === "sunset"}
          lowGraphics={props.lowGraphics}
          ready={ready}
        />
      ) : (
        <SceneLighting
          timeOfDay={props.timeOfDay}
          reducedMotion={props.reducedMotion}
          lowGraphics={props.lowGraphics}
          mode={props.mode}
          paused={props.paused}
        />
      )}
      {props.mode === "map" ? (
        <Ocean
          timeOfDay={props.timeOfDay}
          reducedMotion={props.reducedMotion}
          paused={props.paused}
        />
      ) : null}
      {props.mode === "map" ? (
        <AtlasCamera
          zoom={props.zoom}
          reset={props.reset}
          reducedMotion={props.reducedMotion}
          onZoomChange={props.onZoomChange}
        />
      ) : (
        <CameraRig
          mode={props.mode}
          regionId={region.id}
          zoom={props.zoom}
          reset={props.reset}
          reducedMotion={props.reducedMotion}
          paused={props.paused}
          activeHotspot={props.activeHotspot}
          selectedRegion={props.selectedRegion}
          departing={props.departing}
          presentation={props.presentation}
          panelOpen={props.panelOpen}
          dashboardOpen={props.dashboardOpen}
        />
      )}
      <Suspense fallback={null}>
        <WorldTransitionStage
          transition={props.transition}
          instant={
            props.reducedMotion ||
            props.paused ||
            props.transition.kind === "slide"
          }
        >
          {props.mode === "map" && data && (
            <MapWorld
              data={data}
              lowGraphics={props.lowGraphics}
              selectedRegion={props.selectedRegion}
              onSelectRegion={props.onSelectRegion}
              onHoverRegion={props.onHoverRegion}
            />
          )}
          {props.mode === "region" &&
            [
              region,
              ...(nextRegion && nextRegion.id !== region.id
                ? [nextRegion]
                : []),
            ].map((item) => (
              <SlidingRegion
                key={item.id}
                {...props}
                region={item}
                incoming={item.id !== region.id}
                slideClock={slideClock}
              />
            ))}
          {props.mode === "map" && data && (
            <LivingWorld
              map
              lowGraphics={props.lowGraphics}
              onDiscover={props.onDiscover}
            />
          )}
          {ready && props.mode === "map" && (
            <AtlasClouds lowGraphics={props.lowGraphics} />
          )}
          {ready && props.mode === "region" && (
            <Clouds
              map={false}
              lowGraphics={props.lowGraphics}
              reducedMotion={props.reducedMotion}
            />
          )}
        </WorldTransitionStage>
        {ready && (
          <Ready
            key={`${props.mode}-${props.mode === "region" ? region.id : "indonesia"}`}
            onReady={props.onReady}
          />
        )}
      </Suspense>
    </>
  );
}

function CanvasDescription({
  mode,
  regionId,
  illustrated,
}: {
  mode: "map" | "region";
  regionId?: string;
  illustrated: boolean;
}) {
  const { gl } = useThree();
  useEffect(() => {
    gl.domElement.setAttribute(
      "aria-label",
      mode === "map"
        ? illustrated
          ? "Peta interaktif Indonesia. Seret untuk menjelajah, scroll atau cubit dua jari untuk memperbesar. Gunakan tombol panah untuk bergeser dan Home untuk mengatur ulang."
          : "Atlas 3D Indonesia. Seret untuk memutar dan pilih penanda daerah."
        : `Diorama 3D ${findExploreRegion(regionId ?? "")?.name ?? "daerah"}. Seret untuk melihat dari sudut lain dan pilih penanda cerita.`,
    );
  }, [gl, mode, regionId, illustrated]);
  return null;
}

/** Parent provides a sized container, loading UI, WebGL/error boundary and navigation. */
export default function WorldScene(props: WorldSceneProps) {
  const data = useGeography(props.mode === "map" && !props.atlas2d);
  const [contextLost, setContextLost] = useState(false);
  if (contextLost) throw new Error("The exploration WebGL context was lost.");
  return (
    <Canvas
      orthographic
      frameloop={
        props.renderingSuspended
          ? "never"
          : props.snapshotTransition && props.transition.phase === "out"
            ? "demand"
            : "always"
      }
      shadows={!props.lowGraphics && !props.atlas2d}
      dpr={
        props.lowGraphics
          ? 1
          : props.mode === "map" && !props.atlas2d
            ? [1, 1.25]
            : [1, 1.5]
      }
      performance={{ min: 0.72, max: 1, debounce: 250 }}
      camera={{ position: [0, 38, 30], near: 0.1, far: 550, zoom: 18 }}
      onCreated={({ gl }) => {
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
        gl.toneMappingExposure = 1.05;
        gl.domElement.setAttribute(
          "aria-label",
          "Diorama interaktif Indonesia. Pilih penanda daerah atau cerita dengan tombol yang tersedia.",
        );
        gl.domElement.addEventListener(
          "webglcontextlost",
          () => setContextLost(true),
          { once: true },
        );
      }}
      gl={{
        antialias: !props.lowGraphics,
        alpha: true,
        powerPreference: props.lowGraphics ? "low-power" : "high-performance",
      }}
      style={{
        width: "100%",
        height: "100%",
        touchAction: "none",
        background: "transparent",
        isolation: "isolate",
      }}
      fallback={
        <div
          role="status"
          style={{ padding: 24, color: C.dark, background: "#e9efdf" }}
        >
          Tampilan 3D tidak tersedia. Silakan gunakan daftar daerah.
        </div>
      }
    >
      <AdaptiveDpr />
      <CanvasDescription
        mode={props.mode}
        regionId={props.regionId}
        illustrated={!!props.atlas2d}
      />
      <WorldMotion
        enabled={
          !props.paused &&
          !props.reducedMotion &&
          !(
            props.transition.kind === "slide" &&
            ["preparing", "out"].includes(props.transition.phase)
          )
        }
      >
        <World {...props} data={data} />
      </WorldMotion>
    </Canvas>
  );
}
