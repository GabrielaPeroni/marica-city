from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog

from apps.core.sitemaps import SITEMAPS
from apps.core.views import (
    cron_translate_content_view,
    health_view,
    media_view,
    robots_txt_view,
)
from apps.news.views import cron_crawl_events_view

urlpatterns = [
    path("healthz/", health_view, name="healthz"),
    path("robots.txt", robots_txt_view, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("cron/crawl-events/", cron_crawl_events_view, name="cron_crawl_events"),
    path(
        "cron/translate-content/",
        cron_translate_content_view,
        name="cron_translate_content",
    ),
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("explore/", include("apps.explore.urls")),
    path("eventos/", include("apps.news.urls")),
    path(
        "news/",
        RedirectView.as_view(pattern_name="news:news_list", permanent=True),
    ),
    path(
        "news/<slug:slug>/",
        RedirectView.as_view(pattern_name="news:news_detail", permanent=True),
    ),
    path("", include("apps.core.urls")),
]

# Servir arquivos de mídia durante o desenvolvimento (em produção ficam no R2)
if settings.DEBUG:
    urlpatterns += [
        re_path(rf"^{settings.MEDIA_URL.strip('/')}/(?P<path>.*)$", media_view),
    ]
