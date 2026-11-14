"use client";

import Link from "next/link";
import { useRef, useState, type ReactNode } from "react";
import { ArrowRight, ArrowUpRight, BookOpen, ChevronDown, ChevronLeft, ChevronRight, MapPin, Package, Store, Layers3, X } from "lucide-react";
import { catalogSamplesForTradition, catalogTraditions, type CatalogSample, type CatalogTradition } from "@/lib/catalog-data";
import { api, fileUrl, idr } from "@/lib/api";
import { regionHref } from "@/lib/exploration";
import type { Listing } from "@/components/ListingCard";
import type { GalleryVariant } from "@/lib/variants";
import { CatalogOfferActions } from "@/components/CatalogOfferActions";
import { CatalogImage } from "@/components/CatalogImage";
import "./catalog-motion.css";
import type { ListingDetailData } from "@/components/ListingProductDetail";
import { VerifyOrigin } from "@/components/VerifyOrigin";
import { VisualMatch, type VisualMatchData } from "@/components/VisualMatch";
import { useLoad } from "@/components/ui";

const views = [
  { key: "utama", label: "Tampilan utama" },
  { key: "datar", label: "Lipatan datar" },
  { key: "closeup", label: "Detail tekstur" },
] as const;

export function CatalogTraditionDetail({ tradition, samples, apiSlug, listings, variants, story, offersUnavailable, initialOfferId, initialBuy, initialQuantity, initialSampleCode }: {
  tradition: CatalogTradition;
  samples: CatalogSample[];
  apiSlug?: string;
  listings: Listing[];
  variants: GalleryVariant[];
  story: { story: { body: string } | null; review: { is_demo_seed: boolean } } | null;
  offersUnavailable: boolean;
  initialOfferId?: string;
  initialBuy?: boolean;
  initialQuantity?: string;
  initialSampleCode?: string;
}) {
  const initialOffer = listings.find((listing) => listing.id === initialOfferId);
  const initialVariant = variants.find((variant) => variant.id === initialOffer?.variant_id);
  const initialSample = samples.find((item) => item.code === initialSampleCode) ?? samples.find((item) => item.motif.trim().toLocaleLowerCase("id-ID") === initialVariant?.name.trim().toLocaleLowerCase("id-ID"));
  const [sampleCode, setSampleCode] = useState(initialSample?.code ?? samples[0]?.code ?? "");
  const [view, setView] = useState(0);
  const [offerId, setOfferId] = useState(initialOfferId ?? "");
  const [openAccordion, setOpenAccordion] = useState("story");
  const sample = samples.find((item) => item.code === sampleCode) ?? samples[0];
  const matchingVariants = variants.filter((variant) => variant.name.trim().toLocaleLowerCase("id-ID") === sample?.motif.trim().toLocaleLowerCase("id-ID"));
  const variantId = matchingVariants.length === 1 ? matchingVariants[0].id : undefined;
  const visibleListings = variantId ? listings.filter((listing) => listing.variant_id === variantId) : [];
  const offer = visibleListings.find((item) => item.id === offerId) ?? visibleListings.find((item) => item.stock.in_stock) ?? visibleListings[0];

  return <div className="catalog-detail-shell ecommerce-detail">
    <div className="catalog-detail-layout">
      <div className="catalog-detail-gallery">
        <figure className="catalog-detail-photo" id="catalog-photo">
          {sample && <CatalogImage src={sample.images[views[view].key]} alt={`${tradition.name} · ${sample.label} — ${views[view].label}`} priority />}
          <div className="catalog-detail-views" aria-label="Pilih tampilan kain">{views.map((item, index) => <button key={item.key} type="button" aria-label={item.label} aria-pressed={view === index} aria-controls="catalog-photo" onClick={() => setView(index)}>{sample && <img src={sample.images[item.key]} alt="" loading="lazy" />}</button>)}</div>
          <div className="catalog-photo-nav"><button type="button" aria-label="Gambar sebelumnya" aria-controls="catalog-photo" onClick={() => setView((view + views.length - 1) % views.length)}><ChevronLeft size={18} /></button><span aria-live="polite">{view + 1} / {views.length}</span><button type="button" aria-label="Gambar berikutnya" aria-controls="catalog-photo" onClick={() => setView((view + 1) % views.length)}><ChevronRight size={18} /></button></div>
        </figure>
      </div>

      <section className="catalog-detail-copy" aria-labelledby="catalog-detail-title">
        <nav className="catalog-breadcrumb" aria-label="Jejak navigasi"><Link href="/katalog">Katalog kain</Link><span aria-hidden="true">/</span><span aria-current="page">Detail kain</span></nav>
        <h1 id="catalog-detail-title">{tradition.name}</h1>
        <p className="catalog-detail-origin"><MapPin size={16} aria-hidden="true" /> {tradition.region} <span aria-hidden="true">·</span> {tradition.technique}</p>
        <div className="product-price" aria-live="polite">
          <span className="product-price-prefix">Mulai dari</span>
          <div className="product-price-value" key={offer?.id ?? "unavailable"}>{offer ? <><strong>{idr(offer.price_idr)}</strong><span> / {offer.selling_unit === "meter" ? "meter" : "potong"}</span></> : <><strong>—</strong><span className="product-price-status">{offersUnavailable ? "Harga belum tersedia" : "Belum ada penawaran"}</span></>}</div>
        </div>
        <section className="ecommerce-samples" aria-label="Pilih motif atau ragam">
          <div className="ecommerce-section-title catalog-samples-heading"><h2>Ragam katalog</h2><Link className="catalog-story-link" href={regionHref(tradition.regionId)}>Kenali cerita kain <ChevronRight size={16} aria-hidden="true" /></Link></div>
          <div className="catalog-detail-samples">{samples.map((item) => <button key={item.code} type="button" aria-pressed={item.code === sample?.code} onClick={() => { setSampleCode(item.code); setOfferId(""); setView(0); }}><strong>{item.label}</strong></button>)}</div>
        </section>

        <section className="ecommerce-offers" id="listings" aria-labelledby="offer-title">
          <div className="ecommerce-section-title"><h2 id="offer-title">Pilih penyedia</h2><span>{visibleListings.length} penawaran</span></div>
          {offersUnavailable ? <div className="ecommerce-empty"><Package size={25} /><h3>Penawaran belum dapat dimuat</h3><p>Silakan coba lagi sebentar.</p></div> : visibleListings.length === 0 ? <div className="ecommerce-empty"><Package size={25} /><h3>Belum ada penawaran</h3><p>Belum ada penawaran yang terhubung dengan motif {sample?.label}.</p></div> : <>
            <div className="ecommerce-offer-list" role="group" aria-label="Penawaran penyedia">{visibleListings.map((item) => <div key={item.id} className={`catalog-offer-row${offer?.id === item.id ? " is-selected" : ""}`}>
              <button type="button" className="ecommerce-offer" aria-pressed={offer?.id === item.id} onClick={() => setOfferId(item.id)}>
                <span className="ecommerce-offer-photo">{item.images[0] ? <img src={fileUrl(item.images[0].url)} alt="" /> : <span>Foto belum tersedia</span>}</span>
                <span className="ecommerce-offer-content"><span className="ecommerce-offer-top"><strong>{item.merchant?.shop_name ?? "Penyedia kain"}</strong><b>{idr(item.price_idr)} <small>/ {item.selling_unit === "meter" ? "meter" : "potong"}</small></b></span><span>{item.title}</span><span className="ecommerce-offer-availability">{item.stock.in_stock ? (item.city || "Tersedia") : "Stok habis"} · {item.images[0] ? (/demo/i.test(item.images[0].caption ?? "") ? "Foto demo" : "Foto penyedia") : "Foto belum tersedia"}</span></span>
              </button>
              <OfferPreview listing={item} />
            </div>)}</div>
            {offer && <CatalogOfferActions key={offer.id} listing={offer} initialBuy={initialBuy && offer.id === initialOfferId} initialQuantity={offer.id === initialOfferId ? initialQuantity : undefined} />}
          </>}
        </section>
        <section className="ecommerce-details product-accordions" aria-label="Informasi kain">
          <ProductAccordion id="cerita-kain" panelId="story" title="Cerita kain" open={openAccordion === "story"} onToggle={() => setOpenAccordion(openAccordion === "story" ? "" : "story")}>
            {story?.story?.body ? <>{story.story.body.split("\n").filter(Boolean).map((paragraph, index) => <p key={index}>{paragraph}</p>)}{story.review.is_demo_seed && <p>Cerita ini menggunakan data demo.</p>}</> : <p>Kenali tradisi {tradition.name} dari {tradition.region}, serta ragam dan tekniknya lebih dekat.</p>}
            {apiSlug && <Link className="product-story-more" href={regionHref(tradition.regionId)}>Jelajahi cerita di {tradition.region} <ArrowUpRight size={14} /></Link>}
          </ProductAccordion>
          <ProductAccordion id="spesifikasi-kain" panelId="specs" title="Spesifikasi kain" open={openAccordion === "specs"} onToggle={() => setOpenAccordion(openAccordion === "specs" ? "" : "specs")}>
            {offer ? <dl><div><dt>Bahan</dt><dd>{offer.material ?? "Belum dicantumkan"}</dd></div><div><dt>Satuan</dt><dd>Per {offer.selling_unit === "meter" ? "meter" : "potong"}</dd></div><div><dt>Ukuran</dt><dd>{offer.selling_unit === "meter" ? (offer.usable_width_cm ? `Lebar ${offer.usable_width_cm} cm` : "Belum dicantumkan") : (offer.piece_length_cm && offer.piece_width_cm ? `${offer.piece_length_cm} × ${offer.piece_width_cm} cm` : "Belum dicantumkan")}</dd></div><div><dt>Stok</dt><dd>{offer.selling_unit === "meter" ? `${offer.stock.total_length_m ?? 0} m` : `${offer.stock.available_pieces ?? offer.stock.pieces ?? 0} potong`}</dd></div><div><dt>Persiapan pengiriman</dt><dd>{offer.dispatch_days ? `${offer.dispatch_days} hari` : "Belum dicantumkan"}</dd></div></dl> : <p>Pilih penawaran untuk melihat spesifikasinya.</p>}
          </ProductAccordion>
          {offer && <ProductAccordion id="asal-kain" panelId="origin" title="Tentang penawaran dan asal kain" open={openAccordion === "origin"} onToggle={() => setOpenAccordion(openAccordion === "origin" ? "" : "origin")}><OfferDetails key={offer.id} listing={offer} /></ProductAccordion>}
          <ProductAccordion id="tentang-foto" panelId="photos" title="Tentang foto kain" open={openAccordion === "photos"} onToggle={() => setOpenAccordion(openAccordion === "photos" ? "" : "photos")}>
            <p>Gambar katalog adalah ilustrasi ragam kain. Foto kain yang dijual tersedia pada setiap penawaran penyedia.</p>
          </ProductAccordion>
        </section>
      </section>
    </div>
    <CatalogBenefits />
    <CatalogRelated excludeId={tradition.id} />
  </div>;
}

function OfferDetails({ listing }: { listing: Listing }) {
  const detail = useLoad(() => api<ListingDetailData>(`/listings/${listing.id}`, { token: null }), listing.id);
  return <>
    {listing.description && <p>{listing.description}</p>}
    <p><strong>Klaim penjual:</strong> {listing.origin.merchant_claimed_origin ?? "Tidak ada klaim asal"}</p>
    <p><strong>Verifikasi kurator:</strong> {listing.origin.curator_verified_origin ?? "Belum diverifikasi"}</p>
    {listing.origin.visual_match && <VisualMatch data={listing.origin.visual_match as VisualMatchData} compact />}
    {detail.data && <><p><Link className="product-story-more" href={`/merchants/${detail.data.merchant.id}`}>Profil {detail.data.merchant.shop_name} <ArrowUpRight size={14} /></Link></p><p>{detail.data.merchant.verification_note}</p><VerifyOrigin listingId={listing.id} current={listing.origin.curator_verified_origin} /></>}
    {detail.error && <p>Informasi penyedia belum dapat dimuat.</p>}
  </>;
}

function OfferPreview({ listing }: { listing: Listing }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [photo, setPhoto] = useState(0);
  return <>
    <button type="button" className="catalog-offer-preview" onClick={() => { setPhoto(0); dialog.current?.showModal(); }}>Lihat foto</button>
    <dialog ref={dialog} className="catalog-preview-dialog" aria-labelledby={`preview-title-${listing.id}`}>
      <div className="catalog-preview-header"><div><span>Foto dari penyedia</span><h2 id={`preview-title-${listing.id}`}>{listing.title}</h2></div><button type="button" aria-label="Tutup foto" onClick={() => dialog.current?.close()}><X size={20} /></button></div>
      {listing.images.length ? <><div className="catalog-preview-image"><CatalogImage src={fileUrl(listing.images[photo].url)} alt={listing.images[photo].caption ?? `Foto ${listing.title}`} /></div><div className="catalog-preview-footer"><p>{listing.images[photo].caption || `Foto dari ${listing.merchant?.shop_name ?? "penyedia"}`}</p>{listing.images.length > 1 && <div><button type="button" aria-label="Foto sebelumnya" onClick={() => setPhoto((photo + listing.images.length - 1) % listing.images.length)}><ChevronLeft size={18} /></button><span aria-live="polite">{photo + 1} / {listing.images.length}</span><button type="button" aria-label="Foto berikutnya" onClick={() => setPhoto((photo + 1) % listing.images.length)}><ChevronRight size={18} /></button></div>}</div></> : <div className="catalog-preview-empty">Foto kain belum tersedia.</div>}
    </dialog>
  </>;
}

export function CatalogBenefits() {
  return <section className="catalog-benefits rise" aria-label="Menjelajahi kain di Tenara">
    <div><Layers3 size={28} strokeWidth={1.5} /><h2>Ragam Kain Nusantara</h2><p>Temukan kain dari berbagai daerah di Indonesia.</p></div>
    <div><Store size={28} strokeWidth={1.5} /><h2>Pilihan Penyedia</h2><p>Bandingkan foto dan penawaran dari penyedia kain.</p></div>
    <div><BookOpen size={28} strokeWidth={1.5} /><h2>Cerita di Balik Kain</h2><p>Kenali tradisi dan teknik di balik setiap koleksi.</p></div>
  </section>;
}

export function CatalogRelated({ excludeId }: { excludeId?: string }) {
  return <section className="catalog-related rise" aria-labelledby="related-title">
    <div className="catalog-related-heading"><h2 id="related-title">Kain lainnya</h2><Link href="/katalog">Lihat semua <ArrowRight size={16} /></Link></div>
    <div className="catalog-related-grid">{catalogTraditions.filter((item) => item.id !== excludeId).slice(0, 4).map((item) => <RelatedCard key={item.id} tradition={item} />)}</div>
  </section>;
}

function ProductAccordion({ id, panelId, title, open, onToggle, children }: { id: string; panelId: string; title: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  const contentId = `product-accordion-${panelId}`;
  return <section className={`product-accordion${open ? " is-open" : ""}`} id={id}>
    <h3><button className="product-accordion-trigger" id={`${contentId}-label`} type="button" aria-expanded={open} aria-controls={contentId} onClick={onToggle}>{title}<ChevronDown size={17} aria-hidden="true" /></button></h3>
    <div className="product-accordion-collapse" id={contentId} role="region" aria-labelledby={`${contentId}-label`} aria-hidden={!open} inert={!open}>
      <div className="product-accordion-content">{children}</div>
    </div>
  </section>;
}

function RelatedCard({ tradition }: { tradition: CatalogTradition }) {
  const sample = catalogSamplesForTradition(tradition.id)[0];
  const [view, setView] = useState(0);
  if (!sample) return null;
  return <article className="catalog-related-card"><div className="catalog-related-image"><Link href={`/katalog/${tradition.id}`}><CatalogImage src={sample.images[views[view].key]} alt={`${tradition.name} · ${views[view].label}`} /></Link><div className="catalog-related-thumbnails" aria-label={`Pilih gambar ${tradition.name}`}>{views.map((item, index) => <button type="button" key={item.key} aria-label={`${item.label} ${tradition.name}`} aria-pressed={view === index} onClick={() => setView(index)}><img src={sample.images[item.key]} alt="" loading="lazy" /></button>)}</div></div><Link className="catalog-related-name" href={`/katalog/${tradition.id}`}>{tradition.name}</Link><p>{tradition.region}</p></article>;
}
