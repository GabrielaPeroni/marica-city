# Estrutura do Projeto MaricaCity

**Versão**: 0.2.0
**Django**: 5.2.7
**Python**: 3.13.3
**Última Atualização**: 2026-09-13

---

## Índice

1. [Visão Geral do Projeto](#-visão-geral-do-projeto)
2. [Estrutura Completa de Diretórios](#-estrutura-completa-de-diretórios)
3. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
4. [Aplicações Django](#-aplicações-django)
5. [Fluxo de Páginas e Navegação](#-fluxo-de-páginas-e-navegação)
6. [Fluxo de Dados e Relacionamentos](#-fluxo-de-dados-e-relacionamentos)
7. [Arquitetura Frontend](#-arquitetura-frontend)
8. [Arquitetura Backend](#-arquitetura-backend)
9. [Esquema do Banco de Dados](#-esquema-do-banco-de-dados)
10. [Autenticação e Permissões](#-autenticação-e-permissões)
11. [Endpoints da API](#-endpoints-da-api)
12. [Fluxos de Trabalho Principais](#-fluxos-de-trabalho-principais)
13. [Tecnologias e Dependências](#-tecnologias-e-dependências)

---

## 📋 Visão Geral do Projeto

MaricaCity é uma plataforma de turismo baseada em Django para a cidade de Maricá, RJ, Brasil. A plataforma permite que usuários descubram, criem e avaliem locais turísticos, além de fornecer ferramentas administrativas para moderação de conteúdo.

**Recursos Principais:**

- Locais turísticos enviados por usuários com fluxo de aprovação do administrador
- Upload de múltiplas imagens via formsets
- Sistema de avaliações e classificações (1-5 estrelas, uma avaliação por usuário por local)
- Sistema de favoritos com sincronização localStorage
- Integração com Google OAuth
- Modelo de usuário customizado com permissões baseadas em funções
- Sistema de Notícias/Eventos com categorias
- Painel administrativo com estatísticas

---

## 🗂️ Estrutura Completa de Diretórios

```
marica-city/
│
├── apps/                           # Aplicações Django
│   ├── __init__.py
│   │
│   ├── accounts/                   # Autenticação e gerenciamento de usuários
│   │   ├── __init__.py
│   │   ├── admin.py               # Configuração do admin de usuários
│   │   ├── apps.py                # Configuração da aplicação
│   │   ├── forms.py               # Formulários de usuário (registro, login)
│   │   ├── models.py              # Modelo User customizado
│   │   ├── tests.py               # Testes de contas
│   │   ├── urls.py                # Roteamento de URLs de contas
│   │   ├── views.py               # Views de autenticação e gerenciamento
│   │   └── migrations/            # Migrações do banco de dados
│   │
│   ├── core/                       # Landing, sobre, painel admin
│   │   ├── __init__.py
│   │   ├── admin.py               # Configuração do admin core
│   │   ├── apps.py                # Configuração da aplicação
│   │   ├── context_processors.py # Contexto global (OAuth, stats admin)
│   │   ├── models.py              # Vazio (sem models)
│   │   ├── tests.py               # Testes core
│   │   ├── urls.py                # Roteamento de URLs core
│   │   ├── views.py               # Views de landing, sobre, dashboard
│   │   └── migrations/            # Migrações do banco de dados
│   │
│   ├── explore/                    # CRUD de locais, avaliações, favoritos
│   │   ├── __init__.py
│   │   ├── admin.py               # Admin de Place, Category, Review
│   │   ├── api.py                 # Endpoints da API (dados do mapa, locais)
│   │   ├── apps.py                # Configuração da aplicação
│   │   ├── forms.py               # Formulários de Place, Image, Review
│   │   ├── models.py              # Models Place, Category, Review, Favorite
│   │   ├── ratelimit_handlers.py # Manipulador de erro de limite de taxa
│   │   ├── tests.py               # Testes do app explore
│   │   ├── urls.py                # Roteamento de URLs (23+ URLs)
│   │   ├── views.py               # Views CRUD, fluxo aprovação, favoritos
│   │   ├── migrations/            # Migrações do banco de dados
│   │   └── management/
│   │       └── commands/
│   │           └── populate_test_data.py  # Popular dados de teste
│   │
│   └── news/                       # Sistema de artigos e eventos
│       ├── __init__.py
│       ├── admin.py               # Configuração do admin de notícias
│       ├── apps.py                # Configuração da aplicação
│       ├── forms.py               # Formulários de notícias
│       ├── models.py              # Models News, NewsCategory
│       ├── tests.py               # Testes de notícias
│       ├── urls.py                # Roteamento de URLs de notícias
│       ├── views.py               # Views de lista e detalhe de notícias
│       ├── migrations/            # Migrações do banco de dados
│       └── management/
│           └── commands/
│               └── seed_news.py   # Popular dados de notícias
│
├── config/                         # Configurações Django
│   ├── __init__.py
│   ├── asgi.py                    # Configuração ASGI para async
│   ├── settings/                  # Pacote de settings (por ambiente)
│   │   ├── __init__.py
│   │   ├── base.py                # Configurações comuns a todos os ambientes
│   │   ├── dev.py                 # Overrides de desenvolvimento (padrão)
│   │   └── prod.py                # Overrides de produção (hardening de segurança)
│   ├── urls.py                    # Configuração de URLs raiz
│   └── wsgi.py                    # Configuração WSGI para deploy
│
├── templates/                      # Templates Django (HTML)
│   ├── base.html                  # Template base (navbar, footer, scripts)
│   │
│   ├── includes/                  # Componentes de template reutilizáveis
│   │   ├── navbar.html            # Navbar do site público
│   │   ├── admin_navbar.html     # Navbar admin (layout diferente)
│   │   ├── admin_sidebar.html    # Navegação da barra lateral admin
│   │   ├── admin_topbar.html     # Barra superior admin com stats
│   │   ├── login_dropdown.html   # Menu dropdown de login
│   │   └── remove_place_modal.html  # Modal de exclusão de local
│   │
│   ├── core/                      # Templates do app core
│   │   ├── landing.html           # Homepage com hero, locais em destaque
│   │   ├── about.html             # Página sobre Maricá
│   │   ├── admin_dashboard.html  # Dashboard de estatísticas admin
│   │   └── admin/                # Páginas específicas do admin
│   │       ├── news_list.html    # Lista de notícias admin
│   │       ├── news_form.html    # Criar/editar notícias admin
│   │       └── news_delete_confirm.html
│   │
│   ├── accounts/                  # Templates de autenticação
│   │   ├── register.html          # Registro de usuário
│   │   ├── user_management.html  # Gerenciamento de usuários admin
│   │   └── user_delete_confirm.html
│   │
│   ├── explore/                   # Templates relacionados a locais
│   │   ├── explore.html           # Listar todos os locais (com filtros)
│   │   ├── category_detail.html  # Locais por categoria
│   │   ├── place_detail.html     # Detalhe do local (imagens, reviews, mapa)
│   │   ├── place_form.html       # Criar/editar local (com formset de imagens)
│   │   ├── favorites.html         # Locais favoritos do usuário
│   │   ├── review_form.html      # Criar/editar avaliação
│   │   ├── review_delete_confirm.html
│   │   └── admin/                # Páginas de aprovação admin
│   │       ├── approval_queue.html  # Locais pendentes
│   │       └── backlog.html         # Todos os locais com filtros
│   │
│   └── news/                      # Templates de notícias
│       ├── news_list.html         # Listar notícias/eventos
│       └── news_detail.html       # Detalhe da notícia/evento
│
├── static/                         # Arquivos estáticos (CSS, JS, imagens)
│   ├── css/
│   │   ├── src/app.css            # Fonte Tailwind + Basecoat (tokens); npm run build:css
│   │   ├── app.css                # CSS compilado (commitado)
│   │   ├── components/            # Estilos específicos de componentes
│   │   │   ├── admin_sidebar.css
│   │   │   ├── admin_topbar.css
│   │   │   └── bulk_select.css
│   │   └── pages/                 # Estilos específicos de páginas
│   │       ├── admin.css
│   │       ├── explore.css
│   │       ├── landing.css
│   │       └── place_form.css
│   │
│   ├── js/
│   │   ├── utils.js               # Funções utilitárias
│   │   ├── google_auth.js         # Integração Google OAuth
│   │   ├── login.js               # Lógica da página de login
│   │   ├── landing.js             # Interações da landing page
│   │   ├── landing_map.js         # Google Map da landing page
│   │   ├── place_detail.js        # Interações do detalhe do local
│   │   ├── place_form.js          # Manipulação do formulário de local
│   │   ├── favorites-service.js   # Lógica backend de favoritos
│   │   ├── favorites-ui.js        # Atualizações de UI de favoritos
│   │   └── components/            # Componentes JS reutilizáveis
│   │       ├── address_autocomplete.js  # Autocomplete Google Places
│   │       ├── place_map.js       # Mapa do detalhe do local
│   │       ├── toasts.js          # Notificações toast
│   │       └── user_management.js # Gerenciamento de usuários admin
│   │
│   └── images/                    # Imagens estáticas
│       └── hero/                  # Imagens do carrossel hero
│
├── media/                          # Arquivos enviados por usuários
│   └── places/
│       └── images/                # Imagens de locais (organizadas por data)
│
├── staticfiles/                    # Arquivos estáticos coletados (produção)
│
├── deploy/
│   └── mock-cloudflare/
│       └── Caddyfile              # Proxy Caddy local (perfil docker-compose opcional) para testar o path HTTPS/HSTS sem Cloudflare real
│
├── docs/                   # Documentação do projeto
│   ├── CRUD.md                    # Documentação detalhada CRUD
│   ├── STRUCTURE.md               # Este arquivo - Estrutura completa
│   ├── CONTRIBUTING.md            # Guia de contribuição (setup, testes, lint, workflow de PR)
│   ├── DEPLOYMENT.md              # Runbook de deploy (Docker, Cloudflare, docker-compose)
│   ├── IMPROVEMENT_PLAN.md        # Plano mestre de polimento (histórico de PRs)
│   └── LICENSE.txt                # Informações de licença
│
├── .github/
│   ├── workflows/
│   │   ├── pr-checks.yml          # Lint (black/isort/autoflake/flake8/prettier) + pip-audit + testes + coverage gate
│   │   └── codeql.yml             # CodeQL (python + javascript-typescript), agendado semanalmente
│   ├── dependabot.yml             # Atualizações automáticas de dependências (pip + npm + actions)
│   ├── PULL_REQUEST_TEMPLATE.md   # Checklist de PR
│   └── check_innit.py             # Verificação customizada de arquivos __init__.py
│
├── manage.py                       # Script de gerenciamento Django
├── pyproject.toml                  # Dependências (uv) e config de ferramentas (inclui [tool.commitizen])
├── uv.lock                         # Versões de dependências travadas
├── package.json                    # Dependências JS (ESLint + esbuild) para lint/bundle de static/js
├── eslint.config.js                # Configuração do ESLint
├── scripts/
│   └── build-js.mjs                # Bundler esbuild para os entrypoints de static/js
├── Dockerfile                       # Build multi-stage (uv → venv, collectstatic, gunicorn+whitenoise, usuário não-root)
├── docker-compose.yml               # Stack local: app + postgres + redis (+ perfil opcional mock-cloudflare/Caddy)
├── .dockerignore
├── db.sqlite3                      # Banco de dados SQLite (desenvolvimento, não versionado)
├── .env.example                    # Modelo de variáveis de ambiente (copiar para .env)
├── .env                            # Variáveis de ambiente (não versionado)
├── CHANGELOG.md                    # Gerado/atualizado via commitizen (Keep a Changelog)
├── .gitignore                      # Regras de ignore do Git
├── .pre-commit-config.yaml        # Configuração de hooks pre-commit
└── README.md                       # Visão geral do projeto
```

---

## 🏗️ Visão Geral da Arquitetura

MaricaCity segue o padrão **MVT (Model-View-Template)** do Django com uma arquitetura modular baseada em apps.

### Camadas da Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                      CAMADA DE APRESENTAÇÃO                  │
│  Templates (HTML) + Arquivos Estáticos (CSS, JS) + Frontend │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     CAMADA DE APLICAÇÃO                      │
│     Views (Manipulação de Requisições) + Forms (Validação)  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      LÓGICA DE NEGÓCIO                       │
│   Models (Estrutura de Dados) + Permissões + Workflows      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                       CAMADA DE DADOS                        │
│        Banco de Dados (SQLite/PostgreSQL) + Arquivos Media  │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Requisição

```
1. Usuário visita URL (ex: /explore/place/42/)
   ↓
2. URLconf do Django corresponde ao padrão de URL (config/urls.py → apps/explore/urls.py)
   ↓
3. Função view é chamada (apps/explore/views.py:place_detail_view)
   ↓
4. View recupera dados dos models (Place.objects.get(pk=42))
   ↓
5. View aplica lógica de negócio (permissões, cálculos)
   ↓
6. View renderiza template com contexto (templates/explore/place_detail.html)
   ↓
7. Template renderiza HTML usando dados do contexto
   ↓
8. Resposta HTML enviada ao navegador do usuário
   ↓
9. Navegador carrega arquivos estáticos (CSS, JS) e executa lógica frontend
```

---

## 📦 Aplicações Django

### Visão Geral

| App          | Propósito                                | Models | Views | Templates | Recursos Principais                                 |
| ------------ | ---------------------------------------- | ------ | ----- | --------- | --------------------------------------------------- |
| **accounts** | Autenticação e gerenciamento de usuários | User   | 7     | 3         | Google OAuth, gerenciamento de usuários             |
| **core**     | Páginas gerais do site                   | Nenhum | 3     | 6         | Landing, sobre, painel admin                        |
| **explore**  | Locais, avaliações, favoritos            | 6      | 20+   | 9         | CRUD, fluxo de aprovação, favoritos                 |
| **news**     | Artigos de notícias e eventos            | 2      | 2     | 2         | Listagem de notícias, rastreamento de visualizações |

---

### 1. App Accounts - Autenticação e Gerenciamento de Usuários

**Propósito:** Gerenciar registro de usuários, autenticação, Google OAuth e gerenciamento de usuários admin.

**Models:**

- `User` (apps/accounts/models.py)
  - Usuário customizado estendendo AbstractUser
  - Campos: bio, contact_phone, contact_email, contact_website
  - Propriedades: `can_create_places` (todos autenticados), `can_moderate` (apenas staff/superuser)

**Views:**

- `register_view` - Registro de usuário
- `login_view` - Login (suporta Google OAuth)
- `logout_view` - Logout
- `user_management_view` - Listar todos os usuários (apenas admin)
- `user_update_type_view` - Atualizar permissões de usuário (apenas admin)
- `user_toggle_status_view` - Ativar/desativar usuário (apenas admin)
- `user_delete_view` - Excluir usuário (apenas admin)

**Templates:**

- `accounts/register.html` - Formulário de registro
- `accounts/user_management.html` - Lista de usuários admin com filtros
- `accounts/user_delete_confirm.html` - Confirmação de exclusão

**Recursos Principais:**

- Integração com Google OAuth via `google_auth.js`
- Permissões baseadas em função (usuário regular vs admin/staff)
- Admin pode gerenciar todos os usuários (ativar, desativar, excluir, alterar permissões)

---

### 2. App Core - Landing Page e Páginas Gerais do Site

**Propósito:** Fornecer páginas gerais do site que não pertencem a recursos específicos.

**Models:** Nenhum (models.py vazio)

**Views:**

- `landing_view` - Homepage com carrossel hero, locais em destaque, categorias, mapa
- `about_view` - Página sobre Maricá
- `admin_dashboard_view` - Dashboard de estatísticas admin (apenas admin)

**Templates:**

- `core/landing.html` - Homepage com carrossel hero, locais em destaque, Google Map
- `core/about.html` - Página sobre
- `core/admin_dashboard.html` - Dashboard admin com estatísticas
- `core/admin/news_list.html` - Gerenciamento de notícias admin
- `core/admin/news_form.html` - Criar/editar notícias admin
- `core/admin/news_delete_confirm.html` - Exclusão de notícias admin

**Recursos Principais:**

- Carrossel hero com Swiper.js
- Seção de locais em destaque (maior classificação)
- Visão geral de categorias com ícones
- Google Map interativo mostrando todos os locais
- Dashboard admin com contagem de aprovações pendentes, rascunhos de notícias, estatísticas de usuários

**Context Processors (apps/core/context_processors.py):**

- `google_oauth` - Injeta `GOOGLE_OAUTH_CLIENT_ID` para templates
- `admin_stats` - Injeta contagens de `pending_places` e `draft_news` para badges da barra lateral admin

---

### 3. App Explore - Locais, Avaliações e Favoritos

**Propósito:** Funcionalidade principal da plataforma de turismo - descoberta de locais, criação, avaliações e favoritos.

**Models:**

- `Category` - Categorias de turismo (Restaurantes, Artes e Cultura, Natureza, Hotéis, etc.)
- `Place` - Locais turísticos com fluxo de aprovação
- `PlaceImage` - Múltiplas imagens por local (uma principal)
- `PlaceApproval` - Histórico do fluxo de aprovação
- `PlaceReview` - Avaliações de usuários (1-5 estrelas, uma por usuário por local)
- `Favorite` - Favoritos de usuários

**Views (20+ views):**

**Views Públicas:**

- `explore_view` - Listar todos os locais aprovados com busca e filtros de categoria
- `category_detail_view` - Listar locais por categoria com ordenação
- `place_detail_view` - Visualização detalhada do local com imagens, avaliações, mapa

**CRUD de Local:**

- `place_create_view` - Criar novo local (autenticado, limite de taxa: 5/hora)
- `place_update_view` - Editar local (proprietário/admin, limite de taxa: 10/hora)
- `place_delete_view` - Excluir local (proprietário/admin)

**CRUD de Avaliação:**

- `review_create_view` - Criar avaliação (autenticado, uma por local)
- `review_edit_view` - Editar avaliação (proprietário/admin)
- `review_delete_view` - Excluir avaliação (proprietário/admin)

**Favoritos:**

- `favorites_list_view` - Listar favoritos do usuário
- `toggle_favorite_view` - Endpoint AJAX para adicionar/remover favoritos
- `sync_favorites_view` - Sincronizar favoritos do localStorage com backend
- `favorites_api_list_view` - Endpoint API para IDs de favoritos do usuário

**Aprovação Admin:**

- `approval_queue_view` - Listar locais pendentes (apenas admin)
- `approve_place_view` - Aprovar local (apenas admin)
- `reject_place_view` - Rejeitar local com motivo (apenas admin)
- `backlog_view` - Listar todos os locais com filtros (apenas admin)

**Endpoints da API:**

- `map_data_api` - Endpoint JSON para marcadores do mapa (com limite de taxa)
- `places_by_ids_api` - Endpoint JSON para buscar locais por IDs

**Templates:**

- `explore/explore.html` - Visualização de lista com filtros e busca
- `explore/category_detail.html` - Lista filtrada por categoria
- `explore/place_detail.html` - Detalhe do local com galeria, avaliações, mapa
- `explore/place_form.html` - Criar/editar local com formset de imagens
- `explore/favorites.html` - Locais favoritos do usuário
- `explore/review_form.html` - Criar/editar avaliação
- `explore/review_delete_confirm.html` - Confirmação de exclusão de avaliação
- `explore/admin/approval_queue.html` - Locais pendentes para aprovação
- `explore/admin/backlog.html` - Todos os locais com filtros

**Recursos Principais:**

- **Fluxo de aprovação de local:** Usuários criam locais (is_approved=False) → Admin revisa → Locais aprovados visíveis para todos
- **Upload de múltiplas imagens:** Formset inline para múltiplas imagens, uma marcada como principal
- **Sistema de avaliação:** Classificações de 5 estrelas, uma avaliação por usuário por local, restrição única aplicada
- **Favoritos:** Toggle AJAX, sincronização localStorage para usuários anônimos, persistência backend para autenticados
- **Mapas:** Leaflet + OpenStreetMap no detalhe e na landing page; autocomplete de endereço pelo Google Places (só com `GOOGLE_MAPS_API_KEY`)
- **Limite de taxa:** Criar (5/hora), Atualizar (10/hora), API do Mapa (configurado)

---

### 4. App News - Sistema de Artigos de Notícias e Eventos

**Propósito:** Publicar notícias, eventos e anúncios sobre Maricá.

**Models:**

- `NewsCategory` - Três categorias padrão: Noticias (📰), Evento (📅), Anuncios (📢)
- `News` - Artigos de notícias e eventos com status (DRAFT, PUBLISHED, ARCHIVED)

**Views:**

- `news_list_view` - Listar todas as notícias/eventos publicados com filtros de categoria e data
- `news_detail_view` - Mostrar notícia/evento detalhado, incrementar contagem de visualizações

**Templates:**

- `news/news_list.html` - Visualização de lista com filtros
- `news/news_detail.html` - Visualização de detalhes com metadados

**Recursos Principais:**

- **Tipos de conteúdo:** Notícias regulares e eventos (com campos específicos de evento)
- **Fluxo de status:** DRAFT → PUBLISHED → ARCHIVED
- **Auto-publicação:** `publish_date` automaticamente definido quando status muda para PUBLISHED
- **Rastreamento de visualizações:** Método `increment_view_count()` rastreia visualizações
- **Propriedades:** `is_event`, `is_upcoming_event`, `is_past_event`
- **Gerenciado por admin:** Sem criação/atualização pública, gerenciado via admin Django ou views admin customizadas

---

## 🔀 Fluxo de Páginas e Navegação

### Mapa de Jornada do Usuário

```
┌─────────────────────────────────────────────────────────────┐
│                    LANDING PAGE (/)                          │
│  Carrossel Hero │ Locais Destaque │ Categorias │ Google Map │
└───────┬──────────────────┬──────────────────┬───────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐
│  Página Sobre │  │ Página Explore│  │  Página Notícias/     │
│   (/sobre/)   │  │  (/explore/)  │  │    Eventos (/news/)   │
└───────────────┘  └───────┬───────┘  └───────┬───────────────┘
                           │                  │
        ┌──────────────────┼──────────────────┘
        │                  │
        ▼                  ▼
┌───────────────┐  ┌───────────────────┐
│  Página de    │  │  Detalhe Notícia  │
│  Categoria    │  │   (/news/<slug>/) │
└───────┬───────┘  └───────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│       PÁGINA DETALHE DO LOCAL             │
│  Imagens │ Reviews │ Mapa │ Botão Favorito│
└───────┬───────────────────────────────────┘
        │
        ├────► Login Necessário ────┐
        │                           │
        ▼                           ▼
┌───────────────┐      ┌──────────────────┐
│ Escrever      │      │  Criar Local     │
│ Avaliação     │      │  (/explore/      │
│               │      │   place/create/) │
└───────────────┘      └──────────┬───────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │  Local Pendente      │
                       │  (is_approved=False) │
                       └──────────┬───────────┘
                                  │
                Apenas Admin ─────┤
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │  Fila de Aprovação   │
                       │  (/explore/admin/    │
                       │   approval-queue/)   │
                       └──────────┬───────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    ▼                            ▼
            ┌───────────────┐          ┌─────────────────┐
            │  Aprovar      │          │  Rejeitar       │
            │  (Visível     │          │  (Oculto do     │
            │   para todos) │          │   site público) │
            └───────────────┘          └─────────────────┘
```

### Estrutura de Navegação

**Navegação Pública (navbar.html):**

```
Home (/) → Explore (/explore/) → Notícias (/news/) → Sobre (/sobre/)
                ↓
         Filtro Categoria
                ↓
         Detalhe Local
                ↓
         [Login Necessário: Avaliar, Favoritar, Criar Local]
```

**Navegação Admin (admin_navbar.html + admin_sidebar.html):**

```
Dashboard Admin (/painel-admin/)
    ├── Fila de Aprovação (/explore/admin/approval-queue/) [Badge: contagem pendentes]
    ├── Backlog (/explore/admin/backlog/)
    ├── Gerenciamento Notícias (/painel-admin/news/) [Badge: contagem rascunhos]
    └── Gerenciamento Usuários (/accounts/usuarios/)
```

---

## 🔗 Fluxo de Dados e Relacionamentos

### Diagrama Completo de Fluxo de Dados

```
┌──────────────────────────────────────────────────────────────────┐
│                            USER                                   │
│  (Modelo User Customizado - apps/accounts/models.py)             │
│  Propriedades: can_create_places, can_moderate                   │
└──────┬───────────────────────────────┬───────────────────────────┘
       │ created_by (FK)               │ user (FK)
       │                               │
       ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│      PLACE       │          │   PLACEREVIEW    │
│  (is_approved)   │◄─────────┤ (classificação   │
└────┬─────────────┘ place    │     1-5)         │
     │              (FK)      └──────────────────┘
     │
     ├─────────────► PLACEIMAGE (FK: place) [Múltiplas imagens, uma principal]
     │
     ├─────────────► PLACEAPPROVAL (FK: place) [Histórico de aprovação]
     │                    │
     │                    └─────► USER (FK: reviewer)
     │
     ├────────────◄► CATEGORY (M2M) [Múltiplas categorias por local]
     │
     └─────────────► FAVORITE (FK: place, FK: user) [Favoritos do usuário]


┌──────────────────────────────────────────────────────────────────┐
│                          NEWS                                     │
│  (apps/news/models.py)                                            │
│  Campos: status, publish_date, event_date, view_count            │
└──────┬───────────────────────────────────────────────────────────┘
       │ category (FK)
       │
       ▼
┌──────────────────┐
│  NEWSCATEGORY    │  [3 padrão: Noticias, Evento, Anuncios]
└──────────────────┘
```

### Matriz de Relacionamentos dos Models

| Model     | Relacionado Com | Tipo de Relacionamento          | Acessor Reverso                    |
| --------- | --------------- | ------------------------------- | ---------------------------------- |
| **User**  | Place           | Um-para-Muitos (created_by)     | `user.places.all()`                |
| **User**  | PlaceReview     | Um-para-Muitos (user)           | `user.place_reviews_written.all()` |
| **User**  | Favorite        | Um-para-Muitos (user)           | `user.favorites.all()`             |
| **User**  | PlaceApproval   | Um-para-Muitos (reviewer)       | `user.place_reviews.all()`         |
| **User**  | News            | Um-para-Muitos (author)         | `user.news_items.all()`            |
| **Place** | PlaceImage      | Um-para-Muitos (place)          | `place.images.all()`               |
| **Place** | PlaceReview     | Um-para-Muitos (place)          | `place.reviews.all()`              |
| **Place** | Favorite        | Um-para-Muitos (place)          | `place.favorited_by.all()`         |
| **Place** | PlaceApproval   | Um-para-Muitos (place)          | `place.approval_history.all()`     |
| **Place** | Category        | Muitos-para-Muitos (categories) | `category.places.all()`            |
| **News**  | NewsCategory    | Muitos-para-Um (category)       | `category.news_items.all()`        |

### Restrições e Validações

**Restrições Únicas:**

- `PlaceReview`: unique_together (place, user) - Uma avaliação por usuário por local
- `Favorite`: unique_together (user, place) - Um registro de favorito por usuário por local

**Regras Auto-aplicadas:**

- `PlaceImage`: Apenas uma imagem pode ter `is_primary=True` por local (aplicado no método save)
- `Place`: Novos locais padrão para `is_approved=False` (requer aprovação do admin)
- `News`: `publish_date` auto-definido quando status muda para PUBLISHED

---

## 🎨 Arquitetura Frontend

### Organização de Arquivos Estáticos

```
static/
├── css/
│   ├── src/app.css                 # Fonte: Tailwind v4 + Basecoat, tokens e @theme
│   ├── app.css                     # Compilado por npm run build:css (commitado)
│   ├── components/                 # Estilos de componentes reutilizáveis
│   │   ├── admin_sidebar.css      # Navegação da barra lateral admin
│   │   ├── admin_topbar.css       # Barra superior admin com badges de stats
│   │   └── bulk_select.css        # Barra de seleção em massa
│   └── pages/                      # Estilos específicos de páginas
│       ├── admin.css              # Estilos do dashboard admin
│       ├── explore.css            # Grid e filtros da página explore
│       ├── landing.css            # Hero e seções da landing page
│       └── place_form.css         # Formulário de local e formset de imagens
│
├── js/
│   ├── utils.js                    # Funções utilitárias (getCookie, showToast)
│   ├── google_auth.js              # Inicialização Google OAuth
│   ├── login.js                    # Lógica da página de login
│   ├── landing.js                  # Interações da landing page
│   ├── landing_map.js              # Google Map na landing page
│   ├── place_detail.js             # Galeria e interações do detalhe do local
│   ├── place_form.js               # Manipulação do formulário de local e formset
│   ├── favorites-service.js        # Chamadas de API backend de favoritos
│   ├── favorites-ui.js             # Atualizações de UI de favoritos
│   └── components/                 # Componentes JS reutilizáveis
│       ├── address_autocomplete.js # Autocomplete Google Places
│       ├── place_map.js            # Google Map do detalhe do local
│       ├── toasts.js               # Sistema de notificações toast
│       └── user_management.js      # Gerenciamento de usuários admin AJAX
│
└── images/
    └── hero/                        # Imagens do carrossel hero
```

### Arquitetura JavaScript

**Componentes Principais:**

1. **Sistema de Favoritos (favorites-service.js + favorites-ui.js)**

   - `favorites-service.js`: Chamadas de API, sincronização localStorage, comunicação backend
   - `favorites-ui.js`: Atualizações de UI, alternância de ícone de coração, renderização de página de favoritos
   - Fluxo: Clique no coração → Alternar localStorage → Chamada AJAX → Atualizar UI → Sincronizar com backend

2. **Mapas**

   - `landing_map.js`: Leaflet com todos os locais aprovados na landing page
   - `components/place_map.js`: Leaflet com o local na página de detalhe
   - `components/address_autocomplete.js`: Autocomplete Google Places no formulário de local

3. **Notificações Toast (toasts.js)**

   - Sistema global de toast usando o toast do Basecoat
   - Chamado via `showToast(message, type)` de qualquer página

4. **Formulário de Local (place_form.js)**

   - Manipula formset de imagens (adicionar/remover imagens)
   - Integração com autocomplete Google Maps
   - Seleção de imagem principal

5. **Gerenciamento de Usuários (user_management.js)**
   - Chamadas AJAX para atualizações de tipo de usuário, alternância de status, exclusões
   - Atualizações de UI em tempo real sem recarregar página

---

## 🔧 Arquitetura Backend

### Configuração de Settings (config/settings/)

As configurações estão divididas em um pacote por ambiente, em vez de um
único `settings.py`:

- **`base.py`** — tudo que é comum aos dois ambientes: apps instalados,
  middleware, templates, banco de dados, validadores de senha,
  `CACHES` (configurável via `CACHE_URL`/`REDIS_URL`, com fallback para
  `LocMemCache`) e o esqueleto de `LOGGING` (console/stdout).
- **`dev.py`** — importa de `base.py`; `DEBUG=True` por padrão, hosts
  permissivos (`localhost,127.0.0.1,0.0.0.0`), sem exigir HTTPS. É o módulo
  usado por padrão (`manage.py`, `wsgi.py`, `asgi.py` e o CI de testes).
- **`prod.py`** — importa de `base.py`; ativa o hardening de segurança
  (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` para funcionar atrás de um
  proxy/CDN como o Cloudflare, `SECURE_CONTENT_TYPE_NOSNIFF`) e usa um
  formatter de log estruturado (`key=value`) mais adequado a coletores de
  log de containers. Ativado definindo
  `DJANGO_SETTINGS_MODULE=config.settings.prod` no ambiente de deploy.

**Configurações Principais:**

```python
# Modelo de usuário customizado
AUTH_USER_MODEL = 'accounts.User'

# Apps instalados
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.core',
    'apps.accounts',
    'apps.explore',
    'apps.news',
]

# Context processors
TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                # ... processadores padrão
                'apps.core.context_processors.google_oauth',
                'apps.core.context_processors.admin_stats',
            ],
        },
    },
]

# Arquivos estáticos e de mídia
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Limitação de taxa
RATELIMIT_ENABLE = True  # Desabilitar nos testes
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### Estrutura de Roteamento de URLs

```
config/urls.py (URLconf Raiz)
    ├── healthz/                → health_view (JSON, sem auth, checa DB)
    ├── admin/                  → Django Admin
    ├── accounts/               → apps.accounts.urls
    ├── explore/                → apps.explore.urls
    ├── news/                   → apps.news.urls
    └── /                       → apps.core.urls

apps/accounts/urls.py
    ├── register/               → register_view
    ├── login/                  → login_view
    ├── logout/                 → logout_view
    ├── usuarios/               → user_management_view (admin)
    ├── usuarios/<id>/tipo/     → user_update_type_view (admin)
    ├── usuarios/<id>/status/   → user_toggle_status_view (admin)
    └── usuarios/<id>/excluir/  → user_delete_view (admin)

apps/core/urls.py
    ├── /                       → landing_view
    ├── sobre/                  → about_view
    └── painel-admin/           → admin_dashboard_view (admin)

apps/explore/urls.py (23+ URLs)
    ├── /                       → explore_view
    ├── api/map-data/           → map_data_api (JSON)
    ├── api/places-by-ids/      → places_by_ids_api (JSON)
    ├── category/<slug>/        → category_detail_view
    ├── place/<pk>/             → place_detail_view
    ├── place/create/           → place_create_view
    ├── place/<pk>/edit/        → place_update_view
    ├── place/<pk>/delete/      → place_delete_view
    ├── place/<pk>/review/create/ → review_create_view
    ├── review/<pk>/edit/       → review_edit_view
    ├── review/<pk>/delete/     → review_delete_view
    ├── place/<pk>/favorite/toggle/ → toggle_favorite_view (AJAX)
    ├── favorites/              → favorites_list_view
    ├── favorites/sync/         → sync_favorites_view (AJAX)
    ├── favorites/list/         → favorites_api_list_view (API)
    ├── admin/approval-queue/   → approval_queue_view (admin)
    ├── admin/place/<pk>/approve/ → approve_place_view (admin)
    ├── admin/place/<pk>/reject/ → reject_place_view (admin)
    └── admin/backlog/          → backlog_view (admin)

apps/news/urls.py
    ├── /                       → news_list_view
    └── <slug>/                 → news_detail_view
```

### Formulários e Validação

**Formulários Principais:**

1. **PlaceForm (apps/explore/forms.py)**

   - ModelForm para Place
   - Widget de autocomplete Google Maps para endereço
   - Manipula relacionamento M2M com categorias

2. **PlaceImageFormSet (apps/explore/forms.py)**

   - Formset inline para PlaceImage
   - `can_delete=True`, `extra=3`
   - Permite múltiplos uploads de imagens em um formulário

3. **PlaceReviewForm (apps/explore/forms.py)**

   - ModelForm para PlaceReview
   - Opções de classificação (1-5 estrelas)
   - Comprimento máximo de comentário 1000 caracteres
   - Restrição única validada no nível do model

4. **Formulários de Registro/Login de Usuário (apps/accounts/forms.py)**
   - Formulário de registro customizado
   - Formulário de login com opção Google OAuth

---

## 🗄️ Esquema do Banco de Dados

### Índices do Banco de Dados

**Otimizado para Consultas Comuns:**

```python
# Model Place
indexes = [
    Index(fields=['is_approved', 'is_active']),  # Filtrar aprovado/ativo
    Index(fields=['-created_at']),               # Ordenar por mais recente
]

# Model PlaceImage
indexes = [
    Index(fields=['place', 'display_order']),    # Galeria ordenada
    Index(fields=['place', 'is_primary']),       # Busca de imagem principal
]

# Model PlaceApproval
indexes = [
    Index(fields=['place', '-reviewed_at']),     # Histórico de aprovação
    Index(fields=['reviewer', '-reviewed_at']),  # Ações do revisor
    Index(fields=['action']),                    # Filtrar por tipo de ação
]

# Model PlaceReview
indexes = [
    Index(fields=['place', '-created_at']),      # Avaliações do local
    Index(fields=['user', '-created_at']),       # Avaliações do usuário
    Index(fields=['rating']),                    # Filtrar por classificação
]

# Model Favorite
indexes = [
    Index(fields=['user', '-created_at']),       # Favoritos do usuário
    Index(fields=['place']),                     # Contagem de favoritos do local
]

# Model Category
indexes = [
    Index(fields=['is_active', 'display_order']), # Categorias ativas ordenadas
    Index(fields=['slug']),                       # Busca de URL
]

# Model News
indexes = [
    Index(fields=['status', '-publish_date']),   # Notícias publicadas
    Index(fields=['category', 'status']),        # Filtro de categoria
    Index(fields=['slug']),                      # Busca de URL
    Index(fields=['-publish_date']),             # Ordenar por mais recente
]
```

---

## 🔐 Autenticação e Permissões

### Matriz de Permissões

| Recurso                 | Anônimo | Autenticado      | Admin/Staff |
| ----------------------- | ------- | ---------------- | ----------- |
| Ver Locais Aprovados    | ✅      | ✅               | ✅          |
| Ver Locais Pendentes    | ❌      | Apenas próprios  | ✅ Todos    |
| Avaliar Locais          | ❌      | ✅ (1 por local) | ✅          |
| Favoritar Locais        | ✅\*    | ✅               | ✅          |
| Criar Locais            | ❌      | ✅ (limitado)    | ✅          |
| Editar Próprios Locais  | ❌      | ✅               | ✅          |
| Editar Qualquer Local   | ❌      | ❌               | ✅          |
| Excluir Próprios Locais | ❌      | ✅               | ✅          |
| Excluir Qualquer Local  | ❌      | ❌               | ✅          |
| Aprovar/Rejeitar Locais | ❌      | ❌               | ✅          |
| Acessar Dashboard Admin | ❌      | ❌               | ✅          |
| Gerenciar Usuários      | ❌      | ❌               | ✅          |
| Gerenciar Notícias      | ❌      | ❌               | ✅          |

\*Usuários anônimos podem favoritar via localStorage (apenas lado do cliente, não sincronizado com backend)

### Implementação de Permissões

**Propriedades do Model User (apps/accounts/models.py):**

```python
@property
def can_create_places(self):
    return self.is_authenticated  # Todos os usuários autenticados

@property
def can_moderate(self):
    return self.is_staff or self.is_superuser  # Apenas admin/staff
```

**Decoradores em Nível de View:**

```python
from django.contrib.auth.decorators import login_required, user_passes_test

@login_required  # Requer autenticação
def place_create_view(request):
    ...

@user_passes_test(lambda u: u.can_moderate)  # Requer admin/staff
def approval_queue_view(request):
    ...
```

---

## 🔌 Endpoints da API

### Endpoints JSON tipo REST

| Endpoint                               | Método | Propósito                                    | Limitado | Auth Necessária |
| -------------------------------------- | ------ | -------------------------------------------- | -------- | --------------- |
| `/explore/api/map-data/`               | GET    | Obter todos os marcadores de local para mapa | ✅ Sim   | ❌ Não          |
| `/explore/api/places-by-ids/`          | POST   | Obter locais por IDs                         | ❌ Não   | ❌ Não          |
| `/explore/place/<pk>/favorite/toggle/` | POST   | Alternar favorito                            | ❌ Não   | ✅ Sim          |
| `/explore/favorites/sync/`             | POST   | Sincronizar favoritos localStorage           | ❌ Não   | ✅ Sim          |
| `/explore/favorites/list/`             | GET    | Obter IDs de favoritos do usuário            | ❌ Não   | ✅ Sim          |

### Formatos de Resposta da API

**Resposta toggle_favorite_view:**

```json
{
  "success": true,
  "is_favorited": true,
  "favorites_count": 5,
  "message": "Adicionado aos favoritos"
}
```

**Resposta sync_favorites_view:**

```json
{
  "success": true,
  "favorites": [1, 2, 3, 5, 8],
  "added": 2,
  "message": "Sincronizados 2 novos favoritos"
}
```

**Resposta favorites_api_list_view:**

```json
{
  "success": true,
  "favorites": [1, 2, 3, 5, 8],
  "count": 5
}
```

**Resposta map_data_api:**

```json
[
    {
        "id": 1,
        "name": "Nome do Local",
        "latitude": -22.9194,
        "longitude": -42.8189,
        "category": "Restaurante",
        "rating": 4.5
    },
    ...
]
```

---

## 🔄 Fluxos de Trabalho Principais

### 1. Fluxo de Criação e Aprovação de Local

```
┌─────────────────────────────────────────────────────────┐
│ 1. Usuário clica em "Criar Local" na página Explore    │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Formulário de local carregado com formset de imagens│
│    - Autocomplete Google Maps para endereço            │
│    - Seleção de categoria (M2M)                        │
│    - Uploads de múltiplas imagens (PlaceImageFormSet)  │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Usuário envia formulário                            │
│    - Place.is_approved = False (padrão)                │
│    - Place.created_by = usuário atual                  │
│    - Imagens salvas com display_order                  │
│    - Primeira imagem marcada como principal se não     │
│      especificado                                      │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Local salvo, registro PlaceApproval auto-criado     │
│    - Status: PENDING                                    │
│    - Local não visível no site público                 │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Admin recebe notificação (badge pending_places)     │
│    - Admin navega para Fila de Aprovação               │
│    - Revisa detalhes do local                          │
└────────────────────┬────────────────────────────────────┘
                     ▼
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  APROVAR         │    │  REJEITAR            │
│  - is_approved   │    │  - is_approved =     │
│    = True        │    │    False             │
│  - Visível para  │    │  - is_active = False │
│    todos         │    │  - Motivo de rejeição│
│  - Registro      │    │    salvo             │
│    PlaceApproval │    │  - Registro          │
│    criado        │    │    PlaceApproval     │
│                  │    │    criado            │
└──────────────────┘    └──────────────────────┘
```

### 2. Fluxo de Envio de Avaliação

```
┌─────────────────────────────────────────────────────────┐
│ 1. Usuário visita página de Detalhe do Local           │
│    - Vê avaliações existentes                          │
│    - Clica no botão "Escrever Avaliação"               │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Verificar se usuário já avaliou                     │
│    - Query: PlaceReview.objects.filter(place, user)    │
└────────────────────┬────────────────────────────────────┘
                     ▼
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  Já Avaliou      │    │  Ainda Não Avaliou   │
│  - Redirecionar  │    │  - Mostrar formulário│
│    para editar   │    │    de avaliação      │
│    avaliação     │    │  - Classificação: 1-5│
│                  │    │    estrelas          │
│                  │    │  - Campo comentário  │
└──────────────────┘    └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │ 3. Usuário envia     │
                        │    avaliação         │
                        └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │ 4. Validação         │
                        │    - Verificação     │
                        │      única           │
                        │    - Classificação   │
                        │      1-5             │
                        │    - Comprimento     │
                        │      comentário      │
                        └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │ 5. Salvar avaliação  │
                        │    - Atualizar       │
                        │      average_rating  │
                        │      do local        │
                        │    - Redirecionar    │
                        │      para detalhe    │
                        │      do local        │
                        └──────────────────────┘
```

### 3. Fluxo de Favoritos (com Sincronização localStorage)

```
┌─────────────────────────────────────────────────────────┐
│ 1. Usuário clica no ícone de coração no card do local  │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Verificar autenticação                               │
└────────────────────┬────────────────────────────────────┘
                     ▼
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  Anônimo         │    │  Autenticado         │
│  - Alternar em   │    │  - Chamada AJAX para │
│    localStorage  │    │    toggle_favorite   │
│  - Atualizar UI  │    │  - Backend cria/     │
│  - Sem           │    │    exclui Favorite   │
│    persistência  │    │  - Retorna JSON      │
│    backend       │    │                      │
└──────────────────┘    └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │ 3. Atualizar UI      │
                        │    - Preencher/      │
                        │      esvaziar ícone  │
                        │      de coração      │
                        │    - Mostrar         │
                        │      notificação     │
                        │      toast           │
                        └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │ 4. Usuário faz login │
                        │    depois (se anon)  │
                        │    - Auto-sincroniza │
                        │      localStorage    │
                        │      para backend via│
                        │      sync_favorites  │
                        └──────────────────────┘
```

### 4. Fluxo da Fila de Aprovação Admin

```
┌─────────────────────────────────────────────────────────┐
│ 1. Admin visita Fila de Aprovação                      │
│    - Badge mostra contagem de pendentes                │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Listar locais pendentes (is_approved=False)         │
│    - Mostrar preview do local (nome, imagens, criador) │
│    - Ordenar por created_at (mais antigo primeiro)    │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Admin clica em "Ver Detalhes"                       │
│    - Abre detalhe do local em nova aba OU modal        │
│    - Revisa todas as informações                       │
└────────────────────┬────────────────────────────────────┘
                     ▼
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  Aprovar         │    │  Rejeitar            │
│  1. Clicar       │    │  1. Clicar "Rejeitar"│
│     "Aprovar"    │    │  2. Inserir motivo   │
│  2. Confirmar    │    │  3. Confirmar        │
│  3. Backend:     │    │  4. Backend:         │
│     - Criar      │    │     - Criar          │
│       PlaceAppr- │    │       PlaceApproval  │
│       oval com   │    │       com action=    │
│       action=    │    │       REJECT         │
│       APPROVE    │    │     - Definir        │
│     - Definir    │    │       is_approved    │
│       is_approved│    │       = False        │
│       = True     │    │     - Definir        │
│  4. Local agora  │    │       is_active =    │
│     visível no   │    │       False          │
│     site público │    │  5. Local oculto do  │
│                  │    │     site público     │
│                  │    │  6. Criador          │
│                  │    │     notificado       │
└──────────────────┘    └──────────────────────┘
```

---

## 🛠️ Tecnologias e Dependências

### Dependências Backend (pyproject.toml)

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "django>=5.2.7,<6.0",              # Framework web
    "psycopg2-binary>=2.9.11,<3.0",    # Adaptador PostgreSQL
    "python-decouple>=3.8,<4.0",       # Variáveis de ambiente
    "pillow>=12.3.0,<13.0",            # Processamento de imagens
    "django-ratelimit>=4.1.0,<5.0",    # Limitação de taxa
    "django-redis>=7.0.0,<8.0",        # Cache/rate-limit backend Redis-ready para prod
    "gunicorn>=26.2.0,<27.0",          # Servidor WSGI de produção
    "whitenoise>=6.12.0,<7.0",         # Servir estáticos em produção sem nginx
    "django-storages[s3]>=1.14.6,<2.0", # Storage S3-compatível (Cloudflare R2) para media
]
```

### Dependências de Desenvolvimento

```toml
[dependency-groups]
dev = [
    # Formatação e linting
    "black>=26.3.1,<27.0",
    "isort>=9.0.1,<10.0",
    "autoflake>=2.2.1,<3.0",
    "flake8>=7.3.0,<8.0",
    "flake8-mock-spec>=1.4.0,<2.0",

    # Segurança e upgrades automáticos
    "pip-audit>=2.7.3,<3.0",
    "django-upgrade>=1.15.0,<2.0",
    "pyupgrade>=3.15.0,<4.0",

    # Pre-commit e testes
    "pre-commit>=4.6.2,<5.0",
    "django-extra-checks>=0.17.0,<0.18",
    "coverage>=7.11.0,<8.0",

    # Verificação de tipo (opcional)
    "mypy>=2.3.1,<3.0",
    "django-stubs>=6.0.9,<7.0",

    # Versionamento e changelog (Conventional Commits)
    "commitizen>=4.18.0,<5.0",
]
```

Versões travadas em `uv.lock`; `pyproject.toml` é a fonte da verdade para os
ranges — confira lá antes de assumir uma versão específica.

### Bibliotecas Frontend (CDN)

- **Tailwind CSS 4 + Basecoat** - CSS e componentes (compilados por `npm run build:css`)
- **django-cotton** - Componentes de template (`templates/cotton/`)
- **Lucide** - Ícones SVG inline (`{% icon %}`)
- **Swiper.js 11** - Carrossel/slider
- **Leaflet 1.9 + OpenStreetMap** - Mapas
- **Google Places API** - Autocomplete de endereço
- **Google OAuth** - Autenticação social

### Ferramentas de Desenvolvimento

- **uv** - Gerenciamento de dependências e ambientes Python
- **pre-commit** - Git hooks para qualidade de código
- **SQLite** - Banco de dados de desenvolvimento
- **PostgreSQL** - Banco de dados de produção (opcional)

---

## 🎯 Estatísticas do Projeto

- **Total de Apps Django**: 4 (accounts, core, explore, news)
- **Total de Models**: 8
  - accounts: User (1)
  - core: Nenhum (0)
  - explore: Category, Place, PlaceImage, PlaceApproval, PlaceReview, Favorite (6)
  - news: News, NewsCategory (2)
- **Total de Views**: ~30 (views baseadas em função)
- **Total de Padrões de URL**: ~35
  - core: 3
  - accounts: 7
  - explore: 23+ (incluindo endpoints de API)
  - news: 2
- **Total de Templates**: ~25
- **Total de Arquivos Estáticos**:
  - CSS: 9 arquivos (main + components + pages)
  - JS: 13 arquivos (utilitários + componentes)
- **Endpoints de API**: 5 (dados do mapa, locais por IDs, toggle/sync/lista de favoritos)
- **Views com Limite de Taxa**: 3 (criar local, atualizar local, API de dados do mapa)
- **Views Protegidas por Permissão**: ~15 (login necessário)
- **Views Apenas Admin**: ~8 (moderador/staff necessário)

---

## 📊 Qualidade de Código e Testes

### Testes

- **Framework de Testes**: Django TestCase (`apps/*/tests.py`, arquivo único por app — ainda não convertido para pacote `tests/`)
- **Contagem atual**: 127 testes, todos passando (`uv run python manage.py test apps`)
- **Cobertura de Testes**: Configurada em `[tool.coverage.*]` no pyproject.toml; piso de 70% aplicado em CI (`coverage report --fail-under=70`)
- **Dados de Teste**: Criados via fixtures ou em métodos setUp; `populate_test_data` (explore) e `seed_news` (news) populam dados de exemplo
- **Executar Testes**: `uv run python manage.py test apps`
- **Relatório de Cobertura**: `uv run coverage run manage.py test apps && uv run coverage report`

### Ferramentas de Qualidade de Código

- **Black**: Formatação de código (line-length=88)
- **isort**: Ordenação de imports (profile=black)
- **autoflake**: Remove imports/variáveis não utilizados
- **flake8** + **flake8-mock-spec**: Linting (apenas as regras `TMS0*` de mock-spec estão habilitadas)
- **mypy** + **django-stubs**: Verificação de tipo (opcional/dev)
- **pip-audit**: Auditoria de vulnerabilidades nas dependências Python (roda em CI)
- **django-upgrade** / **pyupgrade**: Modernização automática de sintaxe
- **Prettier**: Formatação de JS/CSS/HTML/JSON/YAML/Markdown (config em `.github/.prettierrc`)
- **ESLint** (`npm run lint:js`) + **esbuild** (`npm run build:js`): lint e bundling do JS em `static/js`
- **pre-commit**: Verificações automatizadas no commit
- **commitizen**: Conventional Commits + geração de `CHANGELOG.md` e tags de versão

### Hooks Pre-commit

Configurado em `.pre-commit-config.yaml`:

- Remoção de espaços em branco no final
- Corretor de fim de arquivo
- Formatação Black
- Ordenação de imports isort
- autoflake (remover imports não utilizados)
- Linting flake8
- prettier (JS/CSS/HTML)
- Verificação customizada para arquivos `__init__.py`

### CI/CD (GitHub Actions)

- **`pr-checks.yml`** — em cada PR e push para `main`: job `lintert` (check `__init__.py`, black, isort, autoflake, flake8, pip-audit, prettier) e job `tests` (Postgres de serviço, `check --deploy`, `makemigrations --check --dry-run`, testes Django, coverage com piso de 70%).
- **`codeql.yml`** — CodeQL para Python e JavaScript/TypeScript, em push/PR para `main` e semanalmente (segunda-feira 06:00 UTC).
- **Dependabot** (`.github/dependabot.yml`) — atualizações automáticas de dependências pip, npm e GitHub Actions.
- **Nenhum workflow de CD** — não há deploy automático a partir de um merge; ver `docs/DEPLOYMENT.md` para o processo manual/documentado.

---

## 📄 Documentação Adicional

- **CRUD.md** - Documentação detalhada de implementação CRUD
- **CONTRIBUTING.md** - Guia prático para contribuir (setup uv, testes, lint, workflow de branch/PR, o que a CI verifica)
- **DEPLOYMENT.md** - Runbook de deploy: Docker, variáveis de ambiente de produção, wiring do Cloudflare (proxy ou Tunnel), docker-compose local e o perfil `mock-cloudflare`
- **IMPROVEMENT_PLAN.md** - Plano mestre de polimento com o histórico de todos os PRs mesclados
- **README.md** - Guia de início rápido

---

## 🔮 Melhorias Futuras

### Recursos Planejados

- Reformulação de design (Fase 9)
- Notificações por e-mail para aprovações/rejeições
- Compartilhamento social para locais e notícias
- Busca avançada com filtros
- Recomendações de locais baseadas em favoritos
- Aplicativo mobile (React Native/Flutter)

---

## 📝 Licença

Veja LICENSE.txt para detalhes.

---
