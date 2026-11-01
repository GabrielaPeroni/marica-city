import json
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts import google
from apps.accounts.models import User

CLAIMS = {
    "sub": "google-123",
    "email": "ana@example.com",
    "email_verified": True,
    "given_name": "Ana",
    "family_name": "Souza",
}


@override_settings(GOOGLE_OAUTH_CLIENT_ID="client-id", RATELIMIT_ENABLE=False)
class GoogleLoginTests(TestCase):
    def setUp(self):
        self.url = reverse("accounts:google_login")
        patcher = mock.patch.object(
            google.id_token,
            "verify_oauth2_token",
            autospec=True,
            return_value=dict(CLAIMS),
        )
        self.verify = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, body=None, client=None):
        return (client or self.client).post(
            self.url,
            json.dumps({"token": "t"} if body is None else body),
            content_type="application/json",
        )

    def logged_in_user(self):
        return self.client.session.get("_auth_user_id")

    def test_new_user_is_created_without_a_password(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(google_sub="google-123")
        self.assertEqual(user.email, "ana@example.com")
        self.assertEqual(user.username, "ana")
        self.assertEqual(user.first_name, "Ana")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertEqual(self.logged_in_user(), str(user.pk))

    def test_token_is_checked_against_our_client_id(self):
        self.post()
        self.assertEqual(self.verify.call_args.args[0], "t")
        self.assertEqual(self.verify.call_args.args[2], "client-id")

    def test_linked_account_signs_in_even_if_google_email_changed(self):
        user = User.objects.create_user(
            "ana", "old@example.com", google_sub="google-123"
        )
        self.post()
        self.assertEqual(self.logged_in_user(), str(user.pk))
        self.assertEqual(User.objects.count(), 1)

    def test_verified_email_links_an_existing_account(self):
        user = User.objects.create_user("ana.s", "ANA@example.com", "pw-12345678")
        self.post()
        user.refresh_from_db()
        self.assertEqual(user.google_sub, "google-123")
        self.assertTrue(user.has_usable_password())
        self.assertEqual(self.logged_in_user(), str(user.pk))

    def test_taken_username_gets_a_suffix(self):
        User.objects.create_user("ana", "other@example.com")
        self.post()
        username = User.objects.get(google_sub="google-123").username
        self.assertTrue(username.startswith("ana-"))

    def test_unverified_email_is_refused(self):
        self.verify.return_value = {**CLAIMS, "email_verified": False}
        User.objects.create_user("victim", "ana@example.com", "pw-12345678")
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.logged_in_user())
        self.assertIsNone(User.objects.get(username="victim").google_sub)

    def test_staff_account_is_never_linked_by_email(self):
        admin = User.objects.create_user(
            "chefe", "ana@example.com", "pw-12345678", is_staff=True
        )
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.logged_in_user())
        admin.refresh_from_db()
        self.assertIsNone(admin.google_sub)

    def test_duplicate_email_is_refused(self):
        User.objects.create_user("a1", "ana@example.com")
        User.objects.create_user("a2", "ana@example.com")
        self.assertEqual(self.post().status_code, 409)
        self.assertIsNone(self.logged_in_user())

    def test_deactivated_account_is_refused(self):
        User.objects.create_user(
            "ana", "ana@example.com", google_sub="google-123", is_active=False
        )
        self.assertEqual(self.post().status_code, 403)
        self.assertIsNone(self.logged_in_user())

    def test_invalid_token_is_refused(self):
        self.verify.side_effect = ValueError("bad signature")
        self.assertEqual(self.post().status_code, 401)
        self.assertIsNone(self.logged_in_user())
        self.assertEqual(User.objects.count(), 0)

    def test_malformed_requests_are_refused(self):
        for body in ({}, {"token": 1}, ["t"]):
            self.assertEqual(self.post(body).status_code, 400)
        response = self.client.post(
            self.url, "not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.verify.assert_not_called()

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_missing_client_id_is_reported(self):
        self.assertEqual(self.post().status_code, 503)
        self.verify.assert_not_called()

    def test_csrf_is_enforced(self):
        response = self.post(client=Client(enforce_csrf_checks=True))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)


class GoogleHeadersTests(TestCase):
    def test_popup_and_origin_headers_allow_google_sign_in(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(
            response["Cross-Origin-Opener-Policy"], "same-origin-allow-popups"
        )
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
