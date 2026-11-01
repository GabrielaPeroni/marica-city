"""Endpoints JSON: mapa da página inicial e favoritos de quem não está logado."""

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.core.content_translation import translated
from apps.core.thumbnails import thumbnail_url

from .models import Place


def _places():
    return (
        Place.objects.public()
        .with_ratings()
        .prefetch_related("images", "categories")
        .order_by("-created_at")
    )


def _summary(place):
    image = place.primary_image
    return {
        "id": place.id,
        "name": translated(place, "name"),
        "image_url": thumbnail_url(image.image, 960) if image else None,
        "url": reverse("explore:place_detail", args=[place.id]),
        "rating": place.average_rating,
        "review_count": place.review_count,
    }


def _response(places):
    return JsonResponse({"places": places, "count": len(places)})


@require_GET
def map_data_api(request):
    """Lugares públicos com coordenadas, para o mapa interativo"""
    places = []
    for place in _places().filter(latitude__isnull=False, longitude__isnull=False):
        category = next(iter(place.categories.all()), None)
        description = translated(place, "description")
        places.append(
            {
                **_summary(place),
                "description": (
                    description[:100] + "..." if len(description) > 100 else description
                ),
                "latitude": float(place.latitude),
                "longitude": float(place.longitude),
                "category": translated(category, "name") if category else _("Outros"),
                "category_icon": category.icon if category else "📍",
            }
        )
    return _response(places)


@require_GET
def places_by_ids_api(request):
    """Detalhes dos lugares em ?ids=1,2,3 (página de favoritos sem login)"""
    try:
        ids = [int(i) for i in request.GET.get("ids", "").split(",") if i.strip()]
    except ValueError:
        return JsonResponse({"error": "Formato de ID inválido"}, status=400)

    places = [
        {
            **_summary(place),
            "description": translated(place, "description"),
            "categories": [
                {"name": translated(c, "name"), "icon": c.icon, "slug": c.slug}
                for c in place.categories.all()
            ],
        }
        for place in _places().filter(id__in=ids)
    ]
    return _response(places)
