# Deployment

The live demo runs on **Vercel** (Django as a serverless function, Neon Postgres,
Cloudflare R2 for photos); see [Vercel](#vercel-production). The Docker image is
built, tested and published by CI on every push and is the way to self-host
(VPS, Cloudflare Tunnel, any container platform); the rest of this file covers
it, the CI/CD pipeline and local testing with `docker-compose.yml`.

## Image

Multi-stage `Dockerfile`: a `builder` stage installs deps with `uv sync
--locked --no-dev` into `/venv` and runs `collectstatic`, then a slim
`runtime` stage copies just the venv + app code and runs as a non-root user
(`app`). Static files are baked into the image at build time — no
`collectstatic` at container start.

```bash
docker build -t maricacity .
docker run --rm -p 8000:8000 --env-file .env \
  -e DJANGO_SETTINGS_MODULE=config.settings.prod \
  maricacity
```

The container serves on `0.0.0.0:8000` via `gunicorn config.wsgi:application`
and has a `HEALTHCHECK` hitting `GET /healthz/` (see below).

## Required env vars (prod)

Copy `.env.example` to `.env` and fill in real values. At minimum for prod:

- `SECRET_KEY`, `ALLOWED_HOSTS`, `GOOGLE_OAUTH_CLIENT_ID` — no defaults, required.
- `DATABASE_URL` (`postgres://user:pass@host:port/name?sslmode=require`, as
  Vercel/Neon provide it) or `DB_ENGINE`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`/
  `DB_HOST`/`DB_PORT` — a real Postgres instance (SQLite is dev-only).
  `DATABASE_URL` wins when both are set.
- `CACHE_URL` or `REDIS_URL` — a Redis instance; without one, `LocMemCache` is
  used, which is not safe across multiple gunicorn workers.
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_HSTS_*` — default to secure values already, only override if you
  know why.
- Media storage (Cloudflare R2, S3-compatible): `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`,
  optionally `AWS_S3_REGION_NAME` (default `auto`) and
  `AWS_S3_CUSTOM_DOMAIN`. Leaving `AWS_STORAGE_BUCKET_NAME` empty falls back
  to local `MEDIA_ROOT` — fine for a single-instance VPS with a persistent
  volume, but uploads will not survive a redeploy on most PaaS/containers.

Static files are always served by whitenoise (compressed + hashed filenames
in prod via `STORAGES["staticfiles"]`) — no separate nginx layer needed for
static assets regardless of which media backend you pick.

## Health check

`GET /healthz/` (`apps/core/views.health_view`) — no auth, runs `SELECT 1`
against the DB and returns `{"status": "ok"}` with a 200. It is answered by
`apps.core.middleware.HealthCheckMiddleware`, first in `MIDDLEWARE`, so probes
that call the container directly (`http://127.0.0.1:8000/healthz/`) are not
rejected by `ALLOWED_HOSTS` or redirected to HTTPS. Chosen over a no-op check so it also catches DB connectivity outages,
which is normally what "the app is unhealthy" means in practice for this
project. Used by the Dockerfile's `HEALTHCHECK` and should be pointed at by
whatever orchestrates the container (PaaS health check URL, VPS process
supervisor, uptime monitor).

## CI/CD pipeline

| Workflow           | When                                          | What                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------ | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pr-checks.yml`    | PRs and `main`                                | Linters (black, isort, autoflake, flake8, Prettier, pip-audit); tests on Postgres under coverage (floor 90%)                                                                                                                                                                                                                                                                                                                 |
| `container.yml`    | PRs, `main`, `v*` tags                        | Builds the image, `check --deploy` with default prod settings, runs it on Postgres, migrates, waits for the Docker healthcheck, smoke-tests pages / `robots.txt` / `sitemap.xml` / hashed static files, Lighthouse CI score floors. On `main`: publishes `ghcr.io/<owner>/<repo>` (`latest`, `sha-…`) with SBOM and build provenance. On a `v*` tag: semver tags plus a GitHub Release from that version's CHANGELOG section |
| `deploy-check.yml` | Vercel reports a successful production deploy | Smoke-tests the live URL and runs Lighthouse against it                                                                                                                                                                                                                                                                                                                                                                      |
| `codeql.yml`       | PRs, `main`, weekly                           | Static security analysis                                                                                                                                                                                                                                                                                                                                                                                                     |

Dependabot keeps Python, npm, GitHub Actions and the Docker base image up to date.

Release: move the `[Unreleased]` section of `CHANGELOG.md` under `## [x.y.z] - date`,
commit, then `git tag vx.y.z && git push --tags`.

## Vercel (production)

Vercel detects `manage.py` and serves `config.wsgi:application` as one function
(`[tool.vercel]` in `pyproject.toml`). It runs `collectstatic` itself and serves
`/static/` from its CDN. The build step `scripts/vercel_build.py` migrates, loads
the demo content on an empty database (`load_demo_data`, from
`apps/core/demo_data/`) and creates the admin when its variables are set.
`vercel.json` sets the function timeout and a daily cron that calls
`/cron/crawl-events/` (protected by `CRON_SECRET`, which Vercel sends as a
Bearer token).

One-time setup:

1. **Vercel**: _Add New → Project_, import this repository. In _Configure
   Project_ (_Build and Output Settings_), keep the defaults: the build step and
   the entry point come from `pyproject.toml`.

   | Setting          | Value                                                                          |
   | ---------------- | ------------------------------------------------------------------------------ |
   | Framework Preset | Django (detected from `manage.py`; pick it if it isn't)                        |
   | Root Directory   | `./` (repository root, where `manage.py` is)                                   |
   | Build Command    | default (runs `scripts/vercel_build.py`, see `pyproject.toml`)                 |
   | Output Directory | default/empty (Django is a function; static files are collected automatically) |
   | Install Command  | default (installs the dependencies from `pyproject.toml`)                      |

2. **Database**: in the project, _Storage → Neon (Postgres)_, connected to
   Production and Preview. It adds `DATABASE_URL` (with Neon branching, each
   preview gets its own database copy).
3. **Photos** (Cloudflare R2, required: Vercel's filesystem is read-only):
   create a bucket and an API token with read/write on it; enable public access
   (r2.dev or a custom domain).
4. **Environment variables** (Project → Settings → Environment Variables). Local
   development keeps using `.env`, so nothing goes in _Development_. _Preview_
   covers the per-branch URLs; give it its own `SECRET_KEY`.

   | Variable                                                                           | Environments        | Value                                                         |
   | ---------------------------------------------------------------------------------- | ------------------- | ------------------------------------------------------------- |
   | `DJANGO_SETTINGS_MODULE`                                                           | Production, Preview | `config.settings.prod`                                        |
   | `SECRET_KEY`                                                                       | Production, Preview | long random string, different per environment                 |
   | `ALLOWED_HOSTS`                                                                    | Production, Preview | `.vercel.app` (plus your domain, comma-separated)             |
   | `GOOGLE_OAUTH_CLIENT_ID`                                                           | Production, Preview | OAuth client id, or any placeholder to disable Google sign-in |
   | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`                                       | Production, Preview | R2 token                                                      |
   | `AWS_STORAGE_BUCKET_NAME`                                                          | Production, Preview | bucket name                                                   |
   | `AWS_S3_ENDPOINT_URL`                                                              | Production, Preview | `https://<account-id>.r2.cloudflarestorage.com`               |
   | `AWS_S3_CUSTOM_DOMAIN`                                                             | Production, Preview | public bucket host, e.g. `pub-….r2.dev`                       |
   | `CRON_SECRET`                                                                      | Production          | long random string (crons only run on production)             |
   | `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | Production, Preview | the admin account created on the first build of each database |
   | `DATABASE_URL`                                                                     | (set by Neon)       | don't add it by hand                                          |

   Generate random strings with
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

5. Deploy. Every push to `main` then deploys production, and every other branch
   gets a preview URL.

To refresh the demo content after curating it locally, run
`manage.py export_demo_data`, commit `apps/core/demo_data/`, and load it into
an empty database (`load_demo_data` never touches a database that already has
places).

Limits to keep in mind:

- After idle time, the first request starts a new instance (cold start).
- There is no long-running process. The crawler runs through the cron above,
  and `translate_content` (Ollama) stays a local task: the snapshot already
  carries the translations.

## Wiring Cloudflare in front

Either approach works unchanged against the same Django app — `prod.py`
already trusts `X-Forwarded-Proto` from a reverse proxy
(`SECURE_PROXY_SSL_HEADER`) and redirects to HTTPS
(`SECURE_SSL_REDIRECT`). Nothing here is specific to one deployment target.

### Option A — Cloudflare as a plain proxy/CDN in front of a VPS/PaaS origin

1. Deploy the container to a VPS or PaaS (Fly.io, Railway, Render, a plain
   VPS with the Docker image, etc.) with a public origin address.
2. Point a DNS record at that origin in Cloudflare, with the proxy (orange
   cloud) enabled.
3. Set Cloudflare's SSL/TLS mode to **Full (strict)** if the origin serves
   its own valid cert, or **Full** if it's self-signed/Let's Encrypt behind a
   basic setup. Avoid **Flexible** — it terminates TLS at Cloudflare only and
   would make `SECURE_SSL_REDIRECT` loop, since the origin never sees HTTPS.
4. Cloudflare forwards `X-Forwarded-Proto: https` automatically; no
   Django-side config needed beyond what's already in `prod.py`.

### Option B — Cloudflare Tunnel (no public origin IP)

1. Run `cloudflared` alongside the container (same host, or as a sidecar
   container) and create a tunnel pointing at `http://app:8000` (or
   `localhost:8000` if run on the same host).
2. Route a public hostname to the tunnel in the Cloudflare dashboard/`cloudflared`
   config.
3. `cloudflared` sets `X-Forwarded-Proto: https` on requests it forwards, so
   `SECURE_PROXY_SSL_HEADER` works the same as in Option A.
4. No inbound ports need to be opened on the origin at all.

Switching between A and B later is purely infra — the Django app and its
settings never change.

## Local dev/testing with docker-compose

`docker-compose.yml` gives a full-stack local setup close to prod, as an
alternative to the plain `uv run manage.py runserver` + SQLite flow (which
still works unchanged — this is additive, not a replacement):

```bash
docker compose up --build
```

Brings up:

- `app` — the Django app built from `Dockerfile`, running under
  `config.settings.prod`, `.env`-configured, talking to `db`/`redis`.
- `db` — `postgres:15`, matching the version CI tests against.
- `redis` — `redis:7`, matching the Redis-ready cache config.

Run migrations/management commands against the compose stack with
`docker compose exec app python manage.py <command>` (adjust the venv path
if invoking directly, or use `docker compose run --rm app <command>`).

### Local mock Cloudflare vs. real Cloudflare

`docker-compose.yml` also has an **opt-in** `mock-cloudflare` service (Caddy)
behind the `mock-cloudflare` profile — it is not part of the default
`docker compose up`:

```bash
docker compose --profile mock-cloudflare up --build
```

This starts a Caddy reverse proxy in front of `app` that terminates TLS with
a self-signed cert (`tls internal`) and forwards `X-Forwarded-Proto: https`,
mimicking what Cloudflare's edge does to the origin. It lets you exercise the
full `SECURE_PROXY_SSL_HEADER`/`SECURE_SSL_REDIRECT` path — HTTPS termination
at the edge, plain HTTP to the app — entirely locally, without a Cloudflare
account or domain:

```bash
curl -k https://localhost:8443/healthz/
```

**This is a local stand-in, not a deployment option.** It exists purely so
the prod security settings are testable today, before the real Cloudflare
target (Option A or B above) is decided. Swapping in real Cloudflare later
means changing the infra in front of the app (DNS + proxy settings, or a
`cloudflared` tunnel) — the `mock-cloudflare` service and its config
(`deploy/mock-cloudflare/Caddyfile`) are not part of that path and are never
used in prod.

## Agenda automática (`crawl_events`) e agendador

`uv run python manage.py crawl_events` consulta a API do portal da Prefeitura
(categorias de Cultura, Turismo, Esportes e MARÉ) e extrai data, horário e local
de cada evento anunciado. Eventos futuros entram na **Triagem de eventos**
(`/painel-admin/eventos/triagem/`), onde a equipe confere os dados e publica na
agenda ou descarta. Nada é publicado sem revisão. A busca é idempotente.

> **Estado atual: desligado.** O projeto está em modo demonstração com conteúdo
> estático: a agenda foi importada uma vez (out/2026) e o
> agendador não roda. Todo o código continua no repositório. Para religar:
>
> 1. `docker compose --profile scheduler up -d` (ou rode `run_scheduler` como
>    serviço / cron com `--once`);
> 2. revise os eventos em `/painel-admin/eventos/triagem/` periodicamente;
> 3. confira se as categorias em `PREFEITURA_CATEGORIES`
>    (`apps/news/event_crawler.py`) ainda existem no portal
>    (`/wp-json/wp/v2/categories`), pois os IDs podem mudar.
>
> Também dá para buscar só uma vez, sem agendador: `manage.py crawl_events`
> ou o botão “Buscar agora” na triagem.

`uv run python manage.py run_scheduler` mantém um processo que roda
`crawl_events` a cada 6 horas (`--interval`, em horas; `--once`
roda uma vez e sai). No `docker-compose.yml` ele é o serviço `scheduler`; fora
do Docker, rode-o como um serviço do sistema ou troque por um cron que chame
`run_scheduler --once`.

## Tradução automática do conteúdo (`translate_content`)

O conteúdo cadastrado (descrições de lugares, categorias, eventos e
avaliações) é traduzido para inglês e espanhol por um LLM local via
[Ollama](https://ollama.com). As traduções ficam no campo `translations` de cada
registro e são servidas sem chamar o modelo, então o site não depende do Ollama
em produção.

- `ollama pull qwen2.5:14b` (ou outro modelo; ajuste `OLLAMA_MODEL`).
- `uv run python manage.py translate_content` traduz o que é novo ou mudou desde
  a última execução. Também roda dentro do `run_scheduler`.
- `OLLAMA_URL` aponta para o servidor (padrão `http://localhost:11434`). Se ele
  não responder, o comando avisa e sai sem erro.
- Correções manuais: Django admin → o registro → "Traduções automáticas".
