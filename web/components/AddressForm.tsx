"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Field, Notice, useAction } from "@/components/ui";

export function AddressForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState({ label: "Rumah", recipient_name: "", phone: "", line1: "", city: "", province: "", postal_code: "" });
  const act = useAction();
  return <div className="grid gap-3">
    <button type="button" className="btn btn-quiet w-fit" onClick={() => setOpen(!open)}>{open ? "Tutup form alamat" : "Tambah alamat"}</button>
    {open && <div className="grid gap-3">
      {([ ["label", "Label alamat"], ["recipient_name", "Nama penerima"], ["phone", "Nomor telepon"], ["line1", "Alamat lengkap"], ["city", "Kota"], ["province", "Provinsi"], ["postal_code", "Kode pos (opsional)"] ] as const).map(([key, label]) =>
        <Field label={label} key={key}><input className="field" value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} /></Field>)}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button type="button" className="btn w-fit" disabled={act.busy || !values.label.trim() || !values.recipient_name.trim() || !values.phone.trim() || !values.line1.trim() || !values.city.trim() || !values.province.trim()} onClick={async () => {
        const address = await act.run(() => api<{ id: string }>("/addresses", { body: { ...values, postal_code: values.postal_code || null } }));
        if (address) { setOpen(false); onCreated(address.id); }
      }}>Simpan alamat</button>
    </div>}
  </div>;
}
