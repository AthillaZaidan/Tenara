"use client";
/* Shader textures/uniforms and refs are imperatively updated by the GPU render loop. */
/* eslint-disable react-hooks/exhaustive-deps, react-hooks/immutability, react-hooks/refs */

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";
import {
  atlasBoats,
  atlasClouds,
  atlasWaves,
  type AtlasManifest,
  type AtlasProp,
} from "./atlas-layout";
import { AtlasGpuCamera } from "./atlas-gpu-camera";
import { useWorldMotion } from "./world-motion";
import type { WorldSceneProps } from "./world-scene";

let manifestRequest: Promise<AtlasManifest> | undefined;
function loadManifest() {
  return (manifestRequest ??= fetch("/assets/exploration/atlas-manifest.json")
    .then(async (response) => {
      if (!response.ok)
        throw new Error("Illustrated atlas assets could not load.");
      const data = (await response.json()) as AtlasManifest;
      if (
        data.version !== 1 ||
        !data.layers?.high ||
        !data.sprites?.frames ||
        !data.landPath
      )
        throw new Error("Invalid atlas art manifest.");
      return data;
    })
    .catch((error) => {
      manifestRequest = undefined;
      throw error;
    }));
}

type Sprite = {
  frame: string;
  x: number;
  y: number;
  scale: number;
  flip?: boolean;
  kind: number;
  phase: number;
  depth: number;
};
function spriteGeometry(manifest: AtlasManifest, sprites: Sprite[]) {
  const positions: number[] = [],
    anchors: number[] = [],
    uvs: number[] = [],
    motions: number[] = [];
  for (const sprite of sprites) {
    const frame = manifest.sprites.frames[sprite.frame],
      [left, top, width, height] = frame.box;
    const corners = [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ];
    for (const index of [0, 3, 1, 1, 3, 2]) {
      const [u, v] = corners[index];
      positions.push(
        (left + u * width) * sprite.scale * (sprite.flip ? -1 : 1),
        -(top + v * height) * sprite.scale,
        0,
      );
      anchors.push(
        sprite.x - manifest.width / 2,
        manifest.height / 2 - sprite.y,
      );
      uvs.push(
        (frame.x + u * frame.w) / manifest.sprites.width,
        1 - (frame.y + v * frame.h) / manifest.sprites.height,
      );
      motions.push(sprite.kind, sprite.phase, sprite.depth);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  geometry.setAttribute("anchor", new THREE.Float32BufferAttribute(anchors, 2));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setAttribute("motion", new THREE.Float32BufferAttribute(motions, 3));
  return geometry;
}

const spriteVertex = `
  uniform float atlasTime;
  uniform vec2 viewCenter;
  attribute vec2 anchor;
  attribute vec3 motion;
  varying vec2 vUv;
  varying float vOpacity;
  void main() {
    vUv = uv;
    vOpacity = 1.;
    vec2 p = position.xy;
    vec2 offset = vec2(0.);
    float kind = motion.x, phase = motion.y;
    if (kind < .5) {
      offset = vec2(sin(atlasTime * .055 + phase) * 17., cos(atlasTime * .1 + phase) * 3.);
    } else if (kind < 1.5) {
      float angle = sin(atlasTime * .8 + phase) * .018;
      p = mat2(cos(angle), -sin(angle), sin(angle), cos(angle)) * p;
      offset = vec2(sin(atlasTime * .08 + phase) * 28., sin(atlasTime * 1.2 + phase) * 1.7);
    } else if (kind < 2.5) {
      offset.x = sin(atlasTime * .35 + phase) * 4.;
      vOpacity = .55 + sin(atlasTime * .65 + phase) * .25;
    } else if (kind < 3.5) {
      float angle = sin(atlasTime * 1.1 + phase) * .035;
      p = mat2(cos(angle), -sin(angle), sin(angle), cos(angle)) * p;
    } else {
      p.y *= .95 + sin(atlasTime * 4. + phase) * .12;
      offset = vec2(sin(atlasTime * .12 + phase * .2) * 35., cos(atlasTime * .2 + phase) * 7.);
    }
    vec2 parallax = clamp(viewCenter, vec2(-500., -200.), vec2(500., 200.)) * motion.z;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(anchor + p + offset + parallax, 0., 1.);
  }
`;
const spriteFragment = `
  uniform sampler2D atlasSprites;
  uniform float sunset;
  varying vec2 vUv;
  varying float vOpacity;
  void main() {
    vec4 color = texture2D(atlasSprites, vUv);
    if (color.a < .005) discard;
    color.rgb *= mix(vec3(1.), vec3(1., .86, .69), sunset * .6);
    gl_FragColor = vec4(color.rgb, color.a * vOpacity);
    #include <colorspace_fragment>
  }
`;

function Painting({
  manifest,
  ...props
}: WorldSceneProps & { manifest: AtlasManifest }) {
  const { camera, gl } = useThree();
  const lowArt = props.lowGraphics || gl.capabilities.maxTextureSize < 4800;
  const texturePath = lowArt ? manifest.layers.low : manifest.layers.high;
  const [land, sprites] = useLoader(THREE.TextureLoader, [
    texturePath,
    manifest.sprites.image,
  ]);
  const motion = useWorldMotion();
  const groundMaterial = useRef<THREE.MeshBasicMaterial>(null),
    ready = useRef(false),
    frames = useRef(0);
  const callback = useRef(props.onReady);
  callback.current = props.onReady;
  useMemo(() => {
    for (const texture of [land, sprites]) {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = Math.min(4, gl.capabilities.getMaxAnisotropy());
    }
  }, [land, sprites, gl]);
  const uniforms = useMemo(
    () => ({
      atlasTime: { value: 0 },
      atlasSprites: { value: sprites },
      viewCenter: { value: new THREE.Vector2() },
      sunset: { value: props.timeOfDay === "sunset" ? 1 : 0 },
    }),
    [sprites],
  );
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms,
        vertexShader: spriteVertex,
        fragmentShader: spriteFragment,
        transparent: true,
        depthWrite: false,
        depthTest: false,
        side: THREE.DoubleSide,
        toneMapped: false,
      }),
    [uniforms],
  );
  const batches = useMemo(() => {
    const sea: Sprite[] = atlasBoats.map(([x, y, scale], i) => ({
      frame: "boat",
      x,
      y,
      scale,
      kind: 1,
      phase: i * 2.1,
      depth: 0,
    }));
    atlasWaves.slice(0, lowArt ? 4 : undefined).forEach(([x, y], i) =>
      sea.push({
        frame: "wave",
        x,
        y,
        scale: 1,
        kind: 2,
        phase: i * 1.7,
        depth: 0,
      }),
    );
    for (let i = 0; i < (lowArt ? 3 : 5); i++)
      sea.push({
        frame: "bird",
        x: 550 + i * 17,
        y: 140 - (i % 3) * 12,
        scale: 1,
        kind: 4,
        phase: i * 0.8,
        depth: 0.02,
      });
    const palms: AtlasProp[] = lowArt
      ? manifest.palms.low
      : manifest.palms.high;
    const fronds: Sprite[] = palms.map((p, i) => ({
      frame: "frond",
      x: p.x + 3 * p.scale * (p.flip ? -1 : 1),
      y: p.y - 43 * p.scale,
      scale: p.scale,
      flip: p.flip,
      kind: 3,
      phase: i * 0.73,
      depth: 0,
    }));
    const clouds: Sprite[] = atlasClouds
      .slice(0, lowArt ? 3 : undefined)
      .map(([x, y, scale], i) => ({
        frame: "cloud",
        x,
        y,
        scale,
        kind: 0,
        phase: i * 1.2,
        depth: 0.055,
      }));
    return [sea, fronds, clouds].map((batch) =>
      spriteGeometry(manifest, batch),
    );
  }, [manifest, lowArt]);
  useEffect(
    () => () => {
      batches.forEach((geometry) => geometry.dispose());
    },
    [batches],
  );
  useEffect(() => () => material.dispose(), [material]);
  const tint = useMemo(() => new THREE.Color(), []);
  useFrame((_, delta) => {
    uniforms.atlasTime.value = motion.current.time;
    uniforms.viewCenter.value.set(camera.position.x, camera.position.y);
    uniforms.sunset.value =
      props.reducedMotion || props.paused
        ? Number(props.timeOfDay === "sunset")
        : THREE.MathUtils.damp(
            uniforms.sunset.value,
            Number(props.timeOfDay === "sunset"),
            5,
            Math.min(delta, 0.04),
          );
    if (groundMaterial.current)
      groundMaterial.current.color.copy(
        tint.setRGB(
          1,
          1 - uniforms.sunset.value * 0.084,
          1 - uniforms.sunset.value * 0.186,
        ),
      );
    if (!ready.current && ++frames.current > 1) {
      ready.current = true;
      callback.current();
    }
  });
  return (
    <>
      {props.atlas2d && (
        <AtlasGpuCamera
          bridge={props.atlas2d}
          zoom={props.zoom}
          reset={props.reset}
          paused={props.paused}
          reducedMotion={props.reducedMotion}
          landPath={manifest.landPath}
          onZoomChange={props.onZoomChange}
          onSelectRegion={props.onSelectRegion}
        />
      )}
      <mesh
        geometry={batches[0]}
        material={material}
        frustumCulled={false}
        renderOrder={1}
        name="atlas-illustrated-sea-life"
      />
      <mesh renderOrder={2} name="atlas-illustrated-land">
        <planeGeometry args={[manifest.width, manifest.height]} />
        <meshBasicMaterial
          ref={groundMaterial}
          map={land}
          transparent
          depthWrite={false}
          depthTest={false}
          toneMapped={false}
        />
      </mesh>
      <mesh
        geometry={batches[1]}
        material={material}
        frustumCulled={false}
        renderOrder={3}
        name="atlas-illustrated-palms"
      />
      <mesh
        geometry={batches[2]}
        material={material}
        frustumCulled={false}
        renderOrder={4}
        name="atlas-illustrated-clouds"
      />
    </>
  );
}

export function AtlasGpuWorld(props: WorldSceneProps) {
  const [manifest, setManifest] = useState<AtlasManifest | null>(null),
    [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    let active = true;
    loadManifest()
      .then((data) => {
        if (active) setManifest(data);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason
              : new Error("Atlas art unavailable"),
          );
      });
    return () => {
      active = false;
    };
  }, []);
  if (error) throw error;
  return manifest ? (
    <Suspense fallback={null}>
      <Painting {...props} manifest={manifest} />
    </Suspense>
  ) : null;
}
