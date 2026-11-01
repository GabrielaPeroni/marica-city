from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _l


class CategoryQuerySet(models.QuerySet):
    def with_place_counts(self):
        return self.annotate(
            public_place_count=models.Count(
                "places",
                filter=models.Q(places__is_active=True, places__is_approved=True),
            )
        )


class Category(models.Model):
    TRANSLATABLE_FIELDS = ("name", "description")

    objects = CategoryQuerySet.as_manager()

    name = models.CharField(
        max_length=100, unique=True, help_text=_l("Nome da categoria")
    )

    slug = models.SlugField(
        max_length=100, unique=True, help_text=_l("Identificador amigável para URL")
    )

    description = models.TextField(blank=True, help_text=_l("Descrição da categoria"))

    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text=_l("Classe do ícone ou emoji para a categoria"),
    )

    is_active = models.BooleanField(
        default=True, help_text=_l("Se a categoria está atualmente ativa")
    )

    display_order = models.IntegerField(
        default=0,
        help_text=_l("Ordem em que a categoria aparece (números menores primeiro)"),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text=_l("Traduções automáticas (en, es); editáveis pela equipe"),
    )

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        indexes = [
            models.Index(fields=["is_active", "display_order"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    @property
    def active_places_count(self):
        """Contagem de lugares ativos aprovados nesta categoria"""
        if hasattr(self, "public_place_count"):
            return self.public_place_count
        return self.places.filter(is_active=True, is_approved=True).count()


class PlaceQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_approved=True, is_active=True)

    def visible_to(self, user):
        """Públicos para todos; o autor vê os seus e moderadores veem todos."""
        if user.is_authenticated and user.can_moderate:
            return self
        if user.is_authenticated:
            return self.filter(
                models.Q(is_approved=True, is_active=True) | models.Q(created_by=user)
            )
        return self.public()

    def with_ratings(self):
        """Anota média e contagem de avaliações (evita uma consulta por card)."""
        return self.annotate(
            rating_avg=models.Avg("reviews__rating"),
            rating_count=models.Count("reviews", distinct=True),
        )


class Place(models.Model):
    TRANSLATABLE_FIELDS = ("name", "description")

    objects = PlaceQuerySet.as_manager()

    name = models.CharField(max_length=200, help_text=_l("Nome do lugar"))

    description = models.TextField(help_text=_l("Descrição detalhada do lugar"))

    address = models.TextField(help_text=_l("Endereço completo do lugar"))

    # Coordenadas de localização
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_l("Coordenada de latitude"),
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_l("Coordenada de longitude"),
    )

    # Relacionamentos
    categories = models.ManyToManyField(
        Category,
        related_name="places",
        blank=True,
        help_text=_l("Categorias às quais este lugar pertence"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="places",
        help_text=_l("Usuário que criou este lugar"),
    )

    # Campos de status
    is_approved = models.BooleanField(
        default=False, help_text=_l("Se o lugar foi aprovado pelo administrador")
    )

    is_active = models.BooleanField(
        default=True, help_text=_l("Se o lugar está atualmente ativo")
    )

    is_featured = models.BooleanField(
        default=False,
        help_text=_l("Em destaque na página inicial"),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text=_l("Traduções automáticas (en, es); editáveis pela equipe"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"
        indexes = [
            models.Index(fields=["is_approved", "is_active"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_pending(self):
        return not self.is_approved

    @property
    def primary_image(self):
        # Iterate the (possibly prefetched) `images` cache instead of
        # filter().first(), which always issues a fresh query and defeats
        # prefetch_related in place-list views.
        for image in self.images.all():
            if image.is_primary:
                return image
        return None

    def can_edit(self, user):
        return user.is_authenticated and (user.can_moderate or self.created_by == user)

    def ensure_primary_image(self):
        """Exatamente uma foto principal: sem nenhuma, a primeira assume; com várias, fica a primeira."""
        primaries = list(
            self.images.filter(is_primary=True).values_list("pk", flat=True)
        )
        if len(primaries) > 1:
            self.images.filter(pk__in=primaries[1:]).update(is_primary=False)
        elif not primaries:
            self.images.filter(pk=self.images.values("pk")[:1]).update(is_primary=True)

    @property
    def average_rating(self):
        """Calcula a avaliação média de todas as avaliações"""
        if hasattr(self, "rating_avg"):
            avg = self.rating_avg
        else:
            avg = self.reviews.aggregate(avg=models.Avg("rating"))["avg"]
        return round(avg, 1) if avg else None

    @property
    def review_count(self):
        """Contagem de avaliações para este lugar"""
        if hasattr(self, "rating_count"):
            return self.rating_count
        return self.reviews.count()


class PlaceImage(models.Model):
    """Imagens para lugares"""

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="images",
        help_text=_l("Lugar ao qual esta imagem pertence"),
    )

    image = models.ImageField(
        upload_to="places/images/%Y/%m/", help_text=_l("Imagem do lugar")
    )

    caption = models.CharField(
        max_length=200, blank=True, help_text=_l("Legenda ou descrição da imagem")
    )

    is_primary = models.BooleanField(
        default=False, help_text=_l("Se esta é a imagem principal/primária do lugar")
    )

    display_order = models.IntegerField(
        default=0,
        help_text=_l(
            "Ordem em que a imagem aparece na galeria (números menores primeiro)"
        ),
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True, help_text=_l("Quando a imagem foi carregada")
    )

    class Meta:
        ordering = ["display_order", "-uploaded_at"]
        verbose_name = "Imagem do Lugar"
        verbose_name_plural = "Imagens do Lugar"
        indexes = [
            models.Index(fields=["place", "display_order"]),
            models.Index(fields=["place", "is_primary"]),
        ]

    def __str__(self):
        return f"{self.place.name} - Image {self.id}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Define todas as outras imagens deste lugar como não-primárias
            PlaceImage.objects.filter(place=self.place, is_primary=True).update(
                is_primary=False
            )
        super().save(*args, **kwargs)


class PlaceApproval(models.Model):
    class ActionType(models.TextChoices):
        APPROVE = "APPROVE", "Aprovado"
        REJECT = "REJECT", "Rejeitado"
        REQUEST_CHANGES = "REQUEST_CHANGES", "Solicitar Alterações"

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="approval_history",
        help_text=_l("Lugar sendo revisado"),
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="place_reviews",
        help_text=_l("Usuário administrador que revisou o lugar"),
    )

    action = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        help_text=_l("Ação realizada pelo revisor"),
    )

    comments = models.TextField(
        blank=True, help_text=_l("Comentários ou feedback do revisor")
    )

    reviewed_at = models.DateTimeField(
        auto_now_add=True, help_text=_l("Quando a revisão foi realizada")
    )

    class Meta:
        ordering = ["-reviewed_at"]
        verbose_name = "Aprovação de Lugar"
        verbose_name_plural = "Aprovações de Lugares"
        indexes = [
            models.Index(fields=["place", "-reviewed_at"]),
            models.Index(fields=["reviewer", "-reviewed_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.place.name} - {self.get_action_display()} by {self.reviewer}"

    @classmethod
    def record(cls, places, reviewer, action, comments=""):
        """Registra a mesma decisão para cada lugar; devolve quantos foram."""
        places = list(places)
        for place in places:
            cls.objects.create(
                place=place, reviewer=reviewer, action=action, comments=comments
            )
        return len(places)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.action == self.ActionType.APPROVE:
            self.place.is_approved = True
            self.place.save(update_fields=["is_approved", "updated_at"])
        elif self.action == self.ActionType.REJECT:
            self.place.is_approved = False
            self.place.is_active = False
            self.place.save(update_fields=["is_approved", "is_active", "updated_at"])


class PlaceReview(models.Model):
    """Avaliações e classificações de usuários para lugares"""

    TRANSLATABLE_FIELDS = ("comment",)

    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text=_l("Traduções automáticas (en, es); editáveis pela equipe"),
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="reviews",
        help_text=_l("Lugar sendo avaliado"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="place_reviews_written",
        help_text=_l("Usuário que escreveu a avaliação"),
    )

    rating = models.IntegerField(
        choices=[
            (1, "1 Estrela"),
            (2, "2 Estrelas"),
            (3, "3 Estrelas"),
            (4, "4 Estrelas"),
            (5, "5 Estrelas"),
        ],
        help_text=_l("Avaliação de 1 a 5 estrelas"),
    )

    comment = models.TextField(
        help_text=_l("Comentário/feedback da avaliação"),
        max_length=1000,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Avaliação de Lugar"
        verbose_name_plural = "Avaliações de Lugares"
        unique_together = (
            "user",
            "place",
        )  # Usuário pode avaliar um lugar apenas uma vez
        indexes = [
            models.Index(fields=["place", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.place.name} ({self.rating}★)"


class Favorite(models.Model):
    """
    Modelo para rastrear favoritos do usuário (lugares salvos).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        help_text=_l("Usuário que favoritou o lugar"),
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        help_text=_l("Lugar que foi favoritado"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (
            "user",
            "place",
        )  # Usuário pode favoritar um lugar apenas uma vez
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["place"]),
        ]

    def __str__(self):
        return f"{self.user.username} favorited {self.place.name}"


class PlaceVisit(models.Model):
    """Uma visita por visitante anônimo, lugar e dia (só com consentimento de cookies)."""

    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="visits")
    visitor = models.CharField(max_length=32)
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["place", "visitor", "date"], name="unique_daily_place_visit"
            )
        ]
        indexes = [models.Index(fields=["place", "date"])]

    def __str__(self):
        return f"{self.place.name} ({self.date})"
