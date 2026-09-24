import { redirect } from "next/navigation";

// The rebuilt interface opens on its first rebuilt area. When the classic
// "Úvod" is rebuilt (area A1), it takes this path.
export default function RehomeHome() {
  redirect("/app/projects");
}
