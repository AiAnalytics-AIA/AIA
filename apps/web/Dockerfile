# syntax=docker/dockerfile:1.7
#
# The Next.js client as a production image: `npm ci`, `next build` with
# standalone output, no `next dev`, non-root at runtime.
#
#   docker build -f apps/web/Dockerfile --build-arg AIA_BUILD_SHA=<sha> -t aia-web:<sha> apps/web
#
# Standalone output traces the server's imports and copies only the modules it
# needs, so the runtime image carries neither devDependencies nor the 600 MB of
# node_modules the build used. The build context is apps/web alone: the client
# has its own lockfile and depends on nothing else in the repository.

ARG NODE_VERSION=22

# ----------------------------------------------------------------- deps -----
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ----------------------------------------------------------------- builder --
FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ----------------------------------------------------------------- runtime --
FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app

ARG AIA_BUILD_SHA
ARG AIA_BUILD_TIME
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    AIA_BUILD_SHA=${AIA_BUILD_SHA} \
    AIA_BUILD_TIME=${AIA_BUILD_TIME}

# The official image ships a `node` user (uid 1000); the standalone server needs
# nothing else. The .next/cache directory is where ISR would write, so it is
# owned by that user even though this client serves only dynamic routes today.
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
RUN mkdir -p .next/cache && chown -R node:node .next

USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=4 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/version').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "server.js"]
