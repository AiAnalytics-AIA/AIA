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

# -------------------------------------------------------------------- deps --
# Third-party dependencies only, from the four pyproject files and nothing else, so
# this stage -- and the one large layer the runtime copies from it -- changes only
# when a dependency does. A source-only commit reuses it from the build cache, and
# the develop host, which stores layers by digest, downloads nothing new for it.
FROM python:${PYTHON_VERSION}-slim-bookworm AS deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY packages/aia_core/pyproject.toml packages/aia_core/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/executors/pyproject.toml apps/executors/pyproject.toml

# A deliberate refresh: the dependency layer is reused until a pyproject changes or
# the build cache drops it, so a release inside a range (a security fix) reaches the
# images only then. Changing this date re-resolves every dependency on the next
# build. CI's pip-audit audits a fresh resolution, not this cached one, so bump it
# when an advisory is fixed upstream within a range.
ARG AIA_DEPS_REFRESH=2026-10-20

# The same pip invocation the images always used, so pip resolves exactly the same
# set, over empty stand-ins for AIA's four packages (an __init__.py each: enough for
# hatchling to build them). The stand-ins are then uninstalled, leaving only the
# third-party distributions; the real packages go in per target, below.
RUN for pkg in packages/aia_core/src/aia_core apps/api/src/aia_api \
               apps/worker/src/aia_worker apps/executors/src/aia_executors; do \
      mkdir -p "$pkg" && touch "$pkg/__init__.py"; \
    done \
 && pip install --upgrade pip \
 && pip install \
      "./packages/aia_core[postgres,s3,bedrock,documents,report,errors]" \
      ./apps/api \
      ./apps/worker \
      ./apps/executors \
 && pip uninstall --yes aia-core aia-api aia-worker aia-executors

# ----------------------------------------------------------------- runtime --
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Nothing here may change per commit: AIA_BUILD_SHA and AIA_BUILD_TIME are set at the
# end of each target, after the layers, because a build argument in a RUN's
# environment makes that RUN, and every layer after it, new on every commit.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIA_LOG_FORMAT=json \
    NUMBA_CACHE_DIR=/tmp/numba

# NUMBA_CACHE_DIR: numba's kernel cache must be writable at import; in a read-only
# container only /tmp is, so the kernels compile once per container start.

# A dedicated unprivileged user with a fixed uid, so a volume mounted for the
# filesystem store (local use only) has a predictable owner.
RUN groupadd --system --gid 10001 aia \
 && useradd --system --uid 10001 --gid aia --home-dir /app --shell /usr/sbin/nologin aia \
 && mkdir -p /app && chown aia:aia /app

COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
USER aia

# ----------------------------------------------------------------- api ------
FROM runtime AS api

# Alembic runs from this image as a one-off deploy step (`alembic upgrade head`),
# never at API start-up. The migrations therefore ship with the API image and
# with nothing else.
COPY --chown=aia:aia alembic.ini alembic.ini
COPY --chown=aia:aia migrations migrations

# AIA's own four packages, without their dependencies (the deps stage installed
# them): a layer of a few megabytes, the only one a source-only commit changes. The
# sources are bind-mounted at the paths the deps stage used, so each package records
# the same origin (pip freeze: `aia-core @ file:///src/packages/aia_core`); `pip
# check` fails the build if a package needs a dependency the deps stage lacks.
USER root
RUN --mount=type=bind,source=packages/aia_core,target=/src/packages/aia_core,rw \
    --mount=type=bind,source=apps/api,target=/src/apps/api,rw \
    --mount=type=bind,source=apps/worker,target=/src/apps/worker,rw \
    --mount=type=bind,source=apps/executors,target=/src/apps/executors,rw \
    cd /src \
 && PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 pip install --no-deps \
      ./packages/aia_core ./apps/api ./apps/worker ./apps/executors \
 && pip check
USER aia

ARG AIA_BUILD_SHA
ARG AIA_BUILD_TIME
ENV AIA_BUILD_SHA=${AIA_BUILD_SHA} \
    AIA_BUILD_TIME=${AIA_BUILD_TIME}

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

# The report's PDF (complete-study-report B3) is headless LibreOffice Writer. It adds
# about 300 MB to the image, so it is installed only when the build asks for it;
# AIA_REPORT_PDF_ENABLED=true on a worker without it stops the worker at start.
ARG AIA_WORKER_PDF=false
USER root
RUN if [ "$AIA_WORKER_PDF" = "true" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends libreoffice-writer-nogui \
      && rm -rf /var/lib/apt/lists/*; \
    fi

# AIA's own packages after LibreOffice, so a source-only commit reuses that layer
# too; the same step as in the api target.
RUN --mount=type=bind,source=packages/aia_core,target=/src/packages/aia_core,rw \
    --mount=type=bind,source=apps/api,target=/src/apps/api,rw \
    --mount=type=bind,source=apps/worker,target=/src/apps/worker,rw \
    --mount=type=bind,source=apps/executors,target=/src/apps/executors,rw \
    cd /src \
 && PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 pip install --no-deps \
      ./packages/aia_core ./apps/api ./apps/worker ./apps/executors \
 && pip check
USER aia

ARG AIA_BUILD_SHA
ARG AIA_BUILD_TIME
ENV AIA_BUILD_SHA=${AIA_BUILD_SHA} \
    AIA_BUILD_TIME=${AIA_BUILD_TIME}

# No inbound port. The worker polls PostgreSQL; a first SIGTERM releases the
# executing step and exits 0, a second exits at once (aia_worker.__main__).
STOPSIGNAL SIGTERM
CMD ["aia-worker"]
