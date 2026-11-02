import json
from io import BytesIO, StringIO
from unittest import mock
from urllib.error import HTTPError

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core import content_translation as ct
from apps.core.content_translation import TranslationUnavailable, translate_pending
from apps.explore.models import Category, Place, PlaceReview
from apps.news.models import News, NewsCategory


def echo(texts, target):
    return [f"{target}:{text}" for text in texts]


def usage(count=0, limit=500_000):
    return {"character_count": count, "character_limit": limit}


@override_settings(
    DEEPL_API_KEY="key:fx",
    TRANSLATE_DAILY_CHAR_LIMIT=20_000,
    TRANSLATE_USAGE_CEILING=0.8,
    TRANSLATE_MAX_ITEM_CHARS=6_000,
)
class TranslationGuardrailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("autor", "a@example.com", "pw-12345678")
        patcher = mock.patch.object(ct, "_deepl", autospec=True, return_value=usage())
        self.deepl = patcher.start()
        self.addCleanup(patcher.stop)

    def place(self, name="Praia", description="Areia", **fields):
        fields.setdefault("is_approved", True)
        return Place.objects.create(
            name=name,
            description=description,
            address="Rua A",
            created_by=self.user,
            **fields,
        )

    def test_only_public_content_is_sent(self):
        public = self.place()
        pending = self.place("Pendente", is_approved=False)
        removed = self.place("Removido", is_active=False)
        translate_pending(ask=echo)
        for place in (public, pending, removed):
            place.refresh_from_db()
        self.assertEqual(public.translations["en"]["name"], "EN-US:Praia")
        self.assertEqual(public.translations["es"]["name"], "ES:Praia")
        self.assertEqual(pending.translations, {})
        self.assertEqual(removed.translations, {})

    def test_draft_news_and_reviews_on_hidden_places_are_not_sent(self):
        category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        draft = News.objects.create(
            title="Rascunho",
            content="Texto",
            category=category,
            author=self.user,
            status=News.DRAFT,
        )
        hidden = self.place("Oculto", is_approved=False)
        review = PlaceReview.objects.create(
            place=hidden, user=self.user, rating=5, comment="Bom"
        )
        translate_pending(ask=echo)
        draft.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(draft.translations, {})
        self.assertEqual(review.translations, {})

    def test_translated_content_is_not_paid_for_twice(self):
        self.place()
        ask = mock.Mock(spec=ct._translate_texts, side_effect=echo)
        self.assertEqual(translate_pending(ask=ask)["translated"], 1)
        ask.reset_mock()
        self.assertEqual(translate_pending(ask=ask)["translated"], 0)
        ask.assert_not_called()

    def test_daily_limit_holds_across_runs(self):
        self.place(description="x" * 100)
        self.place("Outra", description="y" * 100)
        name_cost = (len("Praia") + 100) * 2
        with override_settings(TRANSLATE_DAILY_CHAR_LIMIT=name_cost):
            first = translate_pending(ask=echo)
            second = translate_pending(ask=echo)
        self.assertEqual((first["translated"], first["stopped"]), (1, "budget"))
        self.assertEqual((second["translated"], second["stopped"]), (0, "budget"))

    def test_stops_before_the_monthly_ceiling(self):
        self.place()
        self.deepl.return_value = usage(count=400_000)
        summary = translate_pending(ask=echo)
        self.assertEqual((summary["translated"], summary["stopped"]), (0, "budget"))

    def test_oversized_item_is_skipped_and_the_rest_continue(self):
        huge = self.place("Enorme", description="x" * 6_001)
        normal = self.place("Normal")
        ask = mock.Mock(spec=ct._translate_texts, side_effect=echo)
        summary = translate_pending(ask=ask)
        self.assertEqual((summary["translated"], summary["skipped"]), (1, 1))
        huge.refresh_from_db()
        normal.refresh_from_db()
        self.assertEqual(huge.translations, {})
        self.assertIn("en", normal.translations)

    def test_places_go_before_reviews_when_budget_is_short(self):
        spam = self.place("Aberto")
        PlaceReview.objects.create(
            place=spam, user=self.user, rating=1, comment="s" * 50
        )
        cost = (len("Aberto") + len("Areia")) * 2
        with override_settings(TRANSLATE_DAILY_CHAR_LIMIT=cost):
            summary = translate_pending(ask=echo)
        self.assertEqual((summary["translated"], summary["stopped"]), (1, "budget"))
        spam.refresh_from_db()
        self.assertIn("en", spam.translations)

    def test_failure_stops_the_run_without_retrying(self):
        self.place()
        self.place("Outra")
        ask = mock.Mock(
            spec=ct._translate_texts,
            side_effect=TranslationUnavailable("HTTP Error 456"),
        )
        summary = translate_pending(ask=ask)
        self.assertEqual(summary["stopped"], "unavailable")
        self.assertEqual(ask.call_count, 1)
        self.assertIsNone(cache.get(ct._daily_key()))

    def test_partial_failure_saves_nothing(self):
        place = self.place()
        ask = mock.Mock(
            spec=ct._translate_texts,
            side_effect=[["a", "b"], TranslationUnavailable("x")],
        )
        translate_pending(ask=ask)
        place.refresh_from_db()
        self.assertEqual(place.translations, {})

    def test_run_stops_at_the_time_limit(self):
        self.place()
        with mock.patch.object(
            ct.time, "monotonic", autospec=True, side_effect=[0, 999]
        ):
            summary = translate_pending(ask=echo)
        self.assertEqual((summary["translated"], summary["stopped"]), (0, "time"))

    @override_settings(DEEPL_API_KEY="")
    def test_no_key_means_no_calls(self):
        self.place()
        self.assertEqual(translate_pending()["stopped"], "not_configured")
        self.deepl.assert_not_called()

    def test_command_reports_why_it_stopped(self):
        self.deepl.side_effect = TranslationUnavailable("down")
        err = StringIO()
        call_command("translate_content", stdout=StringIO(), stderr=err)
        self.assertIn("DeepL", err.getvalue())


@override_settings(DEEPL_API_KEY="abc:fx")
class DeeplClientTests(TestCase):
    def response(self, payload):
        return BytesIO(json.dumps(payload).encode())

    def test_request_uses_the_free_host_and_header_auth(self):
        with mock.patch.object(ct.urllib.request, "urlopen", autospec=True) as urlopen:
            urlopen.return_value = self.response({"translations": [{"text": "Beach"}]})
            self.assertEqual(ct._translate_texts(["Praia"], "EN-US"), ["Beach"])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api-free.deepl.com/v2/translate")
        self.assertEqual(request.get_header("Authorization"), "DeepL-Auth-Key abc:fx")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], ct.REQUEST_TIMEOUT)
        body = json.loads(request.data)
        self.assertEqual(body["source_lang"], "PT")
        self.assertEqual(body["target_lang"], "EN-US")

    @override_settings(DEEPL_API_KEY="abc")
    def test_paid_key_uses_the_paid_host(self):
        with mock.patch.object(ct.urllib.request, "urlopen", autospec=True) as urlopen:
            urlopen.return_value = self.response(usage())
            ct._deepl("/v2/usage")
        self.assertEqual(
            urlopen.call_args.args[0].full_url, "https://api.deepl.com/v2/usage"
        )

    def test_quota_error_and_short_reply_become_unavailable(self):
        error = HTTPError("u", 456, "Quota exceeded", {}, BytesIO())
        with mock.patch.object(
            ct.urllib.request, "urlopen", autospec=True, side_effect=error
        ):
            with self.assertRaises(TranslationUnavailable):
                ct._translate_texts(["Praia"], "ES")
        with mock.patch.object(ct.urllib.request, "urlopen", autospec=True) as urlopen:
            urlopen.return_value = self.response({"translations": []})
            with self.assertRaises(TranslationUnavailable):
                ct._translate_texts(["Praia"], "ES")


class CronTranslateViewTests(TestCase):
    def setUp(self):
        self.url = reverse("cron_translate_content")

    @override_settings(CRON_SECRET="s3cret")
    def test_requires_the_secret(self):
        with mock.patch("apps.core.views.translate_pending", autospec=True) as run:
            for headers in ({}, {"HTTP_AUTHORIZATION": "Bearer wrong"}):
                self.assertEqual(self.client.get(self.url, **headers).status_code, 401)
        run.assert_not_called()

    @override_settings(CRON_SECRET="")
    def test_empty_secret_never_authorizes(self):
        with mock.patch("apps.core.views.translate_pending", autospec=True) as run:
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer ")
        self.assertEqual(response.status_code, 401)
        run.assert_not_called()

    @override_settings(CRON_SECRET="s3cret")
    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    @override_settings(CRON_SECRET="s3cret")
    def test_runs_and_reports(self):
        summary = {"translated": 2, "skipped": 0, "chars": 10, "stopped": ""}
        with mock.patch(
            "apps.core.views.translate_pending", autospec=True, return_value=summary
        ):
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), summary)

    @override_settings(CRON_SECRET="s3cret")
    def test_unavailable_is_reported_as_503(self):
        summary = {"translated": 0, "skipped": 0, "chars": 0, "stopped": "unavailable"}
        with mock.patch(
            "apps.core.views.translate_pending", autospec=True, return_value=summary
        ):
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(response.status_code, 503)


class CategoryNotSentWhenInactiveTests(TestCase):
    @override_settings(DEEPL_API_KEY="k:fx")
    def test_inactive_category_is_ignored(self):
        cache.clear()
        category = Category.objects.create(name="Velha", slug="velha", is_active=False)
        with mock.patch.object(ct, "_deepl", autospec=True, return_value=usage()):
            summary = translate_pending(ask=echo)
        self.assertEqual(summary["translated"], 0)
        category.refresh_from_db()
        self.assertEqual(category.translations, {})
