import json
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.core import demo_snapshot
from apps.core.demo_snapshot import OWNER, SNAPSHOT
from apps.explore.models import Place, PlaceImage, PlaceReview
from apps.news.models import News


class SnapshotCase(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def load(self):
        with override_settings(MEDIA_ROOT=self.media.name):
            call_command("load_demo_data", verbosity=0)


class DemoSnapshotTests(SnapshotCase):
    def test_loads_everything_with_translations(self):
        self.load()
        self.assertEqual(Place.objects.public().count(), len(self.data["places"]))
        self.assertEqual(
            PlaceImage.objects.count(),
            sum(len(p["images"]) for p in self.data["places"]),
        )
        self.assertEqual(
            PlaceReview.objects.count(),
            sum(len(p["reviews"]) for p in self.data["places"]),
        )
        self.assertEqual(
            News.objects.published().events().count(), len(self.data["events"])
        )
        place = Place.objects.get(name=self.data["places"][0]["name"])
        self.assertEqual(place.translations, self.data["places"][0]["translations"])

    def test_demo_accounts_cannot_log_in_and_no_admin_is_created(self):
        self.load()
        self.assertFalse(User.objects.filter(is_superuser=True).exists())
        self.assertFalse(any(u.has_usable_password() for u in User.objects.all()))
        self.assertTrue(User.objects.filter(username=OWNER).exists())

    def test_skips_when_places_exist(self):
        self.load()
        self.load()
        self.assertEqual(Place.objects.count(), len(self.data["places"]))

    def test_restores_photos_missing_from_storage(self):
        self.load()
        image = PlaceImage.objects.first()
        with override_settings(MEDIA_ROOT=self.media.name):
            image.image.storage.delete(image.image.name)
            self.assertFalse(image.image.storage.exists(image.image.name))
        self.load()
        with override_settings(MEDIA_ROOT=self.media.name):
            self.assertTrue(image.image.storage.exists(image.image.name))


class DemoSnapshotSyncTests(SnapshotCase):
    def setUp(self):
        super().setUp()
        self.load()
        self.place = Place.objects.get(name=self.data["places"][0]["name"])

    def state(self):
        return (
            sorted(News.objects.values_list("slug", flat=True)),
            sorted(Place.objects.values_list("name", "description", "translations")),
        )

    def test_recreates_missing_events(self):
        slug = self.data["events"][0]["slug"]
        News.objects.get(slug=slug).delete()
        self.load()
        self.assertEqual(
            News.objects.published().events().count(), len(self.data["events"])
        )
        self.assertTrue(News.objects.filter(slug=slug).exists())

    def test_applies_translations_when_text_is_unchanged(self):
        stale = {"source": self.place.translations["source"], "en": {"name": "old"}}
        Place.objects.filter(pk=self.place.pk).update(translations=stale)
        self.load()
        self.place.refresh_from_db()
        self.assertEqual(
            self.place.translations, self.data["places"][0]["translations"]
        )

    def test_edited_description_keeps_its_translations(self):
        self.place.description = "Texto editado em produção"
        self.place.save()
        Place.objects.filter(pk=self.place.pk).update(
            translations={"source": "old", "en": {"name": "Edited"}}
        )
        self.load()
        self.place.refresh_from_db()
        self.assertEqual(self.place.translations["en"], {"name": "Edited"})
        self.assertEqual(self.place.description, "Texto editado em produção")

    def test_running_twice_changes_nothing(self):
        self.load()
        before = self.state()
        self.load()
        self.assertEqual(self.state(), before)
        with override_settings(MEDIA_ROOT=self.media.name):
            self.assertEqual(demo_snapshot.sync(), (0, 0))
