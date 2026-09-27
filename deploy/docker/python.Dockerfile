# syntax=docker/dockerfile:1.7
#
# The API and the worker, from one file and one dependency set, so that both
# always run the same application revision (the brief's requirement for the
# worker, and the only way `alembic upgrade head` in the api image can be
# trusted to match the code the worker executes).
#
#   docker build -f deploy/docker/python.Dockerfile --target api    -t aia-api:<sha>    .
#   docker build -f deploy/docker/python.Dockerfile --target worker -t aia-worker:<sha> .
#
# Build context is the repository root. Nothing here reads a secret; the image
# carries only code and its declared dependencies, and AIA_BUILD_SHA so the
# running process can name its own revision (/api/v1/health, the worker's start
# log, artifact provenance).

ARG PYTHON_VERSION=3.12

# ----------------------------------------------------------------- builder --
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
# Copy only what the install needs first, so a source edit does not re-resolve
# dependencies. pip resolves `aia-core` from the local directory because every
# distribution is installed in one invocation.
COPY packages/aia_core/pyproject.toml packages/aia_core/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/executors/pyproject.toml apps/executors/pyproject.toml
COPY packages/aia_core/src packages/aia_core/src
COPY apps/api/src apps/api/src
COPY apps/worker/src apps/worker/src
COPY apps/executors/src apps/executors/src

RUN pip install --upgrade pip \
 && pip install \
      "./packages/aia_core[postgres,s3,bedrock]" \
      ./apps/api \
      ./apps/worker \
      ./apps/executors

# ----------------------------------------------------------------- runtime --
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG AIA_BUILD_SHA
ARG AIA_BUILD_TIME
ENV AIA_BUILD_SHA=${AIA_BUILD_SHA} \
    AIA_BUILD_TIME=${AIA_BUILD_TIME} \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIA_LOG_FORMAT=json

# A dedicated unprivileged user with a fixed uid, so a volume mounted for the
# filesystem store (local use only) has a predictable owner.
RUN groupadd --system --gid 10001 aia \
 && useradd --system --uid 10001 --gid aia --home-dir /app --shell /usr/sbin/nologin aia \
 && mkdir -p /app && chown aia:aia /app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
USER aia

# ----------------------------------------------------------------- api ------
FROM runtime AS api

# Alembic runs from this image as a one-off deploy step (`alembic upgrade head`),
# never at API start-up. The migrations therefore ship with the API image and
# with nothing else.
COPY --chown=aia:aia alembic.ini alembic.ini
COPY --chown=aia:aia migrations migrations

EXPOSE 8000
# Liveness only: /health touches no dependency, so a database outage restarts
# nothing (readiness is /ready, checked by the smoke test, not by Docker).
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=4 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).status == 200 else 1)"]

# --proxy-headers: Caddy terminates TLS and forwards X-Forwarded-*; the API sits
# on an internal network reachable only from Caddy, so trusting every forwarder
# on that network is the correct scope.
CMD ["uvicorn", "aia_api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]

# ----------------------------------------------------------------- worker ---
FROM runtime AS worker

# No inbound port. The worker polls PostgreSQL; a first SIGTERM releases the
# executing step and exits 0, a second exits at once (aia_worker.__main__).
STOPSIGNAL SIGTERM
CMD ["aia-worker"]
