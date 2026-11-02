"""Every page answers correctly for each kind of visitor, and the JSON APIs keep their
contract: status, shape, methods, malformed input and how many queries they cost."""

import io
import json
import tempfile
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

import django_ratelimit.core
from PIL import Image

from apps.accounts.models import User
from apps.explore.forms import PlaceImageFormSet
from apps.explore.models import Category, Favorite, Place, PlaceReview
from apps.news.models import News, NewsCategory


class Data(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("autor", "a@example.com", "pw-12345678")
        cls.staff = User.objects.create_user(
            "chefe", "c@example.com", "pw-12345678", is_staff=True
        )
        cls.category = Category.objects.create(name="Praias", slug="praias")
        cls.place = cls.make_place("Praia Central")
        cls.hidden = cls.make_place("Pendente", is_approved=False)
        PlaceReview.objects.create(
            place=cls.place, user=cls.author, rating=5, comment="Ótimo"
        )
        event, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        cls.event = News.objects.create(
            title="Festa",
            content="Texto",
            category=event,
            author=cls.staff,
            status=News.PUBLISHED,
            event_date=timezone.now(),
        )

    @classmethod
    def make_place(cls, name, is_approved=True):
        place = Place.objects.create(
            name=name,
            description="Descrição",
            address="Rua A",
            latitude="-22.9",
            longitude="-42.8",
            created_by=cls.author,
            is_approved=is_approved,
        )
        place.categories.add(cls.category)
        return place

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)


@override_settings(RATELIMIT_ENABLE=False)
class PageStatusTests(Data):
    def public_pages(self):
        return [
            reverse("core:landing"),
            reverse("core:about"),
            reverse("explore:explore"),
            reverse("explore:category_detail", args=[self.category.slug]),
            reverse("explore:place_detail", args=[self.place.pk]),
            reverse("explore:favorites"),
            reverse("news:news_list"),
            reverse("news:news_detail", args=[self.event.slug]),
            reverse("accounts:register"),
            reverse("accounts:password_reset"),
            reverse("healthz"),
            reverse("robots_txt"),
            reverse("sitemap"),
        ]

    def moderator_pages(self):
        return [
            reverse("core:admin_dashboard"),
            reverse("core:admin_news_list"),
            reverse("explore:backlog"),
            reverse("accounts:user_management"),
        ]

    def test_public_pages_work_for_everyone(self):
        for user in (None, self.author, self.staff):
            if user:
                self.client.force_login(user)
            for url in self.public_pages():
                with self.subTest(url=url, user=user):
                    self.assertEqual(self.client.get(url, follow=True).status_code, 200)

    def test_create_place_needs_an_account(self):
        url = reverse("explore:place_create")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_moderator_pages_are_closed_to_others(self):
        for user in (None, self.author):
            if user:
                self.client.force_login(user)
            for url in self.moderator_pages():
                with self.subTest(url=url, user=user):
                    self.assertEqual(self.client.get(url).status_code, 302)

    def test_moderator_pages_open_for_staff(self):
        self.client.force_login(self.staff)
        for url in self.moderator_pages():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_unapproved_place_is_hidden_from_visitors(self):
        url = reverse("explore:place_detail", args=[self.hidden.pk])
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(RATELIMIT_ENABLE=False)
class QueryCountTests(Data):
    """Query counts must not grow with the amount of content."""

    def count(self, url):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(queries)

    def assert_flat(self, url):
        self.count(url)
        cache.clear()
        before = self.count(url)
        for i in range(10):
            place = self.make_place(f"Lugar {i}")
            PlaceReview.objects.create(
                place=place, user=self.author, rating=4, comment="Bom"
            )
        cache.clear()
        self.assertLessEqual(self.count(url), before)

    def test_listing_pages_do_not_query_per_place(self):
        for url in (
            reverse("core:landing"),
            reverse("explore:explore"),
            reverse("explore:category_detail", args=[self.category.slug]),
            reverse("explore:map_data_api"),
            reverse("explore:places_by_ids_api")
            + "?ids="
            + ",".join(str(i) for i in range(1, 40)),
        ):
            with self.subTest(url=url):
                self.assert_flat(url)

    def test_pages_stay_within_a_query_budget(self):
        for url, budget in (
            (reverse("core:landing"), 25),
            (reverse("explore:explore"), 15),
            (reverse("explore:place_detail", args=[self.place.pk]), 20),
            (reverse("news:news_list"), 15),
        ):
            cache.clear()
            with self.subTest(url=url):
                self.assertLessEqual(self.count(url), budget)


@override_settings(RATELIMIT_ENABLE=False)
class MapDataApiTests(Data):
    url = "/explore/api/map-data/"

    def test_returns_only_public_places_with_coordinates(self):
        Place.objects.create(
            name="Sem mapa",
            description="x",
            address="Rua",
            created_by=self.author,
            is_approved=True,
        )
        data = self.client.get(self.url).json()
        self.assertEqual(data["count"], 1)
        place = data["places"][0]
        self.assertEqual(place["id"], self.place.pk)
        self.assertEqual(
            set(place),
            {
                "id",
                "name",
                "image_url",
                "url",
                "rating",
                "review_count",
                "description",
                "latitude",
                "longitude",
                "category",
                "category_icon",
            },
        )
        self.assertIsInstance(place["latitude"], float)

    def test_only_get_is_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)


@override_settings(RATELIMIT_ENABLE=False)
class PlacesByIdsApiTests(Data):
    url = "/explore/api/places-by-ids/"

    def test_returns_requested_public_places(self):
        response = self.client.get(
            self.url, {"ids": f"{self.place.pk},{self.hidden.pk}"}
        )
        self.assertEqual([p["id"] for p in response.json()["places"]], [self.place.pk])

    def test_bad_input_never_breaks(self):
        for ids, status in (
            ("", 200),
            ("abc", 400),
            ("1,abc", 400),
            ("99999999999999999999999", 200),
            ("-1", 200),
            (",,,", 200),
        ):
            with self.subTest(ids=ids):
                response = self.client.get(self.url, {"ids": ids})
                self.assertEqual(response.status_code, status)

    def test_a_huge_id_list_is_cut_short(self):
        ids = ",".join(str(i) for i in range(1, 2000))
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url, {"ids": ids})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(queries), 0)


@override_settings(RATELIMIT_ENABLE=False)
class FavoritesApiTests(Data):
    list_url = "/explore/favorites/list/"
    sync_url = "/explore/favorites/sync/"

    def toggle_url(self, pk=None):
        return f"/explore/place/{pk or self.place.pk}/favorite/toggle/"

    def post_json(self, url, body):
        return self.client.post(url, json.dumps(body), content_type="application/json")

    def test_list_needs_login(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 302)

    def test_list_returns_this_users_ids(self):
        Favorite.objects.create(user=self.author, place=self.place)
        Favorite.objects.create(user=self.staff, place=self.hidden)
        self.client.force_login(self.author)
        self.assertEqual(
            self.client.get(self.list_url).json(),
            {"success": True, "favorites": [self.place.pk], "count": 1},
        )

    def test_toggle_adds_then_removes(self):
        self.client.force_login(self.author)
        first = self.client.post(self.toggle_url()).json()
        self.assertTrue(first["is_favorited"])
        self.assertEqual(first["favorites_count"], 1)
        second = self.client.post(self.toggle_url()).json()
        self.assertFalse(second["is_favorited"])
        self.assertFalse(Favorite.objects.exists())

    def test_toggle_for_a_visitor_touches_nothing(self):
        response = self.client.post(self.toggle_url())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Favorite.objects.exists())

    def test_toggle_refuses_hidden_places_and_get(self):
        self.client.force_login(self.author)
        self.assertEqual(
            self.client.post(self.toggle_url(self.hidden.pk)).status_code, 404
        )
        self.assertEqual(self.client.get(self.toggle_url()).status_code, 405)

    def test_simultaneous_toggle_does_not_break(self):
        self.client.force_login(self.author)
        Favorite.objects.create(user=self.author, place=self.place)
        with mock.patch(
            "django.db.models.query.QuerySet.delete",
            autospec=True,
            return_value=(0, {}),
        ):
            response = self.client.post(self.toggle_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_sync_merges_public_places_only(self):
        self.client.force_login(self.author)
        data = self.post_json(
            self.sync_url,
            {"favorites": [self.place.pk, self.hidden.pk, "x", 999999, True]},
        ).json()
        self.assertEqual(data["favorites"], [self.place.pk])
        self.assertEqual(data["added"], 1)

    def test_sync_is_idempotent(self):
        self.client.force_login(self.author)
        body = {"favorites": [self.place.pk]}
        self.post_json(self.sync_url, body)
        self.assertEqual(self.post_json(self.sync_url, body).json()["added"], 0)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_sync_rejects_malformed_bodies(self):
        self.client.force_login(self.author)
        for body in ([1], {"favorites": 5}, {"favorites": None}, {"favorites": "12"}):
            with self.subTest(body=body):
                self.assertEqual(self.post_json(self.sync_url, body).status_code, 400)
        response = self.client.post(
            self.sync_url, "not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Favorite.objects.exists())

    def test_sync_ignores_an_oversized_list(self):
        self.client.force_login(self.author)
        response = self.post_json(self.sync_url, {"favorites": list(range(5000))})
        self.assertEqual(response.status_code, 400)


@override_settings(RATELIMIT_ENABLE=False)
class NulCharacterTests(Data):
    """Postgres refuses NUL, so it must never reach a query (SQLite would hide this)."""

    def test_query_strings_are_refused(self):
        for url in (
            reverse("explore:explore"),
            reverse("explore:category_detail", args=[self.category.slug]),
            reverse("news:news_list"),
        ):
            for query in ("q=%00", "q=a%00b", "%00=x"):
                with self.subTest(url=url, query=query):
                    response = self.client.get(f"{url}?{query}")
                    self.assertEqual(response.status_code, 400)

    def test_forms_are_refused(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "a\x00b", "password": "x"}
        )
        self.assertEqual(response.status_code, 400)

    def test_moderator_filters_are_refused(self):
        self.client.force_login(self.staff)
        for url in (
            reverse("explore:backlog"),
            reverse("core:admin_news_list"),
            reverse("accounts:user_management"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(f"{url}?q=%00").status_code, 400)

    def test_ordinary_requests_pass(self):
        url = reverse("explore:explore")
        self.assertEqual(self.client.get(f"{url}?q=praia").status_code, 200)


@override_settings(RATELIMIT_ENABLE=False)
class LoginApiTests(Data):
    url = "/accounts/login/"

    def test_success_shape(self):
        data = self.client.post(
            self.url, {"username": "autor", "password": "pw-12345678"}
        ).json()
        self.assertEqual(set(data), {"success", "message", "username"})
        self.assertTrue(data["success"])

    def test_failures_keep_one_shape(self):
        for body, status in (
            ({}, 400),
            ({"username": "autor"}, 400),
            ({"username": "autor", "password": "errada"}, 401),
            ({"username": "ninguem", "password": "errada"}, 401),
        ):
            with self.subTest(body=body):
                response = self.client.post(self.url, body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(set(response.json()), {"success", "error"})

    def test_unknown_and_wrong_password_look_the_same(self):
        unknown = self.client.post(self.url, {"username": "x", "password": "y"})
        wrong = self.client.post(self.url, {"username": "autor", "password": "y"})
        self.assertEqual(unknown.json(), wrong.json())


@override_settings(RATELIMIT_ENABLE=False)
class GoogleApiTests(Data):
    url = "/accounts/google/"

    def test_malformed_bodies_are_refused(self):
        for body in (b"", b"not json", b"[1]", b'"x"', b"\xff", b'{"token": 5}'):
            with self.subTest(body=body):
                response = self.client.post(
                    self.url, body, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()["success"])

    def test_get_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


@override_settings(RATELIMIT_ENABLE=False)
class UserManagementApiTests(Data):
    actions = ("accounts:user_update_type", "accounts:user_toggle_status")

    def test_administrator_cannot_be_changed(self):
        admin = User.objects.create_superuser("raiz", "r@example.com", "pw-12345678")
        self.client.force_login(self.staff)
        for action in self.actions:
            with self.subTest(action=action):
                response = self.client.post(reverse(action, args=[admin.pk]))
                self.assertEqual(response.status_code, 403)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)

    def test_visitor_is_sent_to_login_and_nothing_changes(self):
        for action in self.actions:
            with self.subTest(action=action):
                response = self.client.post(reverse(action, args=[self.author.pk]))
                self.assertEqual(response.status_code, 302)
        self.author.refresh_from_db()
        self.assertTrue(self.author.is_active)
        self.assertFalse(self.author.is_staff)

    def test_unknown_user_is_404(self):
        self.client.force_login(self.staff)
        for action in self.actions:
            with self.subTest(action=action):
                self.assertEqual(
                    self.client.post(reverse(action, args=[999999])).status_code, 404
                )


class JsCatalogTests(TestCase):
    def url(self, lang):
        return reverse("javascript-catalog", args=[lang])

    def test_language_comes_from_the_url_not_the_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "pt-br"
        english = self.client.get(self.url("en")).content
        spanish = self.client.get(self.url("es")).content
        self.assertNotEqual(english, spanish)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        self.assertEqual(self.client.get(self.url("en")).content, english)

    def test_can_be_cached_without_setting_cookies(self):
        response = self.client.get(self.url("en"))
        self.assertIn("public", response["Cache-Control"])
        self.assertIn("max-age=3600", response["Cache-Control"])
        self.assertFalse(response.cookies)

    def test_unknown_language_is_404(self):
        self.assertEqual(self.client.get(self.url("xx")).status_code, 404)

    def test_pages_link_the_catalog_of_their_language(self):
        response = self.client.get(reverse("core:about"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertContains(response, f'src="{self.url("es")}"')


class HealthApiTests(Data):
    def test_shape(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.json(), {"status": "ok"})


@override_settings(RATELIMIT_ENABLE=False)
class PlaceSubmitTests(Data):
    url = "/explore/place/create/"

    def setUp(self):
        super().setUp()
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        storage = override_settings(
            MEDIA_ROOT=media.name,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
            },
        )
        storage.enable()
        self.addCleanup(storage.disable)
        self.client.force_login(self.author)

    def body(self, **overrides):
        prefix = PlaceImageFormSet().prefix
        return {
            "name": "Lugar novo",
            "description": "Descrição",
            "address": "Rua B",
            "categories": [self.category.pk],
            f"{prefix}-TOTAL_FORMS": 3,
            f"{prefix}-INITIAL_FORMS": 0,
            f"{prefix}-MIN_NUM_FORMS": 0,
            f"{prefix}-MAX_NUM_FORMS": 10,
            **{f"{prefix}-{i}-display_order": 0 for i in range(3)},
            **overrides,
        }

    def image(self, name="foto.png"):
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buffer, "PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def test_created_as_pending_with_a_primary_photo(self):
        prefix = PlaceImageFormSet().prefix
        response = self.client.post(
            self.url, self.body(**{f"{prefix}-0-image": self.image()})
        )
        place = Place.objects.get(name="Lugar novo")
        self.assertRedirects(
            response,
            reverse("explore:place_detail", args=[place.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(place.is_approved)
        self.assertEqual(place.created_by, self.author)
        self.assertTrue(place.images.get().is_primary)

    def test_refused_submissions_create_nothing(self):
        prefix = PlaceImageFormSet().prefix
        fake = SimpleUploadedFile("foto.png", b"not an image", "image/png")
        for overrides in (
            {"categories": []},
            {"name": ""},
            {"categories": [999999]},
            {f"{prefix}-0-image": fake},
            {"latitude": "abc"},
        ):
            with self.subTest(overrides=list(overrides)):
                response = self.client.post(self.url, self.body(**overrides))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Place.objects.filter(name="Lugar novo").exists())

    def test_refused_submission_does_not_preview_an_unsaved_photo(self):
        prefix = PlaceImageFormSet().prefix
        response = self.client.post(
            self.url,
            self.body(categories=[], **{f"{prefix}-0-image": self.image()}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-existing-image-url")

    def test_edit_form_previews_the_saved_photo_after_a_refused_replacement(self):
        prefix = PlaceImageFormSet().prefix
        self.client.post(self.url, self.body(**{f"{prefix}-0-image": self.image()}))
        place = Place.objects.get(name="Lugar novo")
        saved = place.images.get()
        response = self.client.post(
            reverse("explore:place_edit", args=[place.pk]),
            self.body(
                name="",
                **{
                    f"{prefix}-INITIAL_FORMS": 1,
                    f"{prefix}-0-id": saved.pk,
                    f"{prefix}-0-image": self.image("nova.png"),
                },
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, f'data-existing-image-url="{saved.image.url}"', count=1
        )
        self.assertNotContains(response, "nova.png")

    def test_cannot_approve_itself_or_claim_another_author(self):
        self.client.post(
            self.url,
            self.body(is_approved="on", is_featured="on", created_by=self.staff.pk),
        )
        place = Place.objects.get(name="Lugar novo")
        self.assertFalse(place.is_approved)
        self.assertFalse(place.is_featured)
        self.assertEqual(place.created_by, self.author)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.body()).status_code, 302)
        self.assertFalse(Place.objects.filter(name="Lugar novo").exists())


@override_settings(RATELIMIT_ENABLE=True)
class BeaconRateLimitTests(Data):
    def test_view_beacon_counts_and_is_limited(self):
        url = reverse("news:news_view_beacon", args=[self.event.slug])
        before = self.event.view_count
        self.assertEqual(self.client.post(url).status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.view_count, before + 1)
        with mock.patch.object(
            django_ratelimit.core,
            "_get_window",
            autospec=True,
            return_value=4102444800,
        ):
            statuses = {self.client.post(url).status_code for _ in range(301)}
        self.assertIn(429, statuses)

    def test_beacons_refuse_get(self):
        url = reverse("news:news_view_beacon", args=[self.event.slug])
        self.assertEqual(self.client.get(url).status_code, 405)
        visit = reverse("explore:place_visit", args=[self.place.pk])
        self.assertEqual(self.client.get(visit).status_code, 405)
