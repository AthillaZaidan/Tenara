import { catalogSamples as samples } from "./catalog-data";

/** Original gallery image views, linked by the catalog's actual sample codes. */
export const catalogSamples = samples.map((sample) => ({
  ...sample,
  label: sample.code === "MIN-01" ? "Pandai Sikek" : sample.label,
  images: ["utama", "lipatan-datar", "detail-tekstur"].map(
    (view) => `katalog-tenun/mvp/${sample.code.toLowerCase()}-${view}.webp`,
  ),
  thumbnails: ["utama", "lipatan-datar", "detail-tekstur"].map(
    (view) => `katalog-tenun/mvp/${sample.code.toLowerCase()}-${view}-thumb.webp`,
  ),
}));

export type CatalogSample = (typeof catalogSamples)[number];
export const catalogSamplesForTradition = (id: string) =>
  catalogSamples.filter((sample) => sample.traditionId === id);
export const featuredCatalogSample = (id: string) =>
  catalogSamples.find((sample) => sample.traditionId === id);
