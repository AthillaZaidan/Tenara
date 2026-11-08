import type { Metadata } from "next";
import { Page } from "@/components/ui";
import { GallerySearch } from "@/components/GallerySearch";
import { loadEntries } from "@/lib/types";

export const metadata: Metadata = { title: "Gallery" };

export default async function GalleryPage() {
  const entries = await loadEntries();
  return (
    <Page>
      <h1 className="t-head mb-6 mt-8 max-w-[16ch]">Gallery tenun</h1>
      <p className="mb-12 max-w-[52ch]">Setiap entri disusun dari sumber yang disetujui kurator. Bagian yang belum terverifikasi ditandai, bukan disembunyikan.</p>
      <div className="max-w-3xl"><GallerySearch entries={entries} /></div>
    </Page>
  );
}
