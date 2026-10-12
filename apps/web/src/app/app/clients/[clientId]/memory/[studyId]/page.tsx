import { MemoryStudy } from "@/components/aia/MemoryStudy";

export const metadata = { title: "Projektová paměť · AIA" };

// A past research of the client, read-only (project memory M2).
export default async function Page({ params }: { params: Promise<{ studyId: string }> }) {
  const { studyId } = await params;
  return <MemoryStudy studyId={decodeURIComponent(studyId)} />;
}
