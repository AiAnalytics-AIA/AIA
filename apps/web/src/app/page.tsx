import { redirect } from "next/navigation";

// The product's front door is the client directory (ADR 0015). On the develop
// host Caddy answers `/` with the same redirect before this page is reached;
// this is what a local `make dev` does. Signed out, /app sends you to /login.
export default function Home() {
  redirect("/app/clients");
}
