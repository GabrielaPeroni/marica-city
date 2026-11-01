"""Production settings. Activate with DJANGO_SETTINGS_MODULE=config.settings.prod."""

from django.core.exceptions import ImproperlyConfigured

from decouple import Csv, config

from .base import *  # noqa: F401,F403
from .base import LOGGING

DEBUG = config("DEBUG", default=False, cast=bool)

# Mesmas settings para os dois ambientes publicados; "test" é a homologação
APP_ENV = config("APP_ENV", default="prod")
if APP_ENV not in ("prod", "test"):
    raise ImproperlyConfigured(f"APP_ENV must be 'prod' or 'test', not {APP_ENV!r}")

if APP_ENV == "test":
    # Contas com e-mail desses domínios não recebem e-mail: o código é guardado no
    # servidor e preenchido na tela. Endereços reais seguem o fluxo normal.
    EMAIL_CODE_AUTOFILL = "server"
    EMAIL_CODE_AUTOFILL_DOMAINS = config(
        "EMAIL_CODE_AUTOFILL_DOMAINS", default="maricacity.test", cast=Csv()
    )

ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")

# Trust the reverse proxy / CDN (e.g. Cloudflare) for the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)

SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=86400, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=True, cast=bool)

SECURE_CONTENT_TYPE_NOSNIFF = config(
    "SECURE_CONTENT_TYPE_NOSNIFF", default=True, cast=bool
)

# Compressed + hashed filenames, served by whitenoise (no separate nginx needed).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media (user uploads) on Cloudflare R2 (S3-compatible) so files survive redeploys.
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="auto")
# Só o host (pub-….r2.dev); aceita também a URL completa colada do painel
AWS_S3_CUSTOM_DOMAIN = (
    config("AWS_S3_CUSTOM_DOMAIN", default="").removeprefix("https://").rstrip("/")
)
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
# Upload names never repeat (Django adds a suffix), so browsers and the CDN can keep them.
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "public, max-age=31536000"}

if AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
    }
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

for _handler in LOGGING["handlers"].values():
    _handler["formatter"] = "structured"
LOGGING["root"]["level"] = "INFO"
LOGGING["loggers"]["django"]["level"] = "INFO"
LOGGING["loggers"]["django.request"]["level"] = "ERROR"
LOGGING["loggers"]["apps"]["level"] = "INFO"
