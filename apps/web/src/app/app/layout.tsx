import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { REHOME_SWITCH, rehomeEnabledFrom } from "@/lib/rehome";

// The rebuilt interface (ADR 0014). Caddy puts the gate in front of /app; this
// layout adds the switch: with AIA_INTERFACE_REHOME_ENABLED off, every /app
// path is a 404. Read per request, so flipping the value needs no rebuild.
export const dynamic = "force-dynamic";

export default function RehomeLayout({ children }: { children: ReactNode }) {
  if (!rehomeEnabledFrom(process.env[REHOME_SWITCH])) notFound();
  return children;
}
