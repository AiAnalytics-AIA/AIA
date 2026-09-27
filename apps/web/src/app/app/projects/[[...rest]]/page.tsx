import { redirect } from "next/navigation";

// Moved (ADR 0015): the unscoped classic project store is an administrative
// tool under Nastavení, not a place to work from.
export default function MovedProjectsPath() {
  redirect("/app/settings/classic-projects");
}
