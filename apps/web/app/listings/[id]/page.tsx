import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BuyPanel } from "@/components/BuyPanel";
import type { Listing } from "@/components/ListingCard";
import { Page } from "@/components/ui";
import { ApiError, api, fileUrl, idr } from "@/lib/api";

type Detail = Listing & {
  weight_gsm: number | null;
  thickness_note: string | null;
  motif_orientation: string | null;
  pattern_repeat_cm: number | null;
  merchant: { id: string; shop_name: string; description: string | null; city: string | null; province: string | null; verified: boolean; verification_note: string };
  gallery_entry: { slug: string; name: string } | null;
};

export const metadata: Metadata = { title: "Kain" };

export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let l: Detail;
  try {
    l = await api<Detail>(`/listings/${id}`, { token: null });
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  const meter = l.selling_unit === "meter";
  const specs: [string, string][] = [
    ["Bahan", l.material ?? "-"],
    ["Dijual per", meter ? "meter" : "potong utuh"],
    ...(meter ? ([["Lebar pakai", `${l.usable_width_cm ?? "-"} cm`], ["Stok total", `${l.stock.total_length_m ?? 0} m`], ["Potongan utuh terpanjang", `${l.stock.longest_continuous_m ?? 0} m`]] as [string, string][]) : ([["Ukuran potong", `${l.piece_length_cm ?? "-"} × ${l.piece_width_cm ?? "-"} cm`], ["Stok", `${l.stock.pieces} potong`]] as [string, string][])),
    ["Berat", l.weight_gsm ? `${l.weight_gsm} gsm` : "-"],
    ["Dikirim dalam", l.dispatch_days ? `${l.dispatch_days} hari` : "-"],
    ["Asal pengiriman", [l.city, l.province].filter(Boolean).join(", ")],
  ];
  return (
    <Page>
      {l.gallery_entry && <p className="mb-4 mt-6 text-base"><Link href={`/gallery/${l.gallery_entry.slug}`} className="link">← {l.gallery_entry.name}</Link></p>}
      <h1 className="t-head mb-3 max-w-[20ch]" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 4rem)" }}>{l.title}</h1>
      <p className="mb-10 text-xl">{idr(l.price_idr)} <span className="text-muted">/ {meter ? "meter" : "potong"}</span></p>
      <div className="grid gap-12 md:grid-cols-12">
        <div className="grid content-start gap-8 md:col-span-7">
          {l.images.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {l.images.map((im) => <img key={im.url} src={fileUrl(im.url)} alt={im.caption ?? l.title} className="aspect-square w-full object-cover" />)}
            </div>
          ) : null}
          {l.description && <p className="max-w-[60ch]">{l.description}</p>}
          <dl className="grid max-w-xl gap-x-8 gap-y-3 text-base sm:grid-cols-[auto_1fr]">
            {specs.map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{k}</dt><dd>{v}</dd></div>))}
          </dl>
          <div className="max-w-xl bg-surface p-5 text-base">
            <h2 className="mb-2 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Asal-usul, tiga hal yang dipisahkan</h2>
            <p><span className="text-muted">Kecocokan visual: </span>{l.origin.visual_match ? "tersedia sebagai saran" : "belum dianalisis"}</p>
            <p><span className="text-muted">Klaim penjual: </span>{l.origin.merchant_claimed_origin ?? "tidak ada"}</p>
            <p><span className="text-muted">Diverifikasi kurator: </span>{l.origin.curator_verified_origin ?? "belum diverifikasi"}</p>
          </div>
          <div className="max-w-xl text-base">
            <h2 className="mb-1 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{l.merchant.shop_name}</h2>
            <p>{[l.merchant.city, l.merchant.province].filter(Boolean).join(", ")}</p>
            <p className="text-muted">{l.merchant.verification_note}</p>
          </div>
        </div>
        <div className="md:col-span-5"><BuyPanel listing={l} /></div>
      </div>
    </Page>
  );
}
