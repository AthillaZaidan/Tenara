import Link from "next/link";
import { notFound } from "next/navigation";
import { Page } from "@/components/ui";
import { api, ApiError, idr } from "@/lib/api";

type Tailor = { shop_name: string; bio: string | null; city: string; province: string; service_area: string[]; experience_years: number; capabilities: { template_code: string; base_rate_idr: number; lead_time_days: number; materials: string[] }[] };

export default async function TailorProfile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let tailor: Tailor;
  try { tailor = await api<Tailor>(`/tailors/${id}`, { token: null }); }
  catch (error) { if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound(); throw error; }
  return <Page><div className="mx-auto grid max-w-3xl gap-6 py-10"><p className="text-sm font-semibold uppercase tracking-wider">Mitra penjahit terverifikasi</p><h1 className="t-head">{tailor.shop_name}</h1><p>{tailor.city}, {tailor.province} · pengalaman {tailor.experience_years} tahun</p>{tailor.bio && <p>{tailor.bio}</p>}<p className="text-base">Wilayah layanan: {tailor.service_area.join(", ") || "belum dicantumkan"}</p><h2 className="text-xl font-semibold">Model yang dilayani</h2><ul className="grid list-none gap-3 p-0">{tailor.capabilities.map((c) => <li key={c.template_code} className="rounded-xl bg-surface p-5"><p>{c.template_code} · mulai {idr(c.base_rate_idr)} · {c.lead_time_days} hari</p><p className="text-base">Bahan: {c.materials.join(", ") || "sesuai validasi"}</p></li>)}</ul><p className="text-base">Harga dan kelayakan akhir dikonfirmasi melalui penawaran penjahit.</p><Link href="/galeri" className="btn w-fit">Jelajahi kain</Link></div></Page>;
}
