import { StudyList } from "@/components/aia/clients/StudyList";

export const metadata = { title: "Simulace · AIA" };

export default function SimulationListPage() {
  return <StudyList kind="SIMULATION" />;
}
