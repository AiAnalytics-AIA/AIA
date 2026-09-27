import type { SettingControl, SettingItem, SettingValue } from "@/lib/api/types";
import { t } from "@/i18n/t";

const CONTROL_STYLE: Record<SettingControl, string> = {
  API: "border-blue-200 bg-blue-50 text-blue-800",
  DEPLOYMENT: "border-zinc-300 bg-zinc-100 text-zinc-800",
  CODE: "border-violet-200 bg-violet-50 text-violet-800",
  INVARIANT: "border-zinc-800 bg-zinc-900 text-white",
};

// Shape as well as colour: the glyph carries the meaning in greyscale too.
const CONTROL_GLYPH: Record<SettingControl, string> = {
  API: "✎",
  DEPLOYMENT: "⚙",
  CODE: "</>",
  INVARIANT: "■",
};

export function ControlBadge({ control }: { control: SettingControl }) {
  return (
    <span
      title={t(`settings.controlHelp.${control}`)}
      className={`inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium ${CONTROL_STYLE[control]}`}
    >
      <span aria-hidden>{CONTROL_GLYPH[control]}</span>
      {t(`settings.control.${control}`)}
    </span>
  );
}

// Null is "not configured" and looks like it: never a blank, never a zero.
export function Value({ value, unit }: { value: SettingValue; unit?: string | null }) {
  if (value === null) {
    return <span className="rounded border border-dashed border-zinc-400 px-1.5 text-xs text-zinc-600">∅ {t("settings.notConfigured")}</span>;
  }
  if (typeof value === "boolean") {
    return <span className="font-mono text-sm">{value ? t("settings.yes") : t("settings.no")}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-xs text-zinc-600">{t("settings.emptyList")}</span>;
    return (
      <span className="flex flex-wrap gap-1">
        {value.map((v) => (
          <code key={v} className="rounded bg-zinc-100 px-1.5 text-xs">{v}</code>
        ))}
      </span>
    );
  }
  return (
    <span className="font-mono text-sm tabular-nums">
      {String(value)}
      {unit ? <span className="ml-1 text-xs text-zinc-500">{unit}</span> : null}
    </span>
  );
}

export function SettingRow({ item }: { item: SettingItem }) {
  // An API control's value lives in the live panel beside it; the row shows the route.
  const showValue = item.control !== "API";
  return (
    <div className="grid grid-cols-1 gap-1 border-t border-zinc-100 py-2 first:border-t-0 md:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_auto] md:items-center md:gap-4">
      <div className="min-w-0">
        <div className="text-sm text-zinc-900">{t(`settings.items.${item.key}`)}</div>
        <code className="break-all text-[11px] text-zinc-500">{item.source}</code>
      </div>
      <div className="min-w-0">
        {showValue ? (
          <Value value={item.value} unit={item.unit} />
        ) : (
          <span className="text-xs text-zinc-500">
            {/* Project-level controls live on the project screen, not in this page's panels. */}
            {t(item.source.includes("/projects/") ? "settings.onProjectScreen" : "settings.editInPanel")}
          </span>
        )}
      </div>
      <ControlBadge control={item.control} />
    </div>
  );
}
