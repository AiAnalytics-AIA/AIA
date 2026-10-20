---
status: done
chunks:
  - "[x] 1. Split the Python image's dependency layer from AIA's own code"
  - "[x] 2. Prove the images equivalent and measure them"
  - "[x] 3. (Optional) A check that a source-only change cannot rebuild the dependency layer"
---
# Image build layers

Build infrastructure, approved on its own by the product owner during the MVP scope freeze
(the infra audit of 2026-10-20). No feature code.

## The problem

Every deploy added about 1 GB to the develop host's disk. `deploy/docker/python.Dockerfile`
@ f2b0b92:

- lines 36-39 copied the four packages' sources before the `pip install` at line 41, so any
  source change re-ran the whole dependency install;
- line 70 copied the resulting venv into the runtime stage as one layer, measured at 772 MB
  unpacked / 250 MB compressed, shared by the api and worker images;
- lines 50-56 declared `AIA_BUILD_SHA` / `AIA_BUILD_TIME` at the top of the runtime stage. A
  build argument is in every later `RUN`'s environment, so `RUN groupadd` (line 64), and every
  layer after it -- the venv copy and the worker's LibreOffice install (~300 MB) -- was new on
  every commit even when nothing else changed.

`deploy/develop/bin/image_retention.py` keeps every image younger than 48 hours, so the host
carried roughly that per deploy of the last two days, against the 85 % deploy preflight.

## The design

- A `deps` stage installs third-party dependencies from the four `pyproject.toml` files alone,
  with the same pip invocation as before, over empty stand-ins for AIA's packages that are
  then uninstalled. Same command, so the same resolution; no requirements list to keep in step.
- The `runtime` stage copies that venv as one layer that changes only with a dependency.
  Nothing per-commit precedes it.
- Each target (`api`, `worker`) then installs AIA's four packages with `--no-deps` from
  bind-mounted sources at the old `/src/...` paths (so `pip freeze` records the same origin),
  runs `pip check`, and only then sets `AIA_BUILD_SHA` / `AIA_BUILD_TIME`, which make no layer.
- The worker's LibreOffice `RUN` stays before the code, so it is cached too.

Rejected: generating a requirements file from the pyprojects (a second resolution path that
could drift from the one the images ran); copying only `aia_*` directories out of a full venv
(fragile, and `.dist-info` / entry points would have to be listed by hand).

Kept exactly: the `api` and `worker` targets, `AIA_WORKER_PDF`, `NUMBA_CACHE_DIR=/tmp/numba`,
the read-only container assumptions, the extras, the deploy workflow's cache settings.

## Measurements (local Docker 29.9.1, BuildKit, 2026-10-20)

Built on the same `python:3.12-slim-bookworm` base, the old Dockerfile (develop @ f2b0b92) beside
the new one. Sizes are compressed, as pushed to a registry.

| | before | after |
|---|---|---|
| `aia-api` image | 297.6 MB | 297.6 MB |
| `aia-worker` image (`AIA_WORKER_PDF=false`) | 297.6 MB | 297.6 MB |
| Layers a one-line source change creates | 250 MB (772 MB unpacked), shared by both images | 6.6 MB per image (19.7 MB unpacked), 13 MB for both |
| Rebuild after that change, warm cache | 4 m 30 s (api) | 51 s (api), 53 s (worker) |

In production the worker is built with `AIA_WORKER_PDF=true`, whose LibreOffice layer (~300 MB)
was also new on every commit before (its `RUN` had `AIA_BUILD_SHA` in its environment); it is now
cached. That layer could not be built here: this session's egress refuses `deb.debian.org`.

Equivalence, both builds resolved at the same moment (`--no-cache`): `pip freeze --all` identical
in each target (68 distributions, AIA's four as `aia-core @ file:///src/packages/aia_core` etc.);
every file under `/opt/venv` identical by SHA-256 (10,157 files, `RECORD` and `direct_url.json`
aside), 5,747 `.pyc` in each; the same entry point, command, user, working directory, exposed
port, stop signal and environment. With `--read-only --tmpfs /tmp`, both images import numpy
2.5.4 / scipy 1.18.1 / numba 0.68.0 and both Sociomap modules that use numba; in the worker a
`cache=True` kernel from `aia_core.domain.sociomap.signed_off_layout` compiles and caches under
`/tmp/numba`, as it does in the old image. Against
PostgreSQL 16, read-only: `alembic upgrade head` runs, the API answers `/health` and `/ready`
(`database: ok`) and Docker reports it healthy; the worker logs "worker started", stops on SIGTERM
with exit 0 and logs no ERROR.

## The trade-off

The dependency layer is now reused for as long as the four `pyproject.toml` files are unchanged
and the build cache holds it. Before, every deploy re-resolved the ranges and picked up whatever
was newest (FastAPI published 0.155.0 and 0.156.0 during these measurements). A release inside a
range now reaches develop when a `pyproject.toml` changes or the GitHub Actions cache entry is
evicted, not on the next deploy. The ranges were never a lock; this makes the image no less
reproducible than it was, only less churning.

A deliberate refresh: `ARG AIA_DEPS_REFRESH` in the `deps` stage (a date) is in the install's
environment, so changing its default in the Dockerfile re-resolves every dependency on the next
build; so does any `pyproject.toml` change. This matters for security: CI's pip-audit
(`ci.yml`, "Audit Python dependencies") audits a fresh resolution on the runner, not the image's
cached layer, so a fix released upstream inside a range reaches the images only after a refresh.

## Chunk 3

`tools/dockerfile_layers.py` reads the Dockerfile as text and fails when the `deps` stage reads
anything from the build context but a `pyproject.toml`, when `runtime` copies from the context
or declares `AIA_BUILD_SHA` / `AIA_BUILD_TIME`, or when a target declares either before its last
layer. `packages/aia_core/tests/test_dockerfile_layers.py` runs it on the real file in every
backend CI run and proves each rule refuses a Dockerfile that breaks it.

## Findings

None.
