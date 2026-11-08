export const OPTION_LABEL: Record<string, string> = {
  collar: "Kerah", buttons: "Kancing", pockets: "Saku", motif_placement: "Penempatan motif",
  hem_length_delta_cm: "Ubah panjang bawahan (cm)", sleeve_length_delta_cm: "Ubah panjang lengan (cm)",
  neckline: "Garis leher", skirt_length_delta_cm: "Ubah panjang rok (cm)", waist: "Pinggang", closure: "Penutup",
};

export const VALUE_LABEL: Record<string, string> = {
  classic: "Klasik", mandarin: "Mandarin", none: "Tanpa", plain_01: "Polos", wood_option_01: "Kayu", shell_option_01: "Kerang",
  left_chest_single: "Satu di dada kiri", double_chest: "Dua di dada", all_over: "Seluruh bagian", center_front: "Tengah depan",
  left_chest: "Dada kiri", hem_border: "Pinggiran bawah",
};

export const DIM_LABEL: Record<string, string> = {
  chest_circumference: "Lingkar dada", shoulder_width: "Lebar bahu", back_length: "Panjang punggung", sleeve_length: "Panjang lengan",
  waist_circumference: "Lingkar pinggang", hip_circumference: "Lingkar pinggul", skirt_length: "Panjang rok", inseam: "Panjang dalam celana",
  arm_circumference: "Lingkar lengan", neck_circumference: "Lingkar leher",
};

export const label = (map: Record<string, string>, key: string) => map[key] ?? key.replaceAll("_", " ");

export type OptionDef =
  | { type: "enum"; values: string[]; default: string }
  | { type: "number"; min: number; max: number; unit?: string; default: number };

export const REQUEST_STATUS: Record<string, string> = {
  draft: "Draf", submitted: "Menunggu konfirmasi stok penjual", validating: "Divalidasi penjahit",
  needs_revision: "Perlu direvisi", ready_for_quote: "Spesifikasi siap, penawaran disusun",
  awaiting_buyer: "Menunggu persetujuan pembeli", converted_to_order: "Menjadi pesanan", rejected: "Ditolak", withdrawn: "Ditarik",
};
