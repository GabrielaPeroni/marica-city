# syntax=docker/dockerfile:1
FROM python:3.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

# collectstatic needs settings to import cleanly; values are placeholders, never used at runtime.
RUN SECRET_KEY=build-only \
    GOOGLE_OAUTH_CLIENT_ID=build-only \
    ALLOWED_HOSTS=localhost \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    /venv/bin/python manage.py collectstatic --noinput

FROM python:3.15-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

ENV PATH=/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /venv /venv
COPY --from=builder --chown=app:app /app /app
# WORKDIR created /app as root; uploads without R2 need a writable media folder
RUN mkdir -p /app/media && chown app:app /app/media

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/')" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30"]
