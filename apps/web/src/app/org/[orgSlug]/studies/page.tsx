import { redirect } from "next/navigation";

/** The study list is the Portfolio; this path exists so old and hand-typed links land somewhere real. */
export default async function StudiesIndex({ params }: { params: Promise<{ orgSlug: string }> }) {
  const { orgSlug } = await params;
  redirect(`/org/${orgSlug}/dashboard`);
}
