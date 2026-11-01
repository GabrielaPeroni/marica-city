# Implementação do CRUD

O projeto implementa operações CRUD seguindo o padrão MVT (Model-View-Template) do Django, com funcionalidades distribuídas em 4 apps principais.

### > Estrutura do CRUD

- **Models** (`apps/*/models.py`): Definem a estrutura dos dados e lógica de negócio
- **Views** (`apps/*/views.py`): Processam requisições HTTP e implementam a lógica CRUD
- **Forms** (`apps/*/forms.py`): Validam dados e gerenciam entrada do usuário
- **Templates** (`templates/*/`): Renderizam HTML para a interface
- **URLs** (`apps/*/urls.py`): Mapeiam URLs para views

---

### > Principais Operações CRUD

#### 1. **Places (Lugares Turísticos)** - CRUD Completo

- **CREATE**

  - `place_create_view`: Usuários autenticados podem criar lugares com múltiplas imagens.
  - Usa **formsets** para upload de múltiplas imagens.
  - Lugares começam como **não aprovados** (`is_approved=False`).

- **READ**

  - `explore_view`: Lista todos os lugares aprovados com busca.
  - `place_detail_view`: Mostra detalhes do lugar com reviews (média e distribuição por estrela), galeria de imagens com lightbox e mapa Leaflet/OpenStreetMap.
  - `category_detail_view`: Exibe lugares por categoria.

- **UPDATE**

  - `place_update_view`: Dono ou admin pode editar.
  - Gerencia múltiplas imagens via **formset**.

- **DELETE**
  - `place_delete_view`: Dono ou admin pode deletar.
  - Confirmação via modal (sem navegação para nova página).

---

#### 2. **Sistema de Aprovação**

- `approval_queue_view`: Fila de lugares pendentes (**admin**).
- `approve_place_view`: Aprovar lugar (**admin**).
- `reject_place_view`: Remover lugar com motivo via modal (**admin**).
- `backlog_view`: Exibe todos os lugares com filtros (**admin**).
- `bulk_places_view`: Ações em massa na fila e no backlog (**admin**).
- `place_feature_view`: Marca ou desmarca um lugar como destaque (`is_featured`) para a landing (**admin**).

**Ações em Massa (Django Admin):**

- `approve_places`: Aprovar múltiplos lugares pendentes de uma vez.
- `revoke_approval`: Revogar aprovação de lugares, retornando-os ao status pendente e ocultando-os do site público.

---

#### 3. **Reviews (Avaliações)** — CRUD Completo

- `review_create_view`: Usuários podem avaliar lugares (1 review por usuário para cada lugar). A view verifica se já existe uma `PlaceReview` do usuário para o lugar antes de mostrar o formulário; a unicidade também é garantida no banco por `unique_together = ("user", "place")` no model.
- `place_detail_view`: Exibe todas as avaliações do lugar. Para não-donos/não-moderadores, só retorna o lugar se `is_approved=True` **e** `is_active=True` — um lugar aprovado mas desativado (ex.: rejeitado após já ter sido aprovado) não é exposto a outros usuários.
- `review_edit_view`: Dono ou admin pode editar uma avaliação.
- `review_delete_view`: Dono ou admin pode deletar uma avaliação.
- Na página do lugar, criar/editar/excluir avaliação abre um `<dialog>` que envia o formulário normal para essas views; sem JS, os botões levam às páginas próprias.

---

#### 4. **Favorites (Favoritos)** — Sistema de Toggle

- `toggle_favorite_view`: Endpoint **AJAX** para adicionar ou remover favoritos.
- Usuários autenticados sincronizam com o backend.
- `favorites_list_view`: Lista de favoritos do usuário.
- `sync_favorites_view`: Sincroniza `localStorage` com o backend.

---

#### 5. **Users (Usuários)** — Gerenciamento Admin

- `register_view`: Registro público; envia um código de 6 dígitos por e-mail e a conta só é criada em `register_verify_view`.
- `password_reset_view` / `password_reset_confirm_view`: "Esqueci minha senha" com código por e-mail (mesma resposta exista ou não a conta).
- `resend_code_view`: Reenvia o código de cadastro ou de senha (POST, limitado por IP).
- `user_management_view`: Lista usuários (**admin only**).
- `user_update_type_view`: Atualiza permissões (**admin**).
- `user_toggle_status_view`: Ativa ou desativa usuários (**admin**).
- `user_delete_view`: Deleta usuários (**admin**).

---

#### 6. **News / Events (Notícias e Eventos)**

Público (somente leitura, em `/eventos/`):

- `news_list_view`: Lista notícias e eventos (agenda, filtro por período).
- `news_detail_view`: Exibe detalhes; a contagem de visualizações é feita por `news_view_beacon` quando a página é de fato aberta (não em prefetch).

Painel de administração (`apps/core/views.py`, **admin**, em `/painel-admin/`):

- `admin_news_list_view`, `admin_news_create_view`, `admin_news_edit_view`, `admin_news_delete_view`, `admin_news_bulk_view`: CRUD de notícias e eventos, com ações em massa.
- `admin_event_triage_view`, `admin_event_triage_action_view`, `admin_event_triage_bulk_view`: triagem dos `EventCandidate` encontrados pelo crawler; aprovar cria um `News` publicado.
- `admin_event_crawl_view`: botão "Buscar agora" (roda o crawler).
- `cron_crawl_events_view` (`/cron/crawl-events/`, em `apps/news/views.py`): chamada pelo Vercel Cron, exige `CRON_SECRET`.

---

#### 7. **API JSON e Infraestrutura**

- `map_data_api`: Retorna marcadores de todos os lugares aprovados/ativos para o mapa da landing page. Rating/categoria são calculados via anotações SQL (`annotate`), não por query separada por lugar.
- `place_visit_view`: conta (POST) a visita de uma página aberta a partir de pré-carregamento; só grava se o cookie de consentimento foi aceito.
- `places_by_ids_api`: Retorna lugares por uma lista de IDs (usado pela sincronização de favoritos no frontend); também usa anotações para evitar N+1.
- `GET /healthz/` (`apps.core.views.health_view`): endpoint de health check sem autenticação, executa `SELECT 1` no banco e retorna `{"status": "ok"}`. Usado pelo `HEALTHCHECK` do Docker e por qualquer orquestrador/monitor de uptime.

---

#### **CRUD completo via Django Admin**

- Criação, edição e exclusão disponíveis apenas para administradores.

---

### Sistema de Permissões

| Funcionalidade           | Autenticado | Admin/Staff |
| ------------------------ | ----------- | ----------- |
| Ver lugares aprovados    | Sim         | Sim         |
| Ver lugares pendentes    | Próprios    | Sim         |
| Criar lugares            | Sim         | Sim         |
| Editar próprios lugares  | Sim         | Sim         |
| Avaliar lugares          | Sim         | Sim         |
| Favoritar (localStorage) | Sim         | Sim         |
| Editar qualquer lugar    | Não         | Sim         |
| Aprovar/Rejeitar         | Não         | Sim         |
| Revogar aprovação        | Não         | Sim         |
| Gerenciar usuários       | Não         | Sim         |
