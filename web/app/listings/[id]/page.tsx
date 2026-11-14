import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Footer } from "@/components/Footer";
import { ListingProductDetail, type ListingDetailData } from "@/components/ListingProductDetail";
import { Nav } from "@/components/Nav";
import { ApiError, api } from "@/lib/api";
import { catalogSamplesForTradition, catalogTraditions } from "@/lib/catalog-data";
import type { GalleryVariant } from "@/lib/variants";

export const metadata: Metadata = { title: "Kain" };

export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let listing: ListingDetailData;
  try {
    listing = await api<ListingDetailData>(`/listings/${id}`, { token: null });
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  const tradition = listing.gallery_entry && catalogTraditions.find((item) => item.apiNames.some((name) => name.trim().toLocaleLowerCase("id-ID") === listing.gallery_entry?.name.trim().toLocaleLowerCase("id-ID")));
  if (tradition && listing.gallery_entry && listing.variant_id) {
    let canRedirect = false;
    try {
      const slug = encodeURIComponent(listing.gallery_entry.slug);
      const [variants, offers] = await Promise.all([
        api<GalleryVariant[]>(`/gallery/${slug}/variants`, { token: null }),
        api<{ items: { id: string }[] }>(`/gallery/${slug}/listings?limit=50`, { token: null }),
      ]);
      const variant = variants.find((item) => item.id === listing.variant_id);
      const matches = variant && catalogSamplesForTradition(tradition.id).filter((sample) => sample.motif.trim().toLocaleLowerCase("id-ID") === variant.name.trim().toLocaleLowerCase("id-ID"));
      const matchingVariants = variant && variants.filter((item) => item.name.trim().toLocaleLowerCase("id-ID") === variant.name.trim().toLocaleLowerCase("id-ID"));
      canRedirect = !!matches && matches.length === 1 && matchingVariants?.length === 1 && offers.items.some((item) => item.id === listing.id);
    } catch {
      // Keep the offer accessible if the catalog data cannot be loaded.
    }
    if (canRedirect) redirect(`/katalog/${tradition.id}?offer=${encodeURIComponent(listing.id)}#listings`);
  }
  return (
    <>
      <Nav />
      <main className="catalog-page">
        <ListingProductDetail listing={listing} />
      </main>
      <Footer />
    </>
  );
}
