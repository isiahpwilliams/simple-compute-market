ARG PYTHON_VERSION=3.13

# Stage 1: install the locked dependencies and the stub's own wheel into a venv.
# Built from the repository root after `make dist-inference-model-stub`.
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS builder

ENV UV_LINK_MODE=copy
ENV UV_HTTP_TIMEOUT=120
ENV UV_HTTP_RETRIES=10

WORKDIR /app

# The project sits at the same depth below /repo as in the repository, so the
# committed lock's relative paths resolve the same way.
COPY .dist/ /repo/.dist/
COPY scripts/uv_project.py /repo/scripts/uv_project.py
COPY e2e-tests/model-stub/pyproject.toml e2e-tests/model-stub/uv.lock /repo/e2e-tests/model-stub/
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN --mount=type=cache,target=/root/.cache/uv \
    python3 /repo/scripts/uv_project.py image --project /repo/e2e-tests/model-stub -- --no-dev --no-install-project && \
    python3 /repo/scripts/uv_project.py install-wheel --project /repo/e2e-tests/model-stub

# Stage 2: lean runtime.
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /app
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser
COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "inference_model_stub.app:app", "--host", "0.0.0.0", "--port", "8000"]
