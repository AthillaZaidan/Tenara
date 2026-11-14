"use client";

import { useParams } from "next/navigation";
import { StudioLoading } from "@/components/Studio";
import { StudioWorkspace } from "@/components/StudioWorkspace";
import { RequireAuth } from "@/components/ui";

export default function CustomizePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <main className="studio-route frame">
      <RequireAuth loadingFallback={<StudioLoading />}>
        <StudioWorkspace initialCustomizationId={id} />
      </RequireAuth>
    </main>
  );
}
