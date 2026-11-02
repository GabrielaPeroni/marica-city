import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import ngettext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.content_translation import TARGETS
from apps.core.decorators import moderator_required
from apps.core.ratelimit import limit
from apps.core.utils import safe_next

from .api import MAX_IDS, parse_ids, valid_ids
from .forms import PlaceForm, PlaceImageFormSet, PlaceReviewForm
from .models import Category, Favorite, Place, PlaceApproval, PlaceImage, PlaceReview
from .visits import record_visit

SORTS = ("-created_at", "created_at", "name", "-name")
PENDING_URL = "explore:backlog"


def _sort(request, default="-created_at"):
    sort = request.GET.get("sort", default)
    return sort if sort in SORTS else default


def _is_search(request):
    return bool(request.GET.get("q", "").strip())


def _active_categories():
    return Category.objects.filter(is_active=True).order_by("display_order")


def _text_match(query):
    """Nome e descrição, no original e nas traduções."""
    match = Q(name__icontains=query) | Q(description__icontains=query)
    for lang in TARGETS:
        match |= Q(**{f"translations__{lang}__name__icontains": query})
        match |= Q(**{f"translations__{lang}__description__icontains": query})
    return match


@limit("30/m", method="GET", when=_is_search)
def explore_view(request):
    """Todos os lugares públicos (e os pendentes do próprio usuário), com busca"""
    places = Place.objects.public()
    if request.user.is_authenticated:
        places |= Place.objects.filter(created_by=request.user, is_active=True)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        places = places.filter(
            _text_match(search_query) | Q(categories__name__icontains=search_query)
        ).distinct()

    sort = _sort(request)
    context = {
        "categories": _active_categories(),
        "all_places": places.with_ratings()
        .prefetch_related("images", "categories")
        .order_by(sort),
        "current_sort": sort,
    }
    return render(request, "explore/explore.html", context)


@limit("30/m", method="GET", when=_is_search)
def category_detail_view(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    places = Place.objects.public().filter(categories=category)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        places = places.filter(_text_match(search_query))

    sort = _sort(request)
    cover = (
        PlaceImage.objects.filter(
            is_primary=True,
            place__in=Place.objects.public().filter(categories=category),
        )
        .order_by("-place__created_at")
        .first()
    )
    context = {
        "category": category,
        "cover": cover,
        "places": places.with_ratings()
        .prefetch_related("images", "categories")
        .order_by(sort),
        "all_categories": _active_categories(),
        "current_sort": sort,
    }
    return render(request, "explore/category_detail.html", context)


@csrf_exempt
@require_POST
@limit("300/h")
def place_visit_view(request, pk):
    """Conta a visita de uma página aberta a partir de um pré-carregamento."""
    place = get_object_or_404(Place.objects.public(), pk=pk)
    response = JsonResponse({"ok": True})
    record_visit(request, response, place)
    return response


def place_detail_view(request, pk):
    place = get_object_or_404(
        Place.objects.visible_to(request.user).prefetch_related("images", "categories"),
        pk=pk,
    )
    reviews = place.reviews.select_related("user").order_by("-created_at")
    ratings = [r.rating for r in reviews]
    user_review = (
        next((r for r in reviews if r.user_id == request.user.pk), None)
        if request.user.is_authenticated
        else None
    )
    context = {
        "place": place,
        "can_edit": place.can_edit(request.user),
        "reviews": reviews,
        "user_review": user_review,
        "average_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "rating_distribution": [(n, ratings.count(n)) for n in range(5, 0, -1)],
        "gallery": sorted(place.images.all(), key=lambda image: not image.is_primary),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }
    response = render(request, "explore/place_detail.html", context)
    record_visit(request, response, place)
    return response


def _place_form(request, place=None):
    """Formulário de lugar com galeria; devolve o lugar salvo ou o contexto para renderizar."""
    if request.method == "POST":
        form = PlaceForm(request.POST, instance=place)
        formset = PlaceImageFormSet(request.POST, request.FILES, instance=place)
        if form.is_valid() and formset.is_valid():
            saved = form.save(commit=False)
            if place is None:
                saved.created_by = request.user
            saved.save()
            form.save_m2m()
            formset.instance = saved
            formset.save()
            saved.ensure_primary_image()
            return saved, None
    else:
        form = PlaceForm(instance=place)
        formset = PlaceImageFormSet(instance=place)
    return None, {
        "form": form,
        "formset": formset,
        "place": place,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
        "photos_lost": bool(request.FILES),
    }


@login_required
@limit("5/h", key="user")
def place_create_view(request):
    if not request.user.can_create_places:
        messages.error(request, _("Você não tem permissão para criar lugares."))
        return redirect("explore:explore")

    place, context = _place_form(request)
    if place:
        messages.success(
            request,
            _(
                'Lugar "%(name)s" criado com sucesso! Ele será revisado por um administrador antes de aparecer no site.'
            )
            % {"name": place.name},
        )
        return redirect("explore:place_detail", pk=place.pk)
    context.update(title=_("Cadastrar lugar"), submit_text=_("Enviar para Aprovação"))
    return render(request, "explore/place_form.html", context)


@login_required
@limit("10/h", key="user")
def place_update_view(request, pk):
    place = get_object_or_404(Place, pk=pk)
    if not place.can_edit(request.user):
        messages.error(request, _("Você não tem permissão para editar este lugar."))
        return redirect("explore:place_detail", pk=place.pk)

    saved, context = _place_form(request, place)
    if saved:
        messages.success(
            request,
            _('Lugar "%(name)s" atualizado com sucesso!') % {"name": saved.name},
        )
        return redirect("explore:place_detail", pk=saved.pk)
    context.update(
        title=_("Editar %(name)s") % {"name": place.name},
        submit_text=_("Salvar Alterações"),
    )
    return render(request, "explore/place_form.html", context)


@login_required
@limit("20/h", key="user")
def place_delete_view(request, pk):
    place = get_object_or_404(Place, pk=pk)
    if not place.can_edit(request.user):
        messages.error(request, _("Você não tem permissão para excluir este lugar."))
        return redirect("explore:place_detail", pk=place.pk)
    if request.method != "POST":
        return redirect("explore:place_edit", pk=pk)

    place.delete()
    messages.success(
        request,
        _('Lugar "%(place_name)s" foi excluído com sucesso.')
        % {"place_name": place.name},
    )
    return redirect("explore:explore")


# Moderação


def _removal_comments(reason, custom_comments):
    """Return (comments, error) for a removal reason; "Outros" needs a comment."""
    if not reason:
        return None, _("Por favor, selecione um motivo para a rejeição.")
    if reason != "Outros":
        return reason, None
    if not custom_comments:
        return None, _("Por favor, especifique o motivo da rejeição.")
    return custom_comments, None


def _pending_url():
    return reverse(PENDING_URL) + "?status=pending"


@moderator_required
def approval_queue_view(request):
    """Link antigo da fila de aprovação."""
    return redirect(_pending_url())


@moderator_required
@require_POST
def place_feature_view(request, pk):
    """Liga/desliga o destaque de um lugar aprovado na página inicial"""
    place = get_object_or_404(Place.objects.public(), pk=pk)
    place.is_featured = not place.is_featured
    place.save(update_fields=["is_featured", "updated_at"])
    message = (
        _("%(name)s está em destaque na página inicial.")
        if place.is_featured
        else _("%(name)s saiu dos destaques.")
    )
    messages.success(request, message % {"name": place.name})
    return redirect(safe_next(request, reverse(PENDING_URL)))


@moderator_required
@require_POST
def approve_place_view(request, pk):
    place = get_object_or_404(Place, pk=pk)
    PlaceApproval.record(
        [place],
        request.user,
        PlaceApproval.ActionType.APPROVE,
        request.POST.get("comments", ""),
    )
    messages.success(
        request, _('Lugar "%(name)s" foi aprovado com sucesso!') % {"name": place.name}
    )
    return redirect(_pending_url())


@moderator_required
@require_POST
def reject_place_view(request, pk):
    place = get_object_or_404(Place, pk=pk)
    comments, error = _removal_comments(
        request.POST.get("reason", ""), request.POST.get("comments", "").strip()
    )
    if error:
        messages.error(request, error)
        return redirect(_pending_url())

    PlaceApproval.record(
        [place], request.user, PlaceApproval.ActionType.REJECT, comments
    )
    messages.success(
        request, _('Lugar "%(name)s" foi removido.') % {"name": place.name}
    )
    return redirect(_pending_url())


@moderator_required
@require_POST
def bulk_places_view(request):
    """Aprovar ou remover vários lugares de uma vez."""
    destination = safe_next(request, _pending_url())
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    if not ids:
        messages.error(request, _("Selecione ao menos um lugar."))
        return redirect(destination)

    action = request.POST.get("action")
    if action == "approve":
        pending = Place.objects.filter(pk__in=ids, is_approved=False, is_active=True)
        count = PlaceApproval.record(
            pending, request.user, PlaceApproval.ActionType.APPROVE
        )
        message = ngettext(
            "%(count)d lugar aprovado", "%(count)d lugares aprovados", count
        )
    elif action == "remove":
        comments, error = _removal_comments(
            request.POST.get("reason", ""), request.POST.get("comments", "").strip()
        )
        if error:
            messages.error(request, error)
            return redirect(destination)
        active = Place.objects.filter(pk__in=ids, is_active=True)
        count = PlaceApproval.record(
            active, request.user, PlaceApproval.ActionType.REJECT, comments
        )
        message = ngettext(
            "%(count)d lugar removido", "%(count)d lugares removidos", count
        )
    else:
        messages.error(request, _("Ação inválida."))
        return redirect(destination)

    messages.success(request, message % {"count": count})
    return redirect(destination)


# Filtros da lista de lugares do painel: chave -> (rótulo, filtro, ícone, tom)
STATUS_FILTERS = {
    "all": (_l("Todos"), Q(), "layers", "neutral"),
    "pending": (
        _l("Aguardando aprovação"),
        Q(is_approved=False, is_active=True),
        "hourglass",
        "warning",
    ),
    "approved": (
        _l("Aprovados"),
        Q(is_approved=True, is_active=True),
        "circle-check",
        "success",
    ),
    "featured": (
        _l("Em destaque"),
        Q(is_featured=True, is_approved=True, is_active=True),
        "star",
        "featured",
    ),
    "rejected": (_l("Removidos"), Q(is_active=False), "circle-x", "danger"),
}


@moderator_required
def backlog_view(request):
    """Lista única de lugares do painel; os cartões de status no topo filtram."""
    status_filter = request.GET.get("status", "all")
    if request.GET.get("view") == "queue":  # links antigos da "Fila de aprovação"
        status_filter = "pending"
    if status_filter not in STATUS_FILTERS:
        status_filter = "all"
    category_filter = request.GET.get("category", "all")
    search_query = request.GET.get("q", "").strip()

    places = Place.objects.filter(STATUS_FILTERS[status_filter][1])
    if search_query:
        places = places.filter(name__icontains=search_query)
    if category_filter != "all":
        places = places.filter(categories__slug=category_filter)

    # Pendentes sempre no topo, para não se perderem no histórico
    pending_first = Case(
        When(is_approved=False, is_active=True, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )
    sort = _sort(request)
    places = (
        places.select_related("created_by")
        .prefetch_related("images", "categories")
        .order_by(pending_first, sort)
        .distinct()
    )

    status_cards = [
        (key, label, Place.objects.filter(query).count(), icon, tone)
        for key, (label, query, icon, tone) in STATUS_FILTERS.items()
    ]
    context = {
        "places": places,
        "categories": Category.objects.filter(is_active=True).order_by("name"),
        "status_filter": status_filter,
        "category_filter": category_filter,
        "current_sort": sort,
        "search_query": search_query,
        "status_cards": status_cards,
    }
    return render(request, "explore/admin/backlog.html", context)


# Avaliações


@login_required
@limit("20/h", key="user")
def review_create_view(request, place_pk):
    place = get_object_or_404(Place.objects.public(), pk=place_pk)
    if PlaceReview.objects.filter(place=place, user=request.user).exists():
        messages.warning(
            request, _("Você já avaliou este lugar. Edite sua avaliação existente.")
        )
        return redirect("explore:place_detail", pk=place.pk)

    form = PlaceReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.instance.place = place
        form.instance.user = request.user
        form.save()
        messages.success(request, _("Avaliação enviada com sucesso!"))
        return redirect("explore:place_detail", pk=place.pk)
    return render(request, "explore/review_form.html", {"form": form, "place": place})


def _own_review_or_redirect(request, pk, denied_message):
    """(review, None) se o usuário pode mexer na avaliação; senão (None, redirect)."""
    review = get_object_or_404(PlaceReview, pk=pk)
    if review.user == request.user or request.user.can_moderate:
        return review, None
    messages.error(request, denied_message)
    return None, redirect("explore:place_detail", pk=review.place_id)


@login_required
@limit("30/h", key="user")
def review_edit_view(request, pk):
    review, denied = _own_review_or_redirect(
        request, pk, _("Você não tem permissão para editar esta avaliação.")
    )
    if denied:
        return denied

    form = PlaceReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Avaliação atualizada com sucesso!"))
        return redirect("explore:place_detail", pk=review.place_id)
    context = {"form": form, "place": review.place, "review": review}
    return render(request, "explore/review_form.html", context)


@login_required
@limit("30/h", key="user")
def review_delete_view(request, pk):
    review, denied = _own_review_or_redirect(
        request, pk, _("Você não tem permissão para excluir esta avaliação.")
    )
    if denied:
        return denied

    if request.method == "POST":
        review.delete()
        messages.success(request, _("Avaliação excluída com sucesso!"))
        return redirect("explore:place_detail", pk=review.place_id)
    return render(request, "explore/review_delete_confirm.html", {"review": review})


# Favoritos (o navegador guarda no localStorage; logado, o banco espelha)


def _favorite_ids(user):
    return list(Favorite.objects.filter(user=user).values_list("place_id", flat=True))


@require_POST
@limit("120/m", key="user_or_ip")
def toggle_favorite_view(request, pk):
    place = get_object_or_404(Place.objects.public(), pk=pk)
    if not request.user.is_authenticated:
        # Anônimo: a troca acontece só no localStorage
        return JsonResponse({"success": True, "message": _("Favorito atualizado")})

    deleted, _detail = Favorite.objects.filter(user=request.user, place=place).delete()
    if not deleted:
        # get_or_create: dois cliques simultâneos não quebram a restrição de unicidade
        Favorite.objects.get_or_create(user=request.user, place=place)
    return JsonResponse(
        {
            "success": True,
            "is_favorited": not deleted,
            "favorites_count": place.favorited_by.count(),
            "message": (
                _("Lugar removido dos favoritos")
                if deleted
                else _("Lugar adicionado aos favoritos")
            ),
        }
    )


@limit("60/m", method="GET")
def favorites_list_view(request):
    """Logado: favoritos do banco. Anônimo: o JS pede ?ids= com os do localStorage."""
    if request.user.is_authenticated:
        ids = list(
            Favorite.objects.filter(user=request.user)
            .order_by("-created_at")
            .values_list("place_id", flat=True)
        )
        places = Place.objects.filter(pk__in=ids)
    else:
        try:
            ids = parse_ids(request.GET.get("ids", ""))
        except ValueError:
            ids = []
        places = Place.objects.public().filter(pk__in=ids)
    by_id = {
        p.pk: p for p in places.with_ratings().prefetch_related("images", "categories")
    }
    favorites = [by_id[i] for i in ids if i in by_id]
    context = {
        "favorites": favorites,
        "favorites_count": len(favorites),
        "is_authenticated": request.user.is_authenticated,
    }
    return render(request, "explore/favorites.html", context)


@login_required
@require_POST
@limit("30/m", key="user")
def sync_favorites_view(request):
    """Mescla os favoritos do localStorage com os do banco"""
    try:
        local_ids = json.loads(request.body).get("favorites", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    if not isinstance(local_ids, list) or len(local_ids) > MAX_IDS:
        return JsonResponse({"success": False, "error": "Invalid list"}, status=400)

    existing = set(_favorite_ids(request.user))
    new_places = Place.objects.public().filter(
        pk__in=[i for i in valid_ids(local_ids) if i not in existing]
    )
    added = Favorite.objects.bulk_create(
        [Favorite(user=request.user, place=place) for place in new_places],
        ignore_conflicts=True,
    )
    return JsonResponse(
        {
            "success": True,
            "favorites": _favorite_ids(request.user),
            "added": len(added),
            "message": _("%(value)s favoritos sincronizados") % {"value": len(added)},
        }
    )


@login_required
@limit("60/m", key="user", method="GET")
def favorites_api_list_view(request):
    """IDs dos favoritos do usuário, para o JS sincronizar o localStorage"""
    favorites = _favorite_ids(request.user)
    return JsonResponse(
        {"success": True, "favorites": favorites, "count": len(favorites)}
    )
