# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-10-31

MaricaCity v2: the project is now `marica-city` (GitHub and
[marica-city.vercel.app](https://marica-city.vercel.app)); the original course
project is archived as `Marica-City-v1`.

### Changed

- Frontend redesign: Bootstrap 5 and Bootstrap Icons replaced by Tailwind
  CSS 4 + Basecoat, django-cotton components and inline Lucide icons, with
  self-hosted Fraunces/Inter fonts. `npm run build:css` compiles the CSS;
  the output is committed and CI checks it is current.
  - Navbar is transparent over hero images and solid on scroll, with the
    language switcher inside it and a sheet menu on mobile; the cookie
    notice is a slim bottom bar.
  - Whole-card links, photo category tiles, a sticky filter bar with sort on
    Explorar, and a place page with a photo hero, gallery lightbox, review
    summary and a sticky facts sidebar.
  - Split-layout sign-up and password pages with a 6-box code input.
  - Admin panel on a collapsible sidebar layout with tables, stat cards and
    dialog confirmations.
  - Modals are native `<dialog>` elements; view transitions morph a place
    card into its page.
- Maps use Leaflet + OpenStreetMap (no API key); Google is only used for
  address autocomplete when `GOOGLE_MAPS_API_KEY` is set.

### Added

- Container pipeline (`.github/workflows/container.yml`):
  - Every PR and push builds the production image and runs it against
    Postgres with production settings.
  - It runs `check --deploy`, migrates, waits for the Docker healthcheck,
    smoke-tests the main pages, `robots.txt`, `sitemap.xml` and the hashed,
    immutable static files, and runs Lighthouse CI with score floors
    (accessibility, best practices and SEO ≥ 95; performance ≥ 85).
  - Pushes to `main` publish the image to GHCR with an SBOM and build
    provenance.
  - A `v*` tag creates the GitHub Release from the matching CHANGELOG
    section.
- `robots.txt`, `sitemap.xml` (pages, places, events) and a meta description
  on every page (a place's or event's own text where there is one).
- Dependabot also watches the Docker base image.
- Ready for Vercel (see `docs/DEPLOYMENT.md`):
  - `[tool.vercel]` entry point and a build step (`scripts/vercel_build.py`)
    that migrates, loads the demo content and creates the admin from
    environment variables.
  - `DATABASE_URL` support (Neon) and a daily Vercel Cron for the event
    crawler at `/cron/crawl-events/`, protected by `CRON_SECRET`.
  - `deploy-check.yml` smoke-tests and runs Lighthouse against the live site
    after each production deploy.
- Demo content snapshot: `export_demo_data` writes the curated places,
  photos, reviews, events and translations to `apps/core/demo_data/`, and
  `load_demo_data` recreates them on an empty database. Personal accounts are
  never exported; demo authors have no usable password.
- Staff can feature places (star button in the places list, or the Django
  admin). Featured places lead the "Onde ir" section of the landing page.
- Bulk actions (approve, remove, publish, archive, delete, discard) ask for
  confirmation in a dialog that shows how many items are selected. The removal
  reason is chosen inside that dialog. Shift+click selects a range of rows,
  and the whole checkbox cell is clickable.
- Faster, smoother navigation:
  - Uploaded images are served as resized WebP copies (480/960/1600 px,
    generated once under `media/thumbs/`, `manage.py generate_thumbnails`)
    with `srcset`. The hero slides are WebP too. The landing page's first load
    drops from about 12 MB to 1.3 MB.
  - Cross-document view transitions replace the white flash between pages, and
    speculation rules prerender a page when the pointer rests on its link
    (Chromium). Visits and event views from prerendered pages are counted only
    when the page is actually shown.
  - A thin progress bar appears when a page takes more than 120 ms to load,
    and keeps running until the new page's images have loaded.
  - The hero slides have an inline 32 px blurred preview as their background
    while the photo loads, and the first slide is preloaded.
  - Every photo (cards, place and event pages) has an inline 16 px blurred
    copy of itself as its background, so a loading or decoding image shows a
    soft preview instead of a gray box. Images above the fold load eagerly;
    only the ones further down are lazy.
  - Development serves static files like production: every `{% static %}`
    URL carries a version (`?v=<mtime>`, `config/storage.py`) and is cached
    for a year as immutable, and uploads are immutable too. Before, the dev
    server sent `max-age=0`, so every page change re-requested each image and
    it stayed empty (gray) until the server answered.
  - Place lists annotate ratings in one query (landing page: 74 queries to 9).
  - Swiper loads only on the landing page, the unused Shoelace stylesheet and
    autoloader are gone, the icon font is preloaded, and Google Sign-In loads only when the
    "Entrar" menu is opened.
  - `ConditionalGetMiddleware` adds ETags; media on R2 gets a one-year
    `Cache-Control`.
- One-time cookie consent banner. Visitors who accept get an anonymous
  first-party cookie, and each place page view is counted once per visitor and
  day (`PlaceVisit`). Declining stores the answer and removes the identifier;
  staff and the place's author are not counted. "Em alta" on the landing page
  now lists the most-visited places of the last 7 days, falling back to the
  newest places when there are no visits.
- Bulk actions in the staff panel. The places approval queue and history can
  approve or remove (with a reason, like the single flow) several places at
  once, the event triage can discard several candidates, and the events list
  can publish, archive or delete several events. Each page has row checkboxes,
  a select-all with an indeterminate state and a sticky bar showing the number
  selected; the forms also work without JavaScript.
- `manage.py seed_demo_places` creates 18 real, approved places for the demo
  (at least three per category) from `apps/explore/demo_data/places.json`, with
  the sources recorded for each. It is idempotent (matches by name). Photos from
  Wikimedia Commons (free licences) are only downloaded with `--with-images`,
  and the credit line is appended to the description. Every demo place has a
  photo: of the place itself where Commons has one, otherwise a related photo
  credited as "Imagem ilustrativa (…)".
- "Planeje sua visita" section on the About page (linked from the footer;
  the old `/planeje-sua-visita/` URL redirects to it) with practical tourist
  information: how to get there from Rio and Niterói, the free municipal
  "Vermelhinhos" buses, when to go, sea and trail safety, and emergency numbers.
- Place cards and the place header show the average rating and review count.
- When no event is upcoming, the landing page lists the most recent events
  (marked "Encerrado") instead of hiding the section. This keeps the static demo
  populated after its events have passed.
- Content is translated too. Place descriptions, category names, event and
  news texts, and reviews are machine-translated into English and Spanish by a
  local LLM (Ollama, `qwen2.5:14b` by default) and stored in a `translations`
  JSON field. Staff can edit it in the Django admin. Pages show the version for
  the visitor's language, fall back to Portuguese when no translation exists,
  and mark translated text as "Traduzido automaticamente". `manage.py
translate_content` translates only new or changed items (it tracks a hash of
  the source text). It skips quietly when Ollama is unreachable, and it is part
  of `run_scheduler`. Settings: `OLLAMA_URL` and `OLLAMA_MODEL`.
- The interface is available in Portuguese, English and Spanish. A language
  switcher sits in the bottom-right corner of every page and remembers the
  choice (`LocaleMiddleware` + `set_language`, with unchanged URLs). Templates,
  view messages, forms, model choices and the JavaScript strings (through
  `/jsi18n/`) are all translatable. Catalogs live in `locale/`.
- `scripts/i18n.py` handles `extract`, `translate` and `compile` without GNU
  gettext. It reads templates with Django's own `templatize`, drafts missing
  entries with a local LLM through Ollama (`qwen2.5:14b` by default), and
  writes the `.mo` files. The drafts were reviewed by hand.
- Event pages have "Como chegar" (Google Maps directions) and "Adicionar ao
  calendário" (Google Calendar) actions. Event dates are written naturally in
  each language ("26 a 27 de outubro", "October 26–27", "26 al 27 de octubre").

### Changed

- Backend cleanup (no feature changes):
  - A single `moderator_required` decorator guards every staff view. Denied
    users always go to the home page.
  - `Place.objects.public()`/`visible_to()`, `Place.can_edit()`,
    `Place.ensure_primary_image()` and `PlaceApproval.record()` replace logic
    that was copied across views and the Django admin.
  - Create/edit share one form helper (places and events).
  - The panel's status filters are defined once (places, events).
  - `is_local_url()` backs `next` and the back links.
  - Removed unused context data and leftover
    `News` properties from the old news section (`calendar_url`,
    `is_external`, `tone`, `kind`, `label`, `icon_class`,
    `is_upcoming_event`).
  - View counts increment atomically.
  - `translate_content --limit` stops at the limit.
  - Approve/remove are POST-only.
  - Syncing favorites with invalid IDs ignores them instead of returning a 500.
- Forms (place, review, event) have a "Voltar" button at the top that returns
  to the page you came from, a "Cancelar e voltar" button, and a save bar that
  stays at the bottom of the screen. Leaving after editing asks for
  confirmation.
- Admin panel:
  - "Voltar ao site" is the first and most visible item of the side menu.
    The menu reads "Visão geral", "Lugares", "Eventos", "Usuários".
  - The language switcher, cookie banner and site footer are hidden inside
    the panel.
  - The dashboard cards link to their lists ("Aguardando aprovação" opens the
    pending places).
  - Places and events each have one screen whose status cards filter the
    list. Pending places stay at the top. Event suggestions found by the
    crawler are a "Sugestões" filter on the events screen instead of a
    separate triage page.
  - The administrator account is listed first, with its own badge, on the
    dashboard and in the users list. Moderators can't demote, deactivate or
    delete it.
  - The non-functional top-bar search and a hard-coded trend figure were
    removed.
- The event page follows the place page layout. Its date and place box sits
  below the description, with "Voltar" and "Como chegar" ("Adicionar ao
  calendário" was removed).
- "Explorar por categoria" is a 3×2 grid. The landing page no longer fades in
  from white, and the favorite heart is centered.
- Logging out is a POST form (CSRF-safe; prefetching can't sign anyone out).
- New footer: a short description of the guide, a GitHub link, direct links to
  each category, a "Visite" column (agenda, planning, emergency numbers) and
  the real licensing (MIT code, Wikimedia Commons photos) instead of "Todos os
  direitos reservados".
- The landing carousel's second and third slides use real photos of Maricá
  (Praia de Ponta Negra with Lagoa de Guarapina, and Praia de Jaconé from the
  Ponta Negra coast; Wilfredor, Wikimedia Commons, CC0) instead of repeating the
  first slide's image. The unused solid-colour placeholders are gone.
- Staff reach the admin dashboard from the account menu ("Painel de
  administração", above "Meus favoritos") instead of a floating gear button.
- "Adicionar lugar" is now "Cadastrar lugar" everywhere (EN "Submit a place",
  ES "Registrar lugar").
- `seed_demo_places --with-images` also attaches photos to demo places that
  already exist but have none.
- Related events on an event page use the event card, and news cards write
  event dates in the active language.
- `LANGUAGE_CODE` is now `pt-br`; dates use each locale's formats.
- The public site is now about tourism and events only. The events page
  (`/eventos/`) lists published events: upcoming ones first, then a paginated
  "Eventos anteriores" section. Category tabs, sorting and the press list are
  gone, and event pages show other events as related content. Non-event items
  return 404 on the public site.
- The public pages moved from `/news/` to `/eventos/`; the old URLs redirect
  permanently.
- The staff area calls the content "Eventos" and the create form defaults to
  the Evento category.

### Removed

- The general-news importer: the `fetch_news` command, `apps/news/importer.py`,
  its tests and sample feed, the `NEWS_FEED_URL` setting and the scheduler job.
  The event crawler now has its own HTTPS fetch helper.
- The news card template and the "Na imprensa" press list.

### Fixed

- The image could not store uploads without R2: `/app` was owned by root, so
  the non-root `app` user couldn't create `/app/media`.
- The Docker `HEALTHCHECK` failed in production: the probe to
  `127.0.0.1:8000/healthz/` got a 400 (host not in `ALLOWED_HOSTS`) and would
  then get the HTTPS redirect. `/healthz/` is now answered by a middleware
  ahead of host validation and the redirect.
- CI tests ran on SQLite although the workflow started a Postgres service (it
  wrote `DATABASE_URL`, which the settings don't read). They now run on
  Postgres, which exposed two failures SQLite hid:
  - `translate_content` left a server-side cursor open when stopping early.
  - A triage test assumed the candidate's id was 1.
- The test suite runs once under coverage instead of twice.
- Card titles use the next heading level after their section (they jumped
  from `h2` to `h5`).
- The "ou" separator in the sign-in dropdown and on the sign-up page used a
  white background; it now matches the box it sits in.
- Admin news list: the Publicadas, Rascunhos and Arquivadas tabs compared
  English keys against Portuguese status values and always came back empty, and
  every status badge read "Arquivado".
- Place reviews: the moderator edit/delete menu checked a non-existent
  `user_type` field; it now uses `can_moderate`.

### Security

- Pillow 13.0.0, virtualenv 21.14, filelock 4.2, certifi 2026.10.23 and black
  26.10.1 to clear newly published advisories flagged by `pip-audit`. Pillow 13
  needs Python 3.11, so `requires-python` is now `>=3.11` (CI and the Docker
  image already used 3.11; 3.10 reached end of life this month).

### Added

- Event crawler with an admin triage queue. `manage.py crawl_events` reads the
  Prefeitura's culture, tourism, sports and MARÉ posts and pulls out each
  announced event's date range, start time, venue and a confidence score.
  Each upcoming event becomes an `EventCandidate`. On "Painel admin → Triagem
  de eventos", staff review and edit the extracted fields, then publish the
  candidate or discard it. Publishing turns it into a regular Evento, with the
  post's photo and a "Fonte" link. The queue flags candidates that match an
  existing event or another candidate on the same day and venue.
- `manage.py run_scheduler` runs `crawl_events` and `fetch_news` every 6 hours,
  as the opt-in `scheduler` profile in `docker-compose.yml`. It is off by default.
  The project now runs as a static demo; `DEPLOYMENT.md` explains how to turn
  it back on.

- `manage.py fetch_news`: imports recent Maricá headlines from an RSS feed (Google
  News by default, overridable with `NEWS_FEED_URL`) as external news items that
  link to the original article; `--purge` removes everything it imported.
- `News.source_name` / `News.source_url` for externally published items.
- Shared page header, category tabs and site footer used by every internal page;
  "Últimas notícias" strip on the landing page; pagination on the news list.

### Changed

- `fetch_news --purge` no longer deletes events that came from the crawler.
- Events come first: the landing page shows "Próximos eventos em Maricá" instead
  of the latest headlines, and the news page is now "Agenda de Maricá", leading
  with upcoming and ongoing events (date-first event cards) before announcements,
  past events and press headlines. The navbar link reads "Eventos".
- An event with an end date counts as ongoing until it ends, rather than
  "encerrado" once it starts.
- `TIME_ZONE` is now `America/Sao_Paulo`, so event times show in local time.
- Site palette refreshed: a muted version of Maricá's signature
  red for the navbar and primary actions, warm charcoal replacing near-black
  (footer, dark buttons, admin sidebar), and warm off-white surfaces in place
  of cool greys. Page headers are now a light band instead of a red block.
  Colours live as tokens in `static/css/main.css`; all text pairs meet WCAG AA.
- Landing hero fills the viewport and lines up with the navbar's content
  column; the content column and base font size step up on very wide
  screens (1800px and 2400px). Navbar gains an 'Início' link.
- Dev server serves static files through whitenoise with caching disabled, so
  CSS/JS edits appear on a normal reload.
- News list and detail rebuilt on the same card language as Explorar; one navbar
  style for all pages (active link derived from the URL instead of per-template
  arguments); Sobre page restructured; register page uses the shared navbar.
- A featured news item only leads the news page while it is recent (14 days).
- The news list shows the site's own items first and imported headlines as a
  compact 'Na imprensa' list; place detail, register and the landing page now
  use the shared navbar and page header.

### Security

- Logout no longer redirects to arbitrary `?next=`/Referer URLs (open redirect).

### Fixed

- News category badges were always yellow (the template compared against names
  that never matched).
- Searching inside a category ignored the query and listed every place; a search
  with no matches now says so instead of "no places yet".
- The broken Google Maps embed is no longer rendered when no API key is set; the
  place page gains a "Como chegar" link that works without one.
- Logging in to a deactivated account with the right password now says the
  account is disabled (that branch was unreachable before).
- Place cards no longer nest the favourite button inside the card link; ratings
  have a text alternative; small tap targets enlarged; branded 404/500 pages; a
  login prompt explains the bounce when a logged-out visitor opens a protected page.
- Accessibility: working skip link, AA contrast for navbar and breadcrumb text,
  one `<h1>` per page, hero carousel pause control and reduced-motion support.

## [0.3.0] - 2026-09-14

### Added

- CodeQL scanning (`python`, `javascript-typescript`) on push to main and PRs.
- Dependabot config for `pip`, `npm`, and `github-actions` ecosystems, weekly.
- Coverage floor in CI (`--fail-under=70`) on top of the existing test job.
- `commitizen` for Conventional Commits-based versioning/changelog automation.
- Multi-stage `Dockerfile` (gunicorn + whitenoise), `docker-compose.yml` for local
  parity (app + postgres + redis), an opt-in `mock-cloudflare` proxy for testing
  the prod HTTPS path locally, and `docs/DEPLOYMENT.md`.
- `GET /healthz/` health check endpoint.
- Cloudflare R2 (S3-compatible) media storage via `django-storages`, opt-in via
  `AWS_STORAGE_BUCKET_NAME` — falls back to local disk when unset.
- `docs/CONTRIBUTING.md` and `.github/PULL_REQUEST_TEMPLATE.md`.

### Changed

- Replaced `safety` with `pip-audit` as the dependency vulnerability scanner (dev
  dependency and CI step), removing `safety`'s transitive `nltk` dependency and
  its unpatched CVE.
- Bumped 8 dev/runtime dependencies to current majors after a full audit found 0
  vulnerabilities but significant staleness: `django-redis` 5→7, `isort` 5→9,
  `flake8` 6→7, `django-stubs` 4→6, `mypy` 1→2, `pre-commit` 3→4, `commitizen`
  3→4, `django-extra-checks` (confirmed unused). GitHub Actions bumped to their
  latest majors (`actions/checkout`, `setup-python`, `setup-node`, `setup-uv`,
  `codeql-action`).
- `Place.primary_image` and the map/favorites JSON APIs now read from prefetched
  querysets instead of issuing per-place queries in list/loop views.
- Test coverage 78% → 95% (127 → 254 tests); CI coverage floor raised 70 → 90.

### Fixed

- `PlaceAdmin` fieldsets referenced `Place` fields removed in a past migration,
  crashing the admin add/change page for places entirely.
- `NewsForm` didn't validate that an event's end date isn't before its start date.
- `place_detail_view` only checked `is_approved`, not `is_active`, when deciding
  whether a non-owner/non-moderator could view a place — an approved-but-
  deactivated place was visible to any logged-in user.
- `approval_queue_view` and `reject_place_view` raised `NoReverseMatch` on every
  use — both built a redirect by concatenating a URL name with a query string
  instead of reversing it first.

### Removed

- `static/css/components/carousel.css` — never linked from any template, and its
  selectors didn't match current landing-page markup anyway.

## [0.2.0] - 2026-09-13

### Added

- `.env.example` documenting required and optional environment variables.
- `docs/IMPROVEMENT_PLAN.md` tracking an in-progress polish/hardening plan.
- Production settings module (`config/settings/prod.py`) with SSL redirect, secure cookies, HSTS, and `SECURE_PROXY_SSL_HEADER` for running behind a reverse proxy/CDN (e.g. Cloudflare).
- Redis-backed cache option via `CACHE_URL`/`REDIS_URL`, for multi-process production deployments.
- ESLint config and an esbuild bundling pipeline for `static/js/`.

### Changed

- Dependency management migrated from Poetry to [uv](https://docs.astral.sh/uv/); the `Makefile` was removed in favor of `uv run`/`uv sync`.
- `config/settings.py` split into `config/settings/{base,dev,prod}.py`.
- Untracked `db.sqlite3` and `media/` from git; both are now ignored going forward.
- Rewrote `README.md` with real depth on functionality, architecture, and stack; updated the GitHub repo description to match.

### Fixed

- `PlaceReview` was missing its documented "one review per user per place" constraint at the database level; added `unique_together`.
- 5 dead/unused variables in `static/js/`; 3 form controls missing `aria-label`s.

### Removed

- `aula_exercicios/` (unrelated coursework, not part of the app).

### Security

- Bumped Pillow 11.3.0 → 12.3.0, fixing 18 known CVEs (heap out-of-bounds writes/reads, decompression-bomb DoS, an OS command injection in `WindowsViewer`).
- Bumped black 24.10.0 → 26.5.1, fixing an arbitrary-file-write CVE.

## [0.1.0] - 2026-09-13

### Added

- Initial Django remake of the original Marica-City project: tourist places
  with an admin approval workflow, multi-image uploads, reviews and ratings,
  favorites, news/events, and Google OAuth login.
