import type { Metadata } from "next";
import "./globals.css";

import { ErrorTracking } from "@/components/errors/ErrorTracking";

export const metadata: Metadata = {
  title: "AIA",
  description: "AIA research and simulation platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="cs">
      <body className="antialiased">
        <ErrorTracking />
        {children}
      </body>
    </html>
  );
}
