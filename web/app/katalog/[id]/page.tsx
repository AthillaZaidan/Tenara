import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CatalogTraditionDetail } from "@/components/CatalogTraditionDetail";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { api } from "@/lib/api";
import { catalogSamplesForTradition, findCatalogTradition } from "@/lib/catalog-data";
import type { Entry } from "@/lib/types";
import type { Listing } from "@/components/ListingCard";
import type { GalleryVariant } from "@/lib/variants";
type Passport = { story: { body: string } | null; review: { is_demo_seed: boolean } };

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const tradition = findCatalogTradition(id);
  return { title: tradition?.name ?? "Katalog kain" };
}

export default async function CatalogTraditionPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ offer?: string; buy?: string; qty?: string; pilihan?: string }> }) {
  const { id } = await params;
  const query = await searchParams;
  const tradition = findCatalogTradition(id);
  if (!tradition) notFound();

  let apiSlug: string | undefined;
  let listings: Listing[] = [];
  let variants: GalleryVariant[] = [];
  let story: Passport | null = null;
  let offersUnavailable = false;
  try {
    const entries = (await api<{ items: Entry[] }>("/gallery?limit=100", { token: null })).items;
    const names = tradition.apiNames.map((name) => name.trim().toLocaleLowerCase("id-ID"));
    const entry = entries.find((candidate) => [candidate.name, ...candidate.aliases]
      .some((name) => names.includes(name.trim().toLocaleLowerCase("id-ID"))));
    if (entry) {
      apiSlug = entry.slug;
      const [offersResult, storyResult, variantsResult] = await Promise.allSettled([
        api<{ items: Listing[] }>(`/gallery/${encodeURIComponent(entry.slug)}/listings?limit=50`, { token: null }),
        api<Passport>(`/gallery/${encodeURIComponent(entry.slug)}/passport`, { token: null }),
        api<GalleryVariant[]>(`/gallery/${encodeURIComponent(entry.slug)}/variants`, { token: null }),
      ]);
      if (offersResult.status === "fulfilled") listings = offersResult.value.items;
      else offersUnavailable = true;
      if (storyResult.status === "fulfilled") story = storyResult.value;
      if (variantsResult.status === "fulfilled") variants = variantsResult.value;
      else offersUnavailable = true;
    }
  } catch {
    // The prototype catalog remains browsable while the API is unavailable.
    offersUnavailable = true;
  }

  return (
    <>
      <Nav />
      <main className="catalog-page">
        <CatalogTraditionDetail
          key={`${tradition.id}:${query.pilihan ?? ""}`}
          tradition={tradition}
          samples={catalogSamplesForTradition(tradition.id)}
          apiSlug={apiSlug}
          listings={listings}
          variants={variants}
          story={story}
          offersUnavailable={offersUnavailable}
          initialOfferId={query.offer}
          initialBuy={query.buy === "1"}
          initialQuantity={query.qty}
          initialSampleCode={query.pilihan}
        />
      </main>
      <Footer />
    </>
  );
}
