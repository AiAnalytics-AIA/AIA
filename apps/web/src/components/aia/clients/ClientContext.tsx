"use client";

// One client's workspace (ADR 0015): the client is resolved once by the
// /app/clients/<client> layout -- through AIA's scope, 404 outside it -- and every
// area inside reads it from here. ClientPage draws the frame every area shares:
// the client's name as the title, its areas as tabs, and starting new work. The
// intake sheet (client-workspace C7b) is the client's one way in for files: opened
// from Přidat podklady on any area or by files dropped anywhere on the page.

import { useRouter, usePathname } from "next/navigation";
import { type DragEvent, type ReactNode, createContext, useCallback, useContext, useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientWorkspace, type StudyKind, workspace } from "@/lib/api";
import { type ClientArea, appRoutes } from "@/lib/app-routes";
import { type Ask, AskDialog, Button, Chip } from "../../rehome/ui";
import { AppShell, type Crumb, type Tab } from "../AppShell";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { IntakeSheet } from "./IntakeSheet";

/** Files handed to the intake sheet; `n` moves with every hand-over, so the same files twice still arrive. */
export type Incoming = { files: File[]; n: number };

type Value = {
  client: ClientWorkspace;
  reload: () => void;
  /** The intake sheet is open, with the files handed to it so far. */
  intake: Incoming | null;
  openIntake: (files?: File[]) => void;
  closeIntake: () => void;
  /** Moves each time the sheet adds knowledge, so a list on the page reads again. */
  added: number;
  noteAdded: () => void;
};
const Ctx = createContext<Value | null>(null);

export function useClient(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useClient outside a client workspace");
  return v;
}

/** Test and layout seam: provide an already resolved client. */
export function ClientValue({ client, reload = () => {}, children }: { client: ClientWorkspace; reload?: () => void; children: ReactNode }) {
  const [intake, setIntake] = useState<Incoming | null>(null);
  const [added, setAdded] = useState(0);
  const openIntake = useCallback(
    (files: File[] = []) => setIntake((cur) => ({ files: [...(cur?.files ?? []), ...files], n: (cur?.n ?? 0) + 1 })),
    [],
  );
  const closeIntake = useCallback(() => setIntake(null), []);
  const noteAdded = useCallback(() => setAdded((a) => a + 1), []);
  const value = useMemo(
    () => ({ client, reload, intake, openIntake, closeIntake, added, noteAdded }),
    [client, reload, intake, openIntake, closeIntake, added, noteAdded],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");

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
      title: kind === "RESEARCH" ? t("aia.client.newResearchTitle") : t("aia.client.newSimulationTitle"),
      message: t("aia.client.studyName"),
      placeholder: kind === "RESEARCH" ? t("aia.client.researchPlaceholder") : t("aia.client.simulationPlaceholder"),
      yes: kind === "RESEARCH" ? t("aia.client.createResearch") : t("aia.client.createSimulation"),
      required: true,
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

const AREAS: ClientArea[] = ["overview", "research", "simulations", "knowledge", "data", "profile"];

/** The client's tabs, each with what it counts: open studies, knowledge waiting on a person, datasets. */
export function clientTabs(client: ClientWorkspace, area: ClientArea): Tab[] {
  const c = client.counts;
  const count = (a: ClientArea): Pick<Tab, "count" | "countLabel" | "attention"> => {
    if (!c) return {};
    if (a === "research") return { count: c.research, countLabel: tv("aia.client.counts.open", { n: c.research }) };
    if (a === "simulations") return { count: c.simulations, countLabel: tv("aia.client.counts.open", { n: c.simulations }) };
    if (a === "knowledge") return { count: c.pending_proposals, countLabel: tv("aia.client.counts.pending", { n: c.pending_proposals ?? 0 }), attention: true };
    if (a === "data") return { count: c.datasets, countLabel: tv("aia.client.counts.datasets", { n: c.datasets ?? 0 }) };
    return {};
  };
  return AREAS.map((a) => ({ key: a, label: t(`aia.client.tabs.${a}`), href: appRoutes.area(client.client_id, a), active: a === area, ...count(a) }));
}

function activeArea(path: string, clientId: string): ClientArea {
  const rest = path.slice(appRoutes.client(clientId).length).split("/")[1] ?? "";
  return (AREAS as string[]).includes(rest) ? (rest as ClientArea) : "overview";
}

/** The frame of every area of one client. `actions` defaults to starting new work. */
export function ClientPage({ children, sub, crumbs = [], actions }: { children: ReactNode; sub?: string; crumbs?: Crumb[]; actions?: ReactNode }) {
  const { client, intake, openIntake } = useClient();
  const path = usePathname() ?? "";
  const area = activeArea(path, client.client_id);
  const { start, dialog, error } = useStartStudy();
  const may = canStart(client);
  const mayAdd = mayAddMaterial(client);
  const [dragging, setDragging] = useState(false);
  const defaultActions = may || mayAdd ? (
    <>
      {mayAdd ? <IntakeButton /> : null}
      {may && area !== "simulations" ? <Button variant="primary" icon="plus" onClick={() => start("RESEARCH")}>{t("aia.client.newResearch")}</Button> : null}
      {may && (area === "overview" || area === "simulations") ? (
        <Button variant={area === "simulations" ? "primary" : "secondary"} icon="plus" onClick={() => start("SIMULATION")}>{t("aia.client.newSimulation")}</Button>
      ) : null}
    </>
  ) : null;
  // Files dropped anywhere on the client's page open the intake sheet with them.
  const drop = mayAdd
    ? {
        onDragOver: (e: DragEvent) => {
          if (!hasFiles(e)) return;
          e.preventDefault();
          if (!dragging) setDragging(true);
        },
        onDragLeave: (e: DragEvent) => {
          if (e.relatedTarget === null) setDragging(false);
        },
        onDrop: (e: DragEvent) => {
          if (!hasFiles(e)) return;
          e.preventDefault();
          setDragging(false);
          const files = Array.from(e.dataTransfer.files);
          if (files.length) openIntake(files);
        },
      }
    : {};
  return (
    <div {...drop} className="contents">
    <AppShell
      crumbs={[{ label: t("aia.navClients"), href: appRoutes.clients() }, { label: client.name, href: appRoutes.client(client.client_id) }, ...crumbs]}
      title={client.name}
      sub={sub}
      client={{ id: client.client_id, name: client.name }}
      status={<Chip tone="neutral">{t(`aia.client.status.${client.status}`)}</Chip>}
      action={actions ?? defaultActions}
      tabs={clientTabs(client, area)}
    >
      {error ? <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
      {children}
      {dialog}
    </AppShell>
    {dragging && !intake ? (
      <div aria-hidden="true" className="pointer-events-none fixed inset-3 z-40 flex items-center justify-center rounded-md border-2 border-dashed border-signal bg-signal-wash/80">
        <span className="rounded-md bg-surface-raised px-4 py-2 text-sm font-semibold text-signal">{t("aia.intake.dropHere")}</span>
      </div>
    ) : null}
    {intake ? <IntakeSheet /> : null}
    </div>
  );
}

/** Who may bring material to the client: whoever may add knowledge to it. */
export const mayAddMaterial = (c: ClientWorkspace) => c.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE");

/** Přidat podklady: the client's one way in for files, on every area. */
export function IntakeButton({ variant = "secondary" }: { variant?: "primary" | "secondary" }) {
  const { openIntake } = useClient();
  return (
    <Button variant={variant} icon="attach" aria-haspopup="dialog" onClick={() => openIntake()}>
      {t("aia.client.addKnowledge")}
    </Button>
  );
}
