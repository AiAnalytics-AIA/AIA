import Link from "next/link";
import { ReactNode } from "react";
import { t } from "@/i18n/t";

export function AppShell({ orgSlug, children }: { orgSlug: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <div className="grid grid-cols-[260px_1fr]">
        <aside className="min-h-screen border-r border-zinc-200 bg-white p-4">
          <div className="mb-6">
            <div className="text-base font-semibold">{t("app.name")}</div>
            <div className="text-xs text-zinc-500">{t("app.tagline")}</div>
            <div className="mt-1 text-xs text-zinc-500">/{orgSlug}</div>
          </div>

          <nav className="space-y-1 text-sm">
            <NavLink href={`/org/${orgSlug}/dashboard`}>{t("nav.portfolio")}</NavLink>
            <NavLink href={`/org/${orgSlug}/knowledge-base`}>{t("nav.projectMemory")}</NavLink>
            <NavLink href={`/org/${orgSlug}/admin/settings`}>{t("nav.admin")}</NavLink>
          </nav>
        </aside>

        <div>
          <main className="px-6 py-6">{children}</main>
        </div>
      </div>
    </div>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="block rounded-md px-3 py-2 text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900"
    >
      {children}
    </Link>
  );
}
