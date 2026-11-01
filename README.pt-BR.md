# MaricaCity

[English](./README.md) | Português

MaricaCity é um site de turismo local de Maricá, cidade litorânea do estado do
Rio de Janeiro. Visitantes navegam por lugares, eventos e avaliações em
português, inglês ou espanhol. Usuários cadastrados enviam lugares, que só
entram no ar depois que um moderador aprova. Está em produção em
**[marica-city.vercel.app](https://marica-city.vercel.app)**.

Esta é a versão 2 de um projeto acadêmico. A versão 1 está arquivada como
[Marica-City-v1](https://github.com/GabrielaPeroni/Marica-City-v1); a v2 é uma
reescrita voltada a estrutura, testes, deploy e qualidade do front-end.

<!--
Capturas de tela: coloque os arquivos abaixo em docs/screenshots/ e descomente as tags.
Nomes esperados:
  docs/screenshots/landing.png          página inicial
  docs/screenshots/explore.png          /explore/ com filtros
  docs/screenshots/place-detail.png     página de um lugar (galeria, mapa, avaliações)
  docs/screenshots/admin-dashboard.png  /painel-admin/
  docs/screenshots/mobile.png           landing ou lugar em largura de celular

<p align="center">
  <img src="docs/screenshots/landing.png" alt="Página inicial" width="720">
</p>
<p>
  <img src="docs/screenshots/explore.png" alt="Página Explorar com filtros" width="360">
  <img src="docs/screenshots/place-detail.png" alt="Página de um lugar" width="360">
</p>
<p>
  <img src="docs/screenshots/admin-dashboard.png" alt="Painel administrativo" width="360">
  <img src="docs/screenshots/mobile.png" alt="Layout no celular" width="180">
</p>
-->

_Capturas de tela serão adicionadas._

## Destaques

- **Lugares com moderação.** Usuários enviam lugares com várias fotos; um
  moderador aprova, rejeita ou pede mudanças, e cada decisão fica no histórico.
  Visitantes só veem lugares aprovados.
- **Avaliações e favoritos.** Uma avaliação de 1 a 5 estrelas por usuário e
  lugar. Os favoritos mudam na hora na interface e são reconciliados com o
  servidor em segundo plano.
- **Eventos do portal da Prefeitura.** Um crawler lê as publicações públicas,
  extrai datas e locais e coloca os candidatos numa fila de triagem. A equipe
  publica ou descarta; nada vai ao ar sem revisão.
- **Três idiomas.** A interface usa os catálogos gettext do Django; o conteúdo
  cadastrado é traduzido por um LLM local e guardado junto do original.
- **Cadastro com e-mail verificado.** Um código de 6 dígitos confirma o
  endereço antes de a conta ser criada; a recuperação de senha funciona igual.
- **Painel administrativo.** Fila de aprovação e backlog, gestão de notícias e
  eventos, papéis de usuário, cartões de tendência semanal, além do Django Admin.
- **Pipeline de produção.** Linters, testes em PostgreSQL, teste de fumaça do
  contêiner e pisos de nota do Lighthouse rodam na CI; o app roda na Vercel com
  Postgres da Neon e Cloudflare R2 para as fotos.

## Stack

| Camada      | Escolha                                                                                        |
| ----------- | ---------------------------------------------------------------------------------------------- |
| Backend     | Python 3.11+, Django 5.2, django-ratelimit, django-storages, Pillow                            |
| Dados       | SQLite em desenvolvimento; PostgreSQL (Neon) em produção; cache Redis opcional                 |
| Frontend    | Templates Django, componentes django-cotton, Tailwind CSS 4 + Basecoat, ícones Lucide, Leaflet |
| JavaScript  | Scripts simples, sem bundler; ESLint                                                           |
| Entrega     | Imagem Docker (gunicorn + whitenoise), função serverless na Vercel, Cloudflare R2 para mídia   |
| Ferramentas | uv, npm, black, isort, flake8, Prettier, pre-commit, GitHub Actions, Lighthouse CI, CodeQL     |

## Arquitetura

```text
Navegador ── HTML renderizado no servidor ──────┐
   │  JS pequeno: favoritos, mapas, formulários │
   ▼                                            ▼
Função Vercel / Docker (gunicorn)       Cloudflare R2 (fotos)
   │  config.wsgi → middleware → apps
   ├── core      landing, painel admin, miniaturas, limite de requisições, tradução
   ├── accounts  User, códigos por e-mail, login, gestão de usuários
   ├── explore   Place, avaliação, favorito, aprovação, visita; API JSON de mapa e favoritos
   └── news      Notícias/eventos, EventCandidate, crawler
   │
   ├── PostgreSQL (Neon)         SQLite localmente
   └── cache (Redis ou LocMem)   códigos por e-mail, limites, consultas de miniatura
```

Cada app Django tem seus modelos, views, formulários, URLs e testes. Os
templates ficam em `templates/`, a fonte do Tailwind em `frontend/css/` e o CSS
compilado é versionado em `static/`. O mapa de diretórios está em
[docs/STRUCTURE.md](./docs/STRUCTURE.md).

## Decisões de engenharia

**Tradução de conteúdo com hash da origem.** Lugares, categorias, avaliações e
notícias guardam `translations` em JSON: `{"en": {...}, "es": {...}, "source": "<hash>"}`.
O hash cobre os campos em português, então `translate_content` (um modelo
Ollama local) só retraduz o que mudou, e os templates leem o resultado com
`{{ obj|tr:"campo" }}`, caindo para o português. O site nunca chama o modelo
durante uma requisição. Veja `apps/core/content_translation.py`.

**Crawler de eventos com triagem humana.** `apps/news/event_crawler.py` busca
publicações na API WordPress da Prefeitura, interpreta datas e locais em
português, ignora anúncios no passado e elimina duplicatas por semelhança de
título. Os resultados viram linhas `EventCandidate`; aprovar uma cria um `News`
publicado. A busca é idempotente, então pode rodar num cron diário (Vercel) ou
num agendador de 6 horas (Docker).

**Fluxo de moderação.** `Place.is_approved` começa falso. `PlaceApproval`
registra cada aprovação, rejeição ou pedido de mudanças e atualiza o lugar ao
salvar; `Place.objects.public()` é o único queryset por trás de tudo que o
visitante vê, e `place.can_edit(user)` concentra a checagem dono-ou-moderador.

**Miniaturas e prévias borradas.** Uploads nunca são servidos no tamanho
original em listas. `{{ img|srcset:"480,960" }}` gera cópias WebP de 480, 960 e
1600 px no primeiro uso e as guarda ao lado da mídia. Cada imagem também ganha
uma prévia WebP de 16 px embutida como data URI, que o navegador estica num
fundo borrado enquanto o arquivo real carrega.

**UI otimista e tratamento de falhas.** Todo `fetch` passa por um helper
`request()` com tempo limite e erros tipados (offline, timeout, limite, servidor).
Os favoritos mudam na hora, juntam cliques rápidos num único pedido e voltam
atrás com um aviso se falhar. Formulários desabilitam os botões após o primeiro
envio, uma faixa avisa quando a conexão está offline ou lenta, e imagens e mapas
quebrados viram um estado com "tentar de novo".

**Limite de requisições.** `@limit("30/m", key="user")` protege as views que
gravam ou buscam. O excesso recebe 429 com `Retry-After`: JSON para `fetch`,
página amigável para o navegador. Na Vercel o IP do cliente vem do cabeçalho do
proxy.

**CI.** Pull requests rodam linters, `pip-audit`, a checagem de que o CSS e os
ícones compilados estão atualizados e a suíte de testes em PostgreSQL 15 com
piso de 90% de cobertura. Outro workflow constrói a imagem de produção, roda
`check --deploy`, migra, espera o healthcheck do Docker, testa páginas,
`robots.txt`, `sitemap.xml` e arquivos estáticos com hash, e então roda o
Lighthouse CI (acessibilidade, boas práticas e SEO com 0,95 ou mais; desempenho
com 0,85 ou mais). Pushes em `main` publicam a imagem no GHCR com SBOM e
proveniência.

**Gerador de ilustrações impressas.** As formas botânicas, gaivotas e o skyline
das páginas são SVGs produzidos por `scripts/generate_deco.py` (curvas suaves
por pontos de controle, variação com semente). Os componentes `<c-deco>` e
`<c-wave>` os posicionam; o movimento pausa fora da tela e some com movimento
reduzido.

## Rodando localmente

Requer Python 3.11+, [uv](https://docs.astral.sh/uv/) e Node 22 (só para
recompilar o CSS).

```bash
uv sync
cp .env.example .env            # defina ao menos SECRET_KEY e GOOGLE_OAUTH_CLIENT_ID
uv run python manage.py migrate
uv run python manage.py load_demo_data   # opcional: lugares, eventos e traduções de exemplo
uv run python manage.py createsuperuser  # opcional
uv run python manage.py runserver

npm ci && npm run build:css     # só depois de mudar classes ou ícones nos templates
```

O cadastro envia um código por e-mail. Localmente, `docker compose up mailhog`
o recebe em http://localhost:8025 e a tela de código se preenche sozinha em
desenvolvimento. `docker compose up --build` roda a imagem de produção com
Postgres e Redis.

## Testes

```bash
uv run python manage.py test apps
uv run coverage run manage.py test apps && uv run coverage report
```

A suíte tem 409 testes (`apps/<app>/tests/`). A CI mede a cobertura incluindo
os arquivos de teste e exige 90%. Contando só o código da aplicação, a cobertura
de linhas é 82%.

## Deploy

A produção roda na Vercel (região `gru1`, perto do banco da Neon), com
Cloudflare R2 para as fotos. Configuração, variáveis de ambiente, o cron e as
armadilhas conhecidas estão em [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md).

## Limitações conhecidas

- **O login com Google existe só no front-end.** `static/js/components/google_auth.js`
  envia um token para `/auth/google/`, mas nenhuma view atende essa rota, então
  o botão não consegue autenticar ninguém. E-mail e senha é o único login que
  funciona.
- **Os limites de requisição são por instância sem cache compartilhado.** O
  cache padrão fica na memória; em plataforma serverless cada instância conta
  separado, e um código por e-mail pode ser recusado por uma instância diferente
  da que o emitiu. Defina `CACHE_URL` ou `REDIS_URL` para compartilhar o estado.
- **A tradução precisa de um LLM local.** `translate_content` usa o Ollama; as
  traduções automáticas são sinalizadas como tais e podem ser corrigidas no
  Django Admin.
- **O crawler de eventos depende de um único portal.** Se a Prefeitura mudar os
  IDs de categoria ou o formato das publicações, o `crawl_events` precisa ser
  ajustado.
- **As capturas de tela ainda não foram versionadas.**

## Mais documentação

[Estrutura](./docs/STRUCTURE.md) · [CRUD e permissões](./docs/CRUD.md) ·
[Contribuindo](./docs/CONTRIBUTING.md) · [Deploy (inglês)](./docs/DEPLOYMENT.md) ·
[Changelog (inglês)](./CHANGELOG.md)

## Licença

Código sob [Licença MIT](./LICENSE). As fotos vêm da Wikimedia Commons e de
colaboradores, com os créditos no rodapé do site.
