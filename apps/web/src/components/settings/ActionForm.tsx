"use client";

import { useActionState, type ReactNode } from "react";
import type { ActionState } from "@/app/org/[orgSlug]/admin/settings/actions";

// A form bound to one server action. Shows the API's answer verbatim --
// success or refusal -- and never an optimistic result.
export function ActionForm({
  action,
  submit,
  children,
  inline = false,
  disabled = false,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  submit: string;
  children: ReactNode;
  inline?: boolean;
  disabled?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, null);
  return (
    <form action={formAction} className={inline ? "flex flex-wrap items-end gap-2" : "space-y-2"}>
      {children}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={pending || disabled}
          className="h-8 rounded-md border border-zinc-300 bg-zinc-900 px-3 text-xs font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending ? "Odesílám…" : submit}
        </button>
        {state ? (
          <span role="status" className={`text-xs ${state.ok ? "text-green-700" : "text-red-700"}`}>
            {state.message}
          </span>
        ) : null}
      </div>
    </form>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-zinc-600">
      <span>{label}</span>
      {children}
    </label>
  );
}
