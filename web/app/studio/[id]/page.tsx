"use client";

import { useParams } from "next/navigation";
import { StudioLoading } from "@/components/Studio";
import { StudioWorkspace } from "@/components/StudioWorkspace";
import { RequireAuth } from "@/components/ui";

export default function StudioStartPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <main className="studio-route frame">
      <RequireAuth loadingFallback={<StudioLoading />}>
        <StudioWorkspace initialListingId={id} />
      </RequireAuth>
    </main>
  );
}
