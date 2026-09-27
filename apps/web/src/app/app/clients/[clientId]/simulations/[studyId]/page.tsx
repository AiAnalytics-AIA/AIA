import { SimulationFrame } from "@/components/aia/SimulationFrame";

export const metadata = { title: "Simulace · AIA" };

export default async function SimulationPage({ params }: { params: Promise<{ studyId: string }> }) {
  const { studyId } = await params;
  return <SimulationFrame studyId={decodeURIComponent(studyId)} />;
}
