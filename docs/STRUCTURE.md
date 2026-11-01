# Estrutura do projeto

Mapa curto de onde cada coisa está e de como as requisições principais
atravessam o código. Para o CRUD em detalhe veja [CRUD.md](./CRUD.md); para
subir e publicar, [CONTRIBUTING.md](./CONTRIBUTING.md) e
[DEPLOYMENT.md](./DEPLOYMENT.md).

## Layout do repositório

```text
apps/
  core/       landing, painel admin, sobre, health/robots/sitemap, miniaturas,
              limite de requisições, tradução de conteúdo, snapshot de demo
  accounts/   User customizado, cadastro com código por e-mail, login, gestão de usuários
  explore/    Category, Place, PlaceImage, PlaceReview, PlaceApproval, Favorite,
              PlaceVisit; API JSON do mapa e dos favoritos
  news/       News (notícias e eventos), EventCandidate, crawler da Prefeitura
  <app>/tests/   um pacote por app, arquivos test_*.py
config/
  settings/   base.py, dev.py (SQLite, DEBUG), prod.py (Postgres, HTTPS, R2)
  urls.py, wsgi.py, asgi.py, storage.py, test_runner.py
templates/    HTML (um diretório por app), cotton/ (componentes), includes/
frontend/css/ fonte do Tailwind: app.css e pages/*.css
static/
  css/app.css, fonts/, vendor/   saída de `npm run build:css` (commitada)
  js/components/  comportamentos compartilhados carregados pelo base.html
  js/services/    utils.js (request, getCookie, cloneIcon) e favorites_service.js
  js/pages/       scripts de uma página só (landing, place_detail, place_form)
  images/
locale/       pt-BR (origem), en, es: .po e .mo commitados
scripts/      build-css.mjs, i18n.py, generate_deco.py, vercel_build.py,
              check_init_files.py
docs/         esta documentação; CHANGELOG.md e README ficam na raiz
deploy/       Caddyfile do mock-cloudflare usado pelo docker-compose
.github/      workflows, Lighthouse, Dependabot, config do Prettier
```

Arquivos de configuração na raiz: `pyproject.toml` (dependências, black, isort,
coverage, `[tool.vercel]`), `uv.lock`, `package.json`, `eslint.config.js`,
`Dockerfile`, `docker-compose.yml`, `vercel.json`, `.pre-commit-config.yaml`.

## URLs

| Prefixo                                                          | App                                                           |
| ---------------------------------------------------------------- | ------------------------------------------------------------- |
| `/`                                                              | `core`: landing, `/sobre/`, `/painel-admin/...`               |
| `/accounts/`                                                     | `accounts`: cadastro, login, usuários                         |
| `/explore/`                                                      | `explore`: lugares, categorias, avaliações, favoritos, `api/` |
| `/eventos/`                                                      | `news`: lista e detalhe (`/news/...` redireciona)             |
| `/admin/`                                                        | Django Admin                                                  |
| `/healthz/`, `/robots.txt`, `/sitemap.xml`, `/jsi18n/`, `/i18n/` | infraestrutura                                                |
| `/cron/crawl-events/`                                            | chamada pelo Vercel Cron (exige `CRON_SECRET`)                |

## Modelos

- `accounts.User`: estende `AbstractUser`; `can_create_places`, `can_moderate`.
- `explore.Place`: `is_approved=False` por padrão; manager `Place.objects.public()`
  para tudo que o visitante vê, `.with_ratings()` para evitar consultas por card;
  `can_edit(user)` para dono ou moderador. `PlaceImage` (uma `is_primary`),
  `PlaceReview` (uma por usuário e lugar, nota 1 a 5), `PlaceApproval`
  (histórico; atualiza `Place.is_approved` ao salvar), `Favorite`,
  `PlaceVisit` (uma linha por visitante, lugar e dia, só com consentimento).
- `news.News`: notícia ou evento (`DRAFT`/`PUBLISHED`/`ARCHIVED`, `publish_date`
  preenchida ao publicar); `EventCandidate`: evento encontrado pelo crawler
  aguardando triagem.
- `Category`, `Place`, `PlaceReview` e `News` têm `TRANSLATABLE_FIELDS` e um
  JSON `translations` (en/es + hash do texto de origem).

## Fluxos principais

**Cadastro e senha.** `register_view` guarda os dados na sessão e envia um
código de 6 dígitos (`accounts/codes.py`: HMAC no cache, 15 min, 5
tentativas). O `User` só é criado em `register_verify_view`. "Esqueci a senha"
usa o mesmo mecanismo e responde igual exista ou não a conta.

**Lugar novo e moderação.** O formulário (`explore/forms.py`) usa um inline
formset de imagens. O lugar nasce pendente; moderadores aprovam, rejeitam ou
pedem mudanças na fila (`approval_queue_view`) ou em massa (`bulk_places_view`).
Cada ação grava um `PlaceApproval`. Decorador: `core.decorators.moderator_required`.

**Página de lugar e visitas.** `place_detail_view` renderiza avaliações e
mapa; se o cookie `mc_consent=accepted` existe, `explore/visits.record_visit`
conta a visita. `visits.most_visited()` alimenta "Em alta" na landing.
Contadores ignoram requisições de prefetch (`core.utils.is_speculative`).

**Favoritos.** O coração muda na hora (`favorites_ui.js`), o estado vai para
`localStorage` e é reconciliado com `toggle_favorite_view` e
`sync_favorites_view` em segundo plano; falha volta ao estado confirmado.
Toda chamada passa por `request()` (`services/utils.js`).

**Agenda de eventos.** `crawl_events` consulta a API da Prefeitura
(`news/event_crawler.py`), extrai data e local e cria `EventCandidate`
pendentes. A equipe confere em `/painel-admin/eventos/triagem/`; aprovar cria
um `News` publicado. No Vercel quem chama é o cron; no Docker, o serviço
`scheduler` (`run_scheduler`).

**Tradução de conteúdo.** `translate_content` (Ollama, local) preenche
`translations`; `core/content_translation.py` compara o hash dos campos em
português para só retraduzir o que mudou. Os templates leem com
`{% load content_i18n %}{{ obj|tr:"field" }}`. A interface usa `locale/`
(`scripts/i18n.py extract|translate|compile`).

**Imagens.** `{{ img|thumb:960 }}` e `{{ img|srcset:"480,960" }}`
(`core/thumbnails.py`) geram cópias WebP uma vez e as guardam ao lado da
mídia; `placeholder` devolve o `style` com a prévia borrada.

**Limites e erros.** `core/ratelimit.py` expõe `@limit("30/m", key="user")`;
o excesso vira 429 com `Retry-After` (JSON para fetch, `429.html` para o
navegador). O cache é `LocMemCache` por padrão e Redis com `CACHE_URL`/`REDIS_URL`.

## Frontend

Tailwind CSS 4 + Basecoat, componentes django-cotton em `templates/cotton/`,
ícones Lucide inline (`{% icon "map-pin" %}`), mapas Leaflet. As páginas usam
JavaScript sem bundler: cada `<script>` é carregado por um template (ordem em
`templates/base.html`). `npm run build:css` gera `static/css/app.css`, fontes,
ícones e o JS do Basecoat; a saída é commitada e a CI confere. Props dos
componentes e convenções em [CONTRIBUTING.md](./CONTRIBUTING.md#frontend-css-ícones-e-componentes).

## Testes

`uv run python manage.py test apps` (a CI roda sob `coverage` com piso de 90%).
Cada app tem `tests/` com `test_<app>.py` e arquivos por tema; os dados do
crawler ficam em `apps/news/testdata/`.
