import type { Metadata } from "next";
import { CatalogBrowser, type CatalogRecord } from "@/components/CatalogBrowser";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { catalogSamplesForTradition, catalogTraditions } from "@/lib/catalog-data";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { entriesForRegion, regions } from "@/lib/regions";

export const metadata: Metadata = {
  title: "Katalog Kain Nusantara",
  description: "Jelajahi tradisi kain Nusantara dan temukan penawaran dari penjual.",
};

type GalleryDetail = {
  reference_images?: { id?: string; url: string; caption: string | null }[];
  availability?: { listing_count: number; min_price_idr: number | null };
};

async function loadCatalog(): Promise<CatalogRecord[]> {
  let entries: Entry[] = [];
  try {
    entries = (await api<{ items: Entry[] }>("/gallery?limit=100", { token: null })).items;
  } catch { /* Prototype catalog data is still available offline. */ }

  const detailsById = new Map<string, GalleryDetail>();
  const batchSize = 10;
  for (let start = 0; start < entries.length; start += batchSize) {
    const batch = await Promise.all(entries.slice(start, start + batchSize).map(async (entry): Promise<[string, GalleryDetail]> => {
      try {
        const detail = await api<GalleryDetail>(`/gallery/${encodeURIComponent(entry.slug)}`, { token: null });
        return [entry.id, detail];
      } catch {
        return [entry.id, { reference_images: [], availability: { listing_count: 0, min_price_idr: null } }];
      }
    }));
    batch.forEach(([id, detail]) => detailsById.set(id, detail));
  }

  const matchesTradition = (entry: Entry, apiNames: string[]) => {
    const names = [entry.name, ...entry.aliases].map((name) => name.trim().toLocaleLowerCase("id-ID"));
    return apiNames.some((name) => names.includes(name.trim().toLocaleLowerCase("id-ID")));
  };
  const matchedEntryIds = new Set<string>();
  const traditionRecords: CatalogRecord[] = catalogTraditions.map((tradition) => {
    const entry = entries.find((candidate) => matchesTradition(candidate, tradition.apiNames));
    if (entry) matchedEntryIds.add(entry.id);
    const detail = entry ? detailsById.get(entry.id) : undefined;
    return {
      ...tradition,
      summary: tradition.subtitle,
      aliases: tradition.aliases,
      samples: catalogSamplesForTradition(tradition.id),
      entry,
      reference_images: detail?.reference_images ?? [],
      availability: detail?.availability ?? { listing_count: 0, min_price_idr: null },
    };
  });
  const additionalEntries: CatalogRecord[] = await Promise.all(entries
    .filter((entry) => !matchedEntryIds.has(entry.id))
    .map(async (entry) => {
      const detail = detailsById.get(entry.id);
      let listingImages: { id?: string; url: string; caption: string | null }[] = [];
      if ((detail?.reference_images?.length ?? 0) < 3) {
        try {
          const listings = await api<{ items: { images?: { id?: string; url: string; caption: string | null }[] }[] }>(
            `/gallery/${encodeURIComponent(entry.slug)}/listings?limit=3`,
            { token: null },
          );
          listingImages = [...new Map(listings.items.flatMap((listing) => listing.images ?? []).map((image) => [image.url, image])).values()].slice(0, 3);
        } catch { /* Keep the catalog card; the listing may be unpublished. */ }
      }
      return {
        id: `gallery-${entry.slug}`,
        name: entry.name,
        region: entry.region ?? "Nusantara",
        regionId: regions.find((region) => entriesForRegion([entry], region).length > 0)?.id,
        technique: entry.technique,
        summary: entry.summary,
        aliases: entry.aliases,
        samples: [],
        entry,
        reference_images: detail?.reference_images ?? [],
        listing_images: listingImages,
        availability: detail?.availability ?? { listing_count: 0, min_price_idr: null },
      };
    }));

  return [...traditionRecords, ...additionalEntries];
}

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; daerah?: string }>;
}) {
  const [{ q, daerah }, records] = await Promise.all([searchParams, loadCatalog()]);

  return (
    <>
      <Nav />
      <main className="catalog-page">
        <div className="catalog-shell">
          <header className="catalog-intro">
            <h1>Katalog Kain</h1>
            <p>Kenali tekstil Nusantara dan temukan kain dari penjual pilihanmu.</p>
          </header>
          <CatalogBrowser key={`${q ?? ""}:${daerah ?? ""}`} records={records} initialQuery={q ?? ""} initialRegion={daerah ?? ""} />
        </div>
      </main>
      <Footer />
    </>
  );
}
