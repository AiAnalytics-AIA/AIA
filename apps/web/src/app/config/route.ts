import { NextResponse } from "next/server";

import { buildIdentity } from "@/lib/build";

// Runtime configuration for the browser. Read from the server's environment at
// request time, so one image serves any environment: NEXT_PUBLIC_* values would
// be baked in at `next build` and make the SHA-tagged image environment-specific.
// Nothing here is a secret: the Cognito app client is public (PKCE) by design.
export const dynamic = "force-dynamic";

export type PublicConfig = {
  cognitoDomain: string | null;
  cognitoClientId: string | null;
  publicOrigin: string | null;
  apiBase: string;
  build: { sha: string | null; built_at: string | null };
};

export function GET() {
  const config: PublicConfig = {
    cognitoDomain: process.env.AIA_COGNITO_DOMAIN?.trim() || null,
    cognitoClientId: process.env.AIA_COGNITO_CLIENT_ID?.trim() || null,
    publicOrigin: process.env.AIA_PUBLIC_ORIGIN?.trim() || null,
    apiBase: process.env.AIA_API_BASE?.trim() || "",
    build: buildIdentity(),
  };
  return NextResponse.json(config, { headers: { "Cache-Control": "no-store" } });
}
