from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.ratelimit import limit
from apps.core.utils import is_cron_request, is_speculative

from . import event_crawler
from .models import News

PAGE_SIZE = 12


def news_list_view(request):
    """Agenda de eventos de Maricá: próximos e anteriores"""
    events = News.objects.published().events().select_related("category", "author")
    upcoming = events.upcoming_events()
    past = events.exclude(pk__in=upcoming.values("pk")).order_by(
        "-event_date", "-publish_date"
    )
    page = Paginator(past, PAGE_SIZE).get_page(request.GET.get("page"))
    agenda = list(upcoming)
    context = {
        "news_items": page,
        "agenda": agenda if page.number == 1 else [],
        "upcoming_count": len(agenda),
    }
    return render(request, "news/news_list.html", context)


def news_detail_view(request, slug):
    """Exibir a página de um evento; conteúdo que não é evento não é público"""
    event = get_object_or_404(News.objects.published().events(), slug=slug)
    if not is_speculative(request):
        event.increment_view_count()

    now = timezone.now()
    related_events = (
        News.objects.published()
        .events()
        .exclude(id=event.id)
        .select_related("category")
        .annotate(
            is_past=Case(
                When(Q(event_date__gt=now) | Q(event_end_date__gt=now), then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("is_past", "event_date", "-publish_date")[:3]
    )

    return render(
        request,
        "news/news_detail.html",
        {"news_item": event, "related_news": related_events},
    )


@csrf_exempt
@require_POST
@limit("300/h")
def news_view_beacon(request, slug):
    """Conta a visualização de uma página aberta a partir de um pré-carregamento."""
    get_object_or_404(
        News.objects.published().events(), slug=slug
    ).increment_view_count()
    return JsonResponse({"ok": True})


@require_GET
def cron_crawl_events_view(request):
    """Vercel Cron: busca eventos novos da Prefeitura e os põe em triagem.

    Só responde a quem envia ``Authorization: Bearer <CRON_SECRET>``.
    """
    if not is_cron_request(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    created = event_crawler.store_candidates(event_crawler.fetch_prefeitura_posts())
    return JsonResponse({"created": created})
