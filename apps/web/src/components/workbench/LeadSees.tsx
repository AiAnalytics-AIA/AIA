"use client";

// Co Vedoucí vidí (lead-conversation LC2): what the researcher's last Lead turn could see, layer by
// layer, read from the context that turn froze, with what each layer left out and why. Opened
// inline in the pane from the Vidí chip; the same in the compact drawer.

import { useEffect, useState } from "react";
import { ApiError, lead as leadApi } from "@/lib/api";
import { layerLines, layerName, moreOmitted, reasonWords, totalLine, type OmittedId, type TurnManifest } from "@/lib/lead-manifest";

export function LeadSees({ studyId, turnId, id }: { studyId: string; turnId: string; id: string }) {
  const [read, setRead] = useState<TurnManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [more, setMore] = useState<Record<string, OmittedId[]>>({});

  useEffect(() => {
    // One panel per turn: the pane keys it by the turn, so a newer turn starts it afresh.
    let live = true;
    leadApi.manifest(studyId, turnId).then(
      (m) => { if (live) setRead(m); },
      (e) => { if (live) setError(e instanceof ApiError && e.status === 404 ? "Tuto odpověď nelze přečíst." : "Nepodařilo se načíst, co Vedoucí viděl."); },
    );
    return () => { live = false; };
  }, [studyId, turnId]);

  const loadMore = async (layer: string, after: number) => {
    try {
      const page = await leadApi.omitted(studyId, turnId, layer, after);
      setMore((m) => ({ ...m, [layer]: [...(m[layer] ?? []), ...page.omitted] }));
    } catch {
      setError("Další vynechané položky se nepodařilo načíst.");
    }
  };

  return (
    <section id={id} className="sees" aria-label="Co Vedoucí viděl v poslední odpovědi" data-lead-sees>
      <h3 className="sees__title">Co viděl v poslední odpovědi</h3>
      {error ? <p className="sees__note" role="status">{error}</p> : null}
      {!read && !error ? <p className="sees__note" role="status">Načítám…</p> : null}
      {read && !read.recorded ? <p className="sees__note">Tato odpověď si nezaznamenala, co viděla.</p> : null}
      {read?.manifest ? (
        <>
          <p className="sees__note">{totalLine(read)}</p>
          <ol className="sees__layers">
            {read.manifest.layers.map((l) => {
              const omitted = [...l.omitted, ...(more[l.layer] ?? [])];
              return (
                <li key={l.layer} className={`sees__layer${l.recorded ? "" : " is-unrecorded"}`} data-layer={l.layer}>
                  <h4 className="sees__name">{layerName(l.layer)}</h4>
                  {layerLines(l).map((line) => <p key={line} className="sees__line">{line}</p>)}
                  {omitted.length ? (
                    <ul className="sees__omitted" aria-label={`Vynecháno z vrstvy ${layerName(l.layer)}`}>
                      {omitted.map((o) => <li key={o.id}><code>{o.id}</code> · {reasonWords(o.reason)}</li>)}
                    </ul>
                  ) : null}
                  {moreOmitted(l, omitted.length) ? (
                    <button type="button" className="chip" onClick={() => void loadMore(l.layer, omitted.length)}>Načíst další vynechané</button>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </section>
  );
}
