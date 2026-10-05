"use client";

// One simulation of one client. Its thirteen-stage workflow is not in AIA yet,
// and 18.6.6, where it ran, is no longer part of the product (ADR 0018): the frame
// says so where the person meets it and keeps the client and the study in view.

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { AppShell } from "./AppShell";
import { useClient } from "./clients/ClientContext";
import { CARD, Loaded } from "./states";
import { useResource } from "./useResource";

export function SimulationFrame({ studyId }: { studyId: string }) {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.study(studyId), [studyId]);
  const name = res.state === "ready" ? res.data.study.name : "";
  return (
    <AppShell
      crumbs={[
        { label: t("aia.navClients"), href: appRoutes.clients() },
        { label: client.name, href: appRoutes.client(client.client_id) },
        { label: t("aia.study.crumbSimulations"), href: appRoutes.area(client.client_id, "simulations") },
        { label: name || "…" },
      ]}
      eyebrow={t("aia.kind.SIMULATION")}
      title={name || t("aia.simulation.frameTitle")}
      client={{ id: client.client_id, name: client.name }}
    >
      <Loaded res={res} retry={retry}>
        {(w) =>
          w.study.client_id !== client.client_id || w.study.kind !== "SIMULATION" ? null : (
            <section className={`${CARD} max-w-2xl`}>
              <p className="text-sm leading-6">{tv("aia.simulation.frameText", { client: client.name })}</p>
              <p role="status" className="mt-4 rounded-sm border border-border bg-surface-sunken p-3 text-sm leading-6 text-ink">
                {t("aia.simulation.notInAia")}
              </p>
            </section>
          )
        }
      </Loaded>
    </AppShell>
  );
}
