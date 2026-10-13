import { Suspense } from "react";

import { KnowledgeArea } from "@/components/aia/clients/KnowledgeArea";

export const metadata = { title: "Znalosti · AIA" };

// KnowledgeArea reads ?add= and ?view= with useSearchParams: inside Suspense, so the
// page never needs prerendering to know them.
export default function KnowledgePage() {
  return (
    <Suspense fallback={null}>
      <KnowledgeArea />
    </Suspense>
  );
}
