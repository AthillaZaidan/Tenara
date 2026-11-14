"use client";

import { AddressForm } from "@/components/AddressForm";
import { Notice, useAction, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type Address = { id: string; label: string; recipient_name: string; phone: string; line1: string; city: string; province: string; postal_code: string | null };
type Photo = { id: string; consent_id: string; width: number; height: number; created_at: string; delete_after: string };
type ConsentNotice = { text: string; default_retention_minutes: number; max_retention_days: number };

export function AccountData() {
  const addresses = useLoad(() => api<Address[]>("/addresses"), "addresses");
  const photos = useLoad(() => api<Photo[]>("/body-photos"), "body-photos");
  const notice = useLoad(() => api<ConsentNotice>("/photo-consent-notice", { token: null }), "photo-consent-notice");
  const act = useAction();
  return <div className="grid max-w-4xl gap-12">
    <section className="grid gap-4"><h2 className="t-head text-3xl">Alamat pengiriman</h2><p>Alamat hanya digunakan untuk transaksi dan permintaan yang Anda pilih.</p>{addresses.error && <Notice tone="error">{addresses.error}</Notice>}{act.error && <Notice tone="error">{act.error}</Notice>}
      {addresses.data?.length ? <ul className="grid list-none gap-3 p-0 sm:grid-cols-2">{addresses.data.map((address) => <li key={address.id} className="grid gap-2 rounded-xl bg-surface p-5"><strong>{address.label}</strong><span>{address.recipient_name} · {address.phone}</span><span>{address.line1}, {address.city}, {address.province} {address.postal_code ?? ""}</span><button className="link w-fit text-sm" disabled={act.busy} onClick={async () => { if (!window.confirm(`Hapus alamat ${address.label}?`)) return; const result = await act.run(() => api(`/addresses/${address.id}`, { method: "DELETE" })); if (result) addresses.reload(); }}>Hapus alamat</button></li>)}</ul> : <p>Belum ada alamat tersimpan.</p>}
      <AddressForm onCreated={() => addresses.reload()} />
    </section>
    <section className="grid gap-4"><h2 className="t-head text-3xl">Foto badan dan izin</h2><p>Foto privat. Masa retensi mengikuti izin yang Anda berikan. Menghapus foto tidak menghapus ukuran yang sudah dibuat.</p>{notice.data && <Notice>{notice.data.text} Masa simpan bawaan: {notice.data.default_retention_minutes} menit; maksimum {notice.data.max_retention_days} hari.</Notice>}{photos.error && <Notice tone="error">{photos.error}</Notice>}
      {!photos.data?.length && !photos.loading && <p>Tidak ada foto badan yang masih tersimpan.</p>}
      <ul className="grid list-none gap-3 p-0">{photos.data?.map((photo) => <li key={photo.id} className="grid gap-2 rounded-xl bg-surface p-5"><strong>Foto {photo.width} × {photo.height}</strong><span className="text-base">Diunggah {when(photo.created_at)} · dijadwalkan dihapus {when(photo.delete_after)}</span><div className="flex flex-wrap gap-3"><button className="link w-fit text-base" disabled={act.busy} onClick={async () => { if (!window.confirm("Hapus foto dan semua ilustrasi Fit On yang memakai foto ini? Ukuran tersimpan tetap ada.")) return; const result = await act.run(() => api(`/body-photos/${photo.id}`, { method: "DELETE" })); if (result) photos.reload(); }}>Hapus foto</button><button className="link w-fit text-base text-danger" disabled={act.busy} onClick={async () => { if (!window.confirm("Cabut izin ini? Semua foto yang menggunakan izin ini akan dihapus.")) return; const result = await act.run(() => api(`/photo-consents/${photo.consent_id}/revoke`, { method: "POST" })); if (result) photos.reload(); }}>Cabut izin dan hapus fotonya</button></div></li>)}</ul>
      <p className="text-sm">Izin foto baru diminta di Studio tepat sebelum unggah dan pemrosesan.</p>
    </section>
  </div>;
}
