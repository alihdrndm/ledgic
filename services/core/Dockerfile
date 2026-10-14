# Ledgic core (FastAPI + orchestrator worker + scheduler + MCP). Build from the REPO ROOT so the image
# can include the knowledge base and recorded hero fixtures from tools/corpus:
#
#   docker build -f services/core/Dockerfile -t ledgic-core .
#   docker run --env-file .env -e PORT=8000 -p 8000:8000 ledgic-core
#
# Layout inside the image mirrors the repo (/srv/services/core, /srv/tools/corpus) so app.ai.paths
# finds tools/corpus/{kb,fixtures} without extra configuration.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/.venv

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /usr/local/bin/uv

WORKDIR /srv/services/core

# dependencies first (cached layer)
COPY services/core/pyproject.toml services/core/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# application + data the AI layer reads at runtime
COPY services/core/app ./app
COPY tools/corpus/kb /srv/tools/corpus/kb
COPY tools/corpus/fixtures /srv/tools/corpus/fixtures
COPY contracts/fixtures.json /srv/contracts/fixtures.json
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --home /srv ledgic && chown -R ledgic /srv
USER ledgic

ENV PATH="/srv/.venv/bin:$PATH" \
    PORT=8000 \
    LEDGIC_KB_DIR=/srv/tools/corpus/kb \
    LEDGIC_FIXTURES_DIR=/srv/tools/corpus/fixtures
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
