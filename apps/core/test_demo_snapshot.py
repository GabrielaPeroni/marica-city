import json
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.core.demo_snapshot import OWNER, SNAPSHOT
from apps.explore.models import Place, PlaceImage, PlaceReview
from apps.news.models import News


class DemoSnapshotTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def load(self):
        with override_settings(MEDIA_ROOT=self.media.name):
            call_command("load_demo_data", verbosity=0)

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
