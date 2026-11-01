from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.explore.models import Place


class PlaceFeatureTests(TestCase):
    def setUp(self):
        self.mod = User.objects.create_user("mod", password="x", is_staff=True)
        self.place = Place.objects.create(
            name="Praia",
            description="d",
            address="a",
            created_by=self.mod,
            is_approved=True,
        )
        self.url = reverse("explore:place_feature", args=[self.place.pk])

    def test_moderator_toggles_feature(self):
        self.client.force_login(self.mod)
        self.client.post(self.url)
        self.place.refresh_from_db()
        self.assertTrue(self.place.is_featured)
        self.client.post(self.url)
        self.place.refresh_from_db()
        self.assertFalse(self.place.is_featured)

    def test_regular_user_cannot_feature(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.client.post(self.url)
        self.place.refresh_from_db()
        self.assertFalse(self.place.is_featured)

    def test_featured_place_leads_landing_section(self):
        newer = Place.objects.create(
            name="Nova",
            description="d",
            address="a",
            created_by=self.mod,
            is_approved=True,
        )
        self.place.is_featured = True
        self.place.save()
        places = list(
            self.client.get(reverse("core:landing")).context["featured_places"]
        )
        self.assertEqual(places[:2], [self.place, newer])

    def test_backlog_filters_featured_and_queue_link(self):
        self.client.force_login(self.mod)
        Place.objects.create(
            name="Pendente", description="d", address="a", created_by=self.mod
        )
        response = self.client.get(reverse("explore:backlog"), {"view": "queue"})
        self.assertEqual([p.name for p in response.context["places"]], ["Pendente"])
        self.place.is_featured = True
        self.place.save()
        response = self.client.get(reverse("explore:backlog"), {"status": "featured"})
        self.assertEqual(list(response.context["places"]), [self.place])


class AdminAccountProtectionTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser("root", password="x")
        self.mod = User.objects.create_user("mod", password="x", is_staff=True)
        self.client.force_login(self.mod)

    def test_moderator_cannot_demote_deactivate_or_delete_admin(self):
        self.client.post(reverse("accounts:user_update_type", args=[self.root.pk]))
        self.client.post(reverse("accounts:user_toggle_status", args=[self.root.pk]))
        self.client.post(reverse("accounts:user_delete", args=[self.root.pk]))
        self.root.refresh_from_db()
        self.assertTrue(self.root.is_staff and self.root.is_active)

    def test_admin_listed_first_on_dashboard(self):
        response = self.client.get(reverse("core:admin_dashboard"))
        self.assertEqual(response.context["recent_users"][0], self.root)
