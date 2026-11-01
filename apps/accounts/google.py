"""Entrar com Google: valida o ID token no servidor e encontra ou cria a conta."""

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from .models import User


class GoogleLoginError(Exception):
    """`code` diz à view qual mensagem e status responder."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def verify_token(token):
    """Assinatura, validade, emissor e audiência (nosso client id) conferidos pelo Google."""
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        raise GoogleLoginError("not_configured")
    try:
        return id_token.verify_oauth2_token(token, Request(), client_id)
    except (ValueError, GoogleAuthError) as exc:
        raise GoogleLoginError("invalid_token") from exc


def _unique_username(email):
    base = slugify(email.split("@")[0])[:30] or "usuario"
    username = base
    while User.objects.filter(username=username).exists():
        username = f"{base}-{get_random_string(4).lower()}"
    return username


def user_from_claims(claims):
    """Conta ligada a este Google; senão, a do mesmo e-mail verificado; senão, uma nova."""
    subject = claims.get("sub")
    email = (claims.get("email") or "").strip()
    if not subject or not email or not claims.get("email_verified"):
        raise GoogleLoginError("email_not_verified")

    user = User.objects.filter(google_sub=subject).first()
    if user is None:
        matches = list(User.objects.filter(email__iexact=email)[:2])
        if len(matches) > 1:
            raise GoogleLoginError("ambiguous_email")
        if matches:
            user = matches[0]
            # Conta da equipe tem poderes demais para ser ligada só pelo e-mail
            if user.is_staff or user.is_superuser:
                raise GoogleLoginError("staff_requires_password")
            user.google_sub = subject
            user.save(update_fields=["google_sub", "updated_at"])
        else:
            user = User(
                username=_unique_username(email),
                email=email,
                first_name=(claims.get("given_name") or "")[:150],
                last_name=(claims.get("family_name") or "")[:150],
                google_sub=subject,
            )
            user.set_unusable_password()
            user.save()

    if not user.is_active:
        raise GoogleLoginError("inactive")
    return user
