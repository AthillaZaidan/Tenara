"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { useWorldMotion } from "./world-motion";
import type { RegionId } from "@/lib/exploration";
import { isRegionalGround } from "./regional-terrain";

type V3 = [number, number, number];
const P = {
  wood: "#9b502c",
  timber: "#653b27",
  gold: "#eeb039",
  straw: "#cc8440",
  cream: "#ffe6ac",
  red: "#ad3829",
  clay: "#cc623c",
  stone: "#9e8b72",
  lightStone: "#c8b190",
  darkStone: "#746b60",
  leaf: "#729a29",
  leafLight: "#9eb72f",
  leafDark: "#427433",
};

/** Bake hundreds of small architectural pieces into a few color batches. */
class Model {
  pieces = new Map<string, THREE.BufferGeometry[]>();
  transform = new THREE.Matrix4();
  add(
    geometry: THREE.BufferGeometry,
    color: string,
    position: V3 = [0, 0, 0],
    scale: V3 = [1, 1, 1],
    rotation: V3 = [0, 0, 0],
  ) {
    const matrix = new THREE.Matrix4().compose(
      new THREE.Vector3(...position),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)),
      new THREE.Vector3(...scale),
    );
    const part = geometry.index ? geometry.toNonIndexed() : geometry;
    if (part !== geometry) geometry.dispose();
    part.deleteAttribute("uv");
    part.applyMatrix4(this.transform.clone().multiply(matrix));
    if (!part.getAttribute("normal")) part.computeVertexNormals();
    const list = this.pieces.get(color) ?? [];
    list.push(part);
    this.pieces.set(color, list);
  }
  at(position: V3, scale: number, rotation: number, build: () => void) {
    const old = this.transform.clone();
    this.transform.multiply(
      new THREE.Matrix4().compose(
        new THREE.Vector3(...position),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(0, rotation, 0)),
        new THREE.Vector3(scale, scale, scale),
      ),
    );
    build();
    this.transform.copy(old);
  }
  box(p: V3, s: V3, c: string, r: V3 = [0, 0, 0]) {
    this.add(new THREE.BoxGeometry(...s), c, p, [1, 1, 1], r);
  }
  cylinder(
    p: V3,
    top: number,
    bottom: number,
    height: number,
    c: string,
    segments = 8,
    r: V3 = [0, 0, 0],
  ) {
    this.add(
      new THREE.CylinderGeometry(top, bottom, height, segments),
      c,
      p,
      [1, 1, 1],
      r,
    );
  }
  rock(p: V3, s: V3, c: string, r: V3 = [0, 0, 0]) {
    this.add(new THREE.IcosahedronGeometry(1, 0), c, p, s, r);
  }
  rod(a: V3, b: V3, r: number, c: string) {
    const start = new THREE.Vector3(...a),
      end = new THREE.Vector3(...b),
      d = end.clone().sub(start);
    const g = new THREE.CylinderGeometry(r, r, d.length(), 5);
    g.applyQuaternion(
      new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        d.clone().normalize(),
      ),
    );
    this.add(g, c, start.add(end).multiplyScalar(0.5).toArray() as V3);
  }
  roof(p: V3, w: number, d: number, h: number, c: string, top = 0.1) {
    // A flared eave and steep upper surface give roofs a crafted silhouette.
    const rings = [
      [0, w, d],
      [h * 0.12, w * 0.86, d * 0.86],
      [h, w * top, d * top],
    ];
    const vertices: number[] = [];
    for (let n = 0; n < rings.length - 1; n++)
      for (let side = 0; side < 4; side++) {
        const corners = [
          [-1, -1],
          [1, -1],
          [1, 1],
          [-1, 1],
        ];
        const point = (ring: number, index: number) => {
          const [y, x, z] = rings[ring];
          const [sx, sz] = corners[index % 4];
          return [(sx * x) / 2, y, (sz * z) / 2];
        };
        const a = point(n, side),
          b = point(n, (side + 1) % 4),
          c1 = point(n + 1, side),
          d1 = point(n + 1, (side + 1) % 4);
        vertices.push(...a, ...c1, ...b, ...b, ...c1, ...d1);
      }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    g.computeVertexNormals();
    this.add(g, c, p);
    this.box([p[0], p[1] - 0.025, p[2]], [w, 0.065, d], c);
  }
  finish() {
    return [...this.pieces].map(([color, parts]) => {
      const geometry = mergeGeometries(parts)!;
      parts.forEach((part) => part.dispose());
      return { color, geometry };
    });
  }
}

function Baked({
  build,
  position = [0, 0, 0],
  scale = 1,
  rotation = 0,
}: {
  build: (model: Model) => void;
  position?: V3;
  scale?: number;
  rotation?: number;
}) {
  const batches = useMemo(() => {
    const model = new Model();
    build(model);
    return model.finish();
  }, [build]);
  useEffect(
    () => () => batches.forEach(({ geometry }) => geometry.dispose()),
    [batches],
  );
  return (
    <group position={position} scale={scale} rotation={[0, rotation, 0]}>
      {batches.map(({ color, geometry }) => (
        <mesh key={color} geometry={geometry} castShadow receiveShadow>
          <meshStandardMaterial
            color={color}
            roughness={0.86}
            flatShading
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}
    </group>
  );
}

function cloth(b: Model, p: V3, color = P.red, w = 0.42, h = 0.74) {
  b.box(p, [w, h, 0.025], color);
  [-0.37, 0.37].forEach((x) =>
    b.box([p[0] + x * w, p[1], p[2] + 0.018], [0.025, h, 0.01], P.cream),
  );
  [-0.23, 0, 0.23].forEach((y) =>
    b.box(
      [p[0], p[1] + y * h * 2, p[2] + 0.022],
      [w * 0.19, w * 0.19, 0.01],
      P.cream,
      [0, 0, Math.PI / 4],
    ),
  );
}

function house(
  b: Model,
  style: string,
  scale = 1,
  p: V3 = [0, 0, 0],
  rotation = 0,
) {
  b.at(p, scale, rotation, () => {
    const batakPreview = style === "batak-preview";
    const red = style === "sumba",
      joglo = style === "jawa-tengah";
    [-0.67, 0.67].forEach((x) =>
      [-0.47, 0.47].forEach((z) => {
        b.box([x, 0.23, z], [0.16, 0.46, 0.16], P.stone);
        b.box([x, 0.69, z], [0.1, 0.8, 0.1], P.timber);
      }),
    );
    b.box([0, 0.59, 0], [1.65, 0.15, 1.38], P.wood);
    b.box([0, 1.16, -0.08], [1.4, 1.04, 1.03], "#c28b47");
    b.box([0, 1.03, 0.45], [0.36, 0.82, 0.045], "#413b27");
    [-0.49, 0.49].forEach((x) => {
      b.box([x, 1.22, 0.45], [0.23, 0.34, 0.04], P.timber);
      b.box([x, 1.22, 0.48], [0.018, 0.32, 0.025], P.gold);
    });
    for (let i = 0; i < 7; i++) {
      const x = -0.68 + i * 0.225;
      b.box([x, 0.73, 0.63], [0.04, 0.4, 0.04], P.wood);
    }
    b.box([0, 0.93, 0.63], [1.5, 0.05, 0.06], P.straw);
    [-0.72, 0.72].forEach((x) =>
      b.box([x, 1.22, 0.59], [0.08, 1.15, 0.08], P.timber),
    );
    for (let i = 0; i < 4; i++)
      b.box(
        [0, 0.1 + i * 0.13, 1.12 - i * 0.12],
        [0.55, 0.17, 0.32],
        i % 2 ? P.lightStone : P.stone,
      );
    const roofColor = red
      ? "#bd753c"
      : style === "sumatera-utara" || batakPreview
        ? "#713e2e"
        : P.clay;
    if (
      style === "sumatera-utara" ||
      style === "sumatera-barat" ||
      batakPreview
    ) {
      const vertices: number[] = [];
      for (let i = 0; i < 8; i++) {
        const z = -0.86 + i * 0.215,
          z2 = z + 0.215;
        const y = (z: number) =>
          (batakPreview ? 2.48 : 1.95) +
          Math.pow(z / 0.86, 2) * (batakPreview ? 0.55 : 0.42);
        const eave = (z: number) =>
          1.58 + Math.pow(z / 0.86, 2) * (batakPreview ? 0.42 : 0.3);
        for (const side of [-1, 1])
          vertices.push(
            0,
            y(z),
            z,
            side * 0.99,
            eave(z),
            z,
            0,
            y(z2),
            z2,
            0,
            y(z2),
            z2,
            side * 0.99,
            eave(z),
            z,
            side * 0.99,
            eave(z2),
            z2,
          );
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
      g.computeVertexNormals();
      b.add(g, roofColor);
      [-1, 1].forEach((side) => {
        const peak = batakPreview ? 3.03 : 2.32;
        const edge = batakPreview ? 2.0 : 1.88;
        b.rod(
          [0, peak, side * 0.86],
          [0, peak + 0.23, side * 1.0],
          0.035,
          P.gold,
        );
        b.rod(
          [-0.99, edge, side * 0.86],
          [0, peak + 0.06, side * 0.86],
          0.035,
          P.cream,
        );
        b.rod(
          [0.99, edge, side * 0.86],
          [0, peak + 0.06, side * 0.86],
          0.035,
          P.cream,
        );
      });
      if (batakPreview) {
        const gable = new THREE.BufferGeometry();
        gable.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(
            [-0.86, 1.82, 0.86, 0.86, 1.82, 0.86, 0, 2.94, 0.86],
            3,
          ),
        );
        gable.computeVertexNormals();
        b.add(gable, P.red);
        for (let row = 0; row < 3; row++) {
          const y = 1.94 + row * 0.27;
          const count = 3 - row;
          for (let i = 0; i < count; i++) {
            const x = (i - (count - 1) / 2) * 0.33;
            b.box([x, y, 0.875], [0.14, 0.14, 0.025], P.cream, [
              0,
              0,
              Math.PI / 4,
            ]);
            b.box([x, y, 0.895], [0.07, 0.07, 0.02], P.red, [
              0,
              0,
              Math.PI / 4,
            ]);
          }
        }
        b.box([0, 1.79, 0.88], [1.46, 0.075, 0.04], P.cream);
      }
    } else {
      b.roof([0, 1.65, 0], 2.04, 1.8, 0.6, roofColor, 0.25);
      if (red) {
        b.roof([0, 2.19, 0], 0.96, 0.88, 1.9, "#cb8e43", 0.22);
        for (let i = 0; i < 6; i++) {
          const y = 2.22 + i * 0.29,
            k = 1 - i * 0.125;
          b.box([0, y, 0], [0.96 * k, 0.023, 0.88 * k], "#a36535");
        }
        [-0.25, 0.25].forEach((x) =>
          b.rod([x, 2.25, 0.44], [x * 0.23, 4.06, 0.097], 0.009, "#e4a353"),
        );
      }
      if (joglo) b.roof([0, 2.1, 0], 1.05, 0.85, 0.5, P.clay, 0.3);
      if (style === "lombok") b.roof([0, 2.12, 0], 1.1, 1, 0.6, "#b59a53", 0.2);
      b.box([0, red ? 4.1 : 2.24, 0], [red ? 0.26 : 0.5, 0.07, 0.14], P.gold);
    }
    cloth(b, [-0.49, 1.13, 0.49], red ? P.red : "#ac4b32", 0.28, 0.6);
    if (red) cloth(b, [0.49, 1.13, 0.49], P.red, 0.28, 0.6);
    for (let i = 0; i < 6; i++)
      b.box([-0.63 + i * 0.25, 0.6, 0.6], [0.018, 0.12, 0.13], P.straw);
  });
}

function meru(b: Model, p: V3 = [0, 0, 0], scale = 1, levels = 5) {
  b.at(p, scale, 0, () => {
    for (let i = 0; i < 3; i++)
      b.box(
        [0, 0.15 + i * 0.2, 0],
        [2.2 - i * 0.17, 0.27, 1.95 - i * 0.15],
        i % 2 ? P.lightStone : P.stone,
      );
    [-0.56, 0.56].forEach((x) =>
      [-0.47, 0.47].forEach((z) =>
        b.box([x, 1.15, z], [0.12, 1.3, 0.12], P.wood),
      ),
    );
    b.box([0, 0.92, -0.3], [1.12, 0.58, 0.2], P.gold);
    for (let i = 0; i < levels; i++) {
      const w = 2.32 - i * 0.3,
        y = 1.5 + i * 0.58;
      b.box([0, y + 0.15, 0], [w * 0.46, 0.27, w * 0.42], P.gold);
      b.box([0, y - 0.065, 0], [w * 0.65, 0.085, w * 0.58], P.gold);
      b.roof([0, y, 0], w, w * 0.86, 0.43, "#674439", 0.3);
      [-1, 1].forEach((side) => {
        b.box(
          [0, y - 0.045, side * (w * 0.43 + 0.012)],
          [w, 0.055, 0.035],
          P.gold,
        );
        b.box(
          [side * (w * 0.5 + 0.012), y - 0.045, 0],
          [0.035, 0.055, w * 0.86],
          P.gold,
        );
      });
    }
    b.cylinder([0, 1.65 + levels * 0.58, 0], 0.055, 0.14, 0.3, P.gold, 6);
    b.rock([0, 1.9 + levels * 0.58, 0], [0.1, 0.18, 0.1], "#f7c251");
    for (let i = 0; i < 7; i++)
      b.box(
        [0, 0.1 + i * 0.09, 1.8 - i * 0.15],
        [0.85, 0.16, 0.28],
        i % 2 ? P.lightStone : P.stone,
      );
  });
}

function penjor(b: Model, p: V3, rotation = 0) {
  b.at(p, 1, rotation, () => {
    const points: V3[] = [
      [0, 0, 0],
      [0, 1.4, 0],
      [0.05, 2.15, 0],
      [0.35, 2.55, 0],
      [0.76, 2.48, 0],
      [0.9, 2.12, 0],
    ];
    for (let i = 0; i < points.length - 1; i++)
      b.rod(points[i], points[i + 1], 0.025, i % 2 ? P.cream : P.gold);
    b.cylinder([0.9, 1.96, 0], 0.06, 0.15, 0.28, P.cream, 8);
    b.rock([0.9, 2.13, 0], [0.08, 0.1, 0.08], P.gold);
  });
}

function templeGate(b: Model, p: V3, scale = 1) {
  b.at(p, scale, 0, () => {
    [-1, 1].forEach((side) => {
      for (let i = 0; i < 5; i++)
        b.box(
          [side * (0.58 + i * 0.04), 0.18 + i * 0.27, 0],
          [0.55 - i * 0.07, 0.3, 0.65 - i * 0.06],
          i % 2 ? P.gold : P.stone,
        );
      b.box([side * 0.6, 0.13, 0], [0.85, 0.26, 0.95], P.lightStone);
      b.roof([side * 0.75, 1.45, 0], 0.36, 0.38, 0.18, P.timber);
    });
  });
}

function stupa(b: Model, p: V3, scale = 1) {
  b.at(p, scale, 0, () => {
    b.cylinder([0, 0.08, 0], 0.42, 0.45, 0.16, P.darkStone, 12);
    const profile = [
      [0.38, 0],
      [0.38, 0.12],
      [0.31, 0.45],
      [0.2, 0.61],
      [0.1, 0.64],
    ].map(([r, y]) => new THREE.Vector2(r, y));
    b.add(new THREE.LatheGeometry(profile, 12), P.stone, [0, 0.16, 0]);
    b.cylinder([0, 1.03, 0], 0.035, 0.09, 0.55, P.darkStone, 6);
    for (let i = 0; i < 6; i++) {
      const a = (i * Math.PI) / 3;
      b.box(
        [Math.cos(a) * 0.3, 0.51, Math.sin(a) * 0.3],
        [0.065, 0.1, 0.026],
        "#4d4840",
        [0, Math.PI / 2 - a, Math.PI / 4],
      );
    }
  });
}

function candi(b: Model, p: V3 = [0, 0, 0], scale = 1, low = false) {
  b.at(p, scale, 0, () => {
    for (let i = 0; i < 4; i++) {
      const w = 4.3 - i * 0.7;
      b.box(
        [0, 0.2 + i * 0.38, 0],
        [w, 0.4, w * 0.76],
        i % 2 ? P.stone : P.darkStone,
      );
      b.box(
        [0, 0.42 + i * 0.38, 0],
        [w + 0.07, 0.08, w * 0.76 + 0.07],
        P.lightStone,
      );
    }
    const count = low ? 6 : 10;
    for (let i = 0; i < count; i++) {
      const a = (i * Math.PI * 2) / count;
      stupa(b, [Math.cos(a) * 1.37, 1.5, Math.sin(a) * 1.03], 0.48);
    }
    for (let i = 0; i < 5; i++) {
      const a = (i * Math.PI * 2) / 5;
      stupa(b, [Math.cos(a) * 0.67, 1.92, Math.sin(a) * 0.48], 0.42);
    }
    stupa(b, [0, 2.05, 0], 0.92);
    for (let i = 0; i < 10; i++)
      b.box(
        [0, 0.05 + i * 0.14, 2.8 - i * 0.18],
        [0.72, 0.18, 0.32],
        i % 2 ? P.stone : P.lightStone,
      );
    [-0.54, 0.54].forEach((x) =>
      b.rod([x, 0.2, 2.8], [x, 1.5, 1.05], 0.09, P.darkStone),
    );
    for (let i = 0; i < 9; i++) {
      const x = -1.8 + i * 0.45;
      if (Math.abs(x) < 0.4) continue;
      b.cylinder([x, 0.62, 1.65], 0.04, 0.09, 0.25, P.lightStone, 5);
      b.rock([x, 0.81, 1.65], [0.07, 0.08, 0.04], P.lightStone);
    }
  });
}

function ampera(b: Model, p: V3 = [0, 0, 0], scale = 1) {
  b.at(p, scale, 0, () => {
    b.box([0, 1.05, 0], [6.6, 0.25, 0.86], "#bc3f2c");
    b.box([0, 1.2, 0], [6.6, 0.07, 0.72], "#c09369");
    [-1.8, 1.8].forEach((x) => {
      b.box([x, 0.32, 0], [0.9, 0.64, 1.1], P.stone);
      b.box([x, 0.15, 0], [1.08, 0.3, 1.3], P.lightStone);
      [-0.29, 0.29].forEach((dx) =>
        b.box([x + dx, 2.1, 0], [0.19, 2.05, 0.45], "#bd3524"),
      );
      b.box([x, 3.17, 0], [0.82, 0.4, 0.57], "#c23b28");
      b.box([x, 3.42, 0], [0.95, 0.12, 0.67], P.gold);
      for (let i = 0; i < 4; i++)
        b.box(
          [x - 0.22 + i * 0.15, 3.18, 0.294],
          [0.1, 0.21, 0.012],
          "#f8c347",
        );
      b.box([x, 2.66, 0], [0.67, 0.09, 0.47], P.gold);
    });
    for (let i = 0; i < 19; i++) {
      const x = -3.12 + i * 0.347;
      [-0.39, 0.39].forEach((z) =>
        b.box([x, 1.45, z], [0.045, 0.42, 0.045], P.cream),
      );
    }
    [-0.39, 0.39].forEach((z) =>
      b.box([0, 1.61, z], [6.6, 0.055, 0.055], P.cream),
    );
    for (let i = 0; i < 5; i++) {
      const x = -2.8 + i * 1.4;
      [-0.55, 0.55].forEach((z) => {
        b.cylinder([x, 1.85, z], 0.025, 0.035, 1.05, P.gold, 6);
        b.rock([x, 2.4, z], [0.11, 0.13, 0.11], "#fff0bc");
      });
    }
  });
}

function palm(b: Model, p: V3, scale = 1, rotation = 0) {
  b.at(p, scale, rotation, () => {
    b.cylinder([0.05, 0.95, 0], 0.07, 0.14, 1.9, "#a1793c", 7, [0, 0, -0.05]);
    for (let i = 0; i < 8; i++)
      b.cylinder(
        [0.05, 0.15 + i * 0.22, 0],
        0.14 - i * 0.009,
        0.14 - i * 0.009,
        0.024,
        "#b38e49",
        7,
      );
    for (let n = 0; n < 7; n++) {
      const a = (n * Math.PI * 2) / 7;
      const vertices: number[] = [];
      const leafPoint = (t: number, side: number): V3 => {
        const w = Math.sin(t * Math.PI) * 0.24 * side;
        return [
          Math.sin(a) * t * 1.2 + Math.cos(a) * w,
          1.9 + Math.sin(t * Math.PI) * 0.32 - t * t * 0.3,
          Math.cos(a) * t * 1.2 - Math.sin(a) * w,
        ];
      };
      for (let i = 0; i < 5; i++) {
        const t = i / 5,
          u = (i + 1) / 5;
        for (const side of [-1, 1])
          vertices.push(
            ...leafPoint(t, 0),
            ...leafPoint(u, 0),
            ...leafPoint(t, side),
            ...leafPoint(t, side),
            ...leafPoint(u, 0),
            ...leafPoint(u, side),
          );
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
      g.computeVertexNormals();
      b.add(g, n % 2 ? P.leaf : P.leafLight);
    }
    [-0.12, 0.12].forEach((x) =>
      b.rock([x, 1.8, 0.06], [0.12, 0.15, 0.12], "#86733d"),
    );
  });
}

function plant(b: Model, p: V3, scale = 1, flowers = false) {
  b.at(p, scale, 0, () => {
    for (let i = 0; i < 6; i++) {
      const a = (i * Math.PI) / 3;
      b.rock(
        [Math.sin(a) * 0.22, 0.16, Math.cos(a) * 0.22],
        [0.15, 0.08, 0.5],
        i % 2 ? P.leaf : P.leafDark,
        [Math.cos(a) * 0.6, a, Math.sin(a) * 0.45],
      );
    }
    if (flowers)
      for (let n = 0; n < 3; n++) {
        const x = (n - 1) * 0.25,
          y = 0.37 + (n % 2) * 0.14,
          z = 0.1 * (n - 1);
        b.rod([x * 0.4, 0, z], [x, y, z], 0.018, P.leafDark);
        for (let i = 0; i < 5; i++) {
          const a = (i * Math.PI * 2) / 5;
          b.rock(
            [x + Math.cos(a) * 0.115, y + Math.sin(a) * 0.115, z],
            [0.1, 0.1, 0.035],
            n % 2 ? "#fff3ce" : "#ed7456",
          );
        }
        b.rock([x, y, z + 0.04], [0.047, 0.047, 0.03], P.gold);
      }
  });
}

function mountain(b: Model, p: V3, scale = 1) {
  b.at(p, scale, 0, () => {
    b.cylinder([0, 1.1, 0], 0.12, 1.65, 2.2, "#6c836b", 7);
    b.cylinder([-0.8, 0.5, 0.3], 0.13, 1.1, 1.1, "#82965b", 6);
    b.cylinder([0.6, 0.6, -0.2], 0.07, 1.05, 1.3, "#566f66", 6);
  });
}

function market(b: Model, p: V3, scale = 1) {
  b.at(p, scale, 0, () => {
    b.box([0, 0.34, 0], [1.25, 0.6, 0.64], P.wood);
    b.box([0, 0.67, 0], [1.4, 0.1, 0.78], P.gold);
    [-0.64, 0.64].forEach((x) =>
      b.rod([x, 0, 0], [x, 1.45, 0], 0.035, P.timber),
    );
    b.roof([0, 1.43, 0], 1.65, 1.15, 0.4, P.red, 0.2);
    for (let i = 0; i < 5; i++)
      b.box([-0.6 + i * 0.3, 1.43, 0.59], [0.15, 0.1, 0.05], P.cream);
    cloth(b, [0.22, 0.43, 0.36], P.red, 0.45, 0.44);
    for (let i = 0; i < 6; i++)
      b.rock(
        [-0.45 + (i % 3) * 0.13, 0.79, Math.floor(i / 3) * 0.14],
        [0.085, 0.085, 0.085],
        i % 2 ? P.leafLight : P.gold,
      );
  });
}

function dolmen(b: Model, p: V3, scale = 1) {
  b.at(p, scale, 0, () => {
    [-0.36, 0.36].forEach((x) =>
      b.box([x, 0.26, 0], [0.22, 0.52, 0.44], P.stone, [0, 0, x * 0.14]),
    );
    b.box([0, 0.55, 0], [1.12, 0.2, 0.72], P.lightStone);
    b.box([0, 0.28, 0.24], [0.13, 0.13, 0.012], P.cream, [0, 0, Math.PI / 4]);
  });
}

export function RegionalArchitecture({
  id,
  lowGraphics = false,
  miniature = false,
}: {
  id: string;
  lowGraphics?: boolean;
  miniature?: boolean;
}) {
  const build = useMemo(
    () => (b: Model) => {
      if (miniature) {
        if (id === "bali") meru(b, [0, 0, 0], 1, 4);
        else if (id === "jawa-tengah") candi(b, [0, 0, 0], 0.7, true);
        else if (id === "sumatera-selatan") ampera(b, [0, 0, 0], 0.55);
        else house(b, id, 1);
        return;
      }
      if (id === "bali") {
        meru(b, [0, 0, -1.25], 1.1, 5);
        templeGate(b, [0, 0, 2.0], 1.0);
        house(b, "jawa-tengah", 0.66, [-3.35, 0, 0.2], 0.1);
        meru(b, [3.4, 0, -2.1], 0.48, 3);
        [-1.45, 1.45].forEach((x) =>
          penjor(b, [x, 0, 1.2], x < 0 ? 0 : Math.PI),
        );
        for (let i = 0; i < 7; i++) {
          const x = -2.1 + i * 0.7;
          if (Math.abs(x) < 0.8) continue;
          b.box([x, 0.4, 2.1], [0.6, 0.8, 0.3], P.clay);
          b.box([x, 0.83, 2.1], [0.67, 0.1, 0.4], P.lightStone);
        }
        for (let i = 0; i < 4; i++)
          b.box(
            [-2.4, 0.18 + i * 0.22, -0.1 - i * 0.08],
            [0.52, 0.3, 0.5],
            P.stone,
          );
      } else if (id === "sumba") {
        house(b, id, 1.07, [0, 0, -1.6]);
        house(b, id, 0.78, [-3.3, 0, -1.1], 0.18);
        house(b, id, 0.76, [3.2, 0, -1.7], -0.18);
        dolmen(b, [0.45, 0, 0.65], 1);
        dolmen(b, [1.9, 0, 0.25], 0.7);
        dolmen(b, [-0.8, 0, 0.4], 0.65);
        b.rock([1.2, 0.65, -0.1], [0.2, 0.68, 0.15], P.stone, [0, 0, 0.04]);
      } else if (id === "jawa-tengah") {
        candi(b, [0.4, 0, -1.6], 1, lowGraphics);
        house(b, id, 0.9, [-3.4, 0, 0.5], 0.2);
        house(b, id, 0.6, [3.6, 0, -0.8], -0.2);
      } else if (id === "sumatera-selatan") {
        ampera(b, [0.7, 0, -1.5], 1);
        house(b, id, 0.95, [-3.35, 0, -1.5], 0.2);
        house(b, id, 0.8, [4.2, 0, 1.9], -0.3);
        market(b, [-3.3, 0, 1.3], 0.85);
        market(b, [-1.6, 0, 2.8], 0.6);
        for (let i = 0; i < 6; i++) {
          b.box([3.4 + i * 0.2, 0.1, 2.5], [0.16, 0.1, 1.1], P.straw);
          b.rod([3.4 + i * 0.2, 0, 3], [3.4 + i * 0.2, 0.6, 3], 0.04, P.timber);
        }
      } else {
        const style = id === "sumatera-utara" ? "batak-preview" : id;
        house(b, style, 1.06, [-0.2, 0, -1.5]);
        house(b, style, 0.72, [-3.2, 0, -0.7], 0.15);
        house(b, style, 0.72, [3.1, 0, -1.1], -0.2);
        if (id === "sumatera-barat") {
          house(b, id, 0.55, [1.8, 0, -3.0], -0.1);
          market(b, [2.8, 0, 1.6], 0.65);
        }
        if (id === "sumatera-utara") {
          dolmen(b, [-0.8, 0, 0.1], 0.6);
          dolmen(b, [-1.6, 0, 0.25], 0.5);
        }
      }
    },
    [id, lowGraphics, miniature],
  );
  return <Baked build={build} />;
}

export function LandscapeGarden({
  id,
  lowGraphics = false,
}: {
  id: RegionId;
  lowGraphics?: boolean;
}) {
  const build = useMemo(
    () => (b: Model) => {
      const dry = id === "sumba";
      const river = id === "sumatera-selatan";
      const spots: V3[] = [
        [-4.3, 0, 2.6],
        [-3.2, 0, 3.5],
        [-1, 0, 3.7],
        [1.7, 0, 3.5],
        [3.9, 0, 2.9],
        [4.7, 0, 0.8],
        [-4.9, 0, 0.4],
        [-4.3, 0, -2.5],
        [3.8, 0, -3.2],
      ];
      spots.forEach((p, i) => {
        if (!isRegionalGround(id, p[0], p[2], 0.4)) return;
        if (river && p[0] > 0 && p[0] < 3.6) return;
        if (lowGraphics && i % 2) return;
        plant(b, p, 0.8 + (i % 3) * 0.23, i % 2 === 0);
      });
      if (!dry) {
        [
          [-4.4, 0, 1.3],
          [-3.7, 0, -2.6],
          [3.6, 0, -3.0],
          [4.7, 0, 0.2],
        ].forEach((p, i) => {
          if (
            isRegionalGround(id, p[0], p[2], 0.3) &&
            (!lowGraphics || i % 2 === 0)
          )
            palm(b, p as V3, 0.65 + (i % 2) * 0.2, i * 0.8);
        });
      }
      for (let i = 0; i < (lowGraphics ? 10 : 22); i++) {
        const a = i * 2.399;
        const x = Math.cos(a) * (4.8 + (i % 3) * 0.2),
          z = Math.sin(a) * 3.8;
        if (!isRegionalGround(id, x, z, 0.3) || (river && x > 0 && x < 3.6))
          continue;
        b.rock(
          [x, 0.12, z],
          [0.18 + (i % 3) * 0.09, 0.18 + (i % 2) * 0.1, 0.23],
          i % 2 ? P.stone : P.darkStone,
          [0, i, 0],
        );
      }
      if (id === "lombok") {
        b.at([0.6, 0, -3.9], 1.15, 0, () => {
          b.add(
            new THREE.CylinderGeometry(0.55, 1.7, 2.5, 9, 1, true),
            "#708f4c",
            [0, 1.25, 0],
          );
          b.add(
            new THREE.RingGeometry(0.36, 0.55, 9),
            "#a09a63",
            [0, 2.5, 0],
            [1, 1, 1],
            [-Math.PI / 2, 0, 0],
          );
          b.cylinder([0, 2.3, 0], 0.36, 0.3, 0.4, "#767568", 9);
          b.cylinder([0, 2.51, 0], 0.35, 0.35, 0.025, "#5cbfcb", 9);
          mountain(b, [-1.5, 0, 0.2], 0.65);
        });
      } else if (id !== "sumatera-selatan" && !dry) {
        mountain(
          b,
          id === "flores"
            ? [1.3, 0, -4]
            : id === "sumatera-barat"
              ? [0.6, 0, -4.2]
              : [0.4, 0, -4],
          id === "flores" ? 1.35 : 1.1,
        );
      }
      if (id === "bali" || id === "jawa-tengah" || id === "sumatera-barat") {
        b.at([-3.2, 0, -2.5], 1, 0, () => {
          for (let i = 0; i < 5; i++) {
            b.cylinder(
              [i * 0.14, i * 0.27, 0],
              1.85 - i * 0.24,
              1.95 - i * 0.24,
              0.3,
              i % 2 ? "#9dbb31" : "#819f29",
              16,
            );
            b.cylinder(
              [i * 0.14, 0.16 + i * 0.27, 0],
              1.84 - i * 0.24,
              1.84 - i * 0.24,
              0.025,
              "#bad051",
              16,
            );
          }
        });
      }
      // Paved courtyard remains clear around the moving weaver and walking routes.
      if (id !== "sumatera-selatan")
        for (let i = 0; i < 14; i++) {
          const x = -2.6 + i * 0.36,
            z = 0.8 + Math.sin(i * 0.4) * 0.25;
          if (!isRegionalGround(id, x, z, 0.2)) continue;
          b.box(
            [x, 0.03, z],
            [0.31, 0.055, 0.3],
            i % 3 ? "#d6b681" : "#c8a46b",
            [0, 0, 0],
          );
        }
    },
    [id, lowGraphics],
  );
  return <Baked build={build} position={[0, 0.92, 0]} />;
}

export function MiniatureLandmarks({
  lowGraphics = false,
}: {
  lowGraphics?: boolean;
}) {
  const build = useMemo(
    () => (b: Model) => {
      const project = (lon: number, lat: number): V3 => [
        (lon - 118) * 0.98,
        0.53,
        -(lat + 2.3) * 1.04,
      ];
      b.at(project(115.15, -8.4), 0.65, 0, () => meru(b, [0, 0, 0], 1, 4));
      b.at(project(110.4, -7.2), 0.55, 0, () => candi(b, [0, 0, 0], 0.8, true));
      b.at(project(120.1, -9.65), 0.66, 0, () => house(b, "sumba", 1));
      b.at(project(104.75, -3), 0.46, -0.2, () => ampera(b, [0, 0, 0], 0.65));
      b.at(project(99.05, 2.3), 0.78, -0.25, () =>
        house(b, "sumatera-utara", 1),
      );
      b.at(project(100.3, -0.4), 0.65, 0.2, () =>
        house(b, "sumatera-barat", 1),
      );
      b.at(project(116.3, -8.6), 0.51, 0, () => house(b, "lombok", 1));
      b.at(project(122.2, -8.6), 0.56, 0, () => house(b, "flores", 1));
      b.at(project(119.8, -0.7), 0.63, 0.2, () =>
        house(b, "sulawesi-tengah", 1),
      );
      if (!lowGraphics) {
        b.at(project(114.5, 0.3), 0.55, -0.1, () => mountain(b, [0, 0, 0], 1));
      }
    },
    [lowGraphics],
  );
  return <Baked build={build} />;
}

/** Color-batched 3D scenery for the illustrated atlas; no billboard scenery. */
export function AtlasLandscape({
  lowGraphics = false,
}: {
  lowGraphics?: boolean;
}) {
  const build = useMemo(
    () => (b: Model) => {
      const project = (lon: number, lat: number): V3 => [
        (lon - 118) * 0.98,
        0.53,
        -(lat + 2.3) * 1.04,
      ];
      const ridges = [
        [97.6, 3.4, 0.62],
        [101.4, -1.7, 0.66],
        [103, -3.5, 0.4],
        [113.8, 0.65, 1.05],
        [115.15, 1.3, 0.73],
        [112.7, -0.4, 0.62],
        [119.8, -1.5, 0.65],
        [120.7, -2.2, 0.53],
        [121.25, -3.4, 0.4],
        [108.3, -7, 0.4],
        [112.35, -7.7, 0.4],
        [116.45, -8.4, 0.32],
        [135.5, -3.55, 0.95],
        [137.2, -4.3, 1.05],
        [138.65, -4.8, 0.84],
      ];
      ridges.forEach(([lon, lat, scale], n) => {
        b.at(project(lon, lat), scale, n * 0.7, () => {
          b.add(
            new THREE.SphereGeometry(1, 10, 7),
            "#829c50",
            [-0.25, 0.15, 0.15],
            [1.4, 0.55, 0.95],
          );
          b.cylinder([0.1, 0.7, -0.12], 0.12, 1.08, 1.65, "#779158", 10);
          b.cylinder([-0.6, 0.36, 0.22], 0.08, 0.74, 0.92, "#9aab61", 9);
          b.cylinder([0.62, 0.34, -0.1], 0.06, 0.63, 0.86, "#5f8056", 9);
          b.rock([0.08, 1.45, -0.1], [0.18, 0.12, 0.19], "#c1bd85");
        });
      });
      const terraces = [
        [100.3, -0.1, 0.5],
        [102.4, -2.9, 0.43],
        [109.6, -7.2, 0.49],
        [111.35, -7.55, 0.42],
        [114.95, -8.3, 0.28],
        [112.3, -1.4, 0.65],
      ];
      terraces.forEach(([lon, lat, scale], n) =>
        b.at(project(lon, lat), scale, n * 0.32, () => {
          for (let i = 0; i < 5; i++) {
            const radius = 1.38 - i * 0.19;
            b.cylinder(
              [i * 0.1, 0.05 + i * 0.19, 0],
              radius,
              radius + 0.06,
              0.22,
              i % 2 ? "#a4b849" : "#899f3c",
              22,
            );
            b.cylinder(
              [i * 0.1, 0.17 + i * 0.19, 0],
              radius + 0.015,
              radius + 0.015,
              0.045,
              "#e0ca65",
              22,
            );
          }
        }),
      );
      const villages: [number, number, string, number][] = [
        [107.4, -6.65, "jawa-tengah", 0.29],
        [112.65, -7.8, "jawa-tengah", 0.28],
        [104.4, -3.25, "sumatera-selatan", 0.4],
        [111.5, -0.4, "sumatera-selatan", 0.4],
        [116.3, 1.15, "sumatera-selatan", 0.35],
        [120.25, -3.55, "sulawesi-tengah", 0.34],
        [124.65, 1, "sulawesi-tengah", 0.31],
        [130.6, -3.1, "flores", 0.34],
        [134.25, -2.55, "flores", 0.4],
        [139.9, -6.6, "flores", 0.42],
      ];
      villages.forEach(([lon, lat, id, s], i) =>
        b.at(project(lon, lat), s, i * 0.35 - 0.4, () => house(b, id)),
      );
      const gardens = [
        [98.9, 2.4],
        [100.2, -0.4],
        [104.2, -3.1],
        [110.4, -7.2],
        [115.1, -8.3],
        [116.3, -8.6],
        [120.1, -9.65],
        [122.2, -8.5],
        [119.8, -0.7],
        [112.3, -1.2],
        [116, 1],
        [130.7, -3.2],
        [136.3, -4.5],
      ];
      gardens.forEach(([lon, lat], n) =>
        b.at(project(lon, lat), 1, 0, () => {
          palm(b, [-0.62, 0, -0.3], 0.4, n);
          if (!lowGraphics) palm(b, [0.55, 0, -0.55], 0.32, n + 1);
          plant(b, [-0.44, 0, 0.3], 0.47, true);
          if (!lowGraphics) plant(b, [0.48, 0, 0.15], 0.4, true);
          // A miniature woven textile on a real timber display frame.
          if (n < 9) {
            const x = 0.6;
            [-0.2, 0.2].forEach((dx) =>
              b.rod([x + dx, 0, 0.32], [x + dx, 0.7, 0.32], 0.025, P.straw),
            );
            b.rod(
              [x - 0.26, 0.68, 0.32],
              [x + 0.26, 0.68, 0.32],
              0.025,
              P.straw,
            );
            cloth(
              b,
              [x, 0.41, 0.34],
              n % 2 ? "#a94b33" : "#813e32",
              0.36,
              0.46,
            );
          }
        }),
      );
      // Small waterfall tucked into Borneo's raised garden.
      b.at(project(114.1, -1.35), 0.6, 0, () => {
        b.rock([0, 0.6, 0], [0.55, 0.8, 0.4], "#7e8e68");
        b.box([0.02, 0.65, 0.33], [0.3, 1.2, 0.07], "#9dd2c3");
        b.box([-0.055, 0.65, 0.375], [0.035, 1.2, 0.012], "#f2f1d0");
        b.box([0.07, 0.7, 0.375], [0.02, 1.1, 0.012], "#e7efcd");
        b.cylinder([0, 0.035, 0.55], 0.51, 0.51, 0.04, "#75bcb1", 18);
      });
    },
    [lowGraphics],
  );
  return <Baked build={build} />;
}

export function MapWaveAccents() {
  const build = useMemo(
    () => (b: Model) => {
      const points: V3[] = [
        [-18, -0.14, 7],
        [-8, -0.14, 8],
        [5, -0.14, 3],
        [14, -0.14, -6],
        [19, -0.14, 9],
        [-3, -0.14, -5],
      ];
      points.forEach((p, n) =>
        b.at(p, 1 + (n % 2) * 0.25, 0.2, () => {
          for (let line = 0; line < 2; line++)
            for (let i = 0; i < 10; i++) {
              const x = -0.65 + i * 0.13,
                x2 = x + 0.13;
              b.rod(
                [x, 0, Math.sin(x * 5) * 0.07 + line * 0.15],
                [x2, 0, Math.sin(x2 * 5) * 0.07 + line * 0.15],
                0.018,
                "#c8e8df",
              );
            }
        }),
      );
    },
    [],
  );
  return <Baked build={build} />;
}

export function CoastalEdge({ river = false }: { river?: boolean }) {
  const build = useMemo(
    () => (b: Model) => {
      if (river) return;
      for (let i = 0; i < 8; i++) {
        const a = -1.15 + i * 0.34,
          x = 4.8 + Math.cos(a) * 0.8,
          z = Math.sin(a) * 3.8;
        b.rock(
          [x, 0.8, z],
          [0.38 + (i % 2) * 0.2, 0.6 + (i % 3) * 0.15, 0.5],
          i % 2 ? P.stone : P.darkStone,
          [0, i * 0.3, 0.2],
        );
        b.rock([x + 0.4, 0.18, z + 0.25], [0.27, 0.25, 0.3], P.darkStone);
      }
    },
    [river],
  );
  const water = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(4, -3.7);
    shape.bezierCurveTo(5, -3.4, 6.1, -2, 6.05, 0);
    shape.bezierCurveTo(6.4, 2.1, 5.3, 4.2, 3.9, 3.4);
    shape.bezierCurveTo(4.8, 1.1, 3.4, -1.7, 4, -3.7);
    const g = new THREE.ShapeGeometry(shape, 20);
    g.rotateX(-Math.PI / 2);
    return g;
  }, []);
  useEffect(() => () => water.dispose(), [water]);
  return (
    <>
      <Baked build={build} />
      {!river && (
        <>
          <mesh geometry={water} position={[0, 0.955, 0]} receiveShadow>
            <meshStandardMaterial color="#43b4bf" roughness={0.55} />
          </mesh>
          {Array.from({ length: 7 }, (_, i) => (
            <mesh
              key={i}
              position={[5.2 + (i % 2) * 0.18, 0.965, -2.7 + i * 0.83]}
              rotation={[-Math.PI / 2, 0, 0.1]}
              scale={[1, 0.35, 1]}
            >
              <circleGeometry args={[0.28 + (i % 2) * 0.2, 8]} />
              <meshBasicMaterial color="#e4eee0" />
            </mesh>
          ))}
        </>
      )}
    </>
  );
}

const horseBuild = (b: Model, coat: string) => {
  b.rock([0, 0.68, 0], [0.35, 0.35, 0.67], coat);
  for (const x of [-0.19, 0.19])
    for (const z of [-0.4, 0.4]) {
      b.rod([x, 0.57, z], [x + 0.03, 0.16, z + 0.04], 0.065, coat);
      b.box([x + 0.03, 0.09, z + 0.05], [0.14, 0.12, 0.17], "#573c28");
    }
  b.rod([0, 0.68, -0.55], [0, 0.43, -0.94], 0.045, "#543626");
};
const horseHead = (b: Model, coat: string) => {
  b.rock([0, 0.1, 0.08], [0.19, 0.36, 0.24], coat);
  b.rock([0, -0.1, 0.3], [0.15, 0.16, 0.3], coat);
  [-0.1, 0.1].forEach((x) => b.rock([x, 0.45, 0], [0.04, 0.15, 0.06], coat));
  b.box([0, 0.28, -0.1], [0.1, 0.36, 0.05], "#573c28");
};

export function GrazingHorse({
  position,
  scale = 0.65,
  coat = "#a76032",
}: {
  position: V3;
  scale?: number;
  coat?: string;
}) {
  const head = useRef<THREE.Group>(null);
  const motion = useWorldMotion();
  const bodyModel = useMemo(() => (b: Model) => horseBuild(b, coat), [coat]);
  const headModel = useMemo(() => (b: Model) => horseHead(b, coat), [coat]);
  useFrame(() => {
    if (head.current) {
      head.current.rotation.x =
        0.45 + Math.sin(motion.current.time * 0.8 + position[0]) * 0.18;
      head.current.rotation.z = Math.sin(motion.current.time * 0.5) * 0.04;
    }
  });
  return (
    <group position={position} scale={scale} rotation={[0, -0.65, 0]}>
      <Baked build={bodyModel} />
      <group ref={head} position={[0, 0.95, 0.5]}>
        <Baked build={headModel} />
      </group>
    </group>
  );
}
