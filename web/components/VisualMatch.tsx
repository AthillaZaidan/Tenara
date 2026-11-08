// Read-only view of a fabric scan suggestion and its web evidence. Used by the public listing page
// and by the merchant's scan panel. The photo claim check is shown only outside the public view.
import { fileUrl } from "@/lib/api";

export type Evidence = { id: string; url: string; domain: string; tier: "trusted" | "general" | "commerce"; title: string; excerpt: string };
export type Suggestion = { verdict: "match" | "insufficient"; tradition: string | null; region: string | null; gallery_match: string | null; evidence_ids: string[]; confidence: "low" | "medium" | "high"; reason: string | null };
export type ClaimComparison = { id: string; style: "modern" | "archival"; similarity: number; credit: string | null; license: string | null; source_url: string | null; url: string | null };
export type ClaimCheck = {
  status: "konsisten" | "perlu_dicek" | "belum_ada_referensi" | "gagal"; message: string; claimed: string | null;
  rank: number | null; top: { tradition: string | null; score: number }[]; comparisons: ClaimComparison[]; notes: string[];
};
export type ScanResult = {
  technique: string; motif_category: string; motif_elements: string[]; dominant_colors: string[]; distinctive_features: string[];
  is_traditional_woven_textile: boolean; suggestion?: Suggestion; evidence?: Evidence[]; notes?: string[]; claim_check?: ClaimCheck | null;
};
export type VisualMatchData = ScanResult & { status?: string; needs_merchant_review?: boolean; review?: { decision: string; entry_id?: string } };

export const TECHNIQUE: Record<string, string> = { ikat: "Ikat", songket: "Songket", plain_weave: "Tenun polos", printed_or_batik: "Cetak atau batik", other: "Lainnya", unknown: "Tidak yakin" };
export const CATEGORY: Record<string, string> = { fauna: "Fauna", flora: "Flora", geometric: "Geometris", figurative: "Figuratif", mixed: "Campuran", other: "Lainnya", unknown: "Tidak yakin" };
export const CONFIDENCE: Record<string, string> = { high: "keyakinan tinggi", medium: "keyakinan sedang", low: "keyakinan rendah" };
const TIER: Record<string, string> = { trusted: "lembaga atau museum", general: "situs umum", commerce: "toko" };

export function VisualMatch({ data, compact = false }: { data: VisualMatchData; compact?: boolean }) {
  const s = data.suggestion;
  const cited = new Set(s?.evidence_ids ?? []);
  const evidence = (data.evidence ?? []).filter((e) => !compact || cited.has(e.id));
  return (
    <div className="grid gap-3 text-base">
      <p>
        {TECHNIQUE[data.technique] ?? data.technique} · motif {CATEGORY[data.motif_category]?.toLowerCase() ?? data.motif_category}
        {data.motif_elements?.length ? ` (${data.motif_elements.join(", ")})` : ""}
        {data.dominant_colors?.length ? ` · ${data.dominant_colors.join(", ")}` : ""}
      </p>
      {s?.verdict === "match" ? (
        <p>
          <span className="font-medium">Kemungkinan {s.tradition}{s.region ? `, ${s.region}` : ""}</span> <span className="text-muted">({CONFIDENCE[s.confidence]})</span>
          {s.reason && <span className="mt-1 block">{s.reason}</span>}
        </p>
      ) : (
        <p>Belum cukup bukti untuk menyebut tradisi atau daerah asal kain ini.</p>
      )}
      {evidence.length > 0 && (
        <ul className="grid list-none gap-2 p-0">
          {evidence.map((e) => (
            <li key={e.id}>
              <a href={e.url} target="_blank" rel="noopener noreferrer nofollow" className="link">{e.title || e.domain}</a>
              <span className="block text-muted t-small">{e.domain} · {TIER[e.tier]}{cited.has(e.id) ? " · sumber katalog" : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {!compact && data.notes?.map((n) => <p key={n} className="text-muted">{n}</p>)}
      {!compact && data.claim_check && <ClaimCheckView check={data.claim_check} />}
      <p className="t-small text-muted">Saran otomatis dari foto dan katalog yang disetujui kurator. Bukan sertifikasi asal-usul.</p>
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
