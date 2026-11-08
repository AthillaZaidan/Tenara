import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { Credits } from "@/components/Credits";
import { GallerySearch } from "@/components/GallerySearch";
import { LitNames } from "@/components/LitNames";
import { loadEntries } from "@/lib/types";

const STAGES = [
  { verb: "Kenali", img: "/img/ikat-1.jpg", text: "Setiap entri Gallery menyusun cerita hanya dari sumber yang sudah disetujui kurator, lengkap dengan kutipan dan bagian yang belum terverifikasi." },
  { verb: "Pilih", img: "/img/ikat-3.jpg", text: "Bandingkan penjual terverifikasi untuk kain yang sama: harga, lebar, stok utuh terpanjang, dan klaim asal-usul yang dipisahkan dari verifikasi kurator." },
  { verb: "Rancang", img: "/img/ikat-4.jpg", text: "Pilih salah satu dari lima pola pakaian, ubah lewat kalimat biasa, isi ukuran badan, dan lihat berapa meter kain yang benar-benar dibutuhkan." },
  { verb: "Jahit", img: "/img/songket.jpg", text: "Penjahit yang cocok mengonfirmasi desain, memberi penawaran terperinci, dan kain Anda dikirim langsung dari penjual ke penjahit." },
];

export default async function Home() {
  const entries = await loadEntries();
  const regions = [...new Set(entries.map((e) => e.region).filter(Boolean) as string[])];
  return (
    <>
      <Nav />
      <main>
        {/* Hero: the sentence is the layout; the strip of cloth stands in for the word "kain". */}
        <section className="frame flex min-h-[calc(100svh-84px)] flex-col justify-center pb-16 pt-6">
          <h1 className="t-display" style={{ fontSize: "clamp(40px, 12.4vw, 220px)" }}>
            <span className="flex items-baseline gap-[0.12em]">
              <span>Setiap</span>
              <span
                role="img"
                aria-label="Kain tenun ikat Sumba, arsip KITLV"
                className="rise block flex-1 self-center"
                style={{ height: "0.62em", backgroundImage: "url(/img/ikat-2.jpg)", backgroundSize: "165%", backgroundPosition: "50% 36%", borderRadius: 14 }}
              />
            </span>
            <span className="block">punya cerita</span>
          </h1>
          <div className="mt-10 grid gap-8 md:grid-cols-12">
            <p className="max-w-[44ch] md:col-span-6">
              Pelajari asal-usul tenun dari sumber yang dikurasi, bandingkan penjual terverifikasi, lalu beli kainnya atau jadikan baju bersama penjahit.
            </p>
            <div className="md:col-span-6 md:flex md:justify-end md:items-start">
              <Link href="/gallery" className="btn no-underline">Jelajahi Gallery</Link>
            </div>
          </div>
        </section>

        {/* Showcase: object in front of type */}
        <section className="relative overflow-hidden py-[clamp(96px,14vw,200px)]">
          <div className="frame relative">
            <p aria-hidden className="t-display m-0 whitespace-nowrap text-muted" style={{ fontSize: "clamp(56px, 9vw, 150px)", lineHeight: 0.88 }}>Bukan sekadar</p>
            <h2 className="t-display whitespace-nowrap" style={{ fontSize: "clamp(56px, 9vw, 150px)", lineHeight: 0.88, fontWeight: 100 }}>kain bermotif</h2>
            <p aria-hidden className="t-display m-0 whitespace-nowrap text-muted" style={{ fontSize: "clamp(56px, 9vw, 150px)", lineHeight: 0.88 }}>punya asal-usul</p>
            <div className="mt-24 grid gap-6 md:mt-32 md:grid-cols-12">
              <img
                src="/img/songket.jpg"
                alt="Selendang songket limar dari Palembang, benang emas pada sutra, abad ke-19"
                className="rise w-full max-w-[520px] object-cover md:col-span-4"
                style={{ aspectRatio: "3 / 4", objectPosition: "50% 22%" }}
              />
              <div className="grid content-end gap-5 md:col-span-5 md:col-start-8">
                <p className="rise">Tenara mempertemukan tiga hal yang biasanya terpisah: cerita budaya yang bisa diperiksa sumbernya, penjual kain yang sudah diverifikasi, dan penjahit yang cocok dengan desain Anda.</p>
                <p className="rise" style={{ ["--d" as string]: "80ms" }}>Yang belum pasti ditandai sebagai belum pasti. Yang diklaim penjual tidak pernah disamakan dengan yang diverifikasi kurator.</p>
              </div>
            </div>
          </div>
        </section>

        {/* How it works: one verb at a time */}
        <section aria-label="Cara kerja Tenara">
          {STAGES.map((s) => (
            <div key={s.verb} className="relative h-svh overflow-hidden" style={{ backgroundImage: `url(${s.img})`, backgroundSize: "cover", backgroundPosition: "center" }}>
              <div className="absolute inset-0" style={{ background: "rgba(53,26,43,0.52)" }} />
              <div className="absolute inset-0">
                <div className="sticky top-0 flex h-svh items-center justify-center">
                  <h2 className="t-display text-center" style={{ fontSize: "clamp(88px, 17vw, 300px)", color: "#edccbe", fontWeight: 300 }}>{s.verb}</h2>
                </div>
              </div>
              <p className="frame absolute bottom-0 left-0 z-10 m-0 max-w-[46ch] pb-8 text-base sm:text-lg" style={{ color: "#edccbe" }}>
                <span className="block p-4" style={{ background: "rgba(53,26,43,0.78)" }}>{s.text}</span>
              </p>
            </div>
          ))}
        </section>

        {/* List: the Gallery, with the search */}
        <section id="gallery" className="py-[clamp(96px,14vw,200px)]">
          <div className="frame">
            <h2 className="t-head max-w-[18ch] md:pl-[3vw]" style={{ fontSize: "clamp(40px, 4.5vw, 68px)", lineHeight: 0.98 }}>
              {entries.length ? `${entries.length} kain yang sudah punya cerita` : "Kain yang sudah punya cerita"}
            </h2>
            <div className="mt-16 grid gap-10 md:mt-24 md:grid-cols-12">
              <div className="hidden md:col-span-4 md:flex md:items-end">
                <img src="/img/ikat-3.jpg" alt="Kain ikat laoe komboe dari Sumba, arsip KITLV" className="rise w-[22vw] object-cover" style={{ aspectRatio: "4 / 5" }} />
              </div>
              <div className="md:col-span-6 md:col-start-7"><GallerySearch entries={entries} /></div>
            </div>
          </div>
        </section>

        {/* Proof: the regions, as one sentence */}
        {regions.length > 0 && (
          <section className="frame pb-[clamp(96px,14vw,200px)]">
            <p className="t-statement m-0 max-w-[36ch] md:max-w-none" style={{ fontSize: "clamp(1.5rem, 1.2rem + 1vw, 2.25rem)" }}>
              <span className="text-ink">Gallery saat ini menelusuri: </span>
              <LitNames names={regions} />
            </p>
          </section>
        )}

        {/* The idea again, inverted */}
        <section className="on-field relative flex min-h-[90svh] flex-col justify-between bg-field text-field-ink">
          <h2 className="t-display frame pt-[clamp(48px,8vw,120px)]" style={{ fontSize: "clamp(40px, 10vw, 170px)", lineHeight: 0.9, fontWeight: 100 }}>
            Dari motif<br />sampai jahitan
          </h2>
          <div className="frame grid items-end gap-6 pb-10 md:grid-cols-12">
            <p className="md:col-span-5">Pilih kainnya, rancang bajunya, dan biarkan penjahit yang cocok mengerjakannya, dengan harga rinci sebelum Anda membayar.</p>
            <div className="md:col-span-3 md:col-start-10"><Link href="/gallery" className="btn w-full no-underline">Pilih kain</Link></div>
          </div>
        </section>
      </main>
      <Footer credits={<Credits />} />
    </>
  );
}
