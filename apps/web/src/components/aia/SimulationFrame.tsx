"use client";

// One simulation of one client. Its thirteen-stage workflow is not rebuilt yet;
// the frame says so, keeps the client and the study in view, and offers the
// classic interface explicitly -- never as a fallback the person falls into.

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { classicHref } from "@/lib/interface-handoff";
import { ClassicLink } from "../rehome/ui";
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
    >
      <Loaded res={res} retry={retry}>
        {(w) =>
          w.study.client_id !== client.client_id || w.study.kind !== "SIMULATION" ? null : (
            <section className={`${CARD} max-w-2xl`}>
              <p className="text-sm leading-6">{tv("aia.simulation.frameText", { client: client.name })}</p>
              <div className="mt-4">
                <ClassicLink href={classicHref({ switch: "simulation" })} variant="primary">{t("aia.simulation.openClassic")}</ClassicLink>
              </div>
              <p className="mt-2 text-xs text-ink-faint">{t("aia.simulation.classicNote")}</p>
            </section>
          )
        }
      </Loaded>
    </AppShell>
  );
}
