import { Panel } from "@/components/ui";
import { t } from "@/i18n/t";

export default function AdminSettingsPage() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={t("admin.clients")}>
        <div className="text-xs text-ink-muted">{t("admin.clientsBody")}</div>
      </Panel>
      <Panel title={t("admin.roles")}>
        <div className="text-xs text-ink-muted">{t("admin.rolesBody")}</div>
      </Panel>
    </div>
  );
}
