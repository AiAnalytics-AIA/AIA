import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { THEME_BOOT_SCRIPT } from "@/components/theme/theme";

// Self-hosted faces (see src/app/fonts/README.md). The variable names are the
// ones scripts/build-tokens.mjs points --font-sans/-mono/-serif/-display at.
const plexSans = localFont({
  variable: "--font-plex-sans",
  display: "swap",
  src: [
    { path: "./fonts/IBMPlexSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexSans-Italic.woff2", weight: "400", style: "italic" },
    { path: "./fonts/IBMPlexSans-Medium.woff2", weight: "500", style: "normal" },
    { path: "./fonts/IBMPlexSans-SemiBold.woff2", weight: "600", style: "normal" },
  ],
});
const plexMono = localFont({
  variable: "--font-plex-mono",
  display: "swap",
  src: [
    { path: "./fonts/IBMPlexMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexMono-Medium.woff2", weight: "500", style: "normal" },
  ],
});
const sourceSerif = localFont({
  variable: "--font-source-serif",
  display: "swap",
  src: [
    { path: "./fonts/SourceSerif4-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/SourceSerif4-Italic.woff2", weight: "400", style: "italic" },
    { path: "./fonts/SourceSerif4-Semibold.woff2", weight: "600", style: "normal" },
  ],
});
const sourceSerifDisplay = localFont({
  variable: "--font-source-serif-display",
  display: "swap",
  src: [{ path: "./fonts/SourceSerif4Display-Semibold.woff2", weight: "600", style: "normal" }],
});

export const metadata: Metadata = {
  title: "AIA",
  description: "Agentic AI Analytics — interní výzkumný systém",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: the boot script sets data-theme before hydration.
    <html lang="cs" suppressHydrationWarning className={`${plexSans.variable} ${plexMono.variable} ${sourceSerif.variable} ${sourceSerifDisplay.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
