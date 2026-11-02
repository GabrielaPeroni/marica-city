import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import OuterRef, Subquery
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import ngettext
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET, require_POST
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from apps.accounts.models import User
from apps.core.content_translation import translate_pending
from apps.core.decorators import moderator_required
from apps.core.utils import is_cron_request, safe_next
from apps.explore.models import Category, Place, PlaceImage, PlaceReview
from apps.explore.visits import most_visited
from apps.news import event_crawler
from apps.news.forms import EventCandidateForm, NewsForm
from apps.news.models import EventCandidate, News, NewsCategory

logger = logging.getLogger(__name__)


@require_GET
def cron_translate_content_view(request):
    """Vercel Cron: traduz o conteúdo novo. Só com `Authorization: Bearer <CRON_SECRET>`."""
    if not is_cron_request(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    summary = translate_pending()
    return JsonResponse(
        summary, status=503 if summary["stopped"] == "unavailable" else 200
    )


@require_GET
@cache_control(public=True, max_age=3600, s_maxage=86400)
def js_catalog_view(request, lang):
    """JS strings, loaded on every page. The language is in the URL so it can be cached."""
    if lang not in dict(settings.LANGUAGES):
        raise Http404
    with translation.override(lang):
        return JavaScriptCatalog.as_view()(request)


@require_GET
def health_view(request):
    """Liveness/readiness probe; does a cheap SELECT 1 to also catch DB outages."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@require_GET
def robots_txt_view(request):
    """Rastreadores: tudo público, menos painel, admin e contas; aponta o sitemap"""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /painel-admin/",
        "Disallow: /accounts/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def media_view(request, path):
    """Uploads em desenvolvimento, com cache longo: os nomes nunca se repetem."""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def landing_view(request):
    # Em alta: mais visitados na semana; sem visitas, os cadastrados na semana
    trending_places = list(most_visited())
    if not trending_places:
        trending_places = list(
            Place.objects.public()
            .filter(created_at__gte=timezone.now() - timedelta(days=7))
            .with_ratings()
            .prefetch_related("images", "categories")
            .order_by("-created_at")[:4]
        )
    trending_ids = {place.pk for place in trending_places}

    # "Onde ir": os destacados pela equipe primeiro, depois os mais recentes
    featured_places = list(
        Place.objects.public()
        .with_ratings()
        .prefetch_related("images", "categories")
        .order_by("-is_featured", "-created_at")[:6]
    )
    # view-transition-name precisa ser único: só o card de "Em alta" anima
    for place in featured_places:
        place.morph = place.pk not in trending_ids

    # Foto de capa: imagem principal do lugar público destacado/mais recente
    cover = (
        PlaceImage.objects.filter(
            place__in=Place.objects.public(),
            place__categories=OuterRef("pk"),
            is_primary=True,
        )
        .order_by("-place__is_featured", "-place__created_at")
        .values("pk")[:1]
    )
    categories = list(
        Category.objects.filter(is_active=True)
        .with_place_counts()
        .annotate(cover_id=Subquery(cover))
        .order_by("display_order")[:6]
    )
    covers = PlaceImage.objects.in_bulk(c.cover_id for c in categories if c.cover_id)
    for category in categories:
        category.cover = covers.get(category.cover_id)

    events = News.objects.published().select_related("category")
    upcoming_events = list(events.upcoming_events()[:4])
    # Sem eventos futuros (ex.: site estático), mostra os mais recentes
    recent_events = (
        []
        if upcoming_events
        else list(
            events.filter(category__name=NewsCategory.EVENT)
            .exclude(event_date=None)
            .order_by("-event_date")[:4]
        )
    )

    # Quem visitou conta: avaliações boas e com texto, uma por lugar
    reviews, seen = [], set()
    for review in (
        PlaceReview.objects.filter(
            place__in=Place.objects.public(), rating__gte=4, comment__gt=""
        )
        .select_related("user", "place")
        .order_by("-created_at")[:12]
    ):
        if review.place_id not in seen:
            seen.add(review.place_id)
            reviews.append(review)

    context = {
        "featured_places": featured_places,
        "reviews": reviews[:3],
        "trending_places": trending_places,
        "upcoming_events": upcoming_events,
        "recent_events": recent_events,
        "categories": categories,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, "core/landing.html", context)


def about_view(request):
    """View da página sobre"""
    return render(request, "core/about.html")


def calculate_percentage_change(current, previous):
    """Calcular mudança percentual entre dois valores"""
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 1)


def _weekly(queryset, field):
    """(cadastros nos últimos 7 dias, variação % em relação aos 7 anteriores)"""
    week_ago = timezone.now() - timedelta(days=7)
    this_week = queryset.filter(**{f"{field}__gte": week_ago}).count()
    last_week = queryset.filter(
        **{f"{field}__gte": week_ago - timedelta(days=7), f"{field}__lt": week_ago}
    ).count()
    return this_week, calculate_percentage_change(this_week, last_week)


@moderator_required
def admin_dashboard_view(request):
    """Visão geral do painel (pendências e badges vêm do context processor admin_stats)"""
    places_this_week, places_change = _weekly(Place.objects, "created_at")
    users_this_week, users_change = _weekly(User.objects, "date_joined")
    reviews_this_week, reviews_change = _weekly(PlaceReview.objects, "created_at")

    # O administrador fica sempre no topo; depois, os cadastros mais recentes
    recent_users = [
        *User.objects.filter(is_superuser=True).order_by("date_joined"),
        *User.objects.filter(is_superuser=False).order_by("-date_joined")[:10],
    ]
    context = {
        "places_this_week": places_this_week,
        "places_change": places_change,
        "users_this_week": users_this_week,
        "users_change": users_change,
        "reviews_this_week": reviews_this_week,
        "reviews_change": reviews_change,
        "recent_users": recent_users,
    }
    return render(request, "core/admin_dashboard.html", context)


# Views de Gerenciamento de Notícias


# Filtros da lista de eventos do painel: chave -> (rótulo, status salvo, ícone, tom)
EVENT_FILTERS = {
    "all": (_l("Todos"), None, "layers", "neutral"),
    "suggested": (_l("Sugestões"), None, "sparkles", "warning"),
    "published": (_l("Publicados"), News.PUBLISHED, "circle-check", "success"),
    "draft": (_l("Rascunhos"), News.DRAFT, "square-pen", "featured"),
    "archived": (_l("Arquivados"), News.ARCHIVED, "archive", "neutral"),
}


@moderator_required
def admin_news_list_view(request):
    return render(
        request,
        "core/admin/news_list.html",
        _events_context(request, request.GET.get("status", "all")),
    )


def _events_context(request, status_filter, triage_form=None):
    """Lista de eventos e, no filtro "suggested", os candidatos do crawler."""
    # Links antigos usam o valor salvo ("Publicado") em vez da chave
    by_value = {
        status: key for key, (_x, status, *_r) in EVENT_FILTERS.items() if status
    }
    status_filter = by_value.get(status_filter, status_filter)
    if status_filter not in EVENT_FILTERS:
        status_filter = "all"
    category_filter = request.GET.get("category", "all")
    search_query = request.GET.get("q", "").strip()

    news_list = News.objects.select_related("author", "category").order_by(
        "-created_at"
    )
    stored_status = EVENT_FILTERS[status_filter][1]
    if stored_status:
        news_list = news_list.filter(status=stored_status)
    if category_filter != "all":
        news_list = news_list.filter(category__name=category_filter)
    if search_query:
        news_list = news_list.filter(title__icontains=search_query)

    def count(key, status):
        if key == "suggested":
            return EventCandidate.objects.filter(status=EventCandidate.PENDING).count()
        return (
            News.objects.filter(status=status).count()
            if status
            else News.objects.count()
        )

    context = {
        "news_list": news_list,
        "categories": NewsCategory.objects.all(),
        "status_filter": status_filter,
        "category_filter": category_filter,
        "search_query": search_query,
        "status_cards": [
            (key, label, count(key, status), icon, tone)
            for key, (label, status, icon, tone) in EVENT_FILTERS.items()
        ],
    }
    if status_filter == "suggested":
        context.update(_triage_context(triage_form))
    return context


def _news_form(request, news=None):
    form = NewsForm(request.POST or None, request.FILES or None, instance=news)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if news is None:
            saved.author = request.user
        saved.save()
        return saved, form
    return None, form


@moderator_required
def admin_news_create_view(request):
    if request.method == "GET":
        event = NewsCategory.objects.filter(name=NewsCategory.EVENT).first()
        form, news = NewsForm(initial={"category": event}), None
    else:
        news, form = _news_form(request)
    if news:
        messages.success(
            request, _('Evento "%(title)s" criado com sucesso!') % {"title": news.title}
        )
        return redirect("core:admin_news_list")
    context = {"form": form, "title": _("Criar novo evento"), "submit_text": _("Criar")}
    return render(request, "core/admin/news_form.html", context)


@moderator_required
def admin_news_edit_view(request, pk):
    news = get_object_or_404(News, pk=pk)
    saved, form = _news_form(request, news)
    if saved:
        messages.success(
            request,
            _('Evento "%(title)s" atualizado com sucesso!') % {"title": saved.title},
        )
        return redirect("core:admin_news_list")
    context = {
        "form": form,
        "news": news,
        "title": _("Editar: %(title)s") % {"title": news.title},
        "submit_text": _("Salvar Alterações"),
    }
    return render(request, "core/admin/news_form.html", context)


@moderator_required
def admin_news_delete_view(request, pk):
    news = get_object_or_404(News, pk=pk)
    if request.method != "POST":
        return render(request, "core/admin/news_delete_confirm.html", {"news": news})

    news.delete()
    messages.success(
        request,
        _('Evento "%(news_title)s" excluído com sucesso.') % {"news_title": news.title},
    )
    return redirect("core:admin_news_list")


# Ações em massa que mudam o status; save() de cada item define publish_date ao publicar
BULK_STATUS = {"publish": News.PUBLISHED, "archive": News.ARCHIVED}


def _bulk_message(action, count):
    return {
        "publish": ngettext(
            "%(count)d evento publicado", "%(count)d eventos publicados", count
        ),
        "archive": ngettext(
            "%(count)d evento arquivado", "%(count)d eventos arquivados", count
        ),
        "delete": ngettext(
            "%(count)d evento excluído", "%(count)d eventos excluídos", count
        ),
    }[action] % {"count": count}


@moderator_required
@require_POST
def admin_news_bulk_view(request):
    """Publicar, arquivar ou excluir vários eventos de uma vez."""
    destination = safe_next(request, reverse("core:admin_news_list"))
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    if not ids:
        messages.error(request, _("Selecione ao menos um evento."))
        return redirect(destination)

    items = News.objects.filter(pk__in=ids)
    action = request.POST.get("action")
    if action in BULK_STATUS:
        changed = list(items.exclude(status=BULK_STATUS[action]))
        for item in changed:
            item.status = BULK_STATUS[action]
            item.save()
        count = len(changed)
    elif action == "delete":
        count = items.count()
        items.delete()
    else:
        messages.error(request, _("Ação inválida."))
        return redirect(destination)
    messages.success(request, _bulk_message(action, count))
    return redirect(destination)


# Triagem de eventos encontrados pelo crawler


def _triage_context(bound_form=None):
    pending = list(
        EventCandidate.objects.filter(status=EventCandidate.PENDING).select_related(
            "possible_duplicate"
        )
    )
    candidates = [
        (
            c,
            (
                bound_form
                if bound_form and bound_form.instance.pk == c.pk
                else EventCandidateForm(instance=c, prefix=f"c{c.pk}")
            ),
            [o for o in pending if o.pk != c.pk and event_crawler.same_event(c, o)],
        )
        for c in pending
    ]
    recent = (
        EventCandidate.objects.exclude(status=EventCandidate.PENDING)
        .select_related("news", "reviewed_by")
        .order_by("-reviewed_at")[:10]
    )
    return {"candidates": candidates, "recent": recent}


def _suggestions_url():
    return reverse("core:admin_news_list") + "?status=suggested"


@moderator_required
def admin_event_triage_view(request):
    return redirect(_suggestions_url())


@moderator_required
@require_POST
def admin_event_triage_action_view(request, pk):
    candidate = get_object_or_404(EventCandidate, pk=pk, status=EventCandidate.PENDING)
    if request.POST.get("action") == "reject":
        event_crawler.reject(candidate, request.user)
        messages.info(
            request, _('"%(title)s" foi descartado.') % {"title": candidate.title}
        )
        return redirect(_suggestions_url())

    form = EventCandidateForm(request.POST, instance=candidate, prefix=f"c{pk}")
    if not form.is_valid():
        messages.error(
            request, _('Revise os campos de "%(title)s".') % {"title": candidate.title}
        )
        return render(
            request,
            "core/admin/news_list.html",
            _events_context(request, "suggested", form),
            status=400,
        )

    news = event_crawler.approve(form.save(), request.user)
    messages.success(
        request, _('"%(title)s" publicado na agenda.') % {"title": news.title}
    )
    return redirect(_suggestions_url())


@moderator_required
@require_POST
def admin_event_triage_bulk_view(request):
    """Descartar vários candidatos de uma vez."""
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    if not ids:
        messages.error(request, _("Selecione ao menos um evento."))
    elif request.POST.get("action") == "reject":
        count = event_crawler.reject_many(ids, request.user)
        messages.success(
            request,
            ngettext(
                "%(count)d evento descartado", "%(count)d eventos descartados", count
            )
            % {"count": count},
        )
    else:
        messages.error(request, _("Ação inválida."))
    return redirect(_suggestions_url())


@moderator_required
@require_POST
def admin_event_crawl_view(request):
    try:
        created = event_crawler.store_candidates(event_crawler.fetch_prefeitura_posts())
    except Exception:
        logger.exception("Busca manual de eventos falhou")
        messages.error(request, _("Não foi possível consultar a Prefeitura agora."))
    else:
        messages.success(
            request,
            _("%(created)s evento(s) novo(s) para triagem.") % {"created": created},
        )
    return redirect(_suggestions_url())
