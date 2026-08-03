# TechCorp Knowledge Agent — production image (Module 21).
#
# Multi-stage, uv-based. Stage 1 ("builder") resolves and installs the locked
# dependencies into a virtualenv; stage 2 ("runtime") copies that venv plus the
# source and runs uvicorn as a non-root user. Splitting the stages keeps uv and
# its build caches out of the shipped image, so the runtime layer is smaller and
# has a narrower attack surface.
#
# Build & run from the REPO ROOT (the build context must include src/ and apps/):
#
#     docker build -f deploy/Dockerfile -t techcorp-agent-api .
#     docker run --rm -p 8000:8000 --env-file .env techcorp-agent-api
#
# Docker is OPTIONAL for a learner — `uv run uvicorn apps.api.main:app` works
# with no container at all. See deploy/README.md.

# ---- Stage 1: builder -------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# uv settings: compile bytecode for faster cold starts, and copy (don't symlink)
# packages so the venv is self-contained when we move it to the runtime stage.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first, from the lockfiles only, so this layer is cached
# and only rebuilds when the dependencies actually change (not on every code
# edit). We install into a project-local venv at /app/.venv.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the application source and install the project itself into the venv.
COPY src ./src
COPY apps ./apps
COPY requirements.lock ./requirements.lock
RUN uv sync --frozen --no-dev

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Create an unprivileged user; never run the service as root.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Bring over the fully-built virtualenv and the application code from the builder.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/apps /app/apps

# Put the venv on PATH so `uvicorn`/`python` resolve to it, run offline by
# default (the mock LLM — a learner needs no key to boot the image), and persist
# conversation memory + the vector index on paths a volume can be mounted onto.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    TECHCORP_OFFLINE=true \
    TECHCORP_MEMORY_DB=/app/.chroma/api_memory.sqlite3

# The vector store and memory DB live here; docker-compose mounts a volume on it
# so the index survives container restarts.
RUN mkdir -p /app/.chroma && chown -R app:app /app/.chroma

USER app
EXPOSE 8000

# Liveness: the orchestrator (or `docker inspect`) sees healthy once /health 200s.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
