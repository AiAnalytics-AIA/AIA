"use client";

import { PageError } from "@/components/errors/PageError";

// A render crash anywhere under /app: reported, said, and the shell above it kept.
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <PageError error={error} reset={reset} boundary="app" />;
}
