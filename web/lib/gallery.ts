export type RoomId = "kain" | "motif" | "proses";
export type GalleryView = "overview" | RoomId;
export type Point3 = [number, number, number];

export const galleryAssets = {
  preview: "/assets/gallery-sumba/diorama-preview.webp",
  textile: "/assets/gallery-sumba/textile.webp",
  hero: "/assets/gallery-sumba/hero.webp",
  weaving: "/assets/gallery-sumba/weaving.webp",
  motif: "/assets/gallery-sumba/motif.webp",
};

export const rooms: {
  id: RoomId;
  number: string;
  name: string;
  caption: string;
  position: Point3;
}[] = [
  {
    id: "kain",
    number: "01",
    name: "Galeri Kain",
    caption: "Struktur Hinggi dan warna Kombu–Kawuru.",
    position: [-4.3, 2.5, 0.3],
  },
  {
    id: "motif",
    number: "02",
    name: "Ruang Motif",
    caption: "Motif figuratif, Marapu, dan identitas sosial.",
    position: [0, 2.8, 0.3],
  },
  {
    id: "proses",
    number: "03",
    name: "Proses Tenun",
    caption: "Benang lungsi, heddle, dan teknik ikat.",
    position: [4.3, 2.5, 0.3],
  },
];

export type GalleryStory = {
  id: string;
  room: RoomId;
  label: string;
  title: string;
  intro: string;
  paragraphs: string[];
  study?: "anatomy" | "colors" | "motifs";
  image: string;
  imageAlt: string;
  position: Point3;
  focus: Point3;
};

export const galleryStories: GalleryStory[] = [
  {
    id: "sehelai-sumba",
    room: "kain",
    label: "Anatomi Hinggi",
    title: "Struktur kain Hinggi",
    intro:
      "Selembar Hinggi dibagi secara geometris menjadi tujuh panel atau pita horizontal, dengan bidang tengah, badan, dan pita pengapit yang memiliki fungsi visual berbeda.",
    paragraphs: [
      "Bidang-bidang disusun berpasangan mengapit padua di tengah kain. Pilih bagian pada skema untuk mengenali nama, letak, dan isi motifnya.",
    ],
    study: "anatomy",
    image: galleryAssets.textile,
    imageAlt: "Kain Sumba dengan pola terakota dan indigo",
    position: [-4.3, 2.2, -1.38],
    focus: [-4.3, 2.15, -1.2],
  },
  {
    id: "warna-dan-serat",
    room: "kain",
    label: "Kombu & Kawuru",
    title: "Warna dan penamaan Hinggi",
    intro:
      "Warna dominan pada kain Hinggi menentukan penamaannya. Dua kelompok utamanya adalah Hinggi Kombu dan Hinggi Kawuru.",
    paragraphs: [
      "Akar mengkudu menghasilkan merah tua kecokelatan, sedangkan daun nila atau indigo menghasilkan biru tua. Pemakaian warna ini juga berkaitan dengan lapisan sosial masyarakat Sumba pada masa lampau.",
    ],
    study: "colors",
    image: galleryAssets.motif,
    imageAlt: "Detail serat dan warna kain Sumba",
    position: [-5.1, 0.9, 0.35],
    focus: [-4.5, 1.5, -0.3],
  },
  {
    id: "motif-rusa",
    room: "motif",
    label: "Motif Rusa",
    title: "Rusa dalam tenun Kanatang",
    intro:
      "Di daerah Kanatang, rusa digambarkan dengan anggun sebagai lambang kebijaksanaan dan identitas kain bangsawan.",
    paragraphs: [
      "Pada kain yang ditampilkan, figur rusa disusun berulang dan saling berhadapan. Tanduk bercabang menjadi penanda visual yang mudah dikenali.",
      "Motif hewan berukuran besar biasanya ditempatkan pada hai atau tao, yaitu bidang badan kain. Dalam Hinggi, figur-figur ini juga menyampaikan identitas, strata sosial, dan kepercayaan lokal Marapu.",
    ],
    image: galleryAssets.motif,
    imageAlt: "Detail bentuk rusa dan tanduk pada motif tenun",
    position: [-0.78, 2.25, -1.36],
    focus: [-0.4, 2.1, -1.2],
  },
  {
    id: "irama-motif",
    room: "motif",
    label: "Ragam Motif",
    title: "Bahasa figuratif Hinggi",
    intro:
      "Motif Hinggi merupakan bahasa visual yang menyampaikan strata sosial, kepercayaan Marapu, dan hubungan budaya Sumba dengan dunia luar.",
    paragraphs: [
      "Kuda, burung, pohon andung, hingga naga dan singa membawa pengertian yang berbeda. Buka masing-masing motif untuk membaca keterkaitannya dengan kehidupan masyarakat.",
    ],
    study: "motifs",
    image: galleryAssets.textile,
    imageAlt: "Susunan motif berulang pada kain Sumba",
    position: [1.05, 2.25, -1.36],
    focus: [0.4, 2.1, -1.2],
  },
  {
    id: "loop-heddle",
    room: "proses",
    label: "Loop Heddle",
    title: "Menyiapkan heddle",
    intro:
      "Loop heddle membantu mengangkat kelompok benang lungsi terpilih sehingga terbentuk jalur untuk benang pakan.",
    paragraphs: [
      "Loop heddle adalah jeratan benang pada bagian alat tenun yang membantu mengangkat kelompok benang lungsi terpilih. Ruang di antara kelompok benang menjadi jalur bagi benang pakan.",
      "Perhatikan jeratan berwarna terang pada proses ini. Perangkat dan urutan kerja dapat berbeda menurut alat tenun serta praktik penenunnya.",
    ],
    image: galleryAssets.weaving,
    imageAlt: "Tangan menyiapkan loop heddle pada benang lungsi",
    position: [4.3, 0.95, 0.55],
    focus: [4.3, 1, 0.1],
  },
  {
    id: "benang-lungsi",
    room: "proses",
    label: "Benang Lungsi",
    title: "Lungsi dan teknik ikat",
    intro:
      "Lungsi direntangkan memanjang pada alat tenun, kemudian dipersilangkan dengan benang pakan untuk membentuk kain.",
    paragraphs: [
      "Lungsi adalah benang yang membentang memanjang pada alat tenun. Benang pakan melintas menyilang di antaranya untuk membangun bidang kain.",
      "Dalam teknik ikat, bagian benang diikat untuk membatasi masuknya warna sebelum ditenun. Susunan benang yang telah disiapkan kemudian mempertemukan warna menjadi pola. Buka tab Warna & Teknik pada Tentang kain untuk melihat ringkasannya.",
    ],
    image: galleryAssets.weaving,
    imageAlt: "Benang lungsi indigo dan terakota direntangkan pada alat tenun",
    position: [5.3, 0.72, 1.38],
    focus: [4.5, 0.8, 0.5],
  },
];

export const passportTabs = [
  { id: "asal", label: "Kain" },
  { id: "motif", label: "Motif" },
  { id: "teknik", label: "Warna & Teknik" },
  { id: "referensi", label: "Referensi" },
] as const;

export type PassportTab = (typeof passportTabs)[number]["id"];

export const galleryProgressKey = "tenara-gallery-sumba-v1";

export const hinggiAnatomy = [
  {
    id: "padua",
    name: "Padua",
    alternate: "Pataduku / Paduku",
    location: "Tengah kain",
    description:
      "Bidang tepat di tengah kain. Biasanya berisi motif geometris abstrak, seperti Patola Ratu dengan pengaruh Gujarat, atau simbol kepemilikan khusus keluarga bangsawan (Maramba).",
  },
  {
    id: "telabadita",
    name: "Telabadita",
    alternate: "",
    location: "Pengapit padua",
    description:
      "Sepasang pita yang langsung menjepit atau mengapit bidang tengah (padua). Pita ini menegaskan batas visual bagian tengah kain.",
  },
  {
    id: "hai",
    name: "Hai / Tao",
    alternate: "Badan",
    location: "Panel utama",
    description:
      "Bidang badan kain tempat motif hewan atau figuratif berukuran besar biasanya ditempatkan oleh seniman tenun.",
  },
  {
    id: "telabawawa",
    name: "Telabawawa",
    alternate: "",
    location: "Pengapit bawah",
    description:
      "Pita pengapit bagian bawah yang membatasi area badan dengan bagian ujung kain.",
  },
  {
    id: "kabakil",
    name: "Kabakil",
    alternate: "Ulamata / Ramata",
    location: "Batas ujung sebelum rumbai",
    description:
      "Batas tenunan paling ujung, berupa pita pengikat atau jalinan benang tambahan sebelum rumbai. Biasanya ditemukan pada Hinggi berkualitas tinggi untuk upacara adat dan kaum elite.",
  },
] as const;

export const hinggiBands = [
  "telabawawa",
  "hai",
  "telabadita",
  "padua",
  "telabadita",
  "hai",
  "telabawawa",
] as const;

export const hinggiMotifs = [
  {
    name: "Kuda",
    meaning:
      "Melambangkan kejantanan, keberanian, kekuatan, serta status sosial tinggi pemakainya.",
  },
  {
    name: "Ayam",
    meaning: "Melambangkan kesadaran dan kehidupan wanita dalam rumah tangga.",
  },
  { name: "Kakatua", meaning: "Melambangkan persatuan." },
  {
    name: "Pohon Andung",
    meaning:
      "Dikenal sebagai pohon tengkorak. Menyimbolkan kemenangan, kegagahan, serta aspek ritual pemakaman raja.",
  },
  {
    name: "Rusa Kanatang",
    meaning:
      "Digambarkan dengan anggun sebagai lambang kebijaksanaan dan identitas kain bangsawan, khususnya di daerah Kanatang.",
  },
  {
    name: "Naga, singa, dan jangkar",
    meaning:
      "Akulturasi melalui perdagangan membawa pengaruh naga Cina serta singa dan jangkar dari hubungan dengan Belanda. Variasinya mencakup naga besar bergaya tripartit; singa dan garuda menjadi simbol kekuasaan.",
  },
] as const;

export const hinggiColors = [
  {
    name: "Hinggi Kombu",
    color: "#8d382c",
    tone: "Merah tua kecokelatan",
    dye: "Akar mengkudu (Morinda citrifolia)",
    meaning:
      "Secara tradisional, warna merah menjadi simbol pakaian keluarga kerajaan atau bangsawan.",
  },
  {
    name: "Hinggi Kawuru",
    color: "#283d54",
    tone: "Biru tua",
    dye: "Daun nila / indigo",
    meaning:
      "Pada masa lampau, rakyat jelata umumnya mengenakan kombinasi warna biru dan putih.",
  },
] as const;
