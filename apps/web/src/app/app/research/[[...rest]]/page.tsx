import { redirect } from "next/navigation";

// Retired (ADR 0015): research is opened from its client, never by a bare unit
// project id. An old link lands on the client directory.
export default function RetiredResearchPath() {
  redirect("/app/clients");
}
