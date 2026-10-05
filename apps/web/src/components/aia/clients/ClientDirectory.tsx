"use client";

// Klienti (ADR 0015): the first decision -- which client am I working for? Each
// card is one client of the organization (every member sees all of them, ADR
// 0019), with the work that is active there. Nothing else is on this page.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientCard, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { plural, relative } from "@/lib/format";
import { Icon } from "../../rehome/icons";
import { type Ask, AskDialog, Button } from "../../rehome/ui";
import { AppShell } from "../AppShell";
import { Empty, Loaded } from "../states";
import { useResource } from "../useResource";

export function roleLabel(role: string | null): string {
  return t(`aia.roles.${role ?? "none"}`);
}

function Card({ c }: { c: ClientCard }) {
  return (
    <li>
      <Link
        href={appRoutes.client(c.client_id)}
        className="flex h-full flex-col gap-3 rounded-md border border-border bg-surface-raised p-5 no-underline hover:border-border-strong hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        <div className="flex items-start justify-between gap-3">
          <span className="text-lg font-semibold text-ink">{c.name}</span>
          <Icon name="next" className="mt-1 text-ink-faint" />
        </div>
        <div className="text-sm text-ink-muted">
          {c.active_count ? plural(c.active_count, "aktivní práce", "aktivní práce", "aktivních prací") : t("aia.clients.noActive")}
        </div>
        {c.recent.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {c.recent.map((s) => (
              <li key={s.study_id} className="flex items-center gap-2 text-ink">
                <Icon name={s.kind === "SIMULATION" ? "simulation" : "research"} size={14} className="text-ink-faint" />
                <span className="truncate">{s.name}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="mt-auto flex flex-wrap justify-between gap-2 pt-1 text-xs text-ink-faint">
          <span>{tv("aia.clients.yourRole", { role: roleLabel(c.your_role) })}</span>
          {c.modified_at ? <span>{relative(c.modified_at)}</span> : null}
        </div>
      </Link>
    </li>
  );
}

export function ClientDirectory() {
  const router = useRouter();
  const [clients, retry] = useResource(() => workspace.clients(), []);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);

  const newClient = () =>
    setAsk({
      kind: "prompt",
      message: t("aia.clients.newName"),
      initial: "",
      resolve: (name) => {
        if (!name?.trim()) return;
        workspace.startClient(name.trim()).then(
          (c) => router.push(appRoutes.client(c.client_id)),
          (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
        );
      },
    });

  return (
    <AppShell
      title={t("aia.clients.title")}
      sub={t("aia.clients.sub")}
      action={<Button variant="primary" icon="plus" onClick={newClient}>{t("aia.clients.new")}</Button>}
    >
      {error ? <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
      <Loaded res={clients} retry={retry}>
        {(list) =>
          list.length ? (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {list.map((c) => (
                <Card key={c.client_id} c={c} />
              ))}
            </ul>
          ) : (
            <Empty>
              {t("aia.clients.empty")}
            </Empty>
          )
        }
      </Loaded>
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
    </AppShell>
  );
}
