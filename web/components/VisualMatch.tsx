// Read-only view of a fabric scan suggestion and its web evidence. Used by the public listing page
// and by the merchant's scan panel.

export type Evidence = { id: string; url: string; domain: string; tier: "trusted" | "general" | "commerce"; title: string; excerpt: string };
export type Suggestion = { verdict: "match" | "insufficient"; tradition: string | null; region: string | null; gallery_match: string | null; evidence_ids: string[]; confidence: "low" | "medium" | "high"; reason: string | null };
export type ScanResult = {
  technique: string; motif_category: string; motif_elements: string[]; dominant_colors: string[]; distinctive_features: string[];
  is_traditional_woven_textile: boolean; suggestion?: Suggestion; evidence?: Evidence[]; notes?: string[];
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
      <p className="t-small text-muted">Saran otomatis dari foto dan katalog yang disetujui kurator. Bukan sertifikasi asal-usul.</p>
    </div>
  );
}
