import { notFound, redirect } from "next/navigation";
import { TextileStudy } from "@/components/exploration/textile-study";
import { GalleryWorkspace } from "@/components/gallery";
import { findTradition, textileHref } from "@/lib/exploration";

export default async function TextileStudyPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{
    pilihan?: string | string[];
    museum?: string | string[];
  }>;
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const tradition = findTradition(id);
  if (!tradition) notFound();

  const pilihan = Array.isArray(query.pilihan)
    ? query.pilihan[0]
    : query.pilihan;
  const museum = Array.isArray(query.museum) ? query.museum[0] : query.museum;
  if (id !== tradition.id) {
    const search = new URLSearchParams();
    if (pilihan !== undefined) search.set("pilihan", pilihan);
    if (museum !== undefined) search.set("museum", museum);
    redirect(`${textileHref(tradition.id)}${search.size ? `?${search}` : ""}`);
  }

  return (
    <main id="main-content">
      {tradition.id === "hinggi-sumba" && museum === "1" ? (
        <GalleryWorkspace />
      ) : (
        <TextileStudy tradition={tradition} initialSampleCode={pilihan} />
      )}
    </main>
  );
}
