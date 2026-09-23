import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { Kbd } from "./Kbd";

/**
 * A native <button>: keyboard and focus behaviour come from the platform, the
 * 2px focus ring from globals.css. A permission the viewer lacks is expressed by
 * not rendering the button — never by a disabled one.
 */
type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "disabled"> & {
  variant?: "primary" | "secondary" | "quiet";
  compact?: boolean;
  icon?: IconName;
  kbd?: string;
  children: ReactNode;
};

const VARIANT = {
  primary: "bg-signal text-on-signal border-signal hover:brightness-110",
  secondary: "bg-surface-raised text-ink border-border-strong hover:bg-surface-sunken",
  quiet: "bg-transparent text-ink border-transparent hover:bg-surface-sunken",
} as const;

export function Button({ variant = "secondary", compact = false, icon, kbd, children, type = "button", className = "", ...rest }: Props) {
  return (
    <button
      type={type}
      aria-keyshortcuts={kbd}
      className={`inline-flex items-center gap-2 rounded-sm border font-medium ${compact ? "min-h-6 px-2 text-xs" : "min-h-8 px-3 text-[13px]"} ${VARIANT[variant]} ${className}`}
      {...rest}
    >
      {icon ? <Icon name={icon} size={14} /> : null}
      {children}
      {kbd ? <Kbd>{kbd}</Kbd> : null}
    </button>
  );
}
