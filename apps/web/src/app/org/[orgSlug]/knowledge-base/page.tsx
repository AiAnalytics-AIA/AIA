import { Panel } from "@/components/ui";
import { t } from "@/i18n/t";

export default function ProjectMemoryPage() {
  return (
    <Panel title={t("projectMemory.title")}>
      <div className="text-xs text-ink-muted">{t("projectMemory.body")}</div>
    </Panel>
  );
}
