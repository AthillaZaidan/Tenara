import Link from "next/link";
import { notFound } from "next/navigation";
import { Page } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Merchant = { shop_name: string; description: string | null; city: string; province: string; verification_note: string };

export default async function MerchantProfile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let merchant: Merchant;
  try { merchant = await api<Merchant>(`/merchants/${id}`, { token: null }); }
  catch (error) { if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound(); throw error; }
  return <Page><div className="mx-auto grid max-w-3xl gap-6 py-10"><p className="text-sm font-semibold uppercase tracking-wider">Mitra penjual</p><h1 className="t-head">{merchant.shop_name}</h1><p>{merchant.city}, {merchant.province}</p>{merchant.description && <p>{merchant.description}</p>}<p className="rounded-xl bg-surface p-5 text-base">{merchant.verification_note}</p><Link href="/galeri" className="btn w-fit">Jelajahi kain</Link></div></Page>;
}
