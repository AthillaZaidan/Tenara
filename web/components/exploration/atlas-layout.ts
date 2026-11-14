/** Shared art-space coordinates for the SVG fallback and baked GPU atlas. */
export type AtlasPoint = [number, number];
export type AtlasRing = AtlasPoint[];
type Geography =
  | { type: "Polygon"; coordinates: AtlasRing[] }
  | { type: "MultiPolygon"; coordinates: AtlasRing[][] };
export type GeoDocument =
  | Geography
  | { type: "Feature"; geometry: GeoDocument | null }
  | { type: "FeatureCollection"; features: GeoDocument[] };
export type AtlasIsland = {
  rings: AtlasRing[];
  path: string;
  bounds: number[];
};
export type AtlasProp = {
  x: number;
  y: number;
  symbol: string;
  scale: number;
  flip?: boolean;
};

export const ATLAS_WIDTH = 1600,
  ATLAS_HEIGHT = 660;
export const atlasProject = ([lon, lat]: AtlasPoint): AtlasPoint => [
  (lon - 94) * 32,
  (6 - lat) * 32.5 + 35,
];
export function atlasRandom(n: number, seed = 1) {
  let value = Math.imul(n + 1, 374761393) + Math.imul(seed, 668265263);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
}
export function atlasPolygons(data: GeoDocument): AtlasRing[][] {
  if (data.type === "FeatureCollection")
    return data.features.flatMap(atlasPolygons);
  if (data.type === "Feature")
    return data.geometry ? atlasPolygons(data.geometry) : [];
  return data.type === "Polygon" ? [data.coordinates] : data.coordinates;
}
export function atlasIslands(data: GeoDocument): AtlasIsland[] {
  return atlasPolygons(data).map((polygon) => {
    const rings = polygon.map((ring) => ring.map(atlasProject)),
      points = rings[0];
    return {
      rings,
      path: rings
        .map(
          (ring) =>
            `${ring.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("")}Z`,
        )
        .join(""),
      bounds: [
        Math.min(...points.map((p) => p[0])),
        Math.min(...points.map((p) => p[1])),
        Math.max(...points.map((p) => p[0])),
        Math.max(...points.map((p) => p[1])),
      ],
    };
  });
}
function inside(point: AtlasPoint, ring: AtlasRing) {
  let result = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x, y] = ring[i],
      [previousX, previousY] = ring[j];
    if (
      y > point[1] !== previousY > point[1] &&
      point[0] < ((previousX - x) * (point[1] - y)) / (previousY - y) + x
    )
      result = !result;
  }
  return result;
}
function onLand(point: AtlasPoint, islands: AtlasIsland[]) {
  return islands.some(
    ({ bounds: [left, top, right, bottom], rings }) =>
      point[0] >= left &&
      point[0] <= right &&
      point[1] >= top &&
      point[1] <= bottom &&
      inside(point, rings[0]) &&
      !rings.slice(1).some((ring) => inside(point, ring)),
  );
}

export const atlasLabels: Record<
  string,
  { name?: string; dx: number; dy: number; width: number }
> = {
  "sumatera-utara": { name: "Tanah Batak", dx: -8, dy: 8, width: 160 },
  "sumatera-barat": { name: "Minangkabau", dx: -70, dy: 12, width: 174 },
  "sumatera-selatan": { dx: 22, dy: 0, width: 160 },
  "jawa-tengah": { dx: -65, dy: 34, width: 170 },
  bali: { dx: -53, dy: -48, width: 112 },
  lombok: { dx: -3, dy: 43, width: 135 },
  sumba: { dx: 72, dy: 35, width: 130 },
  flores: { name: "Sikka - Flores", dx: 6, dy: -48, width: 180 },
  "sulawesi-tengah": { dx: -69, dy: -45, width: 145 },
};

/** Pixel-space separation keeps readable HTML labels apart at compact zooms. */
export function atlasLabelNudge(
  id: string,
  viewportWidth: number,
  scale: number,
): AtlasPoint {
  const compact = viewportWidth <= 900;
  if (compact) {
    // Spread the Java–Nusa Tenggara labels into rows as the map zooms out.
    // Interpolation avoids snapping; connectors use these same offsets.
    const tightness = Math.min(1, Math.max(0, (0.5 - scale) / 0.15));
    const blend = (a: AtlasPoint, b: AtlasPoint): AtlasPoint => [
      a[0] + (b[0] - a[0]) * tightness,
      a[1] + (b[1] - a[1]) * tightness,
    ];
    if (id === "jawa-tengah") return blend([-4, 32], [0, 20]);
    if (id === "bali") return blend([0, 0], [-12, -14]);
    if (id === "sumatera-selatan") return [0, -14 * tightness];
    if (id === "lombok") return blend([0, 0], [50, 0]);
    if (id === "flores") return blend([0, 0], [24, -14]);
    if (id === "sumba")
      return blend([12 + Math.max(0, 0.6 - scale) * 140, 4], [42, 46]);
    if (id === "sumatera-barat")
      return [
        -Math.max(0, 0.55 - scale) * 220,
        Math.min(12, Math.max(0, 0.55 - scale) * 60),
      ];
  } else if (scale < 0.75) {
    if (id === "jawa-tengah") return [0, 18];
    if (id === "sumba") return [12, 0];
  }
  return [0, 0];
}
const landmarks: [number, number, string, number][] = [
  [98.65, 2.55, "house-batak", 0.95],
  [100.5, -0.7, "house-minang", 1],
  [104.5, -3.35, "house-stilt", 0.95],
  [107.5, -6.7, "house-joglo", 0.65],
  [110.2, -7.45, "house-joglo", 0.95],
  [112.6, -7.8, "house-joglo", 0.6],
  [115.13, -8.3, "meru", 1],
  [116.35, -8.58, "house-lumbung", 0.7],
  [119.6, -9.45, "house-sumba", 0.85],
  [120.4, -9.85, "house-sumba", 0.64],
  [122.1, -8.5, "house-lumbung", 0.75],
  [119.85, -0.9, "house-tambi", 0.83],
  [111.65, -0.5, "house-stilt", 0.73],
  [116.2, 1.2, "house-stilt", 0.7],
  [120.3, -3.5, "house-toraja", 0.7],
  [125, 1.1, "house-stilt", 0.65],
  [130.7, -3.15, "house-stilt", 0.65],
  [136.2, -4.2, "house-honai", 0.8],
  [140, -6.4, "house-honai", 0.8],
  [134.4, -2.8, "house-stilt", 0.7],
];
export function atlasLandscape(
  islands: AtlasIsland[],
  lowGraphics: boolean,
): AtlasProp[] {
  const props: AtlasProp[] = [];
  for (let i = 0; i < (lowGraphics ? 720 : 2300); i++) {
    const x = 40 + atlasRandom(i, 11) * 1470,
      y = 45 + atlasRandom(i, 12) * 475;
    if (!onLand([x, y], islands)) continue;
    if (
      landmarks.some(([lon, lat]) => {
        const p = atlasProject([lon, lat]);
        return Math.hypot((p[0] - x) * 0.8, p[1] - y) < 24;
      })
    )
      continue;
    const r = atlasRandom(i, 13);
    props.push({
      x,
      y,
      symbol:
        r > 0.87
          ? "flowering-tree"
          : r > 0.69
            ? "palm"
            : r > 0.17
              ? "tree"
              : "bush",
      scale: 0.38 + atlasRandom(i, 14) * 0.4,
      flip: r > 0.5,
    });
  }
  const ranges = [
    [96.8, 4.2, 0.7],
    [98.9, 1.7, 0.85],
    [101.7, -1.9, 0.8],
    [113.7, 0.6, 1.3],
    [114.6, 1.2, 1],
    [112.9, -0.1, 0.8],
    [119.8, -1.6, 0.9],
    [120.5, -2.3, 0.65],
    [121.4, -3.1, 0.65],
    [108.2, -7.15, 0.6],
    [112.3, -7.7, 0.6],
    [116.4, -8.4, 0.58],
    [135.6, -3.6, 1.1],
    [137, -4.2, 1.3],
    [138.5, -4.7, 1],
  ];
  ranges.forEach(([lon, lat, scale]) => {
    const [x, y] = atlasProject([lon, lat]);
    props.push({ x, y, symbol: "mountain", scale });
  });
  const [waterfallX, waterfallY] = atlasProject([114.2, -1.5]);
  props.push({ x: waterfallX, y: waterfallY, symbol: "waterfall", scale: 0.9 });
  const terraces: AtlasPoint[] = [
    [100.4, -0.1],
    [103.2, -3.3],
    [109.2, -7.1],
    [111.1, -7.7],
    [114.9, -8.25],
    [112, -1.5],
  ];
  terraces.forEach((coordinates, i) => {
    const [x, y] = atlasProject(coordinates);
    props.push({ x, y, symbol: "terraces", scale: i === 4 ? 0.52 : 0.65 });
  });
  landmarks.forEach(([lon, lat, symbol, scale]) => {
    const [x, y] = atlasProject([lon, lat]);
    props.push({ x, y, symbol, scale });
    if (scale > 0.8)
      props.push({ x: x + 31, y: y + 8, symbol: "cloth", scale: 0.8 });
    props.push({ x: x - 32, y: y + 2, symbol: "flowering-tree", scale: 0.7 });
    props.push({ x: x + 33, y: y - 8, symbol: "palm", scale: 0.65 });
  });
  return props.sort((a, b) => a.y - b.y);
}
export const atlasClouds = [
  [320, 95, 1.05],
  [760, 65, 0.8],
  [1190, 102, 1],
  [1440, 480, 0.7],
  [330, 565, 0.65],
];
export const atlasBoats = [
  [270, 442, 0.88],
  [970, 346, 0.58],
  [670, 552, 0.62],
];
export const atlasWaves = [
  [170, 400],
  [470, 500],
  [1030, 530],
  [1400, 510],
  [1150, 150],
  [400, 230],
  [680, 80],
];

export type AtlasSpriteFrame = {
  x: number;
  y: number;
  w: number;
  h: number;
  box: [number, number, number, number];
};
export type AtlasManifest = {
  version: number;
  width: number;
  height: number;
  landPath: string;
  layers: { high: string; low: string };
  sprites: {
    image: string;
    width: number;
    height: number;
    frames: Record<string, AtlasSpriteFrame>;
  };
  palms: { high: AtlasProp[]; low: AtlasProp[] };
};
