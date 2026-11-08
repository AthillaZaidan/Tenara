import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Page } from "@/components/ui";
import { ListingCard, type Listing } from "@/components/ListingCard";
import { ApiError, api, fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";

type Passport = {
  entry: Entry;
  story: { body: string; unresolved: string[] } | null;
  citations: { source_id: string; title: string; publisher: string | null; url: string | null; license: string | null; locator: string | null; excerpt: string | null }[];
  reference_images: { url: string; caption: string | null; credit: string | null; license: string | null }[];
  review: { status: string; reviewed_at: string | null; is_demo_seed: boolean };
};

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  return { title: slug.replaceAll("-", " ") };
}

export default async function EntryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let passport: Passport;
  let listings: Listing[] = [];
  try {
    passport = await api<Passport>(`/gallery/${slug}/passport`, { token: null });
    listings = (await api<{ items: Listing[] }>(`/gallery/${slug}/listings`, { token: null })).items;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const { entry, story, citations, reference_images: refs, review } = passport;
  const facts = [entry.technique, entry.region, entry.community].filter(Boolean).join(" · ");
  return (
    <Page>
      <h1 className="t-display mb-6 mt-8" style={{ fontSize: "clamp(44px, 8vw, 128px)" }}>{entry.name}</h1>
      <p className="mb-14 max-w-[52ch] text-lg">{facts}</p>

      <div className="grid gap-12 md:grid-cols-12">
        <article className="rise md:col-span-7">
          <h2 className="t-head mb-6" style={{ fontSize: "clamp(1.75rem, 1.4rem + 1.4vw, 2.5rem)" }}>Ceritanya</h2>
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
        <aside className="rise md:col-span-4 md:col-start-9" style={{ ["--d" as string]: "100ms" }}>
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

      <section className="mt-[clamp(72px,10vw,140px)]" aria-labelledby="listings">
        <h2 id="listings" className="t-head mb-3" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 4rem)" }}>Kain ini dijual oleh</h2>
        <p className="mb-10 max-w-[56ch]">Penjual yang sudah diverifikasi platform. Klaim asal-usul dari penjual ditampilkan terpisah dari verifikasi kurator.</p>
        {listings.length === 0 ? (
          <p>Belum ada penjual yang menawarkan kain untuk entri ini.</p>
        ) : (
          <ul className="grid list-none gap-10 p-0 md:grid-cols-2">{listings.map((l) => <li key={l.id}><ListingCard l={l} /></li>)}</ul>
        )}
      </section>
    </Page>
  );
}

function dedupe<T extends { source_id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((i) => (seen.has(i.source_id) ? false : (seen.add(i.source_id), true)));
}
