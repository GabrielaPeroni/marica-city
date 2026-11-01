# MaricaCity — Plataforma de Turismo Local

MaricaCity é uma plataforma web para descoberta e avaliação de pontos turísticos de Maricá (RJ). Esta é a **versão 2** de um projeto acadêmico original ([Marica-City-v1](https://github.com/GabrielaPeroni/Marica-City-v1), arquivado), reconstruída com foco em uma base de código mais robusta, organizada e preparada para produção. No ar em [marica-city.vercel.app](https://marica-city.vercel.app).

## Funcionalidades

- **Lugares turísticos**: cadastro de pontos turísticos por usuários, com upload de múltiplas imagens e fluxo de aprovação por administradores antes da publicação.
- **Avaliações**: sistema de reviews com nota de 1 a 5 estrelas (uma avaliação por usuário por lugar).
- **Favoritos**: usuários podem salvar lugares favoritos, com sincronização entre sessões.
- **Notícias e eventos**: seção de notícias com categorias, rascunho/publicação/arquivamento e contagem de visualizações; eventos com data, local e destaque na página inicial.
- **Autenticação**: login tradicional e via Google OAuth.
- **Painel administrativo**: fila de aprovação, backlog, gestão de usuários (papéis, ativação/desativação) e métricas, além do Django Admin padrão.
- **Permissões por papel**: usuários comuns podem criar lugares (pendentes de aprovação), avaliar e favoritar; administradores moderam todo o conteúdo.

## Stack e arquitetura

- **Backend**: [Django 5.2](https://www.djangoproject.com/), organizado em apps por domínio (`core`, `accounts`, `explore`, `news`) — veja [STRUCTURE.md](./docs/STRUCTURE.md) para a arquitetura completa e [CRUD.md](./docs/CRUD.md) para os detalhes de implementação do CRUD.
- **Banco de dados**: SQLite por padrão em desenvolvimento; PostgreSQL suportado via variáveis de ambiente para produção.
- **Frontend**: templates Django com Tailwind CSS 4 + Basecoat e componentes django-cotton, ícones Lucide, mapas Leaflet/OpenStreetMap e JavaScript vanilla por página/componente (ESLint para lint; `npm run build:css` compila o CSS).
- **Dependências**: gerenciadas com [uv](https://docs.astral.sh/uv/).
- **Qualidade e CI**: black, isort, autoflake, flake8 e Prettier via pre-commit; testes Django e checagens de segurança/migração rodam em CI a cada PR.
- **Rate limiting**: `django-ratelimit` para proteção contra abuso em endpoints sensíveis.

O plano de melhorias em andamento (hardening de segurança, deploy, cobertura de testes, etc.) está documentado em [IMPROVEMENT_PLAN.md](./docs/IMPROVEMENT_PLAN.md).

## 🚀 Como rodar o projeto

### Pré-requisitos

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) instalado

### 1. Instale as dependências:

```bash
uv sync
```

### 2. Copie o arquivo de ambiente e preencha as variáveis:

```bash
cp .env.example .env
```

### 3. Rode as migrations:

```bash
uv run python manage.py migrate
```

### 4. Crie um superuser (opcional):

```bash
uv run python manage.py createsuperuser
```

### 5. Rode o servidor:

```bash
uv run python manage.py runserver
```

## 📜 Licença

- **Código Django**: [MIT](./LICENSE).
