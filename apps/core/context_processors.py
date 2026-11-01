"""
Processadores de contexto para disponibilizar variáveis em todos os templates.
"""

from django.conf import settings
from django.core.cache import cache


def google_oauth(request):
    """
    Adicionar ID do Cliente Google OAuth ao contexto do template.
    """
    return {
        "GOOGLE_OAUTH_CLIENT_ID": settings.GOOGLE_OAUTH_CLIENT_ID,
    }


def vercel_analytics(request):
    """Liga o Vercel Web Analytics só quando o site roda na Vercel."""
    return {"VERCEL_ANALYTICS": settings.VERCEL_ANALYTICS}


FOOTER_CATEGORIES_KEY = "footer_categories"


def footer_categories(request):
    """Categorias do rodapé: lidas só se o rodapé renderiza e guardadas 5 min (apps.explore limpa ao salvar)."""

    def load():
        from apps.explore.models import Category

        categories = cache.get(FOOTER_CATEGORIES_KEY)
        if categories is None:
            categories = list(
                Category.objects.filter(is_active=True).order_by("display_order")[:6]
            )
            cache.set(FOOTER_CATEGORIES_KEY, categories, 300)
        return categories

    return {"footer_categories": load}


def admin_stats(request):
    """
    Adicionar estatísticas de administração ao contexto para badges da sidebar.
    Calculado apenas para usuários admin autenticados.
    """
    if request.user.is_authenticated and request.user.can_moderate:
        from apps.explore.models import Place
        from apps.news.models import EventCandidate, News

        return {
            "pending_places": Place.objects.filter(
                is_approved=False, is_active=True
            ).count(),
            "draft_news": News.objects.filter(status=News.DRAFT).count(),
            "pending_events": EventCandidate.objects.filter(
                status=EventCandidate.PENDING
            ).count(),
        }
    return {"pending_places": 0, "draft_news": 0, "pending_events": 0}
