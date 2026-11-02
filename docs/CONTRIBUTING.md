# Contribuindo com o MaricaCity

Guia prático para configurar o ambiente, rodar testes/lint e abrir PRs neste
repositório. Para a arquitetura completa veja [STRUCTURE.md](./STRUCTURE.md) e [CRUD.md](./CRUD.md).

## Setup do ambiente

Pré-requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone <repo>
cd marica-city
uv sync                      # cria .venv/ e instala deps (inclui o grupo dev)
cp .env.example .env         # preencha SECRET_KEY e GOOGLE_OAUTH_CLIENT_ID no mínimo
uv run python manage.py migrate
uv run python manage.py createsuperuser   # opcional
uv run python manage.py runserver
```

Não existe Makefile neste projeto — todos os comandos passam por `uv run`.
`config.settings.dev` é o módulo de settings padrão (SQLite, `DEBUG=True`,
hosts permissivos); produção usa `config.settings.prod` (ver
[DEPLOYMENT.md](./DEPLOYMENT.md)).

### Alternativa: docker-compose

```bash
docker compose up --build
```

Sobe o app (settings `prod`) + Postgres + Redis. Útil para testar mais perto
de produção; a rota `uv run manage.py runserver` continua funcionando sem
Docker para o dia a dia. Detalhes em [DEPLOYMENT.md](./DEPLOYMENT.md).

## Rodando os testes

```bash
uv run python manage.py test apps            # suíte completa
uv run python manage.py test apps.explore    # um app específico
uv run python manage.py test apps.explore.tests.test_explore.PlaceModelTests  # uma classe
uv run python manage.py test apps.explore.tests.test_visits                   # um arquivo
```

Cobertura do código da aplicação (sem os testes), com o piso de 80% que a CI aplica (ela roda com
`RATELIMIT_ENABLE=False` e Postgres):

```bash
uv run coverage run manage.py test apps
uv run coverage report --fail-under=80
```

`apps/core/tests/test_api_and_pages.py` cobre o contrato das APIs JSON, o status de
cada página por tipo de visitante e o número de consultas. O que só aparece no
navegador (chamadas repetidas, falhas de rede, erros no console, recarregamentos,
trabalho com a página parada) fica em `scripts/browser_check.mjs`:

```bash
npx playwright install chromium   # uma vez
BASE_URL=http://localhost:8000 CHECK_USER=x CHECK_PASSWORD=y npm run check:browser
```

Cada app tem um pacote `apps/<app>/tests/`: `test_<app>.py` com os testes
gerais do app e um `test_<tema>.py` para cada recurso maior (visitas,
limite de requisições, snapshot de demo...). Teste novo vai no arquivo do tema
ou em um arquivo novo `test_*.py` no mesmo pacote. O `.env` local pode apontar
para o Neon de produção: deixe `DATABASE_URL` e `DATABASE_URL_UNPOOLED` em
branco ao rodar os testes.

## Lint e formatação

Python:

```bash
uv run black .
uv run isort .
uv run autoflake --in-place --remove-all-unused-imports --remove-unused-variables \
  --remove-duplicate-keys --ignore-init-module-imports --recursive apps/ config/ manage.py
uv run flake8 --select=TMS010,TMS011,TMS012,TMS013,TMS020,TMS021,TMS022 apps/ config/ manage.py
uv run mypy .          # opcional, não é gate de CI
uv run pip-audit       # auditoria de vulnerabilidades nas dependências
```

JavaScript (`static/js/`):

```bash
npm ci
npm run lint:js        # ESLint
```

Organização: `components/` (comportamentos compartilhados que o `base.html`
carrega), `services/` (`utils.js` e `favorites_service.js`, que vêm antes dos
demais) e `pages/` (um script por página). Não há bundler: cada arquivo é um
`<script>` num template, e os globais compartilhados estão declarados em
`eslint.config.js`.

Markdown/JSON/CSS/HTML: `prettier` (config em `.github/.prettierrc`), aplicado
via pre-commit.

## Frontend: CSS, ícones e componentes

O visual usa **Tailwind CSS v4 + Basecoat** (os componentes do shadcn/ui em
classes HTML), **django-cotton** para componentes de template e ícones
**Lucide** inline. Não há Bootstrap.

### Build

```bash
npm ci
npm run build:css      # fontes -> static/fonts/, ícones -> apps/core/icons/,
                       # JS do Basecoat -> static/vendor/basecoat/, CSS -> static/css/app.css
npm run watch:css      # só recompila o CSS ao salvar (rode build:css ao usar ícone novo)
```

- A fonte é `frontend/css/app.css` (fora de `static/`, para o collectstatic não publicá-la) (tokens, `@theme`, classes de componente).
  A saída (`static/css/app.css`, fontes, ícones, JS do Basecoat) é **commitada**:
  Docker e Vercel não têm Node. A CI roda `npm run build:css` e falha se o
  resultado for diferente do commitado.
- O Tailwind lê `templates/**`, `static/js/**` e `apps/**/*.py`. Escreva as
  classes por extenso (nada de `"bg-" + cor`), senão elas não entram no CSS.
- Sem `style=` inline e sem cor hex em template: use os tokens. A única exceção
  é a prévia borrada das fotos (`style="{{ img|placeholder }}"`), que é um dado
  por imagem.

### Tokens

| Uso                                     | Classe                                                             |
| --------------------------------------- | ------------------------------------------------------------------ |
| Fundo da página / texto                 | `bg-background`, `text-foreground`                                 |
| Superfície de card / popover            | `bg-card`, `bg-popover`                                            |
| Texto secundário                        | `text-muted-foreground`; fundo neutro `bg-muted`                   |
| Botão principal (carvão)                | `bg-primary text-primary-foreground`                               |
| Acento vermelho de Maricá (só destaque) | `text-brand`, `bg-brand`, `bg-brand-tint`                          |
| Status                                  | `text-success`/`bg-success-tint`, `warning`, `info`, `destructive` |
| Estrelas                                | `text-star`                                                        |
| Bordas                                  | `border` (cor `border-border` já é padrão), `ring-foreground/8`    |
| Sombras                                 | `shadow-card`, `shadow-lift` (hover), `shadow-bar`                 |

Raio: `rounded-md` (0.5rem) em controles, `rounded-xl` (0.75rem) em cards e
diálogos. Tipografia: Inter 16px no corpo; títulos em Fraunces com
`font-display` + `text-display-sm|md|lg|xl` (fluidos), sempre em sentence case
(nada de `uppercase` em título). Largura de página: `container-page`.

### Ícones

```django
{% load icons %}
{% icon "map-pin" class="size-4 text-brand" %}
{% icon "star" aria_label=_("Nota") %}   {# com rótulo: role="img" em vez de aria-hidden #}
```

- Nomes em [lucide.dev/icons](https://lucide.dev/icons). O build copia só os
  ícones usados em `{% icon "..." %}` (ou em `icon="..."` de um `<c-...>`);
  rode `npm run build:css` depois de usar um ícone novo. Nome fora do template
  (vindo do Python, por exemplo) vai em `EXTRA_ICONS` em `scripts/build-css.mjs`.
- Underscore vira hífen nos atributos (`data_icon` -> `data-icon`).
- Ícone inexistente quebra a página em DEBUG e nos testes.
- Ícones inseridos pelo JS: adicione-os em `templates/includes/js_icons.html` e
  use `cloneIcon("check")` (de `services/utils.js`).
- Estado preenchido (coração salvo) é CSS: `[aria-pressed=true] svg { fill: currentColor }`.

### Navbar e chrome

- Cada página inclui `{% include 'includes/navbar.html' %}`. Com hero de foto
  no topo use `{% include 'includes/navbar.html' with transparent=True %}`: a
  barra fica fixa e transparente sobre o hero e vira branca ao rolar
  (`data-scrolled`). Sem `transparent` ela é sticky e sólida, e ocupa espaço.
- Toasts: mensagens do Django aparecem sozinhas; pelo JS use
  `showToast(texto, 'success'|'error'|'warning'|'info')`.
- Diálogos: `<c-dialog>` + `data-dialog-open="id"` no botão; qualquer
  `data-dialog-close` dentro fecha; clicar no fundo fecha (exceto com
  `data-static`). Pelo JS: `document.getElementById(id).showModal()`.
- Basecoat JS carregado no `base.html`: `dropdown-menu`, `popover`, `toast`.
  `sidebar` e `tabs` estão em `static/vendor/basecoat/`; carregue no bloco
  `{% block basecoat_js %}` da página que precisar.
- Classes do Basecoat têm nomes iguais aos do Bootstrap (`btn`, `card`, `badge`,
  `dropdown-menu`, `popover`, `toast`, `alert`, `table`). Marcação antiga do
  Bootstrap que sobrar numa página pega o estilo/JS do Basecoat; troque-a.

### Rede lenta, falhas e envios duplicados

- Todo `fetch` do JS passa por `request(url, {method, json, body, as, timeout})`
  (`services/utils.js`): tem tempo limite e rejeita com `RequestError`
  (`kind`: `offline`, `timeout`, `network`, `ratelimit`, `forbidden`, `server`,
  `http`; `userMessage` já vem traduzida; `data` traz o JSON do erro). Passou de
  4 s, mostra uma vez por minuto o aviso "conexão lenta". Nunca repete sozinho.
- Favoritos são otimistas: o coração troca na hora (`applyFavorite`) e o
  servidor é reconciliado em segundo plano (`scheduleSync`), com cliques
  juntados em um pedido só; se falhar, volta ao estado confirmado e avisa.
- `connection.js`: faixa offline/lenta (`showConnectionNotice`) e região
  `aria-live`. `nav_progress.js` avisa se a navegação passa de 5 s.
- `form_guard.js`: todo `<form method=post>` desabilita os botões com spinner
  ("Enviando…", ou `data-pending-label`) e barra o segundo envio; opte fora com
  `data-no-guard`. Restaura no `pageshow` do cache de páginas.
- `image_fallback.js`: foto que falha vira `.img-fallback` com ícone.
- `lazy_assets.js`: `loadLeaflet()`/`loadSwiper()` baixam a CDN só quando
  precisa; `lazyMap(container, mount)` monta o mapa com esqueleto e estado de
  erro com "Tentar de novo" (templates em `includes/map_errors.html`).
- Limites: `@limit("30/m", key="user")` (`apps/core/ratelimit.py`); o excesso
  vira 429 com `Retry-After` (JSON para fetch, `429.html` para o navegador).

### Componentes (`templates/cotton/`)

Props em string (`variant="outline"`) ou expressão com `:` (`:place="place"`,
`:eager="forloop.first"`); atributos que não são props (`id`, `data-*`,
`aria-*`, `onclick`...) vão para o elemento raiz. `level` é sempre string.

**`<c-button>`** — `variant` (vazio=primário carvão, `brand`, `secondary`,
`outline`, `ghost`, `link`, `destructive`), `size` (`xs`, `sm`, `lg`, `icon`,
`icon-sm`...), `href` (vira `<a>`), `type` (padrão `button`), `class`.

```django
<c-button href="{% url 'explore:place_create' %}" variant="brand">{% icon "circle-plus" %}{% translate "Cadastrar lugar" %}</c-button>
```

**`<c-badge>`** — `variant` (vazio, `secondary`, `outline`, `brand`,
`success`, `warning`, `info`, `destructive`, `overlay` = branco translúcido
sobre foto), `href`, `class`.

```django
<c-badge variant="warning">{% translate "Pendente" %}</c-badge>
```

**`<c-card>`** — `title`, `description`, `level` (`"2"`/`"3"`), `size` (`sm`),
`class`; slots `footer` e `action` (canto do cabeçalho). Conteúdo no slot padrão.

```django
<c-card title="{% translate 'Informações' %}">
  ...
  <c-slot name="footer"><c-button size="sm">{% translate "Salvar" %}</c-button></c-slot>
</c-card>
```

**`<c-page-header>`** — cabeçalho de página interna: `title`, `eyebrow`,
`subtitle`, `class`; slots `crumbs` (itens `<li>`), `actions`; o slot padrão
entra abaixo (busca, filtros).

```django
<c-page-header title="{% translate 'Explorar' %}" subtitle="...">
  <c-slot name="crumbs"><li><a href="/">{% translate "Início" %}</a></li><li>{% translate "Explorar" %}</li></c-slot>
</c-page-header>
```

**`<c-section-heading>`** — `title`, `eyebrow`, `subtitle`, `href` +
`link_text` (padrão "Ver todos"), `id` (vai no `<h2>`), `level` (`"1"` vira
`<h1>`), `align` (`start`|`center`), `class`.

```django
<c-section-heading id="trendingHeading" eyebrow="..." title="{% translate 'Em alta agora' %}" href="{% url 'explore:explore' %}" />
```

**`<c-rating>`** — `:value` (média, float ou `None` = não renderiza),
`:count`, `compact` (estrela única + "4,3 · 12 avaliações"), `class`.

```django
<c-rating :value="place.average_rating" :count="place.review_count" />
```

**`<c-place-card>`** — `:place` (obrigatório), `:eager` (imagem sem lazy),
`morph` (padrão `True`: `view-transition-name: place-<id>` na foto; passe
`:morph="False"` se o mesmo lugar aparecer duas vezes na página), `remove`
(modo "remover dos favoritos"), `level` (`"2"`/`"3"`), `sizes`, `class`.
O card inteiro é um link; o coração fica sobre a foto (`.favorite-btn`,
`data-place-id`, `aria-pressed`) e é ligado pelo `components/favorites_ui.js`. Usa
`place.primary_image`, `place.categories.all.0`, `average_rating`,
`review_count`, `address`, `is_pending`: monte o queryset com
`.with_ratings().prefetch_related("images", "categories")`.

```django
<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
  {% for place in places %}<c-place-card :place="place" :eager="forloop.first" />{% endfor %}
</div>
```

**`<c-event-card>`** — `:event` (obrigatório), `lead` (destaque horizontal com
resumo), `:eager`, `level`, `sizes`, `class`. O card inteiro é um link.

```django
<c-event-card :event="event" :lead="forloop.first" />
```

**`<c-empty-state>`** — `icon` (padrão `search`), `title`, `description`,
`class`; ações no slot padrão.

```django
<c-empty-state icon="map-pin" title="{% translate 'Nenhum lugar encontrado' %}">
  <c-button href="{% url 'explore:explore' %}" variant="outline">{% translate "Limpar busca" %}</c-button>
</c-empty-state>
```

**`<c-skeleton>`** — `variant` (`block` padrão: dê o tamanho via `class`;
`card` no formato do place-card; `text` três linhas), `class`.

```django
<c-skeleton class="h-80 w-full rounded-xl" />
```

**`<c-dialog>`** — `id` (obrigatório), `title`, `description`, `size`
(`sm`|`lg`), `class`, `panel_class`; slot `footer`. Abre com
`data-dialog-open="<id>"`.

```django
<c-button variant="destructive" data-dialog-open="delete-review">{% translate "Excluir" %}</c-button>
<c-dialog id="delete-review" title="{% translate 'Excluir avaliação?' %}">
  <p>...</p>
  <c-slot name="footer">
    <c-button variant="outline" data-dialog-close>{% translate "Cancelar" %}</c-button>
    <form method="post" action="...">{% csrf_token %}<c-button type="submit" variant="destructive">{% translate "Excluir" %}</c-button></form>
  </c-slot>
</c-dialog>
```

**`<c-form-field>`** — `:field` (um BoundField), `label` e `help` (substituem
os do form), `hide_label`, `class`. Renderiza label (com `*` se obrigatório),
widget com as classes do Basecoat (remove `form-control`/`form-select`/`btn*`),
ajuda e erros (`data-invalid`, `role="alert"`). Campo oculto sai só com o input;
checkbox fica na horizontal; radio/checkbox múltiplo vira `<fieldset>` (sem a
opção vazia `---------`). `variant="stars"` mostra um radio de nota 1–5 como
estrelas clicáveis (`.star-picker`).

```django
<form method="post" class="grid gap-5">
  {% csrf_token %}
  {% for field in form %}<c-form-field :field="field" />{% endfor %}
</form>
```

Filtro avulso: `{% load form_ui %}{{ form.campo|ui_widget }}` só o widget com
as classes do Basecoat.

### Ilustrações impressas e movimento

- `<c-deco shape="frond" class="w-64" />`: formas em cor sólida com borda de
  tinta (filtros `#ink`/`#ink-edge` em `base.html`). Formas: `frond`,
  `frond-low`, `monstera`, `aroeira` (frutos em `--deco-accent`), `sun`,
  `gulls`, `skyline`, `wave`. A cor vem de `text-*` (`text-lagoon`,
  `text-lagoon-tint`, `text-sun`, `text-leaf`). Geradas por
  `uv run python scripts/generate_deco.py templates/includes/deco`.
- Para espalhar entre seções: `<span class="deco-float top-10 -left-16 w-64"
data-parallax="0.1"><c-deco shape="monstera" class="w-full" /></span>`
  dentro de uma seção `relative isolate overflow-x-clip` (fica atrás do
  conteúdo; use `z-[2]` para passar por cima da seção vizinha).
- `<c-wave at="top" class="text-lagoon" />` / `at="bottom"`: borda ondulada
  da cor da seção que a contém.
- `data-reveal` (elemento) e `data-reveal-stagger` (filhos em sequência)
  aparecem ao rolar; `data-spotlight` acende uma luz sob o cursor. Tudo some
  com movimento reduzido.

### Pre-commit

```bash
uv run pre-commit install
```

Depois disso, cada commit roda automaticamente: trailing-whitespace,
end-of-file-fixer, check-yaml/json/toml/xml, check-merge-conflict,
debug-statements, black, isort, autoflake, flake8, prettier e uma checagem
customizada de arquivos `__init__.py` (`scripts/check_init_files.py`). Rode
`uv run pre-commit run --all-files` para validar o repo inteiro de uma vez.

## Migrações

Qualquer alteração em `apps/*/models.py` precisa de uma migração no mesmo PR:

```bash
uv run python manage.py makemigrations
uv run python manage.py makemigrations --check --dry-run   # o que a CI roda
```

A CI falha se houver mudanças de model sem migração correspondente.

## Commits e branches

O projeto usa [Conventional Commits](https://www.conventionalcommits.org/)
(`commitizen` está configurado em `[tool.commitizen]` no `pyproject.toml` para
gerar `CHANGELOG.md` e tags `vX.Y.Z`). Prefixos comuns:

- `feat:` — nova funcionalidade
- `fix:` — correção de bug
- `docs:` — apenas documentação
- `test:` — apenas testes
- `refactor:` / `perf:` / `chore:` / `ci:`

Use `uv run cz commit` para montar a mensagem interativamente, se preferir.

Branches: crie a partir de `main` atualizada (`git pull` antes de ramificar),
com um nome descritivo (`fix/…`, `feat/…`, `docs/…`). Abra o PR contra `main`.

## O que a CI verifica

Todo PR roda `.github/workflows/pr-checks.yml`:

- **Linters**: checagem de `__init__.py`, `black --check`, `isort --check-only`,
  `autoflake --check`, `flake8`, `pip-audit`, `prettier --check`, e
  `npm run build:css` sem diferença do que foi commitado.
- **Tests**: `manage.py check`, `makemigrations --check --dry-run`, a suíte
  Django completa contra Postgres, e `coverage report --fail-under=80`.

`.github/workflows/codeql.yml` roda CodeQL (Python + JS/TS) em push/PR para
`main` e semanalmente. O Dependabot (`.github/dependabot.yml`) abre PRs de
atualização de dependências pip/npm/Actions automaticamente — revise se o
`uv.lock`/`package-lock.json` foi regenerado antes de aprovar.

Um PR só é mergeável se todos os checks acima passarem. Rode a suíte de lint
e os testes localmente antes de abrir o PR para evitar voltas.

## Documentação

Ao alterar models, views, permissões ou fluxos principais, atualize também
[CRUD.md](./CRUD.md) e [STRUCTURE.md](./STRUCTURE.md) no mesmo PR — o
checklist do PR cobra isso.
