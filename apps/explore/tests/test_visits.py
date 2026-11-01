from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.explore.models import Place, PlaceVisit
from apps.explore.visits import CONSENT_COOKIE, VISITOR_COOKIE, most_visited


class PlaceVisitTrackingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="x")
        self.place = Place.objects.create(
            name="Praia",
            description="d",
            address="a",
            created_by=self.owner,
            is_approved=True,
        )
        self.url = reverse("explore:place_detail", args=[self.place.pk])

    def test_no_consent_records_nothing(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlaceVisit.objects.exists())
        self.assertNotIn(VISITOR_COOKIE, response.cookies)

    def test_declined_consent_clears_visitor_cookie(self):
        self.client.cookies[CONSENT_COOKIE] = "declined"
        self.client.cookies[VISITOR_COOKIE] = "a" * 32
        response = self.client.get(self.url)
        self.assertFalse(PlaceVisit.objects.exists())
        self.assertEqual(response.cookies[VISITOR_COOKIE].value, "")

    def test_consent_counts_one_visit_per_visitor_per_day(self):
        self.client.cookies[CONSENT_COOKIE] = "accepted"
        response = self.client.get(self.url)
        visitor = response.cookies[VISITOR_COOKIE].value
        self.assertRegex(visitor, r"^[0-9a-f]{32}$")
        self.client.get(self.url)
        self.assertEqual(PlaceVisit.objects.filter(visitor=visitor).count(), 1)

    def test_invalid_visitor_cookie_is_replaced(self):
        self.client.cookies[CONSENT_COOKIE] = "accepted"
        self.client.cookies[VISITOR_COOKIE] = "<script>"
        response = self.client.get(self.url)
        self.assertNotEqual(response.cookies[VISITOR_COOKIE].value, "<script>")
        self.assertEqual(PlaceVisit.objects.count(), 1)

    def test_owner_and_staff_visits_are_not_counted(self):
        staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.client.cookies[CONSENT_COOKIE] = "accepted"
        for user in (self.owner, staff):
            self.client.force_login(user)
            self.client.get(self.url)
        self.assertFalse(PlaceVisit.objects.exists())

    def test_most_visited_ranks_by_recent_visits(self):
        other = Place.objects.create(
            name="Lagoa",
            description="d",
            address="a",
            created_by=self.owner,
            is_approved=True,
        )
        today = timezone.localdate()
        for i in range(3):
            PlaceVisit.objects.create(place=other, visitor=f"{i:032x}", date=today)
        PlaceVisit.objects.create(place=self.place, visitor="f" * 32, date=today)
        for i in range(5):
            PlaceVisit.objects.create(
                place=self.place,
                visitor=f"{i:032x}",
                date=today - timedelta(days=30),
            )
        self.assertEqual(list(most_visited()), [other, self.place])

    def test_landing_shows_most_visited(self):
        PlaceVisit.objects.create(
            place=self.place, visitor="a" * 32, date=timezone.localdate()
        )
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(list(response.context["trending_places"]), [self.place])
