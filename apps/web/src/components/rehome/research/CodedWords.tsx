import type { Coded } from "@/lib/reason-words";

/** A code in words; one the client has no words for keeps its code under technical details. */
export function CodedWords({ coded }: { coded: Coded }) {
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
