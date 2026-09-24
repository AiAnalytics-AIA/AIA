import { ResearchScreen } from "@/components/rehome/research/ResearchScreen";

export const metadata = { title: "Nový výzkum · AIA" };

// A new research project starts at the brief and gets its URL on its first save.
export default function NewResearchPage() {
  return <ResearchScreen projectId={null} step="brief" />;
}
