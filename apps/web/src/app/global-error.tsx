"use client";

import "./globals.css";

import { PageError } from "@/components/errors/PageError";

// A crash in the root layout itself, where no other boundary is left: it replaces the
// document, so it renders its own <html> and <body>.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="cs">
      <body className="antialiased bg-surface">
        <PageError error={error} reset={reset} boundary="global" />
      </body>
    </html>
  );
}
