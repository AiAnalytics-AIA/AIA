// Plain module on purpose: a constant exported from a "use client" file becomes a
// client reference when a server component imports it (see AGENTS.md § Next.js).
export const inputClass =
  "h-8 rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-200";
