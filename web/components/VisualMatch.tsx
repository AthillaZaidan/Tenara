// Read-only view of a fabric scan: what the photo shows, and checks of the seller's own claim.
// The public listing page shows the description only; checks are for the merchant and the curator.
import { fileUrl } from "@/lib/api";

export type ClaimComparison = { id: string; style: "modern" | "archival"; similarity: number; credit: string | null; license: string | null; source_url: string | null; url: string | null };
export type ClaimCheck = {
  status: "konsisten" | "perlu_dicek" | "belum_ada_referensi" | "gagal"; message: string; claimed: string | null;
  rank: number | null; top: { tradition: string | null; score: number }[]; comparisons: ClaimComparison[]; notes: string[];
};
export type TechniqueCheck = { status: "cocok" | "berbeda" | "tidak_jelas"; seen: string; expected: string | null; claimed: string; message: string };
export type ScanResult = {
  technique: string; motif_category: string; motif_elements: string[]; dominant_colors: string[]; distinctive_features: string[];
  is_traditional_woven_textile: boolean; claimed?: string | null; technique_check?: TechniqueCheck | null;
  claim_check?: ClaimCheck | null; notes?: string[];
};
export type VisualMatchData = ScanResult & { status?: string };

export const TECHNIQUE: Record<string, string> = { ikat: "Ikat", songket: "Songket", plain_weave: "Tenun polos", printed_or_batik: "Cetak atau batik", other: "Lainnya", unknown: "Tidak yakin" };
export const CATEGORY: Record<string, string> = { fauna: "Fauna", flora: "Flora", geometric: "Geometris", figurative: "Figuratif", mixed: "Campuran", other: "Lainnya", unknown: "Tidak yakin" };
const TECHNIQUE_STATUS: Record<TechniqueCheck["status"], string> = { cocok: "Teknik sesuai katalog", berbeda: "Teknik berbeda dengan katalog", tidak_jelas: "Teknik belum bisa dibandingkan" };

export function VisualMatch({ data, compact = false }: { data: VisualMatchData; compact?: boolean }) {
  const t = data.technique_check;
  return (
    <div className="grid gap-3 text-base">
      <p>
        {TECHNIQUE[data.technique] ?? data.technique} · motif {CATEGORY[data.motif_category]?.toLowerCase() ?? data.motif_category}
        {data.motif_elements?.length ? ` (${data.motif_elements.join(", ")})` : ""}
        {data.dominant_colors?.length ? ` · ${data.dominant_colors.join(", ")}` : ""}
      </p>
      {data.distinctive_features?.length > 0 && <p className="text-muted">Ciri: {data.distinctive_features.join(", ")}</p>}
      {!compact && t && (
        <p><span className="font-medium">{TECHNIQUE_STATUS[t.status]}.</span> {t.message}</p>
      )}
      {!compact && data.notes?.map((n) => <p key={n} className="text-muted">{n}</p>)}
      {!compact && data.claim_check && <ClaimCheckView check={data.claim_check} />}
      <p className="t-small text-muted">{compact ? "Deskripsi otomatis dari foto. Bukan sertifikasi asal-usul." : "Deskripsi dan pemeriksaan otomatis atas klaim penjual. Bukan sertifikasi asal-usul; kurator Tenara yang memverifikasi."}</p>
    </div>
  );
}

const CLAIM: Record<ClaimCheck["status"], string> = {
  konsisten: "Konsisten dengan foto referensi", perlu_dicek: "Perlu dicek kurator",
  belum_ada_referensi: "Belum ada referensi sebanding", gagal: "Cek foto gagal",
};

/** Seller's claim (the listing's Gallery entry) vs. curator-approved reference photos. A signal, never a verdict. */
export function ClaimCheckView({ check }: { check: ClaimCheck }) {
  return (
    <div className="grid gap-3 pt-2">
      <p className="text-base">
        <span className="font-medium">Cek klaim lewat foto: {CLAIM[check.status]}</span>
        {check.claimed && <span className="text-muted"> (klaim: {check.claimed})</span>}
      </p>
      <p className="text-base">{check.message}</p>
      {check.top.length > 0 && (
        <p className="t-small text-muted">Paling mirip: {check.top.map((t) => t.tradition).filter(Boolean).join(", ")}</p>
      )}
      {check.notes.map((n) => <p key={n} className="text-base">{n}</p>)}
      {check.comparisons.length > 0 && (
        <figure className="grid gap-2">
          <figcaption className="t-small text-muted">Foto pembanding {check.claimed ?? ""}</figcaption>
          <ul className="grid list-none grid-cols-3 gap-2 p-0">
            {check.comparisons.map((c) => (
              <li key={c.id} className="grid gap-1">
                {c.url && <img src={fileUrl(c.url)} alt={`Foto referensi ${check.claimed ?? ""}`} className="aspect-square w-full object-cover" />}
                <span className="t-small text-muted">
                  {c.style === "archival" ? "Arsip" : "Modern"} · {c.source_url ? <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="link">{c.credit ?? "sumber"}</a> : c.credit}{c.license ? ` · ${c.license}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </figure>
      )}
    </div>
  );
}
