import { notFound } from "next/navigation";
import { Page } from "@/components/ui";
import { TextileStudy } from "@/components/TextileStudy";
import { api, ApiError } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { GalleryVariant } from "@/lib/variants";

type Passport = { entry: Entry; story: { body: string; unresolved: string[] } | null; notice: string; reference_images: { url: string; caption: string | null; credit: string | null; license: string | null }[] };

export default async function StudyPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ variant?: string }> }) {
  const { slug } = await params;
  const { variant } = await searchParams;
  let passport: Passport;
  let variants: GalleryVariant[];
  try {
    [passport, variants] = await Promise.all([api<Passport>(`/gallery/${encodeURIComponent(slug)}/passport`, { token: null }), api<GalleryVariant[]>(`/gallery/${encodeURIComponent(slug)}/variants`, { token: null })]);
  } catch (error) { if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound(); throw error; }
  return <Page><div className="py-8"><TextileStudy entry={passport.entry} references={passport.reference_images} variants={variants} initialVariant={variant ?? ""} story={passport.story} notice={passport.notice} /></div></Page>;
}
