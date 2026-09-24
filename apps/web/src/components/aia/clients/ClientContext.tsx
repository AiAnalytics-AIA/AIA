"use client";

// One client's workspace (ADR 0015): the client is resolved once by the
// /app/clients/<client> layout -- through AIA's scope, 404 outside it -- and every
// area inside reads it from here. ClientPage draws the frame every area shares:
// the client's name as the title, its areas as tabs, and starting new work.

import { useRouter, usePathname } from "next/navigation";
import { type ReactNode, createContext, useContext, useState } from "react";

import { t } from "@/i18n/t";
import { type ClientWorkspace, type StudyKind, workspace } from "@/lib/api";
import { type ClientArea, appRoutes } from "@/lib/app-routes";
import { type Ask, AskDialog, Button } from "../../rehome/ui";
import { AppShell, type Crumb } from "../AppShell";
import { Loaded } from "../states";
import { useResource } from "../useResource";

type Value = { client: ClientWorkspace; reload: () => void };
const Ctx = createContext<Value | null>(null);

export function useClient(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useClient outside a client workspace");
  return v;
}

/** Test and layout seam: provide an already resolved client. */
export function ClientValue({ client, reload = () => {}, children }: { client: ClientWorkspace; reload?: () => void; children: ReactNode }) {
  return <Ctx.Provider value={{ client, reload }}>{children}</Ctx.Provider>;
}

export function ClientProvider({ clientId, children }: { clientId: string; children: ReactNode }) {
  const [res, retry] = useResource(() => workspace.client(clientId), [clientId]);
  if (res.state !== "ready") {
    return (
      <AppShell crumbs={[{ label: t("aia.navClients"), href: appRoutes.clients() }]} title={t("aia.navClients")}>
        <Loaded res={res} retry={retry}>{() => null}</Loaded>
      </AppShell>
    );
  }
  return <ClientValue client={res.data} reload={retry}>{children}</ClientValue>;
}

export const canStart = (c: ClientWorkspace) => c.permissions.includes("CREATE_STUDY");

/** Start a research or a simulation for this client, then open it. */
export function useStartStudy(): { start: (kind: StudyKind) => void; dialog: ReactNode; error: string | null } {
  const { client } = useClient();
  const router = useRouter();
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = (kind: StudyKind) =>
    setAsk({
      kind: "prompt",
      message: kind === "RESEARCH" ? t("aia.client.newResearchTitle") : t("aia.client.newSimulationTitle"),
      initial: "",
      resolve: (name) => {
        if (!name?.trim()) return;
        workspace.startStudy(client.client_id, name.trim(), kind).then(
          (s) =>
            router.push(
              kind === "RESEARCH" ? appRoutes.stage(client.client_id, s.study_id, "brief") : appRoutes.study(client.client_id, s.study_id, kind),
            ),
          (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
        );
      },
    });
  return { start, dialog: <AskDialog ask={ask} onDone={() => setAsk(null)} />, error };
}

const AREAS: ClientArea[] = ["overview", "research", "simulations", "knowledge", "data"];

function activeArea(path: string, clientId: string): ClientArea {
  const rest = path.slice(appRoutes.client(clientId).length).split("/")[1] ?? "";
  return (AREAS as string[]).includes(rest) ? (rest as ClientArea) : "overview";
}

/** The frame of every area of one client. `actions` defaults to starting new work. */
export function ClientPage({ children, sub, crumbs = [], actions }: { children: ReactNode; sub?: string; crumbs?: Crumb[]; actions?: ReactNode }) {
  const { client } = useClient();
  const path = usePathname() ?? "";
  const area = activeArea(path, client.client_id);
  const { start, dialog, error } = useStartStudy();
  const may = canStart(client);
  const defaultActions = may ? (
    <>
      {area !== "simulations" ? <Button variant="primary" icon="plus" onClick={() => start("RESEARCH")}>{t("aia.client.newResearch")}</Button> : null}
      {area === "overview" || area === "simulations" ? (
        <Button variant={area === "simulations" ? "primary" : "secondary"} icon="plus" onClick={() => start("SIMULATION")}>{t("aia.client.newSimulation")}</Button>
      ) : null}
    </>
  ) : null;
  return (
    <AppShell
      crumbs={[{ label: t("aia.navClients"), href: appRoutes.clients() }, { label: client.name, href: appRoutes.client(client.client_id) }, ...crumbs]}
      title={client.name}
      sub={sub}
      action={actions ?? defaultActions}
      tabs={AREAS.map((a) => ({ key: a, label: t(`aia.client.tabs.${a}`), href: appRoutes.area(client.client_id, a), active: a === area }))}
    >
      {error ? <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
      {children}
      {dialog}
    </AppShell>
  );
}
