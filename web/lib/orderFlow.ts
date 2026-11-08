// Mirrors the API's order state machines so each role is offered only the actions that can succeed.
// The API remains the authority: every action is re-checked server-side.

export type Role = "buyer" | "merchant" | "tailor" | "admin";

type Rule = { roles: Role[]; from: string[]; label: string; needsNote?: boolean; note?: string };

const FABRIC: Record<string, Rule> = {
  start_preparing: { roles: ["merchant"], from: ["confirmed"], label: "Mulai menyiapkan" },
  dispatch: { roles: ["merchant"], from: ["preparing"], label: "Kirim ke pembeli" },
  simulate_delivery: { roles: ["admin"], from: ["shipped_to_buyer"], label: "Simulasikan tiba" },
  confirm_receipt: { roles: ["buyer"], from: ["delivered"], label: "Konfirmasi barang diterima" },
  cancel: { roles: ["merchant", "admin"], from: ["confirmed", "preparing"], label: "Batalkan", needsNote: true },
};

const CUSTOM: Record<string, Rule> = {
  start_preparing: { roles: ["merchant"], from: ["confirmed"], label: "Mulai menyiapkan kain" },
  dispatch_to_tailor: { roles: ["merchant"], from: ["fabric_preparing"], label: "Kirim kain ke penjahit" },
  receive_fabric: { roles: ["tailor"], from: ["shipped_to_tailor"], label: "Kain diterima penjahit" },
  begin_production: { roles: ["tailor"], from: ["inspection_passed"], label: "Mulai menjahit" },
  complete_production: { roles: ["tailor"], from: ["in_production"], label: "Selesai dijahit", needsNote: true, note: "Catatan pemeriksaan mutu" },
  dispatch_finished: { roles: ["tailor"], from: ["quality_check"], label: "Kirim baju ke pembeli" },
  simulate_delivery: { roles: ["admin"], from: ["shipped_to_buyer"], label: "Simulasikan tiba" },
  confirm_receipt: { roles: ["buyer"], from: ["delivered"], label: "Konfirmasi baju diterima" },
  resolve_issue: { roles: ["admin"], from: ["inspection_issue"], label: "Selesaikan masalah kain", needsNote: true },
  fail_fulfillment: { roles: ["admin"], from: ["inspection_issue"], label: "Gagalkan pesanan", needsNote: true },
  cancel: { roles: ["merchant", "tailor", "admin"], from: ["confirmed", "fabric_preparing"], label: "Batalkan", needsNote: true },
};

export function actionsFor(kind: string, status: string, role: Role) {
  const table = kind === "custom" ? CUSTOM : FABRIC;
  return Object.entries(table)
    .filter(([, r]) => r.roles.includes(role) && r.from.includes(status))
    .map(([event, r]) => ({ event, label: r.label, needsNote: !!r.needsNote, notePlaceholder: r.note ?? "Alasan atau catatan" }));
}

export const STATUS_LABEL: Record<string, string> = {
  confirmed: "Dikonfirmasi", preparing: "Kain disiapkan", fabric_preparing: "Kain disiapkan",
  shipped_to_tailor: "Kain dikirim ke penjahit", received_by_tailor: "Kain diterima penjahit",
  inspection_passed: "Kain lolos pemeriksaan", inspection_issue: "Kain bermasalah",
  in_production: "Sedang dijahit", quality_check: "Pemeriksaan mutu", shipped_to_buyer: "Dikirim ke pembeli",
  delivered: "Tiba", completed: "Selesai", cancelled: "Dibatalkan", failed_fulfillment: "Gagal diproses",
};
export const statusLabel = (s: string) => STATUS_LABEL[s] ?? s.replaceAll("_", " ");
