import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Page } from "@/components/ui";
import { type Listing } from "@/components/ListingCard";
import { VariantOffers } from "@/components/VariantOffers";
import type { GalleryVariant } from "@/lib/variants";
import { ApiError, api, fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { regionExploreHrefForEntry } from "@/lib/regions";

type Passport = {
  entry: Entry;
  story: { body: string; unresolved: string[] } | null;
  citations: { source_id: string; title: string; publisher: string | null; url: string | null; license: string | null; locator: string | null; excerpt: string | null }[];
  reference_images: { url: string; caption: string | null; credit: string | null; license: string | null }[];
  review: { status: string; reviewed_at: string | null; is_demo_seed: boolean };
  notice: string;
};

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  return { title: slug.replaceAll("-", " ") };
}

export default async function EntryPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ variant?: string }> }) {
  const { slug } = await params;
  const { variant } = await searchParams;
  let passport: Passport;
  let listings: Listing[] = [];
  let variants: GalleryVariant[] = [];
  try {
    passport = await api<Passport>(`/gallery/${slug}/passport`, { token: null });
    listings = (await api<{ items: Listing[] }>(`/gallery/${slug}/listings`, { token: null })).items;
    variants = await api<GalleryVariant[]>(`/gallery/${slug}/variants`, { token: null });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const { entry, story, citations, reference_images: refs, review } = passport;
  const facts = [entry.technique, entry.region, entry.community].filter(Boolean).join(" · ");
  return (
    <Page>
      <div className="passport-shell">
      <nav className="catalog-breadcrumb" aria-label="Jejak navigasi"><Link href="/katalog">Katalog kain</Link><span aria-hidden="true">/</span><span>Cerita kain</span></nav>
      <header className="passport-header"><p className="fabric-offers-kicker">Cerita kain</p><h1>{entry.name}</h1>{facts && <p>{facts}</p>}<Link className="btn btn-quiet" href={regionExploreHrefForEntry(entry)}>Jelajahi daerah asal</Link></header>

      <div className="passport-layout">
        <article>
          <h2>Ceritanya</h2>
          {story ? (
            <div className="grid max-w-[62ch] gap-4">
              {story.body.split("\n").map((p, i) => <p key={i}>{p}</p>)}
            </div>
          ) : (
            <p>Cerita untuk entri ini belum tersedia.</p>
          )}
          {review.is_demo_seed && <p className="mt-6 bg-surface p-4 text-base">Entri ini berisi data demo; isi budaya sungguhan berasal dari dataset yang disetujui kurator.</p>}
          {story && story.unresolved.length > 0 && (
            <div className="mt-8">
              <h3 className="mb-3 text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Yang belum terverifikasi</h3>
              <ul className="grid list-disc gap-2 pl-5">{story.unresolved.map((u) => <li key={u}>{u}</li>)}</ul>
            </div>
          )}
        </article>
        <aside>
          {refs.length > 0 && (
            <div className="mb-10 grid gap-4">
              {refs.map((r) => (
                <figure key={r.url} className="m-0">
                  <img src={fileUrl(r.url)} alt={r.caption ?? entry.name} className="w-full object-cover" />
                  <figcaption className="t-small mt-2">{[r.caption, r.credit, r.license].filter(Boolean).join(" · ")}</figcaption>
                </figure>
              ))}
            </div>
          )}
          <h2 className="mb-4 text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Sumber</h2>
          <ul className="grid list-none gap-4 p-0">
            {dedupe(citations).map((c) => (
              <li key={c.source_id} className="text-base">
                {c.url ? <a href={c.url} className="link">{c.title}</a> : c.title}
                <span className="block text-muted">{[c.publisher, c.license].filter(Boolean).join(" · ")}</span>
                {c.excerpt && <span className="mt-1 block">“{c.excerpt}”</span>}
              </li>
            ))}
          </ul>
        </aside>
      </div>
      <p className="mt-8 bg-surface p-4 text-base">{passport.notice}</p>

      <VariantOffers slug={slug} variants={variants} listings={listings} initialVariant={variant} />
      </div>
    </Page>
  );
}

function dedupe<T extends { source_id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((i) => (seen.has(i.source_id) ? false : (seen.add(i.source_id), true)));
}
