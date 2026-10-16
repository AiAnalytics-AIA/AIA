import { t } from "@/i18n/t";
import type { Coded } from "@/lib/reason-words";

/**
 * A code in words; one the client has no words for keeps its code: under technical details in a
 * block, or named after the words where the place is inline (a chip, a span in a line).
 */
export function CodedWords({ coded, inline = false }: { coded: Coded; inline?: boolean }) {
  if (inline) {
    return (
      <>
        {coded.words}
        {coded.code !== null ? (
          <span className="text-xs text-ink-muted"> ({t("research.exec.code.technical")}: <code className="break-all">{coded.code}</code>)</span>
        ) : null}
      </>
    );
  }
  return (
    <>
      {coded.words}
      {coded.code !== null ? (
        <details className="mt-1 text-xs text-ink-muted">
          <summary className="cursor-pointer">Technické podrobnosti</summary>
          <code className="break-all">{coded.code}</code>
        </details>
      ) : null}
    </>
  );
}
