import { notFound } from "next/navigation";
import { JourneyExperience } from "@/components/exploration/journey-experience";
import { findExploreRegion } from "@/lib/exploration";

export default async function RegionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!findExploreRegion(id)) notFound();
  return <main id="main-content"><JourneyExperience key={id} regionId={id} /></main>;
}
