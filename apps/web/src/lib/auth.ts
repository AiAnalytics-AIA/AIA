"use client";

// Authentication for the live pages: Cognito hosted UI, Authorization Code +
// PKCE, no client secret. Cognito proves who the user is; the API decides what
// they may do (ADR 0003). Nothing here reads a role, a client or a study from
// the token, and nothing in the API would honour one if it did.
//
// The id token is what the API verifies (AIA_COGNITO_TOKEN_USE=id). It is kept
// in sessionStorage for the tab's lifetime and refreshed with the refresh token
// when it is within a minute of expiry. Accepted for the develop environment;
// a same-site cookie session is the production shape and is recorded as such in
// the develop plan.

import { useSyncExternalStore } from "react";

import type { PublicConfig } from "@/app/config/route";

const SESSION_KEY = "aia.session";
const PKCE_KEY = "aia.pkce";
const REFRESH_SKEW_MS = 60_000;

export type Session = {
  idToken: string;
  refreshToken: string | null;
  expiresAt: number; // epoch ms
  email: string | null;
  subject: string | null;
};

let configPromise: Promise<PublicConfig> | null = null;

export function loadConfig(): Promise<PublicConfig> {
  if (!configPromise) {
    configPromise = fetch("/config", { cache: "no-store" }).then(async (r) => {
      if (!r.ok) throw new Error(`/config answered ${r.status}`);
      return (await r.json()) as PublicConfig;
    });
  }
  return configPromise;
}

function base64url(bytes: ArrayBuffer | Uint8Array): string {
  const array = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  for (const b of array) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(bytes: number): string {
  const array = new Uint8Array(bytes);
  crypto.getRandomValues(array);
  return base64url(array);
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return base64url(digest);
}

export function decodeClaims(jwt: string): Record<string, unknown> {
  // Display only. The API verifies the signature; the browser never trusts these
  // for anything but showing who is signed in.
  const payload = jwt.split(".")[1] ?? "";
  const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json) as Record<string, unknown>;
}

function redirectUri(config: PublicConfig): string {
  const origin = config.publicOrigin ?? window.location.origin;
  return `${origin}/auth/callback`;
}

function requireCognito(config: PublicConfig): { domain: string; clientId: string } {
  if (!config.cognitoDomain || !config.cognitoClientId) {
    throw new Error("Cognito is not configured for this deployment (AIA_COGNITO_DOMAIN / AIA_COGNITO_CLIENT_ID).");
  }
  return { domain: config.cognitoDomain, clientId: config.cognitoClientId };
}

let snapshotRaw: string | null = null;
let snapshotValue: Session | null = null;

export function readSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    // Cached by the stored string, so React's external-store snapshot is stable
    // between renders and hydration compares equal objects.
    if (raw !== snapshotRaw) {
      snapshotRaw = raw;
      snapshotValue = raw ? (JSON.parse(raw) as Session) : null;
    }
    return snapshotValue;
  } catch {
    return null;
  }
}

const noSubscription = () => () => {};

/** The current session for rendering: null on the server and until hydration. */
export function useSession(): Session | null {
  return useSyncExternalStore(noSubscription, readSession, () => null);
}

function writeSession(session: Session | null) {
  try {
    if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Storage unavailable: the user will simply be asked to sign in again.
  }
}

/** Start the hosted-UI login. Redirects the browser; never resolves normally. */
export async function login(returnTo: string = "/studies"): Promise<void> {
  const config = await loadConfig();
  const { domain, clientId } = requireCognito(config);
  const verifier = randomString(64);
  const state = randomString(24);
  sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state, returnTo }));

  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: redirectUri(config),
    code_challenge: await sha256(verifier),
    code_challenge_method: "S256",
    state,
    identity_provider: "Google",
  });
  window.location.assign(`https://${domain}/oauth2/authorize?${params}`);
}

type TokenResponse = {
  id_token: string;
  access_token: string;
  refresh_token?: string;
  expires_in: number;
};

function sessionFromTokens(tokens: TokenResponse, previous: Session | null): Session {
  const claims = decodeClaims(tokens.id_token);
  return {
    idToken: tokens.id_token,
    refreshToken: tokens.refresh_token ?? previous?.refreshToken ?? null,
    expiresAt: Date.now() + tokens.expires_in * 1000,
    email: typeof claims.email === "string" ? claims.email : null,
    subject: typeof claims.sub === "string" ? claims.sub : null,
  };
}

/** Finish the login on /auth/callback. Returns where to go next. */
export async function completeLogin(code: string, state: string): Promise<string> {
  const config = await loadConfig();
  const { domain, clientId } = requireCognito(config);
  const raw = sessionStorage.getItem(PKCE_KEY);
  sessionStorage.removeItem(PKCE_KEY);
  if (!raw) throw new Error("No login in progress in this tab.");
  const pkce = JSON.parse(raw) as { verifier: string; state: string; returnTo: string };
  if (pkce.state !== state) throw new Error("Login state mismatch; start again.");

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    code,
    redirect_uri: redirectUri(config),
    code_verifier: pkce.verifier,
  });
  const response = await fetch(`https://${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) throw new Error(`Token exchange failed (${response.status}).`);
  writeSession(sessionFromTokens((await response.json()) as TokenResponse, null));
  return pkce.returnTo || "/studies";
}

async function refresh(session: Session): Promise<Session | null> {
  if (!session.refreshToken) return null;
  const config = await loadConfig();
  const { domain, clientId } = requireCognito(config);
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: clientId,
    refresh_token: session.refreshToken,
  });
  const response = await fetch(`https://${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) return null;
  const next = sessionFromTokens((await response.json()) as TokenResponse, session);
  writeSession(next);
  return next;
}

/** A valid id token, refreshing when close to expiry; null when signed out. */
export async function currentIdToken(): Promise<string | null> {
  const session = readSession();
  if (!session) return null;
  if (Date.now() < session.expiresAt - REFRESH_SKEW_MS) return session.idToken;
  const refreshed = await refresh(session);
  if (!refreshed) {
    writeSession(null);
    return null;
  }
  return refreshed.idToken;
}

export async function logout(): Promise<void> {
  const session = readSession();
  writeSession(null);
  const config = await loadConfig();
  if (!config.cognitoDomain || !config.cognitoClientId || !session) {
    window.location.assign("/");
    return;
  }
  const origin = config.publicOrigin ?? window.location.origin;
  const params = new URLSearchParams({
    client_id: config.cognitoClientId,
    logout_uri: `${origin}/`,
  });
  window.location.assign(`https://${config.cognitoDomain}/logout?${params}`);
}
