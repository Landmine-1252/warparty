FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

FROM python:3.12-slim AS runtime

ARG WARPARTY_UID=10001
ARG WARPARTY_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    WARPARTY_ENV=production \
    WARPARTY_DATA_DIR=/data \
    WARPARTY_DATABASE_PATH=/data/warparty.db \
    WARPARTY_PORT=8080 \
    WARPARTY_LOG_LEVEL=info \
    WARPARTY_FORWARDED_ALLOW_IPS=*

WORKDIR /app

RUN groupadd --gid "${WARPARTY_GID}" warparty \
    && useradd --uid "${WARPARTY_UID}" --gid warparty --home-dir /app --no-create-home --shell /usr/sbin/nologin warparty

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

RUN mkdir -p /data && chown -R warparty:warparty /app /data

USER warparty
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"WARPARTY_PORT\", \"8080\")}/healthz', timeout=3).read()"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${WARPARTY_PORT:-8080}\" --proxy-headers --forwarded-allow-ips \"${WARPARTY_FORWARDED_ALLOW_IPS:-*}\" --log-level \"${WARPARTY_LOG_LEVEL:-info}\""]
