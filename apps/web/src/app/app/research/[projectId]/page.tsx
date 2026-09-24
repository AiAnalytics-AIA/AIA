import { redirect } from "next/navigation";

export default async function ResearchProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  redirect(`/app/research/${encodeURIComponent(projectId)}/brief`);
}
