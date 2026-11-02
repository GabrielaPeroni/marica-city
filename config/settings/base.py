from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Aplicativos
    "django_ratelimit",
    "django_cotton",
    "apps.core",
    "apps.accounts",
    "apps.explore",
    "apps.news",
]

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_ratelimit.middleware.RatelimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.google_oauth",
                "apps.core.context_processors.admin_stats",
                "apps.core.context_processors.footer_categories",
                "apps.core.context_processors.vercel_analytics",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def _database_from_url(url):
    """postgres://user:pass@host:port/name?sslmode=require (Vercel/Neon set DATABASE_URL)"""
    parts = urlsplit(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "OPTIONS": dict(parse_qsl(parts.query)),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


DATABASE_URL = config("DATABASE_URL", default="")
DATABASES = {
    "default": (
        _database_from_url(DATABASE_URL)
        if DATABASE_URL
        else {
            "ENGINE": config("DB_ENGINE", default="django.db.backends.sqlite3"),
            "NAME": config("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
            "USER": config("DB_USER", default=""),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default=""),
            "PORT": config("DB_PORT", default=""),
        }
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "pt-br"

LANGUAGES = [
    ("pt-br", "Português"),
    ("en", "English"),
    ("es", "Español"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True

# Points at Redis via CACHE_URL/REDIS_URL/KV_URL (Upstash on Vercel) in prod;
# LocMemCache otherwise (not safe across multiple processes/workers).
_CACHE_URL = config(
    "CACHE_URL", default=config("REDIS_URL", default=config("KV_URL", default=""))
)

if _CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _CACHE_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                # Redis fora do ar deixa o site mais lento, não fora do ar
                "IGNORE_EXCEPTIONS": True,
                "SOCKET_CONNECT_TIMEOUT": 2,
                "SOCKET_TIMEOUT": 2,
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ratelimit-cache",
        }
    }

# O popup do botão do Google precisa falar com a janela que o abriu
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"
# Google Sign-In e os tiles do OpenStreetMap conferem a origem da página
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Arquivos de mídia (Conteúdo enviado pelo usuário)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Modelo de Usuário Personalizado
AUTH_USER_MODEL = "accounts.User"

# Configurações de autenticação
# Redirecionar para a página inicial onde o modal de login está disponível
LOGIN_URL = "core:landing"
LOGIN_REDIRECT_URL = "core:landing"
LOGOUT_REDIRECT_URL = "core:landing"

# Configurações do Google
# Deve ser definido no arquivo .env
GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="")

# E-mail (códigos de cadastro e de senha). O padrão aponta para o MailHog local
# (docker compose up mailhog); em produção defina EMAIL_HOST e credenciais reais.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="MaricaCity <nao-responda@maricacity.local>"
)
# Preenchimento automático das telas de código (apps/accounts/codes.py): "mailhog" no
# dev.py, "server" no prod.py com APP_ENV=test, desligado ("") em produção
EMAIL_CODE_AUTOFILL = ""
EMAIL_CODE_AUTOFILL_DOMAINS = []

# Vercel Cron envia este segredo no cabeçalho Authorization (/cron/...)
CRON_SECRET = config("CRON_SECRET", default="")

# Tradução automática de conteúdo (cron diário ou manage.py translate_content).
# Sem chave, nada é traduzido. Os limites contam caracteres enviados ao DeepL.
DEEPL_API_KEY = config("DEEPL_API_KEY", default="")
TRANSLATE_DAILY_CHAR_LIMIT = config(
    "TRANSLATE_DAILY_CHAR_LIMIT", default=20_000, cast=int
)
# Fração da cota mensal do DeepL que o site pode usar
TRANSLATE_USAGE_CEILING = config("TRANSLATE_USAGE_CEILING", default=0.8, cast=float)
TRANSLATE_MAX_ITEM_CHARS = config("TRANSLATE_MAX_ITEM_CHARS", default=6_000, cast=int)

# Limitação de Taxa (para prevenir abuso de API)
RATELIMIT_ENABLE = config("RATELIMIT_ENABLE", default=True, cast=bool)
RATELIMIT_USE_CACHE = "default"  # Usar cache padrão para limitação de taxa
RATELIMIT_VIEW = "apps.explore.ratelimit_handlers.ratelimited_error"

# Silenciar avisos do django-ratelimit sobre LocMemCache em desenvolvimento
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]

# Configuração de testes
# Usar executor de testes personalizado para excluir .github da descoberta de testes
TEST_RUNNER = "config.test_runner.CustomTestRunner"

# dev.py/prod.py adjust levels and formatter on top of this.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "structured": {
            "format": (
                'level={levelname} time="{asctime}" logger={name} message="{message}"'
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "PIL": {"level": "INFO"},
    },
}

# A Vercel define VERCEL=1 nas funções; fora dela o script de analytics daria 404
VERCEL_ANALYTICS = config("VERCEL", default=False, cast=bool)
