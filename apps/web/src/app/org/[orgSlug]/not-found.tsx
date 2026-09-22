import { t } from "@/i18n/t";

/** Same copy whether the thing is missing or not granted — the API returns 404 for both, by design. */
export default function OrgNotFound() {
  return <p className="text-sm">{t("app.notFound")}</p>;
}
