import { Card } from "@/components/aia/ui";
import { t } from "@/i18n/t";

export default function ProjectMemoryPage() {
  return (
    <Card title={t("projectMemory.title")}>
      <div className="text-xs text-ink-muted">{t("projectMemory.body")}</div>
    </Card>
  );
}
