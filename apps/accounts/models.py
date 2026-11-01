from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _l


class User(AbstractUser):
    bio = models.TextField(blank=True, null=True, help_text=_l("Biografia do usuário"))

    # Informações de contato
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_l("Número de telefone de contato"),
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text=_l("E-mail de contato público (diferente do e-mail de login)"),
    )
    contact_website = models.URLField(
        blank=True, null=True, help_text=_l("Website ou URL de rede social")
    )

    # Identificador estável da conta Google (o e-mail dela pode mudar)
    google_sub = models.CharField(
        max_length=255, unique=True, blank=True, null=True, editable=False
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username

    @property
    def can_create_places(self):
        """Todo usuário logado pode cadastrar lugares (ficam pendentes até a aprovação)"""
        return self.is_authenticated

    @property
    def can_moderate(self):
        """Equipe (staff) e superusuário moderam lugares, eventos e usuários"""
        return self.is_staff or self.is_superuser
