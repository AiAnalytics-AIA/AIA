import Link from "next/link";
import { ReactNode } from "react";
import { t } from "@/i18n/t";
import { ThemeSwitch } from "@/components/theme/ThemeSwitch";
import { Wordmark } from "@/components/brand/Wordmark";
import { apiConfig } from "@/lib/api/client";

export function AppShell({ orgSlug, children }: { orgSlug: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface text-ink">
      <div className="grid grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-h-screen border-r border-border bg-surface-sunken p-4">
          <div className="mb-6">
            <Wordmark height={20} label={t("app.name")} />
            <div className="text-xs text-ink-muted">{t("app.tagline")}</div>
            <div className="mt-1 text-xs text-ink-muted">/{orgSlug}</div>
          </div>

          <nav className="space-y-1 text-sm">
            <NavLink href={`/org/${orgSlug}/dashboard`}>{t("nav.portfolio")}</NavLink>
            <NavLink href={`/org/${orgSlug}/knowledge-base`}>{t("nav.projectMemory")}</NavLink>
            <NavLink href={`/org/${orgSlug}/admin/settings`}>{t("nav.admin")}</NavLink>
          </nav>
          <div className="mt-6">
            <ThemeSwitch />
          </div>
          <DevIdentity />
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
      className="block rounded-md px-3 py-2 text-ink-muted hover:bg-surface-sunken hover:text-ink"
    >
      {children}
    </Link>
  );
}

/**
 * Who the API is being asked as. There is no sign-in yet (OI-14): the identity
 * is the development subject the web server was started with, and it is labelled
 * as exactly that, so a screenshot can never pass for a production session.
 */
function DevIdentity() {
  const { subject } = apiConfig();
  return (
    <div data-unavailable="sign-in" className="mt-6 rounded-md border border-dashed border-border-strong px-3 py-2 text-xs text-ink-muted">
      <div className="font-semibold text-ink">{subject ? t("identity.dev") : t("identity.none")}</div>
      {subject ? <div className="break-all font-mono">{subject}</div> : null}
      <div className="mt-1">{t("identity.noSignIn")}</div>
    </div>
  );
}
