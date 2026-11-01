from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.news import event_crawler
from apps.news.forms import NewsForm
from apps.news.models import EventCandidate, News, NewsCategory


class NewsCategoryModelTests(TestCase):
    """Test suite for NewsCategory model"""

    def test_create_news_category(self):
        """Test creating a news category (or getting existing from migration)"""
        category, created = NewsCategory.objects.get_or_create(
            name=NewsCategory.NEWS,
            defaults={"description": "Latest news", "icon": "📰"},
        )
        self.assertEqual(category.name, NewsCategory.NEWS)
        self.assertEqual(str(category), "Noticias")

    def test_category_choices(self):
        """Test that all category choices work"""
        news_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        event_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        announcement_cat, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.ANNOUNCEMENT
        )

        self.assertEqual(news_cat.get_name_display(), "Noticias")
        self.assertEqual(event_cat.get_name_display(), "Eventos")
        self.assertEqual(announcement_cat.get_name_display(), "Anuncios")


class NewsModelTests(TestCase):
    """Test suite for News model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testauthor", password="testpass123", is_staff=True
        )
        self.category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.NEWS, defaults={"description": "Latest news"}
        )

    def test_create_news(self):
        """Test creating a news article"""
        news = News.objects.create(
            title="Test News Article",
            content="This is test content",
            author=self.user,
            category=self.category,
            status=News.PUBLISHED,
        )
        self.assertEqual(news.title, "Test News Article")
        self.assertEqual(news.status, News.PUBLISHED)
        self.assertIsNotNone(news.slug)  # Auto-generated slug
        self.assertIsNotNone(news.publish_date)  # Auto-set on publish

    def test_news_string_representation(self):
        """Test the string representation of news"""
        news = News.objects.create(
            title="Test News",
            content="Content",
            author=self.user,
            category=self.category,
            publish_date=timezone.now(),
        )
        self.assertEqual(str(news), "Test News")

    def test_news_auto_slug_generation(self):
        """Test that slug is auto-generated from title"""
        news = News.objects.create(
            title="Test News Article",
            content="Content",
            author=self.user,
            category=self.category,
            publish_date=timezone.now(),
        )
        self.assertEqual(news.slug, "test-news-article")

    def test_news_defaults_to_draft(self):
        """Test that new news defaults to draft status"""
        news = News.objects.create(
            title="Draft News",
            content="Content",
            author=self.user,
            category=self.category,
            publish_date=timezone.now(),
        )
        self.assertEqual(news.status, News.DRAFT)

    def test_news_is_event_property(self):
        """Test is_event property for event category"""
        event_category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)

        news = News.objects.create(
            title="Regular News",
            content="Content",
            author=self.user,
            category=self.category,
            publish_date=timezone.now(),
        )

        event = News.objects.create(
            title="Event News",
            content="Content",
            author=self.user,
            category=event_category,
            publish_date=timezone.now(),
            event_date=timezone.now(),
        )

        self.assertFalse(news.is_event)
        self.assertTrue(event.is_event)

    def test_slug_collision_appends_incrementing_suffix(self):
        """Test creating multiple News with the same title generates unique slugs"""
        first = News.objects.create(
            title="Duplicate Title",
            content="Content",
            author=self.user,
            category=self.category,
        )
        second = News.objects.create(
            title="Duplicate Title",
            content="Content",
            author=self.user,
            category=self.category,
        )
        self.assertEqual(first.slug, "duplicate-title")
        self.assertEqual(second.slug, "duplicate-title-1")

    def test_publish_date_reset_when_pk_set_but_row_missing(self):
        """Regression path: if an object has a pk assigned but no matching
        row exists yet (News.objects.get raises DoesNotExist), publishing
        it should still set publish_date to now rather than crash."""
        news = News(
            pk=999999,
            title="Phantom Pk News",
            content="Content",
            author=self.user,
            category=self.category,
            status=News.PUBLISHED,
            publish_date=timezone.now() + timezone.timedelta(days=10),
        )
        news.save()
        self.assertLessEqual(news.publish_date, timezone.now())

    def test_future_publish_date_reset_to_now_on_first_publish(self):
        """Test a brand new PUBLISHED item with a future publish_date gets reset to now"""
        future_date = timezone.now() + timezone.timedelta(days=30)
        news = News.objects.create(
            title="Future Dated News",
            content="Content",
            author=self.user,
            category=self.category,
            status=News.PUBLISHED,
            publish_date=future_date,
        )
        self.assertLess(news.publish_date, future_date)

    def test_auto_publish_date_on_status_change(self):
        """Test that publish_date is auto-set when status changes to PUBLISHED"""
        # Create draft news
        news = News.objects.create(
            title="Draft News",
            content="Content",
            author=self.user,
            category=self.category,
            status=News.DRAFT,
        )

        # publish_date should not be set or be in future for drafts
        news.publish_date

        # Change status to published
        news.status = News.PUBLISHED
        news.save()

        # publish_date should now be set to current time
        self.assertIsNotNone(news.publish_date)
        self.assertLessEqual(
            news.publish_date, timezone.now() + timezone.timedelta(seconds=1)
        )


class NewsFormEventDateValidationTests(TestCase):
    """NewsForm must reject an event ending before it starts"""

    def setUp(self):
        self.event_category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.EVENT
        )

    def _base_data(self, **overrides):
        data = {
            "title": "Some Event",
            "category": self.event_category.pk,
            "content": "Content",
            "excerpt": "",
            "event_date": "2026-06-10T10:00",
            "event_end_date": "2026-06-12T10:00",
            "event_location": "Praça Central",
            "status": News.DRAFT,
        }
        data.update(overrides)
        return data

    def test_valid_event_dates_pass(self):
        form = NewsForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_event_end_date_before_start_date_is_invalid(self):
        form = NewsForm(
            data=self._base_data(
                event_date="2026-06-12T10:00",
                event_end_date="2026-06-10T10:00",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("event_end_date", form.errors)


class EventsListViewTests(TestCase):
    """The public page lists published events only"""

    def setUp(self):
        self.url = reverse("news:news_list")
        self.user = User.objects.create_user(username="testauthor")
        self.news_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.event_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        now = timezone.now()
        self.upcoming = self._make("Upcoming Event", now + timedelta(days=3))
        self.past = self._make("Past Event", now - timedelta(days=10))
        self.older_past = self._make("Older Past Event", now - timedelta(days=60))
        self.draft = self._make(
            "Draft Event", now + timedelta(days=3), status=News.DRAFT
        )
        self.headline = News.objects.create(
            title="Press Headline",
            content="c",
            author=self.user,
            category=self.news_cat,
            status=News.PUBLISHED,
            publish_date=now,
            source_name="Jornal X",
            source_url="https://example.com/x",
        )

    def _make(self, title, when, status=News.PUBLISHED):
        return News.objects.create(
            title=title,
            content="c",
            author=self.user,
            category=self.event_cat,
            status=status,
            publish_date=timezone.now() - timedelta(days=90),
            event_date=when,
            event_location="Orla",
        )

    def test_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/news_list.html")

    def test_lists_only_published_events(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Upcoming Event")
        self.assertContains(response, "Past Event")
        self.assertNotContains(response, "Draft Event")
        self.assertNotContains(response, "Press Headline")

    def test_past_events_section_is_paginated_newest_first(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["agenda"], [self.upcoming])
        self.assertEqual(
            list(response.context["news_items"]), [self.past, self.older_past]
        )
        self.assertContains(response, "Eventos anteriores")
        self.assertNotContains(response, "Na imprensa")

    def test_past_events_paginate_by_twelve(self):
        for i in range(12):
            self._make(f"Extra {i}", timezone.now() - timedelta(days=100 + i))
        first = self.client.get(self.url)
        self.assertEqual(len(first.context["news_items"]), 12)
        second = self.client.get(self.url + "?page=2")
        self.assertEqual(len(second.context["news_items"]), 2)
        self.assertEqual(second.context["agenda"], [])


class EventDetailViewTests(TestCase):
    """Only events have a public detail page"""

    def setUp(self):
        self.user = User.objects.create_user(username="testauthor")
        self.news_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.event_cat, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        now = timezone.now()
        self.event = self._make("Test Event", "test-event", now - timedelta(days=5))
        self.next_event = self._make(
            "Next Event", "next-event", now + timedelta(days=5)
        )
        self.url = reverse("news:news_detail", kwargs={"slug": self.event.slug})

    def _make(self, title, slug, when):
        return News.objects.create(
            title=title,
            slug=slug,
            content="Full content of the event",
            author=self.user,
            category=self.event_cat,
            publish_date=timezone.now() - timedelta(days=30),
            status=News.PUBLISHED,
            event_date=when,
            event_location="Orla",
        )

    def test_detail_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/news_detail.html")
        self.assertContains(response, "Full content of the event")

    def test_detail_increments_view_count(self):
        self.client.get(self.url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.view_count, 1)

    def test_related_events_prefer_upcoming(self):
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["related_news"]), [self.next_event])

    def test_non_event_detail_is_404(self):
        article = News.objects.create(
            title="General Article",
            slug="general-article",
            content="c",
            author=self.user,
            category=self.news_cat,
            publish_date=timezone.now(),
            status=News.PUBLISHED,
        )
        url = reverse("news:news_detail", kwargs={"slug": article.slug})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_draft_event_is_404(self):
        self.event.status = News.DRAFT
        self.event.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unknown_slug_is_404(self):
        url = reverse("news:news_detail", kwargs={"slug": "non-existent"})
        self.assertEqual(self.client.get(url).status_code, 404)


class LegacyNewsRedirectTests(TestCase):
    def test_urls_live_under_eventos(self):
        self.assertEqual(reverse("news:news_list"), "/eventos/")
        self.assertEqual(
            reverse("news:news_detail", kwargs={"slug": "x"}), "/eventos/x/"
        )

    def test_news_list_redirects_permanently(self):
        response = self.client.get("/news/")
        self.assertRedirects(
            response, "/eventos/", status_code=301, fetch_redirect_response=False
        )

    def test_news_detail_redirects_permanently(self):
        response = self.client.get("/news/some-event/")
        self.assertRedirects(
            response,
            "/eventos/some-event/",
            status_code=301,
            fetch_redirect_response=False,
        )


class NewsEventPropertyTests(TestCase):
    """Tests for is_past_event on event and non-event news"""

    def setUp(self):
        self.user = User.objects.create_user(username="author", password="pass123")
        self.news_category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.NEWS
        )
        self.event_category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.EVENT
        )

    def test_non_event_is_never_upcoming_or_past(self):
        """Test regular news items are neither upcoming nor past events"""
        article = News.objects.create(
            title="Regular Article",
            content="Content",
            author=self.user,
            category=self.news_category,
            event_date=timezone.now() + timezone.timedelta(days=1),
        )
        self.assertFalse(article.is_past_event)

    def test_event_without_date_is_neither(self):
        """Test an event with no event_date is treated as neither upcoming nor past"""
        event = News.objects.create(
            title="Dateless Event",
            content="Content",
            author=self.user,
            category=self.event_category,
        )
        self.assertFalse(event.is_past_event)

    def test_future_event_is_upcoming(self):
        """Test an event with a future date is upcoming, not past"""
        event = News.objects.create(
            title="Future Event",
            content="Content",
            author=self.user,
            category=self.event_category,
            event_date=timezone.now() + timezone.timedelta(days=5),
        )
        self.assertFalse(event.is_past_event)

    def test_past_event_is_past(self):
        """Test an event with a past date is past, not upcoming"""
        event = News.objects.create(
            title="Past Event",
            content="Content",
            author=self.user,
            category=self.event_category,
            event_date=timezone.now() - timezone.timedelta(days=5),
        )
        self.assertTrue(event.is_past_event)


class NewsExcerptAutoGenerationTests(TestCase):
    """Tests for automatic excerpt generation on save"""

    def setUp(self):
        self.user = User.objects.create_user(username="author", password="pass123")
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)

    def test_short_content_used_as_excerpt_verbatim(self):
        """Test content under 300 chars becomes the excerpt unchanged"""
        news = News.objects.create(
            title="Short",
            content="A short piece of content.",
            author=self.user,
            category=self.category,
        )
        self.assertEqual(news.excerpt, "A short piece of content.")

    def test_long_content_is_truncated_for_excerpt(self):
        """Test content over 300 chars is truncated to 297 chars plus ellipsis"""
        long_content = "A" * 400
        news = News.objects.create(
            title="Long",
            content=long_content,
            author=self.user,
            category=self.category,
        )
        self.assertEqual(len(news.excerpt), 300)
        self.assertTrue(news.excerpt.endswith("..."))

    def test_explicit_excerpt_is_not_overwritten(self):
        """Test a manually provided excerpt is preserved"""
        news = News.objects.create(
            title="Custom Excerpt",
            content="A" * 400,
            excerpt="My own summary",
            author=self.user,
            category=self.category,
        )
        self.assertEqual(news.excerpt, "My own summary")


class NewsFormValidationTests(TestCase):
    """Tests for NewsForm field validation beyond event date ordering"""

    def setUp(self):
        self.event_category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.EVENT
        )
        self.news_category, _ = NewsCategory.objects.get_or_create(
            name=NewsCategory.NEWS
        )

    def test_event_without_date_is_invalid(self):
        """Test event category requires an event_date"""
        form = NewsForm(
            data={
                "title": "Some Event",
                "category": self.event_category.pk,
                "content": "Content",
                "excerpt": "",
                "event_location": "Praça Central",
                "status": News.DRAFT,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("event_date", form.errors)

    def test_event_without_location_is_invalid(self):
        """Test event category requires an event_location"""
        form = NewsForm(
            data={
                "title": "Some Event",
                "category": self.event_category.pk,
                "content": "Content",
                "excerpt": "",
                "event_date": "2026-06-10T10:00",
                "status": News.DRAFT,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("event_location", form.errors)

    def test_regular_news_does_not_require_event_fields(self):
        """Test non-event categories don't require event_date/location"""
        form = NewsForm(
            data={
                "title": "Regular News",
                "category": self.news_category.pk,
                "content": "Content",
                "excerpt": "",
                "status": News.DRAFT,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_excerpt_over_300_chars_is_invalid(self):
        """Test an explicit excerpt longer than 300 chars is rejected"""
        form = NewsForm(
            data={
                "title": "Long Excerpt",
                "category": self.news_category.pk,
                "content": "Content",
                "excerpt": "A" * 301,
                "status": News.DRAFT,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("excerpt", form.errors)


class NewsAdminTests(TestCase):
    """Tests for NewsAdmin.save_model author assignment"""

    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="pass123", is_staff=True
        )
        self.other_staff = User.objects.create_user(
            username="otherstaff", password="pass123", is_staff=True
        )
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)

    def test_save_model_sets_author_on_create(self):
        """Test creating a News via admin sets author to the current request user"""
        news_admin = admin.site._registry[News]
        request = self.factory.post("/admin/news/news/add/")
        request.user = self.staff_user

        news = News(title="Admin Created", content="Content", category=self.category)
        news_admin.save_model(request, news, form=None, change=False)

        self.assertEqual(news.author, self.staff_user)

    def test_save_model_does_not_override_author_on_change(self):
        """Test editing an existing News via admin keeps the original author"""
        news = News.objects.create(
            title="Existing",
            content="Content",
            author=self.staff_user,
            category=self.category,
        )
        news_admin = admin.site._registry[News]
        request = self.factory.post(f"/admin/news/news/{news.pk}/change/")
        request.user = self.other_staff

        news_admin.save_model(request, news, form=None, change=True)

        self.assertEqual(news.author, self.staff_user)


class AgendaTests(TestCase):
    """The events page leads with upcoming and ongoing events"""

    def setUp(self):
        self.author = User.objects.create_user(username="agenda", password="pass123")
        self.events, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        now = timezone.now()
        self.ongoing = self._event("Festival em andamento", now - timedelta(days=1))
        self.ongoing.event_end_date = now + timedelta(days=2)
        self.ongoing.save()
        self.later = self._event("Show daqui a uma semana", now + timedelta(days=7))
        self.past = self._event("Feira encerrada", now - timedelta(days=30))

    def _event(self, title, when):
        return News.objects.create(
            title=title,
            content="c",
            category=self.events,
            author=self.author,
            status=News.PUBLISHED,
            publish_date=timezone.now() - timedelta(days=40),
            event_date=when,
            event_location="Orla",
        )

    def test_upcoming_events_include_ongoing_in_date_order(self):
        self.assertEqual(
            list(News.objects.published().upcoming_events()),
            [self.ongoing, self.later],
        )

    def test_ongoing_event_is_not_past(self):
        self.assertTrue(self.ongoing.is_ongoing_event)
        self.assertFalse(self.ongoing.is_past_event)

    def test_agenda_leads_and_is_not_repeated_below(self):
        response = self.client.get(reverse("news:news_list"))
        self.assertEqual(response.context["agenda"], [self.ongoing, self.later])
        self.assertEqual(list(response.context["news_items"]), [self.past])
        self.assertContains(response, "Acontecendo agora")

    def test_landing_shows_only_upcoming_events(self):
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Próximos eventos em Maricá")
        self.assertContains(response, "Show daqui a uma semana")
        self.assertNotContains(response, "Feira encerrada")


class EventCrawlerTests(TestCase):
    """Crawler reads a saved API response; no network access"""

    POSTS = Path(__file__).parent / "testdata" / "prefeitura_posts.json"
    NOW = datetime(2026, 10, 21, 12, 0, tzinfo=dt_timezone.utc)

    def setUp(self):
        self.posts = event_crawler.parse_prefeitura_posts(self.POSTS.read_bytes())
        self.moderator = User.objects.create_user(
            username="mod", password="pass123", is_staff=True
        )

    def _store(self):
        return event_crawler.store_candidates(self.posts, now=self.NOW)

    def test_parse_skips_non_https_and_strips_html(self):
        self.assertEqual([p.source_id for p in self.posts], ["101", "102", "103"])
        self.assertEqual(self.posts[0].title, "Maricá terá festival de música na orla")
        self.assertNotIn("<p>", self.posts[0].text)

    def test_extracts_range_time_and_location(self):
        found = event_crawler.extract(self.posts[0])
        local = timezone.localtime(found.start)
        self.assertEqual((local.day, local.month, local.hour), (30, 10, 16))
        self.assertEqual(timezone.localtime(found.end).date().isoformat(), "2026-11-08")
        self.assertEqual(found.location, "Orla do Parque Nanci")

    def test_extracts_numeric_date_and_neighbourhood(self):
        found = event_crawler.extract(self.posts[1])
        local = timezone.localtime(found.start)
        self.assertEqual((local.day, local.month, local.hour), (27, 10, 18))
        self.assertEqual(found.location, "Praça Orlando de Barros Pimentel, Centro")

    def test_only_upcoming_announcements_become_candidates(self):
        self.assertEqual(self._store(), 2)
        self.assertEqual(
            set(EventCandidate.objects.values_list("source_id", flat=True)),
            {"101", "102"},
        )

    def test_store_is_idempotent(self):
        self._store()
        self.assertEqual(self._store(), 0)

    def test_flags_possible_duplicate_of_published_event(self):
        category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        existing = News.objects.create(
            title="Maricá terá festival de música na Orla",
            content="c",
            category=category,
            author=self.moderator,
            status=News.PUBLISHED,
            event_date=datetime(2026, 10, 30, 19, 0, tzinfo=dt_timezone.utc),
            event_location="Orla",
        )
        self._store()
        candidate = EventCandidate.objects.get(source_id="101")
        self.assertEqual(candidate.possible_duplicate, existing)

    def test_approve_publishes_event_with_image_and_source(self):
        self._store()
        candidate = EventCandidate.objects.get(source_id="101")
        news = event_crawler.approve(
            candidate, self.moderator, image_fetcher=lambda url: b"fake-image"
        )
        self.assertTrue(news.is_event)
        self.assertEqual(news.status, News.PUBLISHED)
        self.assertEqual(news.event_location, "Orla do Parque Nanci")
        self.assertTrue(news.featured_image.name.endswith(".jpg"))
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, EventCandidate.APPROVED)
        self.assertEqual(candidate.news, news)
        news.featured_image.delete(save=False)


class EventTriageViewTests(TestCase):
    def setUp(self):
        self.moderator = User.objects.create_user(
            username="mod", password="pass123", is_staff=True
        )
        self.candidate = EventCandidate.objects.create(
            source="prefeitura",
            source_id="1",
            source_name="Prefeitura de Maricá",
            source_url="https://www.marica.rj.gov.br/noticia/x/",
            source_published_at=timezone.now(),
            title="Show na praça",
            summary="Descrição do show.",
            event_date=timezone.now() + timedelta(days=5),
        )
        self.url = reverse("core:admin_event_triage_action", args=[self.candidate.pk])

    def _post(self, action="approve", **overrides):
        fields = {
            "title": "Show na praça",
            "summary": "Descrição do show.",
            "event_date": (timezone.now() + timedelta(days=5)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "event_end_date": "",
            "event_location": "Praça Central",
            **overrides,
        }
        # The form prefix uses the candidate id (sequences don't reset per test on Postgres)
        data = {f"c{self.candidate.pk}-{name}": value for name, value in fields.items()}
        return self.client.post(self.url, {**data, "action": action})

    def test_regular_user_cannot_triage(self):
        User.objects.create_user(username="visitor", password="pass123")
        self.client.login(username="visitor", password="pass123")
        self._post()
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, EventCandidate.PENDING)

    def test_approve_requires_location(self):
        self.client.login(username="mod", password="pass123")
        response = self._post(event_location="")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(News.objects.exists())

    def test_approve_publishes_on_agenda(self):
        self.client.login(username="mod", password="pass123")
        self._post()
        news = News.objects.get()
        self.assertEqual(news.event_location, "Praça Central")
        response = self.client.get(reverse("news:news_list"))
        self.assertIn(news, response.context["agenda"])

    def test_reject(self):
        self.client.login(username="mod", password="pass123")
        self._post(action="reject")
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, EventCandidate.REJECTED)


class EventWhenFilterTests(TestCase):
    """Event dates read naturally in each language"""

    def setUp(self):
        author = User.objects.create_user(username="dates", password="pass123")
        category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        tz = timezone.get_current_timezone()
        self.event = News(
            title="FLIM",
            category=category,
            author=author,
            event_date=datetime(2026, 10, 30, tzinfo=tz),
            event_end_date=datetime(2026, 11, 8, 23, 59, tzinfo=tz),
        )

    def _when(self, lang):
        from django.utils import translation

        from apps.news.templatetags.event_dates import event_when

        with translation.override(lang):
            return event_when(self.event)

    def test_range_across_months(self):
        self.assertEqual(self._when("pt-br"), "30 de outubro a 8 de novembro")
        self.assertEqual(self._when("en"), "October 30 – November 8")
        self.assertEqual(self._when("es"), "30 de octubre al 8 de noviembre")

    def test_range_within_a_month(self):
        self.event.event_date = self.event.event_date.replace(day=26)
        self.event.event_end_date = self.event.event_end_date.replace(month=10, day=27)
        self.assertEqual(self._when("pt-br"), "26 a 27 de outubro")
        self.assertEqual(self._when("en"), "October 26–27")

    def test_maps_link(self):
        self.event.event_location = "Orla do Parque Nanci"
        self.assertIn("Orla+do+Parque+Nanci", self.event.maps_url)


class EventTriageBulkTests(TestCase):
    def setUp(self):
        self.moderator = User.objects.create_user(
            username="mod", password="pass123", is_staff=True
        )
        self.regular = User.objects.create_user(username="reg", password="pass123")
        self.candidates = [
            EventCandidate.objects.create(
                source="prefeitura",
                source_id=str(i),
                source_name="Prefeitura de Maricá",
                source_url=f"https://www.marica.rj.gov.br/noticia/{i}/",
                source_published_at=timezone.now(),
                title=f"Evento {i}",
                summary="Descrição.",
            )
            for i in range(3)
        ]
        self.url = reverse("core:admin_event_triage_bulk")

    def test_bulk_discard(self):
        self.client.login(username="mod", password="pass123")
        ids = [c.pk for c in self.candidates[:2]]
        response = self.client.post(self.url, {"ids": ids, "action": "reject"})
        self.assertEqual(response.status_code, 302)
        statuses = [EventCandidate.objects.get(pk=c.pk).status for c in self.candidates]
        self.assertEqual(
            statuses,
            [
                EventCandidate.REJECTED,
                EventCandidate.REJECTED,
                EventCandidate.PENDING,
            ],
        )
        rejected = EventCandidate.objects.get(pk=ids[0])
        self.assertEqual(rejected.reviewed_by, self.moderator)
        self.assertIsNotNone(rejected.reviewed_at)

    def test_already_reviewed_ignored(self):
        self.client.login(username="mod", password="pass123")
        done = self.candidates[0]
        done.status = EventCandidate.APPROVED
        done.save()
        self.client.post(self.url, {"ids": [done.pk], "action": "reject"})
        done.refresh_from_db()
        self.assertEqual(done.status, EventCandidate.APPROVED)

    def test_non_staff_forbidden(self):
        self.client.login(username="reg", password="pass123")
        self.client.post(self.url, {"ids": [self.candidates[0].pk], "action": "reject"})
        self.candidates[0].refresh_from_db()
        self.assertEqual(self.candidates[0].status, EventCandidate.PENDING)

    def test_triage_page_has_checkboxes(self):
        self.client.login(username="mod", password="pass123")
        response = self.client.get(reverse("core:admin_event_triage"), follow=True)
        self.assertContains(response, "data-bulk-item", count=3)
        self.assertContains(response, "Descartar selecionados")


class CronCrawlEventsTests(TestCase):
    url = "/cron/crawl-events/"

    @override_settings(CRON_SECRET="s3cret")
    def test_rejects_missing_or_wrong_secret(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        wrong = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer nope")
        self.assertEqual(wrong.status_code, 401)

    @override_settings(CRON_SECRET="")
    def test_disabled_without_secret(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer ")
        self.assertEqual(response.status_code, 401)

    @override_settings(CRON_SECRET="s3cret")
    def test_runs_crawler_with_secret(self):
        with mock.patch(
            "apps.news.event_crawler.fetch_prefeitura_posts",
            autospec=True,
            return_value=[],
        ):
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"created": 0})
