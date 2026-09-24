import type { ReactNode } from "react";

import { ResearchStudy } from "@/components/aia/ResearchStudy";

// One research's session for all its stages: a layout is not re-rendered when
// only the stage segment changes, so the working content is loaded once and a
// change still waiting to be saved survives moving to another stage (OI-56).
export default async function ResearchStudyLayout({ children, params }: { children: ReactNode; params: Promise<{ studyId: string }> }) {
  const { studyId } = await params;
  return <ResearchStudy studyId={decodeURIComponent(studyId)}>{children}</ResearchStudy>;
}
