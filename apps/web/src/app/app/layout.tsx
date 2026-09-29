import type { ReactNode } from "react";

// AIA's pages (ADR 0015). Caddy puts AIA's own gate in front of /app (ADR 0018
// decision 3): any active member of an organization, nothing about 18.6.6. There
// is no switch here any more: the one that turned /app off (ADR 0014) existed so
// the classic interface could stand in, and AIA is the product now. Rendered per
// request, as before, so a build never prerenders a page that depends on the
// person reading it.
export const dynamic = "force-dynamic";

export default function AppLayout({ children }: { children: ReactNode }) {
  return children;
}
