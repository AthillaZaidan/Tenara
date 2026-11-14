import type { RegionId } from "./exploration";
import type { JourneyChapter } from "./journey";

type Scene = {
  eyebrow: string;
  title: string;
  lead: string;
  detail: string;
  question: string;
};
type RegionStory = {
  chapters: Record<JourneyChapter, [Scene, Scene]>;
};

export const regionStories: Record<RegionId, RegionStory> = {
  sumba: {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Di tanah sabana Sumba",
          lead: "Di Sumba Timur, kain tidak berdiri sendiri. Ia hidup bersama kampung, keluarga, dan peristiwa yang mempertemukan masyarakat.",
          detail:
            "Rumah beratap tinggi dan padang terbuka sering menjadi pintu mengenal pulau ini. Namun setiap kampung dan komunitas memiliki kisahnya sendiri; diorama ini adalah pengantar, bukan potret satu kampung tertentu.",
          question:
            "Apa yang dapat dibawa selembar kain dari satu keluarga ke keluarga lain?",
        },
        {
          eyebrow: "02 · Hubungan",
          title: "Kain yang ikut hadir",
          lead: "Kain dapat hadir dalam pertukaran, upacara, dan momen penting sepanjang kehidupan.",
          detail:
            "Hinggi dan lau adalah dua bentuk yang dikenal di Sumba. Penggunaannya serta arti ragam hias perlu dilihat melalui komunitas, waktu, dan orang yang membuatnya.",
          question: "Kini ikuti perjalanan benang yang membentuk cerita itu.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Persiapan",
          title: "Pola dimulai sebelum kain",
          lead: "Bayangkan deretan benang lungsi yang direntangkan. Pada ikat lungsi, bagian tertentu diikat sebelum benang dicelup.",
          detail:
            "Ikatan menahan masuknya warna. Setelah dibuka, bagian terang dan gelap pada benang menjadi bekal bagi pola yang kelak tampak di kain.",
          question: "Bagaimana warna pada benang-benang terpisah bertemu?",
        },
        {
          eyebrow: "02 · Penenun",
          title: "Menyatukan yang terpisah",
          lead: "Penenun menyusun benang yang telah diwarnai, lalu menyilangkan pakan untuk membangun bidang kain.",
          detail:
            "Pada Hinggi, figur dan bidang dapat disusun menjadi komposisi yang kaya. Pilihan pewarna, alat, waktu pengerjaan, dan tata letaknya berbeda menurut karya dan pembuatnya.",
          question: "Lihat dua pintu masuk ke bahasa visual Hinggi.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Satu Hinggi, banyak cerita",
          lead: "Hinggi Sumba hadir sebagai kain lembaran dengan bidang-bidang yang dapat memuat beragam figur.",
          detail:
            "Satu helai dapat menampilkan lebih dari satu motif. Karena itu, nama pilihan pada kartu menjadi pintu mengamati satu cerita, bukan daftar seluruh isi kain.",
          question: "Apa yang diceritakan figur kuda dan Andung?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Dari bidang ke detail",
          lead: "Dekati permukaan kain: ikuti pengulangan figur, pertemuan warna, dan batas antara bidang.",
          detail:
            "Kartu berikut memperkenalkan Kuda dan Andung melalui ilustrasi koleksi. Pilih satu untuk membaca kisahnya.",
          question: "Pilih kartu dan temukan kisahnya.",
        },
      ],
    },
  },
  bali: {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Bali, lebih dari satu cerita",
          lead: "Kain hadir dalam berbagai kegiatan masyarakat Bali: dari keseharian hingga peristiwa adat.",
          detail:
            "Mengenal sebuah kain berarti juga mengenal tempat dan masyarakatnya. Jembrana dan Tenganan Pegringsingan, misalnya, menjadi pintu ke dua tradisi berbeda dalam koleksi ini.",
          question: "Bagaimana dua kain dari pulau yang sama dapat berbeda?",
        },
        {
          eyebrow: "02 · Tradisi",
          title: "Jembrana dan Tenganan",
          lead: "Endek dan Gringsing sama-sama dikenal di Bali, tetapi teknik dan ragam penggunaannya tidak bisa disamakan.",
          detail:
            "Di Jembrana, perajin Endek mengembangkan rancangan yang berkaitan dengan lingkungan setempat. Di Tenganan, Gringsing berkaitan dengan tradisi masyarakat desa tersebut.",
          question: "Perbedaannya mulai terlihat sejak benang disiapkan.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Endek",
          title: "Satu arah benang",
          lead: "Pada Endek ikat pakan, benang pakan diberi ikatan dan warna sebelum ditenun.",
          detail:
            "Penenun menyusun bagian yang diwarnai agar bertemu menjadi pola saat benang melintang di antara lungsi. Proses dan alatnya dapat berbeda antarpembuat.",
          question: "Bagaimana jika kedua arah benang dipersiapkan?",
        },
        {
          eyebrow: "02 · Gringsing",
          title: "Dua arah bertemu",
          lead: "Pada Gringsing ikat ganda, lungsi dan pakan sama-sama disiapkan dengan ikatan dan pewarnaan.",
          detail:
            "Ketika ditenun, pola pada dua kelompok benang dipertemukan dengan teliti. Keterampilan ini menjadi bagian penting tradisi Tenganan Pegringsingan.",
          question: "Sekarang bandingkan ragam Endek dan Gringsing.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Dua tradisi",
          title: "Endek dan Gringsing",
          lead: "Di sini kamu akan menemukan Endek Jembrana dan Gringsing Tenganan dalam satu daerah eksplorasi.",
          detail:
            "Mekepung dan Jalak Bali dikenal sebagai nama ragam Endek Jembrana. Wayang Kebo dan Pat Likur Isi adalah nama ragam Gringsing Tenganan.",
          question: "Kain mana yang ingin kamu kenali lebih dekat?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Buka satu per satu",
          lead: "Setiap kartu berangkat dari satu pilihan dalam katalog Tenara.",
          detail:
            "Amati gambar dan baca kisah pilihanmu. Nama motif dan cara penyusunannya tetap mengikuti konteks kain serta pembuatnya.",
          question: "Empat pilihan menunggu untuk dibuka.",
        },
      ],
    },
  },
  lombok: {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Di antara rumah dan benang",
          lead: "Di Sukarara, Lombok Tengah, menenun menjadi bagian dari keterampilan yang diwariskan dalam masyarakat Sasak.",
          detail:
            "Penenun bekerja dengan alat tradisional, merangkai benang menjadi kain yang digunakan dan diperdagangkan. Tradisi di satu desa tidak mewakili seluruh praktik tenun Lombok.",
          question: "Cerita apa yang dapat tumbuh di sekitar alat tenun?",
        },
        {
          eyebrow: "02 · Pembuat",
          title: "Belajar dari tangan ke tangan",
          lead: "Keterampilan menenun diteruskan melalui belajar dan praktik, sekaligus terus menghadapi perubahan kebutuhan pembuat serta pemakai.",
          detail:
            "Ragam visual di Sukarara dapat mengambil inspirasi dari lingkungan sekitar. Menyebut penenun dan sentranya membantu kita memahami kain dengan lebih dekat.",
          question: "Mari mendekat ke prosesnya.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Benang",
          title: "Menyiapkan susunan",
          lead: "Penenun menyiapkan benang dan alat sebelum memulai persilangan lungsi dan pakan.",
          detail:
            "Warna serta bahan dipilih untuk rancangan kain. Sumber tentang Sukarara mencatat penggunaan berbagai bahan dan pewarna; rincian kain tertentu perlu mengikuti pembuatnya.",
          question: "Di mana hiasan mulai terbentuk?",
        },
        {
          eyebrow: "02 · Hiasan",
          title: "Mengisi bidang kain",
          lead: "Pada songket, benang hias tambahan dapat disisipkan untuk membentuk corak di atas tenunan dasar.",
          detail:
            "Pengulangan pekerjaan menuntut perhatian pada posisi benang dan susunan pola. Lama pengerjaan berbeda menurut kain dan kerumitan rancangan.",
          question: "Buka pilihan ragam Sasak pada kartu.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Ragam dari Sukarara",
          lead: "Subahnale dan Rangrang tercantum sebagai dua nama pilihan tenun Sasak dari Sukarara di katalog Tenara.",
          detail:
            "Nama serupa dapat muncul pada konteks tenun berbeda. Sumber yang tersedia belum menjelaskan kedua ragam ini secara spesifik; keterangan penenun Sukarara akan menambah konteksnya.",
          question: "Apa yang dapat kita kenali dari masing-masing pilihan?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Melihat sambil bertanya",
          lead: "Perhatikan bentuk, jarak, dan perulangan pada permukaan kartu kain.",
          detail:
            "Setiap pilihan memiliki kisah awal; ragam yang belum terkonfirmasi dapat dikenali sambil bertanya kepada penenunnya.",
          question: "Balik kartu untuk mulai mengenalinya.",
        },
      ],
    },
  },
  flores: {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Berangkat dari Sikka",
          lead: "Di bagian timur Flores, Sikka menjadi salah satu wilayah dengan tradisi kain ikat yang hidup di tengah masyarakatnya.",
          detail:
            "Flores memiliki banyak komunitas dan tradisi tenun. Cerita Sikka membuka satu pintu, bukan rangkuman seluruh kain di pulau ini.",
          question: "Ke mana selembar kain dapat bepergian?",
        },
        {
          eyebrow: "02 · Hubungan",
          title: "Kain di antara keluarga",
          lead: "Dokumentasi tentang Sikka mencatat peran kain ikat dalam hubungan keluarga dan peristiwa kehidupan.",
          detail:
            "Komunitas dan pembuat dapat memiliki gaya, nama, serta susunan bidang yang berbeda. Untuk memahami satu kain, penting mengetahui siapa dan di mana ia dibuat.",
          question: "Ikuti benang menuju alat tenun.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Ikat",
          title: "Mengikat ruang warna",
          lead: "Sebagian benang diikat sebelum dicelup. Ikatan menjaga bagian tertentu agar tidak menerima warna dengan cara yang sama.",
          detail:
            "Pada contoh ikat lungsi Sikka, benang yang telah disiapkan disusun memanjang untuk membentuk rancangan kain.",
          question: "Kapan susunan itu menjadi pola?",
        },
        {
          eyebrow: "02 · Tenun",
          title: "Bertemu di alat tenun",
          lead: "Penenun mempertemukan susunan benang dengan pakan, satu lintasan demi satu lintasan.",
          detail:
            "Bidang-bidang dan warna pada kain muncul melalui keterampilan penyusunan. Rincian proses dan pewarna mengikuti praktik masing-masing penenun.",
          question: "Kenali dua pilihan Sikka dalam koleksi.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Dua nama dari Sikka",
          lead: "Utan Ruha dan Manu Hutu tercantum sebagai dua nama pilihan kain Sikka di katalog Tenara.",
          detail:
            "Keduanya membuka pintu mengenali ragam Sikka. Penjelasan rinci masih dapat dilengkapi dengan cerita dari komunitas pembuat.",
          question:
            "Apa yang bisa dilihat sebelum kita mengenal seluruh ceritanya?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Perhatikan susunannya",
          lead: "Mulailah dengan mengamati bidang, garis, dan pertemuan warna pada setiap ilustrasi.",
          detail:
            "Pilih kartu untuk membaca pengantar yang tersedia dan mengenali lebih jauh kisah di balik ragamnya.",
          question: "Pilih kartu untuk melihat lebih dekat.",
        },
      ],
    },
  },
  "jawa-tengah": {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Dua sentra",
          title: "Dari Troso hingga Lurik",
          lead: "Dua pintu membawa kita ke keragaman tenun Jawa: Troso di Jepara dan tradisi Lurik yang juga dikenal di Yogyakarta serta Klaten.",
          detail:
            "Keduanya berkembang melalui lingkungan dan perjalanan pembuat yang berbeda. Satu wilayah administratif tidak membatasi seluruh jejak suatu tradisi.",
          question: "Apa yang membuat keduanya mudah dibedakan?",
        },
        {
          eyebrow: "02 · Kehidupan",
          title: "Kain yang dipakai dan dibuat",
          lead: "Lurik dikenal melalui susunan garis, sedangkan perajin Troso mengembangkan berbagai motif ikat dan adaptasi rancangan.",
          detail:
            "Kain hadir sebagai kebutuhan sandang sekaligus hasil keterampilan yang memberi penghidupan. Cara pakai dan rancangan terus berubah bersama masyarakat.",
          question: "Mari ikuti dua cara membangun corak.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Troso",
          title: "Pakan yang diikat",
          lead: "Pada contoh motif khas Troso, pola disiapkan dengan mengikat benang pakan sebelum pencelupan.",
          detail:
            "Setelah diberi warna, pakan ditenun dengan ATBM. Perajin menata benang agar bagian-bagian pola bertemu ketika kain terbentuk.",
          question: "Bagaimana garis Lurik dibangun?",
        },
        {
          eyebrow: "02 · Lurik",
          title: "Irama dalam garis",
          lead: "Pada Lurik, penataan benang dan warna menghadirkan susunan garis atau persilangan yang menjadi corak.",
          detail:
            "Lebar, jarak, serta kombinasi garis membuka banyak kemungkinan. Kesederhanaan tampilan tidak menghapus ketelitian kerja penenunnya.",
          question: "Bandingkan Ampel, Kedawung, dan dua corak Lurik.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Dua cara melihat pola",
          lead: "Ampel dan Kedawung membawa kita ke lingkungan Troso. Telupat dan Tumbar Pecah membuka kisah penamaan dalam Lurik.",
          detail:
            "Keempat pilihan memperlihatkan bahwa satu daerah eksplorasi dapat menjadi rumah bagi beberapa jenis tenun dan banyak cerita.",
          question: "Apakah bentuk alam dapat hadir sebagai garis?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Dekatkan pandangan",
          lead: "Lihat perulangan bentuk pada Troso, lalu bandingkan irama garis dalam Lurik.",
          detail: "Pilih kartu untuk membaca cerita di balik koleksi tersebut.",
          question: "Pilih salah satu kartu untuk memulai.",
        },
      ],
    },
  },
  "sumatera-utara": {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Kain dalam hubungan manusia",
          lead: "Di lingkungan masyarakat Batak, Ulos dikenali bukan hanya dari tenunannya, tetapi juga dari hubungan antara pemberi dan penerima.",
          detail:
            "Ragam dan penggunaan ulos berbeda menurut komunitas dan peristiwa. Kawasan Danau Toba menjadi salah satu pintu untuk mengenal tradisi yang beragam ini.",
          question: "Apa yang ingin disampaikan ketika kain diberikan?",
        },
        {
          eyebrow: "02 · Pemberian",
          title: "Sehelai yang menyertai",
          lead: "Ulos dapat hadir dalam berbagai peristiwa kehidupan dan hubungan kekerabatan.",
          detail:
            "Bentuk pemberian dan ragam yang digunakan mengikuti konteks keluarga dan adat. Cerita satu jenis ulos tidak otomatis berlaku untuk semua jenis lainnya.",
          question: "Sebelum memilih ragamnya, lihat pekerjaan penenun.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Benang",
          title: "Menyusun warna",
          lead: "Benang disiapkan dan ditata sebelum ditenun menjadi kain dengan garis serta bidang yang berbeda.",
          detail:
            "Kapas dikenal sebagai salah satu bahan dalam tradisi Ulos; bahan dan pewarna pada suatu kain dapat berbeda menurut pembuatnya.",
          question: "Bagaimana susunan itu menjadi kain?",
        },
        {
          eyebrow: "02 · Alat",
          title: "Garis demi garis",
          lead: "Penenun menyilangkan lungsi dan pakan untuk membangun bidang kain.",
          detail:
            "Susunan warna dan ragam hias membantu membedakan jenis Ulos. Alat serta cara pengerjaannya dapat berbeda antara penenun dan sentra.",
          question: "Kenali Ragi Hotang dan Sadum.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Ragam",
          title: "Bukan sekadar satu Ulos",
          lead: "Ragi Hotang dan Sadum adalah dua ragam Ulos yang dapat dijelajahi dalam koleksi ini.",
          detail:
            "Nama keduanya merujuk pada ragam kain, bukan semata-mata satu bentuk hias kecil. Setiap ragam hadir dengan konteks penggunaan dan penjelasannya sendiri.",
          question: "Apa perbedaan yang dapat kamu temukan?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Pilih ragamnya",
          lead: "Mulailah dari susunan bidang dan warna, lalu buka kartu untuk membaca konteksnya.",
          detail:
            "Makna dan penggunaan Ulos mengikuti ragam serta konteks komunitas, keluarga, dan peristiwa.",
          question: "Balik kartu untuk membaca lebih jauh.",
        },
      ],
    },
  },
  "sumatera-barat": {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Berangkat dari Pandai Sikek",
          lead: "Di Tanah Datar, Pandai Sikek dikenal sebagai salah satu sentra songket dalam lingkungan budaya Minangkabau.",
          detail:
            "Satu nagari menjadi pintu untuk mengenal kerja penenun, tetapi tidak mewakili seluruh tradisi songket di Sumatera Barat.",
          question: "Apa yang membuat kain dari sini mudah dikenali?",
        },
        {
          eyebrow: "02 · Keterampilan",
          title: "Pengetahuan yang diteruskan",
          lead: "Keterampilan menenun diwariskan dan dipelajari, sementara hasilnya hadir dalam berbagai bentuk busana dan kelengkapan adat.",
          detail:
            "Ragam hias dan cara pengerjaan menjadi bagian dari identitas kain. Bahan benang dan pilihan rancangan juga berubah mengikuti waktu.",
          question: "Dekati benang hiasnya.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Dasar",
          title: "Menyiapkan bidang",
          lead: "Kain songket dibangun dari tenunan dasar dan benang hias tambahan.",
          detail:
            "Penenun menata benang pada alat tenun, lalu menyisipkan benang hias mengikuti rancangan. Hasilnya membuat sebagian pola tampak menonjol pada permukaan.",
          question: "Apakah seluruh bidang selalu dipenuhi hiasan?",
        },
        {
          eyebrow: "02 · Susunan",
          title: "Penuh atau bertabur",
          lead: "Pada Pandai Sikek dikenal susunan balapak dan batabua.",
          detail:
            "Balapak memiliki hiasan yang memenuhi bidang, sedangkan batabua menyebarkan hiasan pada bagian tertentu. Bahan, kepadatan, dan waktu pengerjaan berbeda pada setiap karya.",
          question: "Temui contoh koleksi Pandai Sikek.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Ragam dalam satu songket",
          lead: "Songket Pandai Sikek memiliki banyak nama ragam hias, dari Saik Kalamai sampai Tampuak Manggih.",
          detail:
            "Pilihan dalam katalog ini memperkenalkan koleksinya secara umum; nama motif pada contoh kain belum dibedakan dalam daftar final.",
          question: "Apa yang bisa kita amati dari susunannya?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Kilau dan bidang",
          lead: "Perhatikan bagaimana bidang dasar dan hiasan membangun irama pada kain.",
          detail:
            "Buka kartu untuk membaca pengantar koleksi dan mengenali ragam songket lebih dekat.",
          question: "Ada satu kartu untuk dibuka.",
        },
      ],
    },
  },
  "sumatera-selatan": {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Palembang dan kainnya",
          lead: "Dari lingkungan sungai dan kehidupan kota Palembang, kita berangkat mengenal salah satu tradisi songket Nusantara.",
          detail:
            "Songket menjadi bagian dari berbagai bentuk busana dan peristiwa. Ragamnya tumbuh melalui keterampilan pembuat dan perjumpaan budaya yang panjang.",
          question: "Bagaimana perjumpaan itu terlihat pada kain?",
        },
        {
          eyebrow: "02 · Ragam",
          title: "Pertemuan dalam hiasan",
          lead: "Nama dan bentuk ragam hias menyimpan jejak cerita yang berbeda-beda.",
          detail:
            "Dalam peliputan koleksi Museum Balaputra Dewa, Bungo Cino dikaitkan dengan perjumpaan budaya Tionghoa dan Palembang. Pemaknaan suatu kain tetap perlu dilihat dalam konteksnya.",
          question: "Mari lihat bagaimana hiasan disusun.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Dasar",
          title: "Di atas kain dasar",
          lead: "Tenun songket mempertemukan benang dasar dengan benang hias tambahan.",
          detail:
            "Penenun mengatur urutan benang pada alat untuk membentuk bidang kain, lalu menyisipkan hiasan mengikuti susunan yang diinginkan.",
          question: "Apa yang membuat hiasannya tampak berkilau?",
        },
        {
          eyebrow: "02 · Hiasan",
          title: "Kilau yang disusun",
          lead: "Benang hias menghasilkan permukaan yang dapat tampak berkilau dan berpola rapat atau tersebar.",
          detail:
            "Kilau saja tidak menjelaskan bahan benangnya. Bahan dan teknik spesifik suatu kain perlu mengikuti keterangan pembuat atau penjual.",
          question: "Lihat dua nama dalam Songket Palembang.",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Nago dan bunga",
          lead: "Nago Besaung dan Bungo Cino adalah dua pilihan untuk mulai mengenal ragam Songket Palembang.",
          detail:
            "Sebuah nama motif dapat membawa kisah dan penafsiran yang berubah menurut tempat maupun masa. Keduanya menjadi pintu, bukan keseluruhan ragam Palembang.",
          question: "Cerita mana yang ingin kamu buka?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Membaca hiasannya",
          lead: "Amati hubungan motif dengan bidang dasar dan benang hias pada gambar.",
          detail:
            "Balik kartu untuk membaca pengantar berdasarkan peliputan koleksi Museum Balaputra Dewa.",
          question: "Pilih satu kartu untuk mulai.",
        },
      ],
    },
  },
  "sulawesi-tengah": {
    chapters: {
      culture: [
        {
          eyebrow: "01 · Tempat",
          title: "Dari pesisir Donggala",
          lead: "Donggala menjadi pintu mengenal tenun dan sarung yang hidup di Sulawesi Tengah.",
          detail:
            "Cerita kain berhubungan dengan sentra, penenun, dan masyarakat pemakainya. Ragam di satu tempat tidak otomatis mewakili seluruh Sulawesi Tengah.",
          question: "Siapa yang menjaga keterampilan ini?",
        },
        {
          eyebrow: "02 · Pembuat",
          title: "Penenun dan kain",
          lead: "Penenun meneruskan keterampilan sambil menghadirkan kain untuk berbagai kebutuhan masa kini.",
          detail:
            "Koleksi dalam perjalanan ini berangkat dari pengenalan tenun Donggala dan contoh ragam Subi Sulawesi Tengah. Lokasi spesifik tiap kain tetap mengikuti keterangan pembuat.",
          question: "Mendekatlah ke pekerjaan benangnya.",
        },
      ],
      weaving: [
        {
          eyebrow: "01 · Benang",
          title: "Membangun bidang",
          lead: "Sehelai kain dimulai dari benang yang ditata pada alat tenun.",
          detail:
            "Lungsi dan pakan disilangkan untuk membentuk kain dasar. Bahan, alat, dan cara pembuatannya dapat berbeda menurut pembuat dan jenis kain.",
          question: "Bagaimana hiasan ditempatkan?",
        },
        {
          eyebrow: "02 · Ragam",
          title: "Hiasan pada tenunan",
          lead: "Subi dikenal sebagai salah satu ragam tenun hias di Sulawesi Tengah.",
          detail:
            "Bunga Bomba dan Bunga Ketupat dikenal sebagai ragam tenun hias Sulawesi Tengah. Bahan dan pewarna dapat berbeda menurut pembuatnya.",
          question: "Dua bunga apa yang akan kamu temukan?",
        },
      ],
      textiles: [
        {
          eyebrow: "01 · Koleksi",
          title: "Bunga pada kain",
          lead: "Bunga Bomba dan Bunga Ketupat menjadi dua pilihan dalam koleksi Donggala Tenara.",
          detail:
            "Nama dan penjelasan awal memperkenalkan ragam Subi Sulawesi Tengah. Sentra pembuat pada contoh kain ini masih perlu dipastikan.",
          question: "Apa kisah yang disampaikan di balik nama itu?",
        },
        {
          eyebrow: "02 · Amati",
          title: "Temukan dua ragam",
          lead: "Amati perbedaan susunan bentuk pada kedua kartu, lalu pilih salah satunya.",
          detail: "Pilih salah satu kartu untuk membaca pengantar ceritanya.",
          question: "Balik kartu untuk mengenal motifnya.",
        },
      ],
    },
  },
};
