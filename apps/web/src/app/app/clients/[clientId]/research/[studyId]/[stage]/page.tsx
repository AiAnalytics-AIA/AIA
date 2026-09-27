import { ResearchStage } from "@/components/aia/ResearchStudy";

export const metadata = { title: "Výzkum · AIA" };

export default async function ResearchStagePage({ params }: { params: Promise<{ stage: string }> }) {
  const { stage } = await params;
  return <ResearchStage slug={stage} />;
}
