"use client";

// Profil: what AIA holds about the client itself. Today that is the client
// record -- its name, its status and your role in it -- read from the workspace
// the layout already resolved. The profile proper (industry, market, brands,
// competitors, contacts) is not in AIA yet, and the page says so where a person
// looks for it rather than offering fields that save nowhere.

import { t } from "@/i18n/t";
import { Chip } from "../../rehome/ui";
import { CARD } from "../states";
import { ClientPage, useClient } from "./ClientContext";
import { roleLabel } from "./ClientDirectory";

export function ProfileArea() {
  const { client } = useClient();
  return (
    <ClientPage sub={t("aia.profile.sub")}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <section className={CARD} aria-labelledby="profile-record">
          <h2 id="profile-record" className="text-base font-semibold">{t("aia.profile.recordTitle")}</h2>
          <dl className="mt-3 grid grid-cols-[10rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
            <dt className="text-ink-muted">{t("aia.profile.name")}</dt>
            <dd>{client.name}</dd>
            <dt className="text-ink-muted">{t("aia.profile.status")}</dt>
            <dd>
              <Chip tone="neutral">{t(`aia.client.status.${client.status}`)}</Chip>
            </dd>
            <dt className="text-ink-muted">{t("aia.profile.yourRole")}</dt>
            <dd>{roleLabel(client.your_role)}</dd>
          </dl>
          <p className="mt-4 text-xs leading-5 text-ink-faint">{t("aia.profile.statusOwner")}</p>
        </section>
        <section className={CARD} aria-labelledby="profile-missing">
          <h2 id="profile-missing" className="text-base font-semibold">{t("aia.profile.missingTitle")}</h2>
          <p className="mt-2 text-sm leading-6 text-ink-muted">{t("aia.profile.missingText")}</p>
        </section>
      </div>
    </ClientPage>
  );
}
