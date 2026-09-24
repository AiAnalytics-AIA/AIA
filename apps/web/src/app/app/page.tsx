import { redirect } from "next/navigation";

// The application's home is the client directory (ADR 0015).
export default function AppIndex() {
  redirect("/app/clients");
}
