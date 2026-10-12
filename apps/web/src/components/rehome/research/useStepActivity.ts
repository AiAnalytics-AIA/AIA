"use client";

// A run's event feed, read live (.planning/plans/step-activity.md): after its cursor, every
// ACTIVITY_POLL_MS while something runs, once more when it stops (so the last word, "Krok
// dokončen", is read), then not at all. Events land in PostgreSQL as the worker writes them;
// this is the stream a person sees, at most ACTIVITY_POLL_MS behind the worker. A failed read
// keeps what was read and tries again on the next tick: the feed is commentary, the run's own
// state comes from its own poll.

import { useEffect, useRef, useState } from "react";

import type { RunEvent } from "@/lib/api";
import { EMPTY_ACTIVITY, foldActivity, type ActivityState } from "@/lib/step-activity";

export const ACTIVITY_POLL_MS = 1500;
/** The API's default page; a shorter page means the feed has been read to its end. */
const PAGE = 500;
/** Pages read in one go when a long run is first opened; the rest follows on the next ticks. */
const MAX_PAGES = 8;

export type EventReader = (since: number) => Promise<RunEvent[]>;

/**
 * `key` names the feed (a run's id); a new key starts from nothing. `read` may change identity
 * between renders; the latest one is used. Null `key` reads nothing.
 */
export function useStepActivity(key: string | null, read: EventReader, live: boolean): ActivityState {
  const [held, setHeld] = useState<{ key: string | null; activity: ActivityState }>({ key, activity: EMPTY_ACTIVITY });
  const reader = useRef(read);
  useEffect(() => {
    reader.current = read;
  });
  // The cursor of the feed being read, so a change of `live` does not read it again from 0.
  const cursor = useRef<{ key: string | null; at: number }>({ key, at: 0 });

  useEffect(() => {
    if (!key) return;
    if (cursor.current.key !== key) cursor.current = { key, at: 0 };
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const drain = async () => {
      for (let page = 0; page < MAX_PAGES && !stopped; page++) {
        const events = await reader.current(cursor.current.at);
        if (stopped) return;
        if (!Array.isArray(events)) throw new Error("the event feed is not a list");
        if (events.length) {
          cursor.current = { key, at: Math.max(cursor.current.at, ...events.map((e) => e.event_id)) };
          setHeld((h) => ({ key, activity: foldActivity(h.key === key ? h.activity : EMPTY_ACTIVITY, events) }));
        }
        if (events.length < PAGE) return;
      }
    };
    const tick = async () => {
      try {
        await drain();
      } catch {
        // Kept as read; the next tick tries again.
      }
      if (!stopped && live) timer = setTimeout(tick, ACTIVITY_POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [key, live]);

  return held.key === key ? held.activity : EMPTY_ACTIVITY;
}
