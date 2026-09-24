"use client";

// One read from the AIA API for a page: loading, the data, a failure said in
// words, and a way to read it again. A 404 is its own state -- scope denial is
// always 404 (ADR 0004), and the page says "nothing here" rather than an error.
// A missing session sends the person to sign in and back.

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, Unauthenticated } from "@/lib/api";

export type Resource<T> =
  | { state: "loading" }
  | { state: "ready"; data: T }
  | { state: "not-found" }
  | { state: "failed"; message: string };

export function useResource<T>(load: () => Promise<T>, deps: readonly unknown[]): [Resource<T>, () => void] {
  const [res, setRes] = useState<Resource<T>>({ state: "loading" });
  const [version, setVersion] = useState(0);
  // A ref, not a dependency: the read must not re-run because the router object did.
  const router = useRouter();
  const routerRef = useRef(router);
  useEffect(() => {
    routerRef.current = router;
  }, [router]);
  // `load` is recreated on every render; `deps` says when the read changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);
  useEffect(() => {
    let live = true;
    run().then(
      (data) => live && setRes({ state: "ready", data }),
      (e: unknown) => {
        if (!live) return;
        if (e instanceof Unauthenticated) {
          return routerRef.current.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
        }
        if (e instanceof ApiError && e.status === 404) return setRes({ state: "not-found" });
        setRes({ state: "failed", message: e instanceof Error ? e.message : String(e) });
      },
    );
    return () => {
      live = false;
    };
  }, [run, version]);
  return [res, () => setVersion((v) => v + 1)];
}
