"""Every page answers correctly for each kind of visitor, and the JSON APIs keep their
contract: status, shape, methods, malformed input and how many queries they cost."""

import json
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

import django_ratelimit.core

from apps.accounts.models import User
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
