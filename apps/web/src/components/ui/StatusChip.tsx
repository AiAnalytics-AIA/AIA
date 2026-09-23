import { appearance, type StatusKind, type ViewerActionability } from "@/design/status";
import { StatusGlyph } from "./StatusGlyph";
import { TONE_CHIP } from "./tone";

/**
 * A domain status, drawn. It maps a value to an appearance; it never decides
 * what the status is. `viewer` is what the API said about the authenticated
 * viewer (OI-11); without it, a human-waiting status is shown as the team's,
 * never as "yours". Always glyph + text: colour is never the only cue.
 */
export function StatusChip({
  kind, value, viewer, small = false, showAudience = false,
}: {
  kind: StatusKind;
  value: string;
  viewer?: ViewerActionability;
  small?: boolean;
  showAudience?: boolean;
}) {
  const a = appearance(kind, value, viewer);
  return (
    <span
      data-status={value}
      data-tone={a.tone}
      className={`inline-flex max-w-full items-center gap-1.5 rounded-sm border ${small ? "min-h-5 px-1.5 text-xs" : "min-h-6 px-2 text-xs"} font-medium leading-4 tracking-[0.01em] ${TONE_CHIP[a.tone]}`}
    >
      <StatusGlyph tone={a.tone} size={small ? 12 : 14} />
      <span className="whitespace-normal">
        {a.label}
        {showAudience && a.audience ? <span className="font-normal"> · {a.audience}</span> : null}
      </span>
    </span>
  );
}
