import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from PIL import Image

from apps.accounts.models import User
from apps.explore.models import Place, PlaceImage, PlaceVisit
from apps.explore.visits import CONSENT_COOKIE
from apps.news.models import News, NewsCategory

PREFETCH = {"HTTP_SEC_PURPOSE": "prefetch;prerender"}


def jpeg(width, height):
    buffer = BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, "JPEG")
    return ContentFile(buffer.getvalue(), "photo.jpg")


class ThumbnailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        owner = User.objects.create_user("owner", password="x")
        place = Place.objects.create(
            name="P", description="d", address="a", created_by=owner
        )
        self.image = PlaceImage.objects.create(place=place, image=jpeg(2000, 1000))

    def tearDown(self):
        self.override.disable()
        self.media.cleanup()

    def render(self, text):
        return Template("{% load thumbs %}" + text).render(
            Context({"img": self.image.image})
        )

    def test_thumb_is_resized_webp(self):
        url = self.render("{{ img|thumb:480 }}")
        self.assertTrue(url.endswith(".webp"))
        name = url.removeprefix("/media/")
        with self.image.image.storage.open(name) as f, Image.open(f) as thumb:
            self.assertEqual((thumb.format, thumb.size), ("WEBP", (480, 240)))

    def test_srcset_lists_each_width(self):
        srcset = self.render("{{ img|srcset:'480,960' }}")
        self.assertRegex(srcset, r"^\S+\.webp 480w, \S+\.webp 960w$")

    def test_unreadable_image_falls_back_to_original(self):
        broken = PlaceImage.objects.create(
            place=self.image.place, image=ContentFile(b"not an image", "bad.jpg")
        )
        url = Template("{% load thumbs %}{{ img|thumb:480 }}").render(
            Context({"img": broken.image})
        )
        self.assertEqual(url, broken.image.url)


class SpeculativeLoadTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("owner", password="x")
        self.place = Place.objects.create(
            name="P", description="d", address="a", created_by=owner, is_approved=True
        )
        self.event = News.objects.create(
            title="Festa",
            content="c",
            author=owner,
            category=NewsCategory.objects.get(name=NewsCategory.EVENT),
            status=News.PUBLISHED,
            event_date=timezone.now(),
        )

    def test_prerendered_place_is_counted_only_by_beacon(self):
        self.client.cookies[CONSENT_COOKIE] = "accepted"
        url = reverse("explore:place_detail", args=[self.place.pk])
        self.client.get(url, **PREFETCH)
        self.assertFalse(PlaceVisit.objects.exists())
        self.client.post(reverse("explore:place_visit", args=[self.place.pk]))
        self.assertEqual(PlaceVisit.objects.count(), 1)

    def test_prerendered_event_is_counted_only_by_beacon(self):
        url = reverse("news:news_detail", args=[self.event.slug])
        self.client.get(url, **PREFETCH)
        self.event.refresh_from_db()
        self.assertEqual(self.event.view_count, 0)
        self.client.post(reverse("news:news_view_beacon", args=[self.event.slug]))
        self.event.refresh_from_db()
        self.assertEqual(self.event.view_count, 1)

    def test_beacons_reject_get(self):
        response = self.client.get(reverse("explore:place_visit", args=[self.place.pk]))
        self.assertEqual(response.status_code, 405)
