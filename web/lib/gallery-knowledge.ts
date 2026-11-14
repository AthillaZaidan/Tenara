type CollectionKnowledge = {
  introduction: string;
  technique: string;
};
type SampleKnowledge = {
  story: string;
  sources: { title: string; publisher: string; url: string }[];
};

// Sources read on 14 November 2026. Maker interpretations are attributed in the
// copy rather than presented as universal meanings of a regional tradition.
const motifSources = {
  sumba: { title: "Perempuan Adat Sumba Menulis Lewat Tenunan", publisher: "AMAN", url: "https://www.aman.or.id/news/read/1803" },
  andung: { title: "Textile, As1949,10.1 — catatan motif andung", publisher: "British Museum", url: "https://www.britishmuseum.org/collection/object/A_As1949-10-1" },
  endek: { title: "Penggunaan Endek Bali Keberpihakan Ekonomi Lokal", publisher: "NusaBali", url: "https://www.nusabali.com/berita/90709/penggunaan-endek-bali-keberpihakan-ekonomi-lokal" },
  gringsing: { title: "Kain Gringsing — ragam dan teknik", publisher: "Perpustakaan Digital Budaya Indonesia", url: "https://budaya-indonesia.org/kain-gringsing" },
  subahnale: { title: "Tenun Subahnale, dari Animisme Hindu Islam hingga Kewajiban Perempuan Sasak", publisher: "Museum Negeri NTB", url: "https://museumnegeri.ntbprov.go.id/index.php/tulisan/64" },
  rangrang: { title: "Kain Tenun Khas Pulau Lombok", publisher: "Oleh-Oleh Khas Lombok", url: "https://oleholehkhaslombok.net/kain-tenun-khas-pulau-lombok/" },
  utanRuha: { title: "Utan Ruha — tenun ikat Sikka, Watubo", publisher: "Noesa / Watubo", url: "https://noesa.co.id/products/utan-ruha-sarong-288-x-87-tenun-ikat-sikka-flores-natural-dye-watubo" },
  sikka: { title: "Motif Sarung Sikka dan Maknanya", publisher: "Tokotenun", url: "https://www.tokotenun.com/pt/motif-sarung-sikka-dan-maknanya/" },
  troso: { title: "Tenun Troso Jepara: Asal-usul, Motif, dan Proses Pembuatannya", publisher: "Indonesia Travel", url: "https://www.indonesia.travel/id/id/travel-ideas/culture/tenun-troso" },
  lurik: { title: "Lurik Indonesia, Berkembang Mengikuti Zaman", publisher: "Universitas Negeri Yogyakarta", url: "https://www.uny.ac.id/id/berita/lurik-indonesia-berkembang-mengikuti-zaman" },
  ulos: { title: "Ulos: Kain Tradisional Batak yang Penuh Makna dan Filosofi", publisher: "Indonesia Travel", url: "https://www.indonesia.travel/id/id/travel-ideas/heritage/tak-hanya-memesona-5-kain-ulos-khas-danau-toba-ini-juga-sarat-makna" },
  pandaiSikek: { title: "Songket Pandai Sikek, Ratu Kain Tenun dari Sumatra Barat", publisher: "Indonesia Kaya", url: "https://indonesiakaya.com/pustaka-indonesia/songket-pandai-sikek-ratu-kain-tenun-dari-sumatra-barat/" },
  palembang: { title: "Aneka Motif Cantik Kain Songket Palembang — koleksi Museum Balaputra Dewa", publisher: "detikTravel", url: "https://travel.detik.com/domestic-destination/d-3103467/aneka-motif-cantik-kain-songket-palembang" },
  bomba: { title: "Tenun Subi Sulawesi Tengah Motif Bunga Bomba", publisher: "Tenun Alhikmah / KKI Bank Indonesia", url: "https://www.karyakreatifindonesia.co.id/umkm/tenun-alhikmah/39052" },
  ketupat: { title: "Tenun Subi Sulawesi Tengah Motif Bunga Ketupat", publisher: "Tenun Alhikmah / KKI Bank Indonesia", url: "https://www.karyakreatifindonesia.co.id/umkm/tenun-alhikmah/57115" },
};

export const collectionKnowledge: Record<string, CollectionKnowledge> = {
  "hinggi-sumba": {
    introduction:
      "Hinggi adalah kain lembaran yang dikenal dalam tradisi Sumba Timur. Susunan bidang dan ragam hiasnya mempertemukan keterampilan penenun dengan kisah masyarakat setempat.",
    technique:
      "Dalam tradisi Hinggi ikat lungsi, bagian benang lungsi diikat sebelum dicelup dan ditenun. Warna dan pengerjaan berbeda menurut kain dan pembuatnya.",
  },
  endek: {
    introduction:
      "Endek merupakan kain tenun Bali. Di Jembrana, penenun mengembangkan ragam yang berkaitan dengan lingkungan dan kehidupan daerahnya.",
    technique:
      "Pada ikat pakan, bagian benang pakan diikat dan diberi warna sebelum ditenun. Penenun menyusun benang agar pola bertemu saat kain terbentuk.",
  },
  gringsing: {
    introduction:
      "Gringsing dari Tenganan Pegringsingan di Karangasem dikenal dengan ragam kain dan penggunaan dalam kehidupan adat masyarakat setempat.",
    technique:
      "Ikat ganda mengikat dan mewarnai benang lungsi serta pakan sebelum keduanya ditenun. Pertemuan kedua susunan benang membentuk pola.",
  },
  sasak: {
    introduction:
      "Di Sukarara, Lombok Tengah, keterampilan menenun diwariskan melalui praktik para penenun Sasak. Corak dan bahan beragam menurut kain serta pembuatnya.",
    technique:
      "Benang lungsi dan pakan disilangkan pada alat tenun. Pada songket, benang hias tambahan dapat membentuk ragam visual di atas tenunan dasar.",
  },
  sikka: {
    introduction:
      "Tenun ikat dari Sikka di Flores memiliki ragam yang berbeda antarkomunitas. Kain hadir dalam berbagai hubungan keluarga dan peristiwa kehidupan.",
    technique:
      "Pada ikat lungsi, bagian benang yang diikat menahan warna saat pencelupan. Susunan benang kemudian mempertemukan pola ketika ditenun.",
  },
  troso: {
    introduction:
      "Tenun Troso berkembang di Desa Troso, Jepara. Perajin mengolah motif yang berangkat dari lingkungan setempat maupun inspirasi daerah lain.",
    technique:
      "Pada motif khas Troso, benang pakan diikat sebelum pencelupan, lalu ditenun menggunakan ATBM.",
  },
  lurik: {
    introduction:
      "Lurik dikenal melalui irama garis yang ditenun. Tradisinya dijumpai di lingkungan budaya Jawa, termasuk Yogyakarta dan Klaten.",
    technique:
      "Susunan dan warna benang membentuk garis atau persilangan pada kain. Corak dapat berbeda menurut penataan benang dan penenunnya.",
  },
  ulos: {
    introduction:
      "Ulos memiliki beragam jenis dalam kehidupan masyarakat Batak. Penggunaan serta pemberiannya mengikuti komunitas, hubungan keluarga, dan peristiwa.",
    technique:
      "Penenun menyilangkan benang lungsi dan pakan pada alat tenun. Susunan benang membentuk warna, garis, dan ragam hias yang berbeda pada setiap jenis ulos.",
  },
  "pandai-sikek": {
    introduction:
      "Songket Pandai Sikek berasal dari sentra tenun di Tanah Datar, Sumatera Barat. Ragam hiasnya tumbuh dalam tradisi masyarakat Minangkabau.",
    technique:
      "Benang hias disisipkan pada tenunan dasar. Pada balapak, hiasan memenuhi bidang kain; pada batabua hiasan tersebar di bagian tertentu.",
  },
  songket: {
    introduction:
      "Songket Palembang dikenal melalui ragam hias dan keterampilan menempatkan benang hias di atas kain dasar. Berbagai jenis kain digunakan dalam konteks yang berbeda.",
    technique:
      "Penenun menyusun dan menyisipkan benang hias untuk membangun pola. Jenis benang, alat, serta kepadatan hias berbeda pada masing-masing kain.",
  },
  donggala: {
    introduction:
      "Kain tenun Donggala dan sekitarnya dikenal melalui ragam tenun hias Sulawesi Tengah. Buya atau sarung hadir dalam berbagai susunan hias dan bahan.",
    technique:
      "Subi merupakan salah satu ragam tenun hias yang dikenal di Sulawesi Tengah. Rincian bahan, pewarna, dan sentra perlu mengikuti penenun tiap kain.",
  },
};

export const sampleKnowledge: Record<string, SampleKnowledge> = {
  "SUM-01": {
    story:
      "Figur kuda pada Hinggi Sumba Timur melambangkan keberanian, kebanggaan, dan kedudukan sosial. Polanya dibentuk lewat benang yang diikat serta diwarnai sebelum ditenun.",
    sources: [motifSources.sumba],
  },
  "SUM-02": {
    story:
      "Andung, pohon tengkorak pada tenun ikat Sumba, merekam sejarah perang masa lalu. Dalam catatan museum, cabang berujung bentuk kepala berkaitan dengan perlindungan kampung dan kemakmuran.",
    sources: [motifSources.andung],
  },
  "BAL-01": {
    story:
      "Endek Jembrana mengangkat Makepung, tradisi balap kerbau dari kehidupan pertanian. Dalam ikat pakan, benang diwarnai dahulu, lalu disusun saat ditenun hingga membentuk ragam khas daerah ini.",
    sources: [motifSources.endek],
  },
  "BAL-02": {
    story:
      "Jalak putih atau Jalak Bali menjadi ragam khas Endek Jembrana. Sosok burung dibentuk melalui ikat pakan, mempertemukan kekayaan fauna Bali dengan keterampilan penenun mengatur warna benang.",
    sources: [motifSources.endek],
  },
  "BAL-03": {
    story:
      "Wayang Kebo menghadirkan sosok wayang lelaki pada Gringsing Tenganan. Ikat ganda mempertemukan pola pada benang lungsi dan pakan yang sama-sama diikat serta diwarnai sebelum ditenun.",
    sources: [motifSources.gringsing],
  },
  "BAL-04": {
    story:
      "Hiasan Gringsing Isi memenuhi bidang kain tanpa ruang kosong. Pat Likur merujuk pada kelompok ukurannya. Kain ikat ganda dari Tenganan ini dikenal sebagai sarana upacara.",
    sources: [motifSources.gringsing],
  },
  "LOM-01": {
    story:
      "Songket Sasak dengan bidang segi enam menyerupai sarang lebah dan isian bunga. Dalam cerita masyarakat, nama Subahnale berasal dari ‘Subhanallah’, seruan takjub pada keindahan tenunan.",
    sources: [motifSources.subahnale],
  },
  "LOM-02": {
    story:
      "Zig-zag, belah ketupat, dan warna tegas menjadi ciri Rangrang; namanya merujuk pada celah kecil tenunan. Ragam dari Nusa Penida ini juga diadaptasi penenun Lombok.",
    sources: [motifSources.rangrang],
  },
  "SIK-01": {
    story:
      "Utan adalah sarung perempuan Sikka; Utan Ruha juga hadir dalam koleksi Watubo, Flores. Ragam hias ikat disiapkan dengan mengikat dan mewarnai benang sebelum ditenun menjadi kain.",
    sources: [motifSources.utanRuha, motifSources.sikka],
  },
  "SIK-02": {
    story:
      "Manu Hutu menggambarkan induk ayam yang dikelilingi empat anaknya. Pada sarung ikat Sikka, susunan figur ini dimaknai sebagai perlindungan, membawa kisah pengasuhan ke dalam kain.",
    sources: [motifSources.sikka],
  },
  "JTG-01": {
    story:
      "Padi, kubah masjid, dan garis geometris menggambarkan kehidupan agraris serta keagamaan di Troso. Motif Ampel dibentuk melalui ikat pakan, lalu ditenun dengan alat tenun bukan mesin.",
    sources: [motifSources.troso],
  },
  "JTG-02": {
    story:
      "Kapas, pohon bambu, dan gedheg atau anyaman bambu menginspirasi Kedawung. Motif ikat pakan Troso ini mengolah lingkungan serta kegiatan kerajinan setempat menjadi susunan geometris berulang.",
    sources: [motifSources.troso],
  },
  "JTG-03": {
    story:
      "Telupat menyusun garis tiga dan empat: telu dan papat dalam bahasa Jawa. Jumlah tujuh atau pitu dikaitkan dengan pitulungan dan pitutur, harapan akan pertolongan serta nasihat baik.",
    sources: [motifSources.lurik],
  },
  "JTG-04": {
    story:
      "Persilangan garis Lurik Tumbar Pecah mengingatkan pada biji ketumbar yang dibelah. Seperti aromanya saat pecah, corak ini membawa harapan agar pemakainya berguna dan mengharumkan nama baik.",
    sources: [motifSources.lurik],
  },
  "BTK-01": {
    story:
      "Hotang berarti rotan, merujuk pada motif yang menyerupai jalinannya. Ulos Batak ini hadir dalam pernikahan sebagai pemberian adat dan restu keluarga, mengikuti hubungan kekerabatan setempat.",
    sources: [motifSources.ulos],
  },
  "BTK-02": {
    story:
      "Warna cerah dan susunan hias yang ramai menjadi ciri Sadum. Jenis ulos Batak ini kerap dipakai sebagai selendang pernikahan, dengan pola benang yang membangun irama pada bidang kain.",
    sources: [motifSources.ulos],
  },
  "MIN-01": {
    story:
      "Benang tambahan berkilau membentuk hiasan Songket Pandai Sikek. Pada balapak, hiasan memenuhi bidang; pada batabua, hiasan tersebar. Ragam khasnya antara lain batang pinang dan bijo bayam.",
    sources: [motifSources.pandaiSikek],
  },
  "PLB-01": {
    story:
      "Dua sosok naga menjadi ciri Nago Besaung pada Songket Palembang. Menurut penjelasan koleksi Museum Balaputra Dewa, ragam berbenang hias ini berkaitan dengan kekuasaan, kejayaan, dan kemakmuran.",
    sources: [motifSources.palembang],
  },
  "PLB-02": {
    story:
      "Bungo Cino berarti bunga Cina. Bunga berbenang hias berkilau memperlihatkan perjumpaan budaya Tionghoa dan Palembang. Koleksi museum mencatat paduan merah dan emas sebagai salah satu cirinya.",
    sources: [motifSources.palembang],
  },
  "DGL-01": {
    story:
      "Bunga Bomba menghiasi Tenun Subi Sulawesi Tengah. Menurut Tenun Alhikmah, motif ini melambangkan cinta tulus, kesetiaan, dan harmoni dalam hubungan dengan keluarga, sesama, serta alam.",
    sources: [motifSources.bomba],
  },
  "DGL-02": {
    story:
      "Menurut Tenun Alhikmah, Bunga Ketupat pada Tenun Subi melambangkan kesungguhan membangun keluarga. Motif ini juga dimaknai sebagai ikatan dua keluarga yang saling menghormati dan menjaga kebersamaan.",
    sources: [motifSources.ketupat],
  },
};
