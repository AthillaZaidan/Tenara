import { catalogTraditions } from "./catalog-data";

/** Gallery artwork shares the catalog's canonical textile identities. */
export const asset = (name: string) => `/assets/${name}`;

export type Gallery = {
  id: string;
  name: string;
  region: string;
  technique: string;
  image: string;
  images?: string[];
  thumbnails?: string[];
  color: string;
  subtitle: string;
};

const artwork: Record<string, { slug: string; color: string }> = {
  "hinggi-sumba": { slug: "sumba", color: "#ad513c" },
  sikka: { slug: "sikka", color: "#8e4d3e" },
  sasak: { slug: "sasak", color: "#9d9d7b" },
  endek: { slug: "endek", color: "#53766e" },
  gringsing: { slug: "gringsing", color: "#aa7043" },
  troso: { slug: "troso", color: "#547b73" },
  lurik: { slug: "lurik", color: "#798274" },
  ulos: { slug: "ulos", color: "#96483f" },
  songket: { slug: "songket-palembang", color: "#b28c3a" },
  "pandai-sikek": { slug: "pandai-sikek", color: "#a88749" },
  donggala: { slug: "donggala", color: "#567a80" },
};

export const galleries: Gallery[] = catalogTraditions.map((tradition) => {
  const { slug, color } = artwork[tradition.id];
  const views = ["utama", "lipatan-datar", "detail-tekstur"];
  const images = views.map((view) => `katalog-tenun/tenun-${slug}-${view}.webp`);
  return {
    id: tradition.galleryId,
    name: tradition.name,
    region: tradition.region,
    technique: ["endek", "gringsing"].includes(tradition.id) ? "Ikat" : tradition.technique,
    subtitle: tradition.subtitle,
    color,
    image: images[0],
    images,
    thumbnails: views.map((view) => `katalog-tenun/tenun-${slug}-${view}-thumb.webp`),
  };
});
