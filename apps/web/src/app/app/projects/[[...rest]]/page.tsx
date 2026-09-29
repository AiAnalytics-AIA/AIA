import { redirect } from "next/navigation";

// Retired (ADR 0015, ADR 0018): the unscoped 18.6.6 project store is not part of
// AIA. A study's work is found through its client; an old link lands on the
// client directory.
export default function RetiredProjectsPath() {
  redirect("/app/clients");
}
