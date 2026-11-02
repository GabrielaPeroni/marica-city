import json
import logging
import smtplib

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.http import require_POST

from apps.core.decorators import moderator_required
from apps.core.ratelimit import limit
from apps.core.utils import local_url

from . import codes, google
from .forms import (
    EmailCodeForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    UserRegistrationForm,
)
from .models import User

logger = logging.getLogger(__name__)

# A conta só é criada depois que o código enviado ao e-mail é confirmado
SIGNUP_SESSION = "pending_signup"
RESET_SESSION = "password_reset_email"

CODE_SUBJECTS = {
    codes.SIGNUP: _l("Seu código de cadastro no MaricaCity"),
    codes.PASSWORD_RESET: _l("Código para redefinir sua senha no MaricaCity"),
}


def _pending_email(request, purpose):
    if purpose == codes.SIGNUP:
        return request.session.get(SIGNUP_SESSION, {}).get("email")
    return request.session.get(RESET_SESSION)


def _send_code(request, purpose, email):
    try:
        codes.send_code(purpose, email, str(CODE_SUBJECTS[purpose]))
    except (OSError, smtplib.SMTPException):
        logger.exception("Falha ao enviar código de %s", purpose)
        messages.error(
            request,
            _("Não foi possível enviar o e-mail agora. Tente novamente em instantes."),
        )
        return False
    return True


def _render_code_page(request, form, email, purpose, **context):
    autofill = ""
    if request.method == "GET":
        autofill = codes.autofill_code(purpose, email)
        form.initial["code"] = autofill
    context.update(
        {
            "form": form,
            "email": email,
            "resend_purpose": purpose,
            "autofilled": bool(autofill),
            "code_minutes": codes.CODE_TTL // 60,
            "code_attempts": codes.MAX_ATTEMPTS,
        }
    )
    return render(request, "accounts/email_code.html", context)


@limit("10/h")
def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:landing")

    form = UserRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        request.session[SIGNUP_SESSION] = {
            "username": user.username,
            "email": user.email,
            "password": user.password,  # já com hash
        }
        if _send_code(request, codes.SIGNUP, user.email):
            return redirect("accounts:register_verify")
    return render(request, "accounts/register.html", {"form": form})


@limit("30/h")
def register_verify_view(request):
    pending = request.session.get(SIGNUP_SESSION)
    if not pending:
        return redirect("accounts:register")

    form = EmailCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if codes.check_code(codes.SIGNUP, pending["email"], form.cleaned_data["code"]):
            del request.session[SIGNUP_SESSION]
            taken = User.objects.filter(
                Q(username__iexact=pending["username"])
                | Q(email__iexact=pending["email"])
            ).exists()
            if taken:
                messages.error(
                    request,
                    _(
                        "Esse nome de usuário ou e-mail acabou de ser usado. Tente outro."
                    ),
                )
                return redirect("accounts:register")
            user = User.objects.create(**pending)
            login(request, user)
            messages.success(
                request, _("Cadastro realizado com sucesso! Bem-vindo ao MaricaCity.")
            )
            return redirect("core:landing")
        form.add_error("code", _("Código inválido ou expirado."))

    return _render_code_page(
        request,
        form,
        pending["email"],
        codes.SIGNUP,
        title=_("Confirme seu e-mail"),
        submit_label=_("Confirmar cadastro"),
    )


def _reset_user(email):
    # Contas antigas podem repetir e-mail; nesse caso não há como saber qual redefinir
    users = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
    return users[0] if len(users) == 1 else None


@limit("5/h")
def password_reset_view(request):
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        # Mesma resposta exista ou não a conta, para não revelar quem está cadastrado
        if _reset_user(email) is None or _send_code(
            request, codes.PASSWORD_RESET, email
        ):
            request.session[RESET_SESSION] = email
            return redirect("accounts:password_reset_confirm")
    return render(
        request,
        "accounts/email_code.html",
        {
            "form": form,
            "title": _("Esqueci minha senha"),
            "subtitle": _("Informe o e-mail da sua conta para receber um código."),
            "submit_label": _("Enviar código"),
        },
    )


@limit("20/h")
def password_reset_confirm_view(request):
    email = request.session.get(RESET_SESSION)
    if not email:
        return redirect("accounts:password_reset")

    user = _reset_user(email)
    form = PasswordResetConfirmForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        if user and codes.check_code(codes.PASSWORD_RESET, email, code):
            user.set_password(form.cleaned_data["new_password1"])
            user.save()
            del request.session[RESET_SESSION]
            messages.success(
                request, _("Senha alterada! Entre com a nova senha no menu Entrar.")
            )
            return redirect("core:landing")
        form.add_error("code", _("Código inválido ou expirado."))

    return _render_code_page(
        request,
        form,
        email,
        codes.PASSWORD_RESET,
        title=_("Redefinir senha"),
        submit_label=_("Salvar nova senha"),
    )


@require_POST
@limit("5/h")
def resend_code_view(request, purpose):
    if purpose not in CODE_SUBJECTS:
        raise Http404
    email = _pending_email(request, purpose)
    if not email:
        return redirect("core:landing")
    target = {
        codes.SIGNUP: "accounts:register_verify",
        codes.PASSWORD_RESET: "accounts:password_reset_confirm",
    }[purpose]
    if purpose == codes.SIGNUP or _reset_user(email):
        if not _send_code(request, purpose, email):
            return redirect(target)
    messages.success(request, _("Enviamos um novo código."))
    return redirect(target)


def _json_error(message, status):
    return JsonResponse({"success": False, "error": message}, status=status)


@limit("20/m")
@limit("100/h")
def login_view(request):
    """Login do menu "Entrar" (AJAX): responde em JSON"""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            return _json_error(_("Por favor, preencha todos os campos."), 400)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Bem-vindo de volta, %(username)s!")
                    % {"username": user.username},
                    "username": user.username,
                }
            )
        # authenticate() devolve None para contas inativas; só revelamos a
        # desativação a quem acertou a senha.
        inactive = User.objects.filter(username=username, is_active=False).first()
        if inactive and inactive.check_password(password):
            return _json_error(
                _("Sua conta foi desativada. Entre em contato com o administrador."),
                403,
            )
        return _json_error(_("Nome de usuário ou senha incorretos."), 401)

    return _json_error(_("Método não permitido"), 405)


def _google_errors():
    return {
        "not_configured": (_("O login com Google não está disponível agora."), 503),
        "invalid_token": (_("Não foi possível validar sua conta Google."), 401),
        "email_not_verified": (
            _("Sua conta Google precisa ter um e-mail verificado."),
            403,
        ),
        "ambiguous_email": (
            _("Há mais de uma conta com este e-mail. Entre com seu usuário e senha."),
            409,
        ),
        "staff_requires_password": (
            _("Contas da equipe entram com usuário e senha."),
            403,
        ),
        "inactive": (
            _("Sua conta foi desativada. Entre em contato com o administrador."),
            403,
        ),
    }


@require_POST
@limit("20/m")
def google_login_view(request):
    """Recebe o ID token do botão do Google, valida e abre a sessão"""
    try:
        token = json.loads(request.body or b"{}").get("token")
    except (ValueError, AttributeError):
        token = None
    if not token or not isinstance(token, str):
        return _json_error(_("Requisição inválida."), 400)
    try:
        user = google.user_from_claims(google.verify_token(token))
    except google.GoogleLoginError as exc:
        return _json_error(*_google_errors()[exc.code])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse(
        {
            "success": True,
            "message": _("Bem-vindo de volta, %(username)s!")
            % {"username": user.username},
            "username": user.username,
        }
    )


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, _("Você saiu com sucesso."))

    # Volta para a página de origem, ou para a inicial
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(local_url(request, next_url, "core:landing"))


# Gerenciamento de usuários (painel)

ROLE_FILTERS = {
    "admin": Q(is_superuser=True),
    "staff": Q(is_staff=True, is_superuser=False),
    "regular": Q(is_staff=False, is_superuser=False),
}
STATUS_FILTERS = {"active": Q(is_active=True), "inactive": Q(is_active=False)}


@moderator_required
def user_management_view(request):
    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")

    users = User.objects.filter(
        ROLE_FILTERS.get(role_filter, Q()), STATUS_FILTERS.get(status_filter, Q())
    )
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    context = {
        # Administrador primeiro, depois moderadores, depois os demais
        "users": users.order_by("-is_superuser", "-is_staff", "-created_at"),
        "role_filter": role_filter,
        "status_filter": status_filter,
        "search_query": search_query,
    }
    return render(request, "accounts/user_management.html", context)


def _managed_user(request, user_id, self_error):
    """(usuário, None) se o moderador pode alterá-lo; senão (None, resposta de erro).

    O administrador é protegido e ninguém altera a própria conta por aqui.
    """
    if not request.user.can_moderate:
        return None, _json_error(_("Sem permissão"), 403)
    if request.method != "POST":
        return None, _json_error(_("Método não permitido"), 405)
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        return None, _json_error(_("O administrador não pode ser alterado."), 403)
    if user == request.user:
        return None, _json_error(self_error, 400)
    return user, None


@login_required
@limit("60/m", key="user")
def user_update_type_view(request, user_id):
    """Alterna entre moderador e usuário comum"""
    user, error = _managed_user(
        request, user_id, _("Você não pode alterar seu próprio status")
    )
    if error:
        return error
    user.is_staff = not user.is_staff
    user.save(update_fields=["is_staff"])
    role_display = _("Moderador") if user.is_staff else _("Regular")
    return JsonResponse(
        {
            "success": True,
            "message": _("Status de %(username)s alterado para %(role_display)s.")
            % {"username": user.username, "role_display": role_display},
            "role_display": role_display,
            "is_staff": user.is_staff,
        }
    )


@login_required
@limit("60/m", key="user")
def user_toggle_status_view(request, user_id):
    """Ativa ou desativa a conta"""
    user, error = _managed_user(
        request, user_id, _("Você não pode desativar sua própria conta")
    )
    if error:
        return error
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    message = (
        _("Usuário %(username)s ativado com sucesso.")
        if user.is_active
        else _("Usuário %(username)s desativado com sucesso.")
    )
    return JsonResponse(
        {
            "success": True,
            "is_active": user.is_active,
            "message": message % {"username": user.username},
        }
    )


@moderator_required
@limit("30/m", key="user")
def user_delete_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, _("O administrador não pode ser excluído."))
        return redirect("accounts:user_management")
    if user == request.user:
        messages.error(request, _("Você não pode excluir sua própria conta."))
        return redirect("accounts:user_management")

    if request.method == "POST":
        user.delete()
        messages.success(
            request,
            _("Usuário %(username)s excluído com sucesso.")
            % {"username": user.username},
        )
        return redirect("accounts:user_management")
    return render(
        request, "accounts/user_delete_confirm.html", {"user_to_delete": user}
    )
