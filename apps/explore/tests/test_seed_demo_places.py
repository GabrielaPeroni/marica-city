import json
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.explore.management.commands.seed_demo_places import DATA_FILE
from apps.explore.models import Category, Place

from .tests import TINY_GIF

SLUGS = [
    "restaurantes",
    "hoteis-pousadas",
    "natureza-parques",
    "artes-cultura",
    "praias",
    "compras",
]


class FakeResponse:
    def __init__(self, data, content_type="image/jpeg"):
        self._data = data
        self.headers = {"Content-Type": content_type}

    def read(self, size=-1):
        return self._data if size < 0 else self._data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def seed(*args):
    out = StringIO()
    call_command("seed_demo_places", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


class SeedDemoPlacesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("root", "root@example.com", "x")
        for order, slug in enumerate(SLUGS):
            Category.objects.create(name=slug, slug=slug, display_order=order)
        cls.entries = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    def test_data_file_covers_every_category_three_times(self):
        for slug in SLUGS:
            count = sum(slug in e["categories"] for e in self.entries)
            self.assertGreaterEqual(count, 3, slug)

    def test_creates_approved_active_places_with_categories(self):
        seed()
        self.assertEqual(Place.objects.count(), len(self.entries))
        for entry in self.entries:
            place = Place.objects.get(name=entry["name"])
            self.assertTrue(place.is_approved)
            self.assertTrue(place.is_active)
            self.assertEqual(place.created_by, self.admin)
            self.assertCountEqual(
                place.categories.values_list("slug", flat=True), entry["categories"]
            )

    def test_is_idempotent(self):
        seed()
        seed()
        self.assertEqual(Place.objects.count(), len(self.entries))

    def test_no_network_without_flag(self):
        with mock.patch("urllib.request.urlopen", autospec=True) as urlopen:
            seed()
        urlopen.assert_not_called()
        self.assertFalse(Place.objects.filter(description__contains="Foto:").exists())

    def test_errors_without_staff_user(self):
        User.objects.all().delete()
        with self.assertRaises(CommandError):
            seed()

    def test_errors_when_category_missing(self):
        Category.objects.filter(slug="praias").delete()
        with self.assertRaises(CommandError):
            seed()

    def test_with_images_downloads_and_credits(self):
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            with mock.patch(
                "urllib.request.urlopen",
                autospec=True,
                return_value=FakeResponse(TINY_GIF),
            ) as urlopen:
                seed("--with-images")
            with_image = [e for e in self.entries if e["image"]]
            self.assertEqual(urlopen.call_count, len(with_image))
            for entry in with_image:
                place = Place.objects.get(name=entry["name"])
                primary = place.images.get(is_primary=True)
                self.assertTrue(primary.image.name)
                image = entry["image"]
                label = (
                    f"Imagem ilustrativa ({image['illustrative']})"
                    if image.get("illustrative")
                    else "Foto"
                )
                self.assertTrue(
                    place.description.endswith(
                        f"{label}: {image['author']} / Wikimedia Commons "
                        f"({image['license']})."
                    )
                )

    def test_with_images_backfills_existing_places_once(self):
        seed()
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            with mock.patch(
                "urllib.request.urlopen",
                autospec=True,
                return_value=FakeResponse(TINY_GIF),
            ) as urlopen:
                seed("--with-images")
                seed("--with-images")
            with_image = [e for e in self.entries if e["image"]]
            self.assertEqual(urlopen.call_count, len(with_image))

    def test_non_image_response_is_skipped(self):
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            with mock.patch(
                "urllib.request.urlopen",
                autospec=True,
                return_value=FakeResponse(b"<html>", "text/html"),
            ):
                seed("--with-images")
        self.assertEqual(Place.objects.count(), len(self.entries))
        self.assertFalse(Place.objects.get(name="Praia de Itaipuaçu").images.exists())
