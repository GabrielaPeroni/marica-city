from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from django_ratelimit import core

from apps.accounts.models import User
from apps.explore.models import Place

AJAX = {"HTTP_ACCEPT": "application/json"}


@override_settings(RATELIMIT_ENABLE=True)
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        # Janela fixa: uma sequência que cruza a virada do minuto zeraria a contagem
        patcher = mock.patch.object(
            core, "_get_window", autospec=True, return_value=4102444800
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user("ana", password="x")
        self.place = Place.objects.create(
            name="P",
            description="d",
            address="a",
            created_by=self.user,
            is_approved=True,
        )

    def tearDown(self):
        cache.clear()

    def toggle(self, **extra):
        url = reverse("explore:toggle_favorite", args=[self.place.pk])
        return self.client.post(url, **extra)

    def test_normal_heart_clicking_is_not_limited(self):
        self.client.force_login(self.user)
        for _ in range(60):
            self.assertEqual(self.toggle(**AJAX).status_code, 200)

    def test_toggle_flood_gets_json_429_with_retry_after(self):
        self.client.force_login(self.user)
        for _ in range(120):
            self.toggle(**AJAX)
        response = self.toggle(**AJAX)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertGreaterEqual(int(response["Retry-After"]), 1)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("Aguarde", body["error"])
        self.assertEqual(body["retry_after"], int(response["Retry-After"]))

    def test_fetch_without_accept_header_still_gets_json(self):
        self.client.force_login(self.user)
        for _ in range(120):
            self.toggle()
        response = self.toggle(HTTP_SEC_FETCH_DEST="empty")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_browser_gets_friendly_page(self):
        for _ in range(21):
            self.client.post(reverse("accounts:login"), {"username": "x"})
        response = self.client.post(
            reverse("accounts:login"), {"username": "x"}, HTTP_SEC_FETCH_DEST="document"
        )
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "429.html")
        self.assertIn("Retry-After", response)
        self.assertContains(response, "Aguarde", status_code=429)

    def test_login_is_limited_per_ip(self):
        for _ in range(20):
            response = self.client.post(
                reverse("accounts:login"),
                {"username": "ana", "password": "bad"},
                **AJAX,
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            reverse("accounts:login"), {"username": "ana", "password": "bad"}, **AJAX
        )
        self.assertEqual(response.status_code, 429)

    def test_map_api_is_limited(self):
        url = reverse("explore:map_data_api")
        for _ in range(30):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 429)

    def test_places_by_ids_api_is_limited(self):
        url = reverse("explore:places_by_ids_api")
        for _ in range(60):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 429)

    def test_only_searches_count_against_the_search_limit(self):
        url = reverse("explore:explore")
        for _ in range(40):
            self.assertEqual(self.client.get(url).status_code, 200)
        for _ in range(30):
            self.assertEqual(self.client.get(url, {"q": "praia"}).status_code, 200)
        self.assertEqual(self.client.get(url, {"q": "praia"}).status_code, 429)

    def test_favorites_sync_is_limited(self):
        self.client.force_login(self.user)
        url = reverse("explore:sync_favorites")
        for _ in range(30):
            self.assertEqual(
                self.client.post(
                    url, "{}", content_type="application/json"
                ).status_code,
                200,
            )
        response = self.client.post(url, "{}", content_type="application/json", **AJAX)
        self.assertEqual(response.status_code, 429)

    def test_review_creation_is_limited(self):
        self.client.force_login(self.user)
        url = reverse("explore:review_create", args=[self.place.pk])
        for _ in range(20):
            self.assertNotEqual(self.client.post(url, {}).status_code, 429)
        self.assertEqual(self.client.post(url, {}).status_code, 429)

    def test_password_reset_and_code_screens_are_limited(self):
        for name, allowed in (
            ("accounts:register_verify", 30),
            ("accounts:password_reset_confirm", 20),
            ("accounts:password_reset", 5),
        ):
            cache.clear()
            url = reverse(name)
            for _ in range(allowed):
                self.assertNotEqual(self.client.post(url, {}).status_code, 429, name)
            self.assertEqual(self.client.post(url, {}).status_code, 429, name)

    def test_limits_can_be_disabled(self):
        with override_settings(RATELIMIT_ENABLE=False):
            for _ in range(35):
                self.assertEqual(
                    self.client.get(reverse("explore:map_data_api")).status_code, 200
                )
