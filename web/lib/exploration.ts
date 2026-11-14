import { galleries, type Gallery } from "./gallery-data";

export type RegionId =
  | "sumba"
  | "bali"
  | "lombok"
  | "flores"
  | "jawa-tengah"
  | "sumatera-utara"
  | "sumatera-barat"
  | "sumatera-selatan"
  | "sulawesi-tengah";
export type ExploreRegion = {
  id: RegionId;
  name: string;
  province: string;
  coordinates: [number, number];
  color: string;
  landscape: "savanna" | "terraces" | "highland" | "river";
  tagline: string;
  introduction: string;
  stories: { title: string; text: string }[];
  galleryIds: string[];
};

export const exploreRegions: ExploreRegion[] = [
  {
    id: "sumba",
    name: "Sumba",
    province: "Nusa Tenggara Timur",
    coordinates: [120.1, -9.65],
    color: "#b77445",
    landscape: "savanna",
    tagline: "Tanah sabana, kisah dalam tenunan.",
    introduction:
      "Perbukitan terbuka, kampung dengan rumah beratap tinggi, dan tradisi tenun menjadi pintu untuk mengenal Sumba. Mari mulai dari tempat kain ini hidup.",
    stories: [
      {
        title: "Rumah, kampung, dan ingatan",
        text: "Rumah dengan atap menjulang merupakan salah satu penanda lanskap budaya Sumba. Bentuk kampung dan praktik masyarakatnya beragam; diorama ini adalah pengantar visual, bukan gambaran satu kampung tertentu.",
      },
      {
        title: "Tenun dalam kehidupan",
        text: "Kain hadir dalam busana, pertukaran, dan berbagai peristiwa kehidupan masyarakat Sumba. Hinggi dan lau merupakan bentuk kain yang dikenal di sini. Penggunaan dan ragamnya perlu dipahami dalam konteks komunitas pembuatnya.",
      },
      {
        title: "Dari benang menjadi cerita",
        text: "Pada tenun ikat, bagian benang diikat sebelum dicelup agar membentuk pola ketika ditenun. Keterampilan menyusun warna dan benang diwariskan melalui praktik, dengan variasi antarsentra tenun.",
      },
    ],
    galleryIds: ["sumba"],
  },
  {
    id: "bali",
    name: "Bali",
    province: "Bali",
    coordinates: [115.15, -8.4],
    color: "#66865a",
    landscape: "terraces",
    tagline: "Ritme kehidupan, ragam warna dan benang.",
    introduction:
      "Dari lingkungan persawahan hingga permukiman, kain menjadi bagian dari kehidupan Bali. Kenali ragam tradisinya sebelum melihat motif dan teknik dari dekat.",
    stories: [
      {
        title: "Kain dan keseharian",
        text: "Wastra digunakan dalam keseharian, busana, dan berbagai kegiatan adat di Bali. Bentuk dan penggunaannya beragam menurut tempat, masyarakat, dan kesempatan.",
      },
      {
        title: "Ragam yang saling berbeda",
        text: "Endek dan Gringsing adalah dua tradisi kain yang dapat dijelajahi di sini. Keduanya tidak dapat disamakan hanya karena berasal dari pulau yang sama.",
      },
      {
        title: "Mengenal teknik ikat",
        text: "Endek dikenal dengan teknik ikat pakan, sementara Gringsing dari Tenganan Pegringsingan dikenal dengan ikat ganda. Buka galeri kain untuk membandingkan cara pola terbentuk.",
      },
    ],
    galleryIds: ["bali", "gringsing"],
  },
  {
    id: "lombok",
    name: "Lombok",
    province: "Nusa Tenggara Barat",
    coordinates: [116.3, -8.6],
    color: "#83925c",
    landscape: "highland",
    tagline: "Jejak tangan dalam tradisi Sasak.",
    introduction:
      "Temui lanskap Lombok dan pengenalan tradisi tenun Sasak. Dari benang dan alat tenun, lahir ragam kain yang hidup bersama masyarakatnya.",
    stories: [
      {
        title: "Mengenal lingkungan Sasak",
        text: "Tradisi tenun menjadi salah satu bagian kehidupan masyarakat Sasak di Lombok. Setiap sentra dapat memiliki pilihan bahan, ragam visual, dan kebiasaan menenun yang berbeda.",
      },
      {
        title: "Kain dan pembuatnya",
        text: "Mengenal kain juga berarti mengenal orang yang membuatnya. Nama daerah saja belum menjelaskan keseluruhan bahan, teknik, atau proses selembar kain.",
      },
      {
        title: "Ketelitian yang berulang",
        text: "Persilangan benang lungsi dan pakan membangun bidang kain. Susunan warna dan pekerjaan tambahan pada tenunan dapat membentuk ragam hias yang berbeda.",
      },
    ],
    galleryIds: ["lombok"],
  },
  {
    id: "flores",
    name: "Sikka · Flores",
    province: "Nusa Tenggara Timur",
    coordinates: [122.2, -8.6],
    color: "#9a674f",
    landscape: "highland",
    tagline: "Perbukitan, pesisir, dan tenun ikat.",
    introduction:
      "Jelajahi pengenalan Sikka di Pulau Flores. Tradisi ikat menghubungkan kerja tangan, kehidupan masyarakat, dan ragam visual kain.",
    stories: [
      {
        title: "Berangkat dari Sikka",
        text: "Sikka berada di Pulau Flores, Nusa Tenggara Timur. Tradisi kain di Flores sangat beragam; pengenalan Sikka tidak mewakili seluruh tenun di pulau ini.",
      },
      {
        title: "Ragam dalam kain",
        text: "Susunan bidang dan motif menjadi cara untuk melihat lebih dekat kain dari suatu komunitas. Nama dan pemaknaannya perlu mengikuti keterangan pembuat atau sumber setempat.",
      },
      {
        title: "Mengikat sebelum menenun",
        text: "Pada teknik ikat, bagian benang diberi ikatan untuk membatasi masuknya warna. Pola yang direncanakan pada benang bertemu kembali ketika kain ditenun.",
      },
    ],
    galleryIds: ["sikka"],
  },
  {
    id: "jawa-tengah",
    name: "Jawa Tengah",
    province: "Jawa Tengah",
    coordinates: [110.4, -7.2],
    color: "#6d8b71",
    landscape: "terraces",
    tagline: "Garis sederhana, keterampilan yang panjang.",
    introduction:
      "Kenali Lurik dan tenun Troso melalui lingkungan tempat tradisi itu berkembang. Dua pintu untuk melihat keberagaman tenun di Jawa Tengah.",
    stories: [
      {
        title: "Beragam sentra, beragam karya",
        text: "Troso di Jepara dan tradisi Lurik merupakan dua pengenalan dalam koleksi ini. Keduanya membantu melihat bahwa satu provinsi tidak hanya memiliki satu ragam kain.",
      },
      {
        title: "Melihat irama garis",
        text: "Pada Lurik, susunan garis dan warna menjadi ciri visual yang mudah dikenali. Kombinasi yang tampak sederhana tetap membutuhkan ketelitian dalam penataan benang.",
      },
      {
        title: "Tradisi yang terus dikerjakan",
        text: "Praktik tenun tumbuh bersama pembuat dan pengguna kain. Peralatan, rancangan, serta bahan dapat berbeda antarsentra dan penawaran produk.",
      },
    ],
    galleryIds: ["troso", "lurik"],
  },
  {
    id: "sumatera-utara",
    name: "Tanah Batak",
    province: "Sumatera Utara",
    coordinates: [99.05, 2.3],
    color: "#8b6652",
    landscape: "highland",
    tagline: "Kain yang hadir dalam hubungan manusia.",
    introduction:
      "Masuki pengenalan Ulos dan lingkungan budaya Batak. Mulai dari masyarakatnya, kemudian telusuri ragam kain yang menyertai berbagai peristiwa kehidupan.",
    stories: [
      {
        title: "Mengenal Ulos",
        text: "Ulos berkaitan erat dengan kehidupan masyarakat Batak. Ragam serta aturan penggunaannya tidak tunggal dan perlu dilihat menurut komunitas dan peristiwanya.",
      },
      {
        title: "Pemberian yang bermakna",
        text: "Dalam berbagai konteks adat, pemberian Ulos menjadi bagian hubungan antarmanusia. Penjelasan suatu ragam Ulos perlu menyebutkan konteksnya secara spesifik.",
      },
      {
        title: "Benang dan susunan bidang",
        text: "Warna, garis, dan ragam hias membangun bidang kain. Foto detail membantu mengenali struktur visual, tetapi identifikasi ragam tetap memerlukan keterangan yang tepat.",
      },
    ],
    galleryIds: ["ulos"],
  },
  {
    id: "sumatera-barat",
    name: "Minangkabau",
    province: "Sumatera Barat",
    coordinates: [100.3, -0.4],
    color: "#aa8950",
    landscape: "highland",
    tagline: "Kilau benang di kaki perbukitan.",
    introduction:
      "Kenali pengantar tradisi songket Pandai Sikek dalam lingkungan budaya Minangkabau. Jelajahi tempat, keterampilan, dan rincian tenunannya.",
    stories: [
      {
        title: "Berangkat dari Pandai Sikek",
        text: "Pandai Sikek dikenal sebagai salah satu sentra songket di Sumatera Barat. Koleksi ini menjadi pintu pengenalan, bukan rangkuman seluruh tradisi tekstil Minangkabau.",
      },
      {
        title: "Kain dalam kehidupan adat",
        text: "Songket hadir dalam berbagai bentuk busana dan kegiatan adat. Ragam pemakaiannya mengikuti konteks masyarakat setempat.",
      },
      {
        title: "Kilau pada permukaan kain",
        text: "Benang hias tambahan membentuk ragam visual songket. Bahan dan jenis benang perlu diperiksa pada masing-masing produk yang akan dibeli.",
      },
    ],
    galleryIds: ["pandai-sikek"],
  },
  {
    id: "sumatera-selatan",
    name: "Palembang",
    province: "Sumatera Selatan",
    coordinates: [104.75, -3],
    color: "#b89955",
    landscape: "river",
    tagline: "Aliran sungai, kilau tradisi.",
    introduction:
      "Jelajahi pengenalan Palembang dengan lanskap sungai dan tradisi songketnya. Lihat bagaimana keterampilan benang hias membentuk ragam kain.",
    stories: [
      {
        title: "Kota dan sungainya",
        text: "Sungai Musi merupakan bagian penting lingkungan Palembang. Diorama mengambil inspirasi lanskap sungai sebagai pintu untuk mengenal tradisi kainnya.",
      },
      {
        title: "Mengenal songket",
        text: "Songket Palembang memiliki beragam susunan motif dan bentuk penggunaan. Identitas motif perlu mengikuti informasi pembuat dan sumber yang relevan.",
      },
      {
        title: "Menyusun benang hias",
        text: "Pada songket, benang tambahan membentuk ragam hias di atas struktur dasar tenunan. Kilau tidak selalu menjelaskan bahan yang digunakan; periksa rincian produk.",
      },
    ],
    galleryIds: ["songket"],
  },
  {
    id: "sulawesi-tengah",
    name: "Donggala",
    province: "Sulawesi Tengah",
    coordinates: [119.8, -0.7],
    color: "#608f85",
    landscape: "river",
    tagline: "Benang dari pesisir Sulawesi.",
    introduction:
      "Kenali pengantar tenun Donggala dan lingkungannya di Sulawesi Tengah. Lanjutkan ke galeri untuk mengamati susunan kain dari dekat.",
    stories: [
      {
        title: "Pintu dari pesisir",
        text: "Donggala menjadi salah satu wilayah pengenalan tradisi tenun di Sulawesi Tengah. Praktik serta ragam kain dapat berbeda menurut sentra dan pembuatnya.",
      },
      {
        title: "Melihat ragam kain",
        text: "Warna, bahan, dan struktur kain perlu dikenali bersama. Nama daerah merupakan titik awal, bukan pengganti informasi produk yang lengkap.",
      },
      {
        title: "Keterampilan menenun",
        text: "Benang lungsi dan pakan disusun menjadi bidang kain. Rincian teknik setiap koleksi dapat dipelajari lebih lanjut melalui sumber serta keterangan pembuat.",
      },
    ],
    galleryIds: ["donggala"],
  },
];

export type TextileTradition = {
  id: string;
  galleryId: string;
  regionId: RegionId;
  name: string;
  gallery: Gallery;
  description: string;
  technique: string;
};

export const textileTraditions: TextileTradition[] = galleries.map(
  (gallery) => {
    const region = exploreRegions.find((region) =>
      region.galleryIds.includes(gallery.id),
    )!;
    return {
      id:
        gallery.id === "sumba"
          ? "hinggi-sumba"
          : gallery.id === "bali"
            ? "endek"
            : gallery.id === "lombok"
              ? "sasak"
              : gallery.id,
      galleryId: gallery.id,
      regionId: region.id,
      name: gallery.id === "sumba" ? "Hinggi Sumba" : gallery.name,
      gallery,
      description:
        gallery.id === "sumba"
          ? "Kenali struktur Hinggi, ragam motif figuratif, serta warna Kombu dan Kawuru dalam galeri tiga dimensi."
          : gallery.subtitle,
      technique:
        gallery.id === "gringsing"
          ? "Ikat ganda"
          : gallery.id === "bali"
            ? "Ikat pakan"
            : gallery.technique,
    };
  },
);

export const findExploreRegion = (id: string) =>
  exploreRegions.find((region) => region.id === id);
export const findTradition = (id: string) =>
  textileTraditions.find(
    (tradition) => tradition.id === id || tradition.galleryId === id,
  );
export const regionHref = (id: string) => `/galeri/daerah/${id}`;
export const textileHref = (id: string) =>
  `/galeri/kain/${findTradition(id)?.id ?? id}`;
export const catalogHref = (id: string) =>
  `/katalog/${findTradition(id)?.id ?? id}`;
