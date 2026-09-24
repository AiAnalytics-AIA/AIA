import type { ReactNode } from "react";

import { ResearchSession } from "@/components/rehome/research/ResearchScreen";

// One research project's session for all its steps: a layout is not re-rendered
// when only the step segment changes, so the project is loaded once and a
// change still waiting to be saved survives moving to another step.
export default async function ResearchProjectLayout({ children, params }: { children: ReactNode; params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <ResearchSession projectId={decodeURIComponent(projectId)}>{children}</ResearchSession>;
}
