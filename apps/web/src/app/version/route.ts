import { NextResponse } from "next/server";

import { buildIdentity } from "@/lib/build";

// The web container's own build identity, for the deploy smoke test and for an
// operator checking which revision answered. Read at request time from the
// environment the image was built with; never cached across builds.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(buildIdentity());
}
