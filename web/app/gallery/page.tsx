import type { Metadata } from "next";
import { Page } from "@/components/ui";
import { GallerySearch } from "@/components/GallerySearch";
import { loadEntries } from "@/lib/types";

export const metadata: Metadata = { title: "Gallery" };

export default async function GalleryPage() {
  const entries = await loadEntries();
  return (
    <Page>
      <h1 className="t-display rise mb-12 mt-8" style={{ fontSize: "clamp(48px, 10vw, 160px)" }}>Gallery tenun</h1>
      <div className="grid gap-12 md:grid-cols-12">
        <div className="md:col-span-6">
          <p className="rise mb-10 max-w-[48ch]">Setiap entri disusun dari sumber yang disetujui kurator. Bagian yang belum terverifikasi ditandai, bukan disembunyikan.</p>
          <div className="rise" style={{ ["--d" as string]: "120ms" }}><GallerySearch entries={entries} /></div>
        </div>
        <img src="/img/ikat-3.jpg" alt="Kain ikat laoe komboe dari Sumba, arsip KITLV" className="rise w-full object-cover md:col-span-5 md:col-start-8" style={{ aspectRatio: "4 / 5" }} />
      </div>
      <div className="mt-[clamp(72px,10vw,140px)] grid grid-cols-3 gap-4">
        {[["/img/ikat-1.jpg", "Ikat Sumba, arsip KITLV"], ["/img/ikat-4.jpg", "Ikat dengan warna merah, arsip KITLV"], ["/img/songket.jpg", "Selendang songket limar, Palembang"]].map(([src, alt], i) => (
          <img key={src} src={src} alt={alt} className="rise aspect-[3/4] w-full object-cover" style={{ ["--d" as string]: `${i * 90}ms` }} />
        ))}
      </div>
    </Page>
  );
}
