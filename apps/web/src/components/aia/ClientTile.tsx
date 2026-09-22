import { ACCENT_BG, accentSlot, monogram } from "@/design/accent";

/** The client's monogram on its accent. Decorative beside the written name, so hidden from assistive tech. */
export function ClientTile({ client }: { client: { client_id: string; name: string; accent_slot?: number | null } }) {
  const slot = accentSlot(client.client_id, client.accent_slot);
  return (
    <span aria-hidden="true" data-accent-slot={slot} className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm text-[11px] font-semibold text-on-client ${ACCENT_BG[slot]}`}>
      {monogram(client.name)}
    </span>
  );
}
