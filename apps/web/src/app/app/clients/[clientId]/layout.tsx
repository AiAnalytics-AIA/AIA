import type { ReactNode } from "react";

import { ClientProvider } from "@/components/aia/clients/ClientContext";

// One client's workspace: the client is resolved once, through AIA's scope, for
// every area and study inside it (ADR 0015).
export default async function ClientLayout({ children, params }: { children: ReactNode; params: Promise<{ clientId: string }> }) {
  const { clientId } = await params;
  return <ClientProvider clientId={decodeURIComponent(clientId)}>{children}</ClientProvider>;
}
