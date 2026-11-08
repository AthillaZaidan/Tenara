"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";

function Form() {
  const router = useRouter();
  const entries = useLoad(() => api<{ items: Entry[] }>("/gallery?limit=100"), "e");
  const act = useAction();
  const [f, setF] = useState({ entry_id: "", title: "", description: "", selling_unit: "meter", price_idr: "", min_quantity: "1", quantity_increment: "0.5", material: "", usable_width_cm: "", piece_length_cm: "", piece_width_cm: "", city: "", province: "", dispatch_days: "3", merchant_claimed_origin: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const meter = f.selling_unit === "meter";
  const num = (v: string) => (v ? Number(v) : null);
  return (
    <form
      className="grid max-w-2xl gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { entry_id: f.entry_id, title: f.title, description: f.description, selling_unit: f.selling_unit, price_idr: Number(f.price_idr), min_quantity: meter ? f.min_quantity : "1", quantity_increment: meter ? f.quantity_increment : "1", material: f.material || null, usable_width_cm: meter ? num(f.usable_width_cm) : null, piece_length_cm: meter ? null : num(f.piece_length_cm), piece_width_cm: meter ? null : num(f.piece_width_cm), city: f.city || null, province: f.province || null, dispatch_days: Number(f.dispatch_days), merchant_claimed_origin: f.merchant_claimed_origin || null };
        const l = await act.run(() => api<{ id: string }>("/listings", { body }));
        if (l) router.push(`/merchant/listings/${l.id}`);
      }}
    >
      <Field label="Entri Gallery" hint="Kain Anda ditautkan ke satu entri tradisi.">
        <select className="field" required value={f.entry_id} onChange={set("entry_id")}>
          <option value="">Pilih entri…</option>
          {entries.data?.items.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </Field>
      <Field label="Judul"><input className="field" required value={f.title} onChange={set("title")} /></Field>
      <Field label="Deskripsi"><textarea className="field" value={f.description} onChange={set("description")} /></Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Dijual per"><select className="field" value={f.selling_unit} onChange={set("selling_unit")}><option value="meter">Meter</option><option value="piece">Potong utuh</option></select></Field>
        <Field label="Harga (Rp)"><input className="field" required inputMode="numeric" value={f.price_idr} onChange={set("price_idr")} /></Field>
        {meter ? (<>
          <Field label="Lebar pakai (cm)" hint="Dipakai untuk menghitung kebutuhan kain."><input className="field" required inputMode="numeric" value={f.usable_width_cm} onChange={set("usable_width_cm")} /></Field>
          <Field label="Minimum pembelian (m)"><input className="field" inputMode="decimal" value={f.min_quantity} onChange={set("min_quantity")} /></Field>
          <Field label="Kelipatan (m)"><input className="field" inputMode="decimal" value={f.quantity_increment} onChange={set("quantity_increment")} /></Field>
        </>) : (<>
          <Field label="Panjang potong (cm)"><input className="field" required inputMode="numeric" value={f.piece_length_cm} onChange={set("piece_length_cm")} /></Field>
          <Field label="Lebar potong (cm)"><input className="field" required inputMode="numeric" value={f.piece_width_cm} onChange={set("piece_width_cm")} /></Field>
        </>)}
        <Field label="Bahan"><input className="field" value={f.material} onChange={set("material")} placeholder="katun, sutra, songket…" /></Field>
        <Field label="Dikirim dalam (hari)"><input className="field" inputMode="numeric" value={f.dispatch_days} onChange={set("dispatch_days")} /></Field>
        <Field label="Kota asal kirim"><input className="field" value={f.city} onChange={set("city")} /></Field>
        <Field label="Provinsi asal kirim"><input className="field" value={f.province} onChange={set("province")} /></Field>
      </div>
      <Field label="Klaim asal-usul menurut Anda" hint="Ditampilkan terpisah dari verifikasi kurator. Tidak menjadi bukti keaslian."><textarea className="field" value={f.merchant_claimed_origin} onChange={set("merchant_claimed_origin")} /></Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy}>Simpan sebagai draf</button>
    </form>
  );
}

export default function NewListingPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/merchant" className="link">← Dasbor</Link></p>
      <h1 className="t-head mb-10">Kain baru</h1>
      <RequireAuth role="merchant"><Form /></RequireAuth>
    </Page>
  );
}
