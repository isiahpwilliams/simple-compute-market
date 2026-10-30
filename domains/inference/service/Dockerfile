ARG PYTHON_VERSION=3.13

# Stage 1: install deps into a venv. Built from the repo root (see the
# root Makefile build-inference-service target) so the internal wheels in .dist/ resolve.
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS builder

ENV UV_LINK_MODE=copy
# Internal package names resolve from /.dist; PyPI intermittently 5xxs on
# the index lookups that should 404, so back off through the flap. The
# timeout caps a wedged connection (podman's gvproxy can leave a socket
# open with no data) so the retries fire instead of hanging at 0% CPU.
ENV UV_HTTP_TIMEOUT=120
ENV UV_HTTP_RETRIES=10

WORKDIR /app

# The lock is used as committed: the project's pyproject and lock sit at the
# same depth below /repo as below the repository root, so the lock's relative
# wheelhouse path resolves to /repo/.dist. uv_project.py derives the internal
# packages from the lock and reinstalls them, so a cached build of a
# same-version wheel is never reused.
COPY .dist/ /repo/.dist/
COPY scripts/uv_project.py /repo/scripts/uv_project.py
COPY domains/inference/service/pyproject.toml domains/inference/service/uv.lock /repo/domains/inference/service/
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN --mount=type=cache,target=/root/.cache/uv \
    python3 /repo/scripts/uv_project.py image --project /repo/domains/inference/service -- --no-dev --no-install-project

# Stage 2: lean runtime.
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /app
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser && \
    mkdir -p /app/data && chown -R appuser:appuser /app

COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --chown=appuser:appuser domains/inference/service/src ./src
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
# Persist the SQLite DB on the named volume mounted at /app/data.
ENV INFERENCE_DATABASE_URL="sqlite:////app/data/inference.db"
VOLUME ["/app/data"]
USER appuser

ARG PORT=8086
ENV INFERENCE_PORT=${PORT}
EXPOSE ${PORT}

HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8086/health')" || exit 1

CMD ["uvicorn", "inference_service.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8086"]
