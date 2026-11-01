# MaricaCity

English | [Português](./README.pt-BR.md)

MaricaCity is a local tourism site for Maricá, a coastal city in Rio de Janeiro
state, Brazil. Visitors browse places, events and reviews in Portuguese,
English or Spanish. Registered users submit places, which go live only after a
moderator approves them. It runs in production at
**[marica-city.vercel.app](https://marica-city.vercel.app)**.

This is version 2 of an academic project. Version 1 is archived as
[Marica-City-v1](https://github.com/GabrielaPeroni/Marica-City-v1); v2 is a
rewrite focused on structure, tests, deployment and front-end quality.

<!--
Screenshots: put the files below in docs/screenshots/ and uncomment the tags.
Expected filenames:
  docs/screenshots/landing.png          landing page
  docs/screenshots/explore.png          /explore/ with filters
  docs/screenshots/place-detail.png     a place page (gallery, map, reviews)
  docs/screenshots/admin-dashboard.png  /painel-admin/
  docs/screenshots/mobile.png           landing or place page at phone width

<p align="center">
  <img src="docs/screenshots/landing.png" alt="Landing page" width="720">
</p>
<p>
  <img src="docs/screenshots/explore.png" alt="Explore page with filters" width="360">
  <img src="docs/screenshots/place-detail.png" alt="Place detail page" width="360">
</p>
<p>
  <img src="docs/screenshots/admin-dashboard.png" alt="Admin dashboard" width="360">
  <img src="docs/screenshots/mobile.png" alt="Mobile layout" width="180">
</p>
-->

_Screenshots to be added._

## Highlights

- **Places with moderation.** Users submit places with several photos; a
  moderator approves, rejects or asks for changes, and each decision is kept as
  history. Visitors only ever see approved places.
- **Reviews and favorites.** One 1 to 5 star review per user per place.
  Favorites update instantly in the UI and reconcile with the server in the
  background.
- **Events from the city portal.** A crawler reads the Prefeitura's public
  posts, extracts dates and venues, and puts candidates in a triage queue. Staff
  publish or discard them; nothing goes live unreviewed.
- **Three languages.** The interface is translated with Django's gettext
  catalogs; user and editorial content is translated by a local LLM and stored
  next to the original.
- **Email-verified signup.** A 6-digit code confirms the address before the
  account row is created; password reset works the same way.
- **Admin panel.** Approval queue and backlog, news and event management,
  user roles, weekly trend cards, plus the Django admin.
- **Production pipeline.** Linters, tests on PostgreSQL, a container
  smoke test and Lighthouse score floors run in CI; the app is deployed on
  Vercel with Neon Postgres and Cloudflare R2 for photos.

## Stack

| Layer      | Choice                                                                                       |
| ---------- | -------------------------------------------------------------------------------------------- |
| Backend    | Python 3.11+, Django 5.2, django-ratelimit, django-storages, Pillow                          |
| Data       | SQLite in development; PostgreSQL (Neon) in production; Redis cache optional                 |
| Frontend   | Django templates, django-cotton components, Tailwind CSS 4 + Basecoat, Lucide icons, Leaflet |
| JavaScript | Plain scripts, no bundler; ESLint                                                            |
| Delivery   | Docker image (gunicorn + whitenoise), Vercel serverless function, Cloudflare R2 for media    |
| Tooling    | uv, npm, black, isort, flake8, Prettier, pre-commit, GitHub Actions, Lighthouse CI, CodeQL   |

## Architecture

```text
Browser ── HTML (server-rendered) ──────────────┐
   │  small JS: favorites, maps, forms          │
   ▼                                            ▼
Vercel function / Docker (gunicorn)     Cloudflare R2 (photos)
   │  config.wsgi → middleware → apps
   ├── core      landing, admin panel, thumbnails, rate limit, translation helpers
   ├── accounts  User, email codes, login, user management
   ├── explore   Place, review, favorite, approval, visit; JSON map/favorites API
   └── news      News/events, EventCandidate, crawler
   │
   ├── PostgreSQL (Neon)         SQLite locally
   └── cache (Redis or LocMem)   email codes, rate limits, thumbnail lookups
```

Each Django app owns its models, views, forms, URLs and tests. Templates live
in `templates/`, the Tailwind source in `frontend/css/`, and the compiled CSS
is committed under `static/`. The directory map is in
[docs/STRUCTURE.md](./docs/STRUCTURE.md).

## Running locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Node 22 (only to
rebuild CSS).

```bash
uv sync
cp .env.example .env            # set SECRET_KEY and GOOGLE_OAUTH_CLIENT_ID at least
uv run python manage.py migrate
uv run python manage.py load_demo_data   # optional: sample places, events, translations
uv run python manage.py createsuperuser  # optional
uv run python manage.py test apps
uv run python manage.py runserver

npm ci && npm run build:css     # only after changing templates' classes or icons
```

Signup sends a code by email. Locally, `docker compose up mailhog` catches it
at http://localhost:8025 and the code screen fills itself in development.
`docker compose up --build` runs the production image with Postgres and Redis.

## Tests

```bash
uv run python manage.py test apps
uv run coverage run manage.py test apps && uv run coverage report
```

The suite has 409 tests (`apps/<app>/tests/`). CI measures coverage with test
files included and requires 90%.

## Documentation

[docs/STRUCTURE.md](./docs/STRUCTURE.md)
[docs/CRUD.md](./docs/CRUD.md)
[/docs/CONTRIBUTING.md)](./docs/CONTRIBUTING.md)
[docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)
[Changelog](./CHANGELOG.md)

Code under the [MIT License](./LICENSE). Photos come from Wikimedia Commons and
contributors, as credited in the site footer.
