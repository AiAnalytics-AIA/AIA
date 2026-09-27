"use server";

// Every mutation on the settings page. Each one forwards to an existing API
// route and reports the API's own answer; nothing here decides whether an
// action is allowed -- the API does, and its refusal is shown as given.

import { revalidatePath } from "next/cache";
import { api, type ApiResult } from "@/lib/api/server";

export type ActionState = { ok: boolean; message: string } | null;

const PAGE = "/org/[orgSlug]/admin/settings";

function text(form: FormData, name: string): string {
  const v = form.get(name);
  return typeof v === "string" ? v.trim() : "";
}

function report(result: ApiResult<unknown>, done: string): ActionState {
  if (result.ok) {
    revalidatePath(PAGE, "page");
    return { ok: true, message: done };
  }
  const { status, code, message, requestId } = result.error;
  const where = status === null ? "API nedostupné" : `HTTP ${status}`;
  return { ok: false, message: `${where} · ${code}: ${message}${requestId ? ` (req ${requestId})` : ""}` };
}

export async function addMember(_: ActionState, form: FormData): Promise<ActionState> {
  return report(
    await api.post("/members", {
      email: text(form, "email"),
      role: text(form, "role"),
      display_name: text(form, "display_name"),
    }),
    "Člen přidán.",
  );
}

export async function createClient(_: ActionState, form: FormData): Promise<ActionState> {
  return report(
    await api.post("/clients", {
      slug: text(form, "slug"),
      name: text(form, "name"),
      reference: text(form, "reference"),
    }),
    "Klient založen.",
  );
}

export async function setClientStatus(_: ActionState, form: FormData): Promise<ActionState> {
  const id = encodeURIComponent(text(form, "client_id"));
  return report(await api.put(`/clients/${id}/status`, { status: text(form, "status") }), "Stav klienta změněn.");
}

export async function grantClientAccess(_: ActionState, form: FormData): Promise<ActionState> {
  const id = encodeURIComponent(text(form, "client_id"));
  return report(
    await api.post(`/clients/${id}/grants`, { user_id: text(form, "user_id"), role: text(form, "role") }),
    "Přístup ke klientovi udělen.",
  );
}

export async function createStudy(_: ActionState, form: FormData): Promise<ActionState> {
  const raw = text(form, "budget_usd");
  const budget = raw === "" ? NaN : Number(raw);
  // An empty or malformed budget is refused here rather than sent as 0: a
  // study with no stated budget is not a study with a zero budget.
  if (!Number.isFinite(budget)) return { ok: false, message: "Rozpočet musí být číslo (USD)." };
  return report(
    await api.post("/studies", {
      client_id: text(form, "client_id"),
      slug: text(form, "slug"),
      name: text(form, "name"),
      budget_usd: budget,
    }),
    "Studie založena.",
  );
}

export async function setStudyStatus(_: ActionState, form: FormData): Promise<ActionState> {
  const id = encodeURIComponent(text(form, "study_id"));
  return report(await api.put(`/studies/${id}/status`, { status: text(form, "status") }), "Stav studie změněn.");
}

export async function setStudyBudget(_: ActionState, form: FormData): Promise<ActionState> {
  const id = encodeURIComponent(text(form, "study_id"));
  const raw = text(form, "budget_usd");
  const budget = raw === "" ? NaN : Number(raw);
  if (!Number.isFinite(budget)) return { ok: false, message: "Rozpočet musí být číslo (USD)." };
  return report(await api.put(`/studies/${id}/budget`, { budget_usd: budget }), "Rozpočet studie nastaven.");
}

export async function grantStudyAccess(_: ActionState, form: FormData): Promise<ActionState> {
  const id = encodeURIComponent(text(form, "study_id"));
  return report(
    await api.post(`/studies/${id}/grants`, { user_id: text(form, "user_id"), role: text(form, "role") }),
    "Přístup ke studii udělen.",
  );
}

export async function setSelfApproval(_: ActionState, form: FormData): Promise<ActionState> {
  const choice = text(form, "allowed");
  const allowed = choice === "allow" ? true : choice === "forbid" ? false : choice === "inherit" ? null : undefined;
  if (allowed === undefined) return { ok: false, message: "Vyberte povolit, zakázat nebo dědit." };
  const target = text(form, "target"); // "", "client:<id>" or "study:<id>"
  const [kind, id] = target.includes(":") ? target.split(":", 2) : ["", ""];
  return report(
    await api.put("/self-approval", {
      allowed,
      client_id: kind === "client" ? id : undefined,
      study_id: kind === "study" ? id : undefined,
    }),
    "Pravidlo samoschválení uloženo.",
  );
}
