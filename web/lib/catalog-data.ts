import type { RegionId } from "./exploration";

export type CatalogSample = {
  code: string;
  traditionId: string;
  origin: string;
  motif: string;
  label: string;
  images: { utama: string; datar: string; closeup: string };
};

export type CatalogTradition = {
  id: string;
  galleryId: string;
  regionId: RegionId;
  name: string;
  region: string;
  technique: string;
  subtitle: string;
  aliases: string[];
  apiNames: string[];
};

const sampleDetails: Omit<CatalogSample, "images" | "label">[] = [
  { code: "SUM-01", traditionId: "hinggi-sumba", origin: "Sumba Timur, NTT", motif: "Kuda" },
  { code: "SUM-02", traditionId: "hinggi-sumba", origin: "Sumba Timur, NTT", motif: "Andung" },
  { code: "BAL-01", traditionId: "endek", origin: "Jembrana, Bali", motif: "Mekepung" },
  { code: "BAL-02", traditionId: "endek", origin: "Jembrana, Bali", motif: "Jalak Bali" },
  { code: "BAL-03", traditionId: "gringsing", origin: "Tenganan, Karangasem, Bali", motif: "Wayang Kebo" },
  { code: "BAL-04", traditionId: "gringsing", origin: "Tenganan, Karangasem, Bali", motif: "Pat Likur Isi" },
  { code: "LOM-01", traditionId: "sasak", origin: "Sukarara, Lombok Tengah, NTB", motif: "Subahnale" },
  { code: "LOM-02", traditionId: "sasak", origin: "Sukarara, Lombok Tengah, NTB", motif: "Rangrang" },
  { code: "SIK-01", traditionId: "sikka", origin: "Sikka, Maumere, NTT", motif: "Utan Ruha" },
  { code: "SIK-02", traditionId: "sikka", origin: "Sikka, Maumere, NTT", motif: "Manu Hutu" },
  { code: "JTG-01", traditionId: "troso", origin: "Troso, Jepara, Jawa Tengah", motif: "Ampel" },
  { code: "JTG-02", traditionId: "troso", origin: "Troso, Jepara, Jawa Tengah", motif: "Kedawung" },
  { code: "JTG-03", traditionId: "lurik", origin: "Klaten–Yogyakarta", motif: "Telupat" },
  { code: "JTG-04", traditionId: "lurik", origin: "Klaten–Yogyakarta", motif: "Tumbar Pecah" },
  { code: "BTK-01", traditionId: "ulos", origin: "Tanah Batak, Sumatera Utara", motif: "Ragi Hotang" },
  { code: "BTK-02", traditionId: "ulos", origin: "Tanah Batak, Sumatera Utara", motif: "Sadum" },
  { code: "MIN-01", traditionId: "pandai-sikek", origin: "Pandai Sikek, Tanah Datar, Sumatera Barat", motif: "Tidak dibedakan per motif" },
  { code: "PLB-01", traditionId: "songket", origin: "Palembang, Sumatera Selatan", motif: "Nago Besaung" },
  { code: "PLB-02", traditionId: "songket", origin: "Palembang, Sumatera Selatan", motif: "Bungo Cino" },
  { code: "DGL-01", traditionId: "donggala", origin: "Donggala, Sulawesi Tengah", motif: "Bunga Bomba" },
  { code: "DGL-02", traditionId: "donggala", origin: "Donggala, Sulawesi Tengah", motif: "Bunga Ketupat" },
];

const sampleFiles: Record<string, { utama: string; datar: string; closeup: string }> = {
  "SUM-01": { utama: "sum-01-preview-katalog.png", datar: "sum-01-lipatan-datar.png", closeup: "sum-01-detail.png" },
  "SUM-02": { utama: "sum-02-preview-katalog.png", datar: "sum-02-lipatan-datar.png", closeup: "sum-02-detail.png" },
  "BAL-01": { utama: "bal-01-preview-katalog.png", datar: "bal-01-lipatan-datar.png", closeup: "bal-01-detail.png" },
  "BAL-02": { utama: "bal-02-preview-katalog.png", datar: "bal-02-lipatan-datar.png", closeup: "bal-02-detail.png" },
  "BAL-03": { utama: "bal-03-preview-katalog.png", datar: "bal-03-lipatan-datar.png", closeup: "bal-03-detail.png" },
  "BAL-04": { utama: "bal-04-preview-katalog.png", datar: "bal-04-lipatan-datar.png", closeup: "bal-04-detail.png" },
  "LOM-01": { utama: "lom-01-preview-katalog.png", datar: "lom-01-lipatan-datar.png", closeup: "lom-01-detail.png" },
  "LOM-02": { utama: "lom-02-preview-katalog.png", datar: "lom-02-lipatan-datar.png", closeup: "lom-02-detail.png" },
  "SIK-01": { utama: "sik-01-preview-katalog.png", datar: "sik-01-lipatan-datar.png", closeup: "sik-01-detail.png" },
  "SIK-02": { utama: "sik-02-preview-katalog.png", datar: "sik-02-lipatan-datar.png", closeup: "sik-02-detail.png" },
  "JTG-01": { utama: "jtg-01-preview.png", datar: "jtg-01-preview-closeup.png", closeup: "jtg-01-detail-tekstur.png" },
  "JTG-02": { utama: "jtg-02-preview.png", datar: "jtg-02-preview-closeup.png", closeup: "jtg-02-detail-tekstur.png" },
  "JTG-03": { utama: "jtg-03-preview.png", datar: "jtg-03-preview-closeup.png", closeup: "jtg-03-detail-tekstur.png" },
  "JTG-04": { utama: "jtg-04-preview.png", datar: "jtg-04-preview-closeup.png", closeup: "jtg-04-detail-tekstur.png" },
  "BTK-01": { utama: "btk-01-preview.png", datar: "btk-01-preview-closeup.png", closeup: "btk-01-detail-tekstur.png" },
  "BTK-02": { utama: "btk-02-preview.png", datar: "btk-02-preview-closeup.png", closeup: "btk-02-detail-tekstur.png" },
  "MIN-01": { utama: "min-01-preview.png", datar: "min-01-preview-closeup.png", closeup: "min-01-detail-tekstur.png" },
  "PLB-01": { utama: "plb-01-preview.png", datar: "plb-01-preview-closeup.png", closeup: "plb-01-detail-tekstur.png" },
  "PLB-02": { utama: "plb-02-preview.png", datar: "plb-02-preview-closeup.png", closeup: "plb-02-detail-tekstur.png" },
  "DGL-01": { utama: "dgl-01.png", datar: "dgl-01.png", closeup: "dgl-01-bunga-bomba-detail.png" },
  "DGL-02": { utama: "dgl-02.png", datar: "dgl-02.png", closeup: "dgl-02-bunga-ketupat-detail.png" },
};

const imagePath = (folder: string, filename: string) => `/assets/catalog/${folder}/${filename}`;

export const catalogSamples: CatalogSample[] = sampleDetails.map((sample) => ({
  ...sample,
  label: sample.motif,
  images: {
    utama: imagePath("preview-utama", sampleFiles[sample.code].utama),
    datar: imagePath("preview-datar", sampleFiles[sample.code].datar),
    closeup: imagePath("preview-closeup", sampleFiles[sample.code].closeup),
  },
}));

export const catalogSamplesForTradition = (id: string) =>
  catalogSamples.filter((sample) => sample.traditionId === id);

export const catalogTraditions: CatalogTradition[] = [
  { id: "hinggi-sumba", galleryId: "sumba", regionId: "sumba", name: "Hinggi Sumba", region: "Nusa Tenggara Timur", technique: "Ikat", subtitle: "Warna yang berani. Cerita yang mengakar.", aliases: ["sumba", "hinggi", "sumba timur"], apiNames: ["Tenun Ikat Sumba", "Hinggi Sumba"] },
  { id: "sikka", galleryId: "sikka", regionId: "flores", name: "Tenun Ikat Sikka", region: "Nusa Tenggara Timur", technique: "Ikat", subtitle: "Ragam garis dan warna dalam satu hamparan.", aliases: ["sikka", "maumere", "flores"], apiNames: ["Tenun Ikat Sikka", "Tenun Ikat Flores"] },
  { id: "sasak", galleryId: "lombok", regionId: "lombok", name: "Tenun Sasak", region: "Nusa Tenggara Barat", technique: "Tenun", subtitle: "Tekstur dan susunan benang yang berirama.", aliases: ["sasak", "lombok", "sukarara"], apiNames: ["Tenun Sasak"] },
  { id: "endek", galleryId: "bali", regionId: "bali", name: "Tenun Endek", region: "Bali", technique: "Ikat pakan", subtitle: "Permainan warna untuk dilihat lebih dekat.", aliases: ["endek", "bali", "jembrana"], apiNames: ["Tenun Endek", "Endek Bali"] },
  { id: "gringsing", galleryId: "gringsing", regionId: "bali", name: "Tenun Gringsing", region: "Bali", technique: "Ikat ganda", subtitle: "Pola berulang yang menghadirkan ritme visual.", aliases: ["gringsing", "tenganan", "karangasem"], apiNames: ["Tenun Gringsing", "Gringsing Tenganan"] },
  { id: "troso", galleryId: "troso", regionId: "jawa-tengah", name: "Tenun Troso", region: "Jepara, Jawa Tengah", technique: "Tenun", subtitle: "Tradisi yang terus menemukan bentuk baru.", aliases: ["troso", "jepara", "jawa tengah"], apiNames: ["Tenun Troso"] },
  { id: "lurik", galleryId: "lurik", regionId: "jawa-tengah", name: "Tenun Lurik", region: "Jawa Tengah", technique: "Tenun", subtitle: "Keindahan garis dalam susunan yang sederhana.", aliases: ["lurik", "klaten", "yogyakarta"], apiNames: ["Tenun Lurik"] },
  { id: "ulos", galleryId: "ulos", regionId: "sumatera-utara", name: "Ulos", region: "Sumatera Utara", technique: "Tenun", subtitle: "Sebuah ruang untuk mengenal dan menghargai.", aliases: ["ulos", "batak", "tanah batak"], apiNames: ["Ulos", "Ulos Batak"] },
  { id: "songket", galleryId: "songket", regionId: "sumatera-selatan", name: "Songket Palembang", region: "Sumatera Selatan", technique: "Songket", subtitle: "Kilau detail, kehangatan sebuah karya.", aliases: ["songket", "palembang", "sumatera selatan"], apiNames: ["Songket Palembang"] },
  { id: "pandai-sikek", galleryId: "pandai-sikek", regionId: "sumatera-barat", name: "Songket Pandai Sikek", region: "Sumatera Barat", technique: "Songket", subtitle: "Detail motif yang memberi karakter pada kain.", aliases: ["pandai sikek", "minangkabau", "sumatera barat"], apiNames: ["Songket Pandai Sikek"] },
  { id: "donggala", galleryId: "donggala", regionId: "sulawesi-tengah", name: "Tenun Donggala", region: "Sulawesi Tengah", technique: "Tenun", subtitle: "Koleksi visual dari pesisir Sulawesi Tengah.", aliases: ["donggala", "sulawesi tengah", "subi"], apiNames: ["Tenun Donggala", "Tenun Donggala (Subi)"] },
];

export const featuredCatalogSample = (traditionId: string) =>
  catalogSamples.find((sample) => sample.traditionId === traditionId);

export const findCatalogTradition = (id: string) =>
  catalogTraditions.find((tradition) => tradition.id === id || tradition.galleryId === id);
