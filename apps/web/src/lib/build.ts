// The git commit this client was built from.
//
// `AIA_BUILD_SHA` is baked into the image by the deployment (apps/web/Dockerfile).
// The value is validated rather than trusted: a branch name or "latest" in the
// slot would be a broken build step, and reporting it as a revision would hide
// that. A blank value reports `null`, never a placeholder.

const GIT_SHA = /^[0-9a-f]{7,40}$/;

export type BuildIdentity = {
  sha: string | null;
  built_at: string | null;
};

export function parseBuildSha(raw: string | undefined | null): string | null {
  const value = (raw ?? "").trim().toLowerCase();
  if (!value) return null;
  if (!GIT_SHA.test(value)) {
    throw new Error(`AIA_BUILD_SHA must be a 7-40 character hex git SHA, got ${JSON.stringify(raw)}`);
  }
  return value;
}

export function buildIdentity(env: NodeJS.ProcessEnv = process.env): BuildIdentity {
  return {
    sha: parseBuildSha(env.AIA_BUILD_SHA),
    built_at: (env.AIA_BUILD_TIME ?? "").trim() || null,
  };
}
