"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Upload, type Uploaded } from "@/components/Upload";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

function Form() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const order = useLoad(() => api<{ kind: string }>(`/orders/${id}`), id);
  const act = useAction();
  const [target, setTarget] = useState("merchant");
  const [component, setComponent] = useState("fabric");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<Uploaded[]>([]);
  const custom = order.data?.kind === "custom";
  return (
    <form
      className="grid max-w-xl gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const claim = await act.run(() => api<{ id: string }>(`/orders/${id}/claims`, { body: { target, component, description, evidence_file_ids: files.map((f) => f.id) } }));
        if (claim) router.push(`/claims/${claim.id}`);
      }}
    >
      <p className="text-base">Klaim dapat diajukan dalam 14 hari setelah barang diterima (kebijakan demo). Penjual atau penjahit punya 48 jam untuk menanggapi.</p>
      <Field label="Yang dikomplain">
        <select className="field" value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="merchant">Penjual kain</option>
          {custom && <option value="tailor">Penjahit</option>}
        </select>
      </Field>
      <Field label="Bagian yang bermasalah">
        <select className="field" value={component} onChange={(e) => setComponent(e.target.value)}>
          <option value="fabric">Kain</option>
          <option value="garment">Hasil jahitan</option>
          <option value="shipping">Pengiriman</option>
          <option value="service">Layanan</option>
        </select>
      </Field>
      <Field label="Ceritakan masalahnya" hint="Minimal 5 karakter. Sebutkan apa yang diharapkan dan apa yang diterima.">
        <textarea className="field" required minLength={5} value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <Upload kind="claim_evidence" label="Foto bukti (opsional, bisa lebih dari satu)" onUploaded={(f) => setFiles((p) => [...p, f])} />
      {files.length > 0 && <ul className="grid list-none gap-1 p-0 text-base">{files.map((f) => <li key={f.id}>Terlampir: {f.content_type}</li>)}</ul>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy}>Kirim klaim</button>
    </form>
  );
}

export default function NewClaimPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href={`/orders/${id}`} className="link">← Pesanan</Link></p>
      <h1 className="t-head mb-8">Ajukan klaim</h1>
      <RequireAuth><Form /></RequireAuth>
    </Page>
  );
}
