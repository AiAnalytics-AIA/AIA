// The parts of @sentry/browser the reporter uses, named, so the bundler keeps only these.
// Loaded by lib/error-tracking.ts with a dynamic import, and only when /config has a DSN.
export { captureException, init, withScope } from "@sentry/browser";
