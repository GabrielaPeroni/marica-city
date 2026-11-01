import importlib
import json
import os
import re
import sys
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import codes

User = get_user_model()

SIGNUP_DATA = {
    "username": "newuser",
    "email": "new@example.com",
    "password1": "newpass123!",
    "password2": "newpass123!",
}


def _sent_code():
    return re.search(r"^\s*(\d{6})\s*$", mail.outbox[-1].body, re.M).group(1)


def _wrong(code):
    return "000000" if code != "000000" else "111111"


def _register(client, data=SIGNUP_DATA):
    """Cadastro completo: formulário + código recebido por e-mail"""
    client.post(reverse("accounts:register"), data)
    return client.post(reverse("accounts:register_verify"), {"code": _sent_code()})


class UserModelTests(TestCase):
    """Testes para o modelo User personalizado"""

    def test_create_user(self):
        """Testa a criação de um usuário regular"""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """Testa a criação de um superusuário"""
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin123",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_user_string_representation(self):
        """Testa a representação em string do usuário"""
        user = User.objects.create_user(username="testuser", password="pass123")
        self.assertEqual(str(user), "testuser")

    def test_user_permissions_properties(self):
        """Testa propriedades de permissões personalizadas"""
        regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        staff_user = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )

        # Testa can_create_places - todos os usuários autenticados podem criar
        self.assertTrue(regular_user.can_create_places)
        self.assertTrue(staff_user.can_create_places)

        # Testa can_moderate - apenas usuários staff podem moderar
        self.assertFalse(regular_user.can_moderate)
        self.assertTrue(staff_user.can_moderate)

    def test_all_logged_in_users_can_create_places(self):
        """Testa que todos os usuários logados podem criar lugares"""
        regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        self.assertTrue(regular_user.can_create_places)

    def test_only_staff_can_moderate(self):
        """Testa que apenas usuários staff podem moderar"""
        regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        staff_user = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )
        self.assertFalse(regular_user.can_moderate)
        self.assertTrue(staff_user.can_moderate)


class AuthenticationViewTests(TestCase):
    """Testes para views de autenticação"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_register_page_loads(self):
        """Testa que a página de registro carrega com sucesso"""
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_user_can_login(self):
        """Testa que o usuário pode fazer login com credenciais corretas via AJAX"""
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 200)  # JSON response
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["username"], "testuser")

    def test_user_cannot_login_with_wrong_password(self):
        """Testa que o usuário não pode fazer login com senha incorreta via AJAX"""
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "testuser", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 401)  # Unauthorized
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_user_registration(self):
        """Testa que um novo usuário pode se registrar"""
        response = _register(self.client)
        self.assertEqual(response.status_code, 302)  # Redirect after registration

        # Verificar que o usuário foi criado
        self.assertTrue(User.objects.filter(username="newuser").exists())
        new_user = User.objects.get(username="newuser")
        self.assertEqual(new_user.email, "new@example.com")
        self.assertFalse(new_user.is_staff)  # Usuário regular por padrão

    def test_registration_form_no_user_type_field(self):
        """Testa que o formulário de registro não mostra seleção de tipo de usuário"""
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)
        # Campo de tipo de usuário não deve estar no formulário
        self.assertNotContains(response, 'name="user_type"')

    def test_new_users_default_to_regular_account(self):
        """Testa que usuários recém-registrados são contas regulares (não staff)"""
        response = _register(self.client)
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username="newuser")
        self.assertFalse(new_user.is_staff)
        self.assertTrue(new_user.can_create_places)
        self.assertFalse(new_user.can_moderate)

    def test_logout(self):
        """Testa que o usuário pode fazer logout"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)

    def test_logout_rejects_get(self):
        """Logout só por POST, para que links ou pré-carregamentos não deslogem"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_endpoint_rejects_get_requests(self):
        """Testa que o endpoint de login só aceita POST (apenas AJAX)"""
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 405)  # Method not allowed
        data = response.json()
        self.assertFalse(data["success"])

    def test_login_dropdown_present_on_pages(self):
        """Testa que o dropdown de login está presente nas páginas"""
        # Testar na página inicial
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Entre na sua conta")
        self.assertContains(response, 'id="login-popover"')

        # Testar na página de explorar
        response = self.client.get(reverse("explore:explore"))
        self.assertContains(response, "Entre na sua conta")
        self.assertContains(response, 'id="login-popover"')

    def test_login_button_present_for_anonymous_users(self):
        """Testa que o botão de login aparece para usuários anônimos"""
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, 'id="login-popover"')
        self.assertContains(response, "Entrar")

    def test_login_button_not_present_for_authenticated_users(self):
        """Testa que o botão de login não aparece para usuários autenticados"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("core:landing"))
        # Deve mostrar Sair em vez de Entrar
        self.assertContains(response, "Sair")
        # Deve mostrar o nome de usuário
        self.assertContains(response, "testuser")

    def test_google_client_id_in_register_context(self):
        """Testa que o ID do cliente Google OAuth é passado para a página de registro"""
        response = self.client.get(reverse("accounts:register"))
        self.assertIn("GOOGLE_OAUTH_CLIENT_ID", response.context)

    def test_authenticated_user_redirected_from_register(self):
        """Testa que usuário já autenticado é redirecionado ao acessar registro"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("accounts:register"))
        self.assertRedirects(response, reverse("core:landing"))

    def test_login_rejects_missing_credentials(self):
        """Testa que o login via AJAX exige usuário e senha"""
        response = self.client.post(
            reverse("accounts:login"), {"username": "", "password": ""}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])

    def test_login_tells_inactive_user_account_is_disabled(self):
        """Senha correta em conta desativada recebe a mensagem específica"""
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("desativada", response.json()["error"])

    def test_login_does_not_reveal_inactive_account_on_wrong_password(self):
        """Senha errada em conta desativada recebe o erro genérico"""
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "testuser", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("desativada", response.json()["error"])

    def test_logout_redirects_to_next_param(self):
        """Testa que o logout redireciona para o parâmetro 'next' quando fornecido"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(reverse("accounts:logout"), {"next": "/explore/"})
        self.assertRedirects(response, "/explore/", fetch_redirect_response=False)

    def test_logout_ignores_external_next_url(self):
        """Logout must not redirect to another site via ?next= or Referer"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            reverse("accounts:logout"),
            {"next": "https://evil.example/phish"},
            HTTP_REFERER="https://evil.example/",
        )
        self.assertRedirects(
            response, reverse("core:landing"), fetch_redirect_response=False
        )

    def test_logout_falls_back_to_landing_page(self):
        """Testa que o logout redireciona para a página inicial sem 'next' ou referer"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:landing"))


class SignupEmailCodeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_sends_code_and_defers_account(self):
        response = self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        self.assertRedirects(response, reverse("accounts:register_verify"))
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_correct_code_creates_account_and_logs_in(self):
        _register(self.client)
        user = User.objects.get(username="newuser")
        self.assertTrue(user.check_password("newpass123!"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_wrong_code_is_rejected(self):
        self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        response = self.client.post(
            reverse("accounts:register_verify"), {"code": _wrong(_sent_code())}
        )
        self.assertContains(response, "Código inválido ou expirado")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_code_dies_after_max_attempts(self):
        self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        code = _sent_code()
        for _ in range(codes.MAX_ATTEMPTS):
            self.client.post(
                reverse("accounts:register_verify"), {"code": _wrong(code)}
            )
        self.client.post(reverse("accounts:register_verify"), {"code": code})
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_resend_sends_a_new_code(self):
        self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        self.client.post(reverse("accounts:resend_code", args=[codes.SIGNUP]))
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.post(
            reverse("accounts:register_verify"), {"code": _sent_code()}
        )
        self.assertRedirects(response, reverse("core:landing"))

    def test_resend_unknown_purpose_404(self):
        response = self.client.post(reverse("accounts:resend_code", args=["nope"]))
        self.assertEqual(response.status_code, 404)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("other", "NEW@example.com", "x")
        response = self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        self.assertContains(response, "Já existe uma conta com este e-mail")
        self.assertEqual(len(mail.outbox), 0)

    def test_verify_without_pending_signup_redirects(self):
        response = self.client.get(reverse("accounts:register_verify"))
        self.assertRedirects(response, reverse("accounts:register"))

    def test_smtp_failure_shows_error_instead_of_500(self):
        with mock.patch.object(codes, "send_mail", autospec=True, side_effect=OSError):
            response = self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível enviar o e-mail")


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("maria", "maria@example.com", "old-pass-9")

    def _confirm(self, code, password="brand-new-pass-7"):
        return self.client.post(
            reverse("accounts:password_reset_confirm"),
            {"code": code, "new_password1": password, "new_password2": password},
        )

    def test_reset_with_code_changes_password(self):
        self.client.post(
            reverse("accounts:password_reset"), {"email": "Maria@example.com"}
        )
        response = self._confirm(_sent_code())
        self.assertRedirects(response, reverse("core:landing"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pass-7"))

    def test_unknown_email_gets_same_response_without_mail(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_confirm"))
        self.assertEqual(len(mail.outbox), 0)

    def test_weak_password_keeps_code_valid(self):
        self.client.post(
            reverse("accounts:password_reset"), {"email": "maria@example.com"}
        )
        code = _sent_code()
        self._confirm(code, password="123")
        self._confirm(code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pass-7"))

    def test_wrong_code_keeps_old_password(self):
        self.client.post(
            reverse("accounts:password_reset"), {"email": "maria@example.com"}
        )
        response = self._confirm(_wrong(_sent_code()))
        self.assertContains(response, "Código inválido ou expirado")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-pass-9"))

    def test_login_dropdown_links_to_reset(self):
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, reverse("accounts:password_reset"))


class AutofillTests(TestCase):
    """Preenchimento do código: MailHog no dev, servidor na homologação, nunca em prod"""

    mailhog_reply = json.dumps(
        {"items": [{"Content": {"Body": "Olá\r\n\r\n    654321\r\n\r\nValidade 15"}}]}
    ).encode()

    def setUp(self):
        cache.clear()

    def _mailhog(self, email="a@example.com"):
        with mock.patch.object(codes, "urlopen", autospec=True) as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = (
                self.mailhog_reply
            )
            return codes.autofill_code(codes.SIGNUP, email), urlopen

    @override_settings(
        DEBUG=True,
        EMAIL_CODE_AUTOFILL="mailhog",
        EMAIL_CODE_AUTOFILL_DOMAINS=["*"],
        MAILHOG_API_URL="http://mailhog:8025",
    )
    def test_dev_reads_code_from_mailhog(self):
        code, _ = self._mailhog()
        self.assertEqual(code, "654321")

    @override_settings(
        DEBUG=False, EMAIL_CODE_AUTOFILL="mailhog", EMAIL_CODE_AUTOFILL_DOMAINS=["*"]
    )
    def test_mailhog_mode_needs_debug(self):
        code, urlopen = self._mailhog()
        self.assertEqual(code, "")
        urlopen.assert_not_called()

    @override_settings(EMAIL_CODE_AUTOFILL="", EMAIL_CODE_AUTOFILL_DOMAINS=["*"])
    def test_off_by_default(self):
        codes.send_code(codes.SIGNUP, "a@maricacity.test", "x")
        self.assertEqual(codes.autofill_code(codes.SIGNUP, "a@maricacity.test"), "")
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_CODE_AUTOFILL="server", EMAIL_CODE_AUTOFILL_DOMAINS=["maricacity.test"]
    )
    def test_server_mode_test_domain_skips_mail_and_prefills(self):
        response = self.client.post(
            reverse("accounts:register"),
            {**SIGNUP_DATA, "email": "ana@MaricaCity.test"},
        )
        self.assertEqual(len(mail.outbox), 0)
        page = self.client.get(response.url)
        self.assertContains(page, "Ambiente de testes")
        code = page.context["form"].initial["code"]
        self.client.post(reverse("accounts:register_verify"), {"code": code})
        self.assertTrue(
            User.objects.filter(email__iexact="ana@maricacity.test").exists()
        )

    @override_settings(
        EMAIL_CODE_AUTOFILL="server", EMAIL_CODE_AUTOFILL_DOMAINS=["maricacity.test"]
    )
    def test_server_mode_real_domain_gets_normal_flow(self):
        response = self.client.post(reverse("accounts:register"), SIGNUP_DATA)
        self.assertEqual(len(mail.outbox), 1)
        page = self.client.get(response.url)
        self.assertNotContains(page, "Ambiente de testes")
        self.assertFalse(page.context["form"].initial.get("code"))

    def _load_prod(self, **env):
        env = {"ALLOWED_HOSTS": "example.com", **env}
        with mock.patch.dict(os.environ, env):
            sys.modules.pop("config.settings.prod", None)
            try:
                return importlib.import_module("config.settings.prod")
            finally:
                sys.modules.pop("config.settings.prod", None)

    def test_prod_settings_never_autofill(self):
        prod = self._load_prod()
        self.assertEqual(prod.APP_ENV, "prod")
        self.assertEqual(prod.EMAIL_CODE_AUTOFILL, "")

    def test_test_env_autofills_only_test_domains(self):
        prod = self._load_prod(APP_ENV="test")
        self.assertEqual(prod.EMAIL_CODE_AUTOFILL, "server")
        self.assertEqual(prod.EMAIL_CODE_AUTOFILL_DOMAINS, ["maricacity.test"])

    def test_unknown_app_env_refuses_to_start(self):
        with self.assertRaises(ImproperlyConfigured):
            self._load_prod(APP_ENV="staging")


class UserManagementViewTests(TestCase):
    """Testes para a view de gerenciamento de usuários (admin)"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.staff_user = User.objects.create_user(
            username="staffer", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular",
            password="pass123",
            is_staff=False,
            email="regular@example.com",
        )
        self.inactive_user = User.objects.create_user(
            username="inactive", password="pass123", is_active=False
        )
        self.url = reverse("accounts:user_management")

    def test_requires_login(self):
        """Testa que a página exige autenticação"""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/?next={self.url}")

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem acessar a página"""
        self.client.login(username="regular", password="pass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:landing"))

    def test_loads_for_moderator_listing_everyone(self):
        """Moderadores veem todos os usuários"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["users"]), 4)

    def test_filter_by_role_staff(self):
        """Testa filtro de usuários por função (staff)"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url + "?role=staff")
        usernames = {u.username for u in response.context["users"]}
        self.assertEqual(usernames, {"admin", "staffer"})

    def test_filter_by_role_regular(self):
        """Testa filtro de usuários por função (regular)"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url + "?role=regular")
        usernames = {u.username for u in response.context["users"]}
        self.assertEqual(usernames, {"regular", "inactive"})

    def test_filter_by_status_active(self):
        """Testa filtro de usuários por status (ativos)"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url + "?status=active")
        usernames = {u.username for u in response.context["users"]}
        self.assertNotIn("inactive", usernames)

    def test_filter_by_status_inactive(self):
        """Testa filtro de usuários por status (inativos)"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url + "?status=inactive")
        usernames = {u.username for u in response.context["users"]}
        self.assertEqual(usernames, {"inactive"})

    def test_search_by_username_or_email(self):
        """Testa busca de usuários por nome ou e-mail"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(self.url + "?q=regular@example.com")
        usernames = {u.username for u in response.context["users"]}
        self.assertEqual(usernames, {"regular"})


class UserUpdateTypeViewTests(TestCase):
    """Testes para alternar o status de staff de um usuário"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem alterar tipo de usuário"""
        self.client.login(username="regular", password="pass123")
        response = self.client.post(
            reverse("accounts:user_update_type", kwargs={"user_id": self.admin.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_request_not_allowed(self):
        """Testa que requisições GET não são permitidas"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse(
                "accounts:user_update_type", kwargs={"user_id": self.regular_user.id}
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_cannot_change_own_status(self):
        """Testa que um usuário não pode alterar seu próprio status de staff"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("accounts:user_update_type", kwargs={"user_id": self.admin.id})
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])

    def test_toggles_staff_status(self):
        """Testa que o status de staff de outro usuário é alternado com sucesso"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse(
                "accounts:user_update_type", kwargs={"user_id": self.regular_user.id}
            )
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_staff"])
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)


class UserToggleStatusViewTests(TestCase):
    """Testes para alternar o status ativo de um usuário"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem alterar status ativo"""
        self.client.login(username="regular", password="pass123")
        response = self.client.post(
            reverse("accounts:user_toggle_status", kwargs={"user_id": self.admin.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_request_not_allowed(self):
        """Testa que requisições GET não são permitidas"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse(
                "accounts:user_toggle_status", kwargs={"user_id": self.regular_user.id}
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_cannot_deactivate_own_account(self):
        """Testa que um usuário não pode desativar sua própria conta"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("accounts:user_toggle_status", kwargs={"user_id": self.admin.id})
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])

    def test_toggles_active_status(self):
        """Testa que o status ativo de outro usuário é alternado com sucesso"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse(
                "accounts:user_toggle_status", kwargs={"user_id": self.regular_user.id}
            )
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["is_active"])
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_active)


class UserDeleteViewTests(TestCase):
    """Testes para a exclusão de conta de usuário pelo administrador"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem excluir usuários"""
        self.client.login(username="regular", password="pass123")
        response = self.client.post(
            reverse("accounts:user_delete", kwargs={"user_id": self.admin.id})
        )
        self.assertRedirects(
            response,
            reverse("core:landing"),
            fetch_redirect_response=False,
        )
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_cannot_delete_own_account(self):
        """Testa que um usuário não pode excluir sua própria conta"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("accounts:user_delete", kwargs={"user_id": self.admin.id})
        )
        self.assertRedirects(response, reverse("accounts:user_management"))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_get_shows_confirmation_page(self):
        """Testa que GET exibe a página de confirmação de exclusão"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("accounts:user_delete", kwargs={"user_id": self.regular_user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/user_delete_confirm.html")

    def test_post_deletes_user(self):
        """Testa que POST exclui a conta do usuário"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("accounts:user_delete", kwargs={"user_id": self.regular_user.id})
        )
        self.assertRedirects(response, reverse("accounts:user_management"))
        self.assertFalse(User.objects.filter(pk=self.regular_user.pk).exists())
