import Link from "next/link";
import { fileUrl, idr } from "@/lib/api";

export type Listing = {
  id: string;
  entry_id: string;
  variant_id: string | null;
  title: string;
  material: string | null;
  selling_unit: "meter" | "piece";
  price_idr: number;
  usable_width_cm: number | null;
  piece_length_cm: number | null;
  piece_width_cm: number | null;
  city: string | null;
  province: string | null;
  dispatch_days: number | null;
  description: string | null;
  min_quantity: number;
  quantity_increment: number;
  images: { id: string; url: string; caption: string | null }[];
  stock: { unit: string; total_length_m: number | null; longest_continuous_m: number | null; pieces: number; available_pieces?: number; in_stock: boolean };
  origin: { visual_match: unknown; merchant_claimed_origin: string | null; curator_verified_origin: string | null };
  custom_order_ready: boolean;
  missing_for_custom: string[];
  merchant?: { id?: string; shop_name: string; city?: string | null; province?: string | null };
};

export function ListingCard({ l }: { l: Listing }) {
  const img = l.images[0];
  return (
    <Link href={`/listings/${l.id}`} className="group grid gap-4 no-underline sm:grid-cols-[160px_1fr]">
      {img ? (
        <img src={fileUrl(img.url)} alt={img.caption ?? l.title} className="aspect-square w-full object-cover sm:w-40" />
      ) : (
        <div className="aspect-square w-full bg-surface sm:w-40" />
      )}
      <div className="grid content-start gap-1">
        <h3 className="text-xl font-medium group-hover:underline underline-offset-4" style={{ fontFamily: "var(--font-hanken)" }}>{l.title}</h3>
        <p className="text-base text-muted">{l.merchant?.shop_name} · {l.city}, {l.province}</p>
        <p className="text-lg">{idr(l.price_idr)} <span className="text-base text-muted">/ {l.selling_unit === "meter" ? "meter" : "potong"}</span></p>
        <p className="text-base">
          {l.selling_unit === "meter"
            ? `Lebar ${l.usable_width_cm ?? "?"} cm · stok utuh terpanjang ${l.stock.longest_continuous_m ?? 0} m`
            : `${l.piece_length_cm ?? "?"} × ${l.piece_width_cm ?? "?"} cm · ${l.stock.pieces} potong`}
          {l.custom_order_ready && " · bisa dijadikan baju"}
        </p>
      </div>
    </Link>
  );
}
