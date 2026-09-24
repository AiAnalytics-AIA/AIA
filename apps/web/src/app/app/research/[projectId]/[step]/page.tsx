import { notFound } from "next/navigation";

import { ResearchScreen } from "@/components/rehome/research/ResearchScreen";
import { isStepKey } from "@/unit/research/steps";

export const metadata = { title: "Výzkum · AIA" };

export default async function ResearchStepPage({ params }: { params: Promise<{ projectId: string; step: string }> }) {
  const { projectId, step } = await params;
  if (!isStepKey(step)) notFound();
  return <ResearchScreen projectId={decodeURIComponent(projectId)} step={step} />;
}
