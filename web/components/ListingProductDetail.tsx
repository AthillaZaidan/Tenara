"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, MapPin, Truck } from "lucide-react";
import { BuyPanel } from "@/components/BuyPanel";
import { CatalogBenefits, CatalogRelated } from "@/components/CatalogTraditionDetail";
import { CatalogImage } from "@/components/CatalogImage";
import { VerifyOrigin } from "@/components/VerifyOrigin";
import { VisualMatch, type VisualMatchData } from "@/components/VisualMatch";
import type { Listing } from "@/components/ListingCard";
import { fileUrl, idr } from "@/lib/api";
import { regionExploreHrefForTerms } from "@/lib/regions";

export type ListingDetailData = Listing & {
  weight_gsm: number | null;
  thickness_note: string | null;
  motif_orientation: string | null;
  pattern_repeat_cm: number | null;
  merchant: {
    id: string;
    shop_name: string;
    description: string | null;
    city: string | null;
    province: string | null;
    verified: boolean;
    verification_note: string;
  };
  gallery_entry: { slug: string; name: string } | null;
};

export function ListingProductDetail({ listing }: { listing: ListingDetailData }) {
  const [openAccordion, setOpenAccordion] = useState("story");
  const meter = listing.selling_unit === "meter";
  const location = [listing.merchant.city ?? listing.city, listing.merchant.province ?? listing.province].filter(Boolean).join(", ");
  const specs: [string, string][] = [
    ["Bahan", listing.material ?? "Belum dicantumkan"],
    ["Satuan", meter ? "Per meter" : "Per potong"],
    ...(meter
      ? ([
          ["Lebar pakai", `${listing.usable_width_cm ?? "-"} cm`],
          ["Stok total", `${listing.stock.total_length_m ?? 0} m`],
          ["Potongan utuh terpanjang", `${listing.stock.longest_continuous_m ?? 0} m`],
        ] as [string, string][])
      : ([
          ["Ukuran potong", `${listing.piece_length_cm ?? "-"} × ${listing.piece_width_cm ?? "-"} cm`],
          ["Stok", `${listing.stock.pieces} potong`],
        ] as [string, string][])),
    ["Berat", listing.weight_gsm ? `${listing.weight_gsm} gsm` : "Belum dicantumkan"],
    ["Ketebalan", listing.thickness_note ?? "Belum dicantumkan"],
    ["Arah motif", listing.motif_orientation ?? "Belum dicantumkan"],
    ["Pengulangan motif", listing.pattern_repeat_cm ? `${listing.pattern_repeat_cm} cm` : "Belum dicantumkan"],
    ["Dikirim dalam", listing.dispatch_days ? `${listing.dispatch_days} hari` : "Belum dicantumkan"],
    ["Asal pengiriman", location || "Belum dicantumkan"],
  ];

  return <div className="catalog-detail-shell ecommerce-detail listing-product-detail">
    <div className="catalog-detail-layout">
      <ListingPhotoGallery listing={listing} />

      <section className="catalog-detail-copy" aria-labelledby="listing-detail-title">
        <nav className="catalog-breadcrumb" aria-label="Jejak navigasi">
          <Link href="/katalog">Katalog kain</Link><span aria-hidden="true">/</span><span aria-current="page">{listing.title}</span>
        </nav>
        <h1 id="listing-detail-title">{listing.title}</h1>
        <p className="catalog-detail-origin"><MapPin size={16} aria-hidden="true" />{location || "Lokasi penyedia belum dicantumkan"}</p>

        <div className="product-price" aria-live="polite">
          <span className="product-price-prefix">Harga penawaran</span>
          <div className="product-price-value"><strong>{idr(listing.price_idr)}</strong><span>/ {meter ? "meter" : "potong"}</span></div>
        </div>
        {listing.gallery_entry && <Link className="catalog-story-link" href={regionExploreHrefForTerms([listing.gallery_entry.name])}>Kenali cerita kain <ChevronRight size={16} aria-hidden="true" /></Link>}

        <section className="listing-provider" aria-labelledby="listing-provider-title">
          <div className="ecommerce-section-title"><h2 id="listing-provider-title">Penyedia kain</h2><span>{listing.merchant.verified ? "Terverifikasi" : "Penawaran penyedia"}</span></div>
          <div className="ecommerce-offer listing-provider-card">
            <span className="ecommerce-offer-photo">{listing.images[0] ? <img src={fileUrl(listing.images[0].url)} alt="" /> : <span>Foto belum tersedia</span>}</span>
            <div className="ecommerce-offer-content">
              <div className="ecommerce-offer-top"><Link href={`/merchants/${listing.merchant.id}`}>{listing.merchant.shop_name}</Link><b>{idr(listing.price_idr)} <small>/ {meter ? "meter" : "potong"}</small></b></div>
              <span>{listing.title}</span>
              <span className="ecommerce-offer-availability">{location || "Lokasi belum dicantumkan"} · {listing.stock.in_stock ? "Tersedia" : "Stok habis"}</span>
            </div>
          </div>
          <BuyPanel listing={listing} />
          <p className="ecommerce-dispatch"><Truck size={16} aria-hidden="true" />{listing.dispatch_days ? `Dikirim dalam ${listing.dispatch_days} hari` : "Waktu pengiriman dikonfirmasi penjual"}</p>
        </section>

        <section className="ecommerce-details product-accordions" aria-label="Informasi kain">
          <ProductAccordion id="cerita-kain" panelId="listing-story" title="Cerita kain" open={openAccordion === "story"} onToggle={() => setOpenAccordion(openAccordion === "story" ? "" : "story")}>
            {listing.description && <p>{listing.description}</p>}
            {listing.gallery_entry && <Link className="product-story-more" href={regionExploreHrefForTerms([listing.gallery_entry.name])}>Jelajahi cerita {listing.gallery_entry.name} <ChevronRight size={14} aria-hidden="true" /></Link>}
          </ProductAccordion>
          <ProductAccordion id="asal-kain" panelId="listing-origin" title="Asal-usul kain" open={openAccordion === "origin"} onToggle={() => setOpenAccordion(openAccordion === "origin" ? "" : "origin")}>
            <div className="listing-origin-story">
              <p><strong>Kecocokan visual</strong></p>
              {listing.origin.visual_match ? <VisualMatch data={listing.origin.visual_match as VisualMatchData} compact /> : <p>Belum dianalisis.</p>}
              <p><strong>Klaim penjual:</strong> {listing.origin.merchant_claimed_origin ?? "Tidak ada klaim asal"}</p>
              <p><strong>Verifikasi kurator:</strong> {listing.origin.curator_verified_origin ?? "Belum diverifikasi"}</p>
            </div>
            <div className="listing-merchant-story">
              <h3><Link href={`/merchants/${listing.merchant.id}`}>{listing.merchant.shop_name}</Link></h3>
              {listing.merchant.description && <p>{listing.merchant.description}</p>}
              <p>{listing.merchant.verification_note}</p>
            </div>
            <VerifyOrigin listingId={listing.id} current={listing.origin.curator_verified_origin} />
          </ProductAccordion>
          <ProductAccordion id="spesifikasi-kain" panelId="listing-specs" title="Spesifikasi kain" open={openAccordion === "specs"} onToggle={() => setOpenAccordion(openAccordion === "specs" ? "" : "specs")}>
            <dl>{specs.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          </ProductAccordion>
          <ProductAccordion id="tentang-foto" panelId="listing-photos" title="Tentang foto kain" open={openAccordion === "photos"} onToggle={() => setOpenAccordion(openAccordion === "photos" ? "" : "photos")}>
            <p>Foto di halaman ini berasal dari penawaran penyedia kain.</p>
            {listing.images.map((image, index) => <p key={image.id}>{image.caption || `Foto ${index + 1} kain dari ${listing.merchant.shop_name}`}</p>)}
            {listing.images.length === 0 && <p>Foto kain belum tersedia.</p>}
          </ProductAccordion>
        </section>
      </section>
    </div>

    <CatalogBenefits />
    <CatalogRelated />
  </div>;
}

function ListingPhotoGallery({ listing }: { listing: ListingDetailData }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const photos = listing.images;
  const activePhoto = photos[activeIndex];

  return <div className="catalog-detail-gallery">
    <figure className="catalog-detail-photo" id="listing-photo">
      {activePhoto ? <CatalogImage src={fileUrl(activePhoto.url)} alt={activePhoto.caption ?? listing.title} priority /> : <div className="listing-detail-gallery-empty">Foto kain belum tersedia</div>}
      {activePhoto?.caption && <figcaption>{activePhoto.caption}</figcaption>}
      {photos.length > 1 && <>
        <div className="catalog-detail-views" aria-label="Pilih foto kain">
          {photos.map((photo, index) => <button key={photo.id} type="button" aria-label={`Lihat foto ${index + 1}`} aria-pressed={activeIndex === index} aria-controls="listing-photo" onClick={() => setActiveIndex(index)}>
            <img src={fileUrl(photo.url)} alt="" loading="lazy" />
          </button>)}
        </div>
        <div className="catalog-photo-nav">
          <button type="button" aria-label="Foto sebelumnya" aria-controls="listing-photo" onClick={() => setActiveIndex((activeIndex + photos.length - 1) % photos.length)}><ChevronLeft size={18} /></button>
          <span aria-live="polite">{activeIndex + 1} / {photos.length}</span>
          <button type="button" aria-label="Foto berikutnya" aria-controls="listing-photo" onClick={() => setActiveIndex((activeIndex + 1) % photos.length)}><ChevronRight size={18} /></button>
        </div>
      </>}
    </figure>
  </div>;
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
