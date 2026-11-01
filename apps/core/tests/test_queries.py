from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.explore.models import Category, Place, PlaceReview


class QueryCountTests(TestCase):
    """Trava o número de consultas das páginas públicas (visitante anônimo, cache quente)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ana", password="x")
        cls.category = Category.objects.create(name="Cachoeiras", slug="cachoeiras")
        for i in range(3):
            place = Place.objects.create(
                name=f"Lugar {i}",
                description="d",
                address="a",
                created_by=cls.user,
                is_approved=True,
            )
            place.categories.add(cls.category)
        cls.place = place
        PlaceReview.objects.create(
            place=place, user=cls.user, rating=5, comment="ótimo"
        )

    def setUp(self):
        cache.clear()

    def assert_queries(self, url, expected):
        self.client.get(url)  # esquenta o cache do rodapé
        with self.assertNumQueries(expected):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_landing(self):
        self.assert_queries(reverse("core:landing"), 11)

    def test_explore(self):
        self.assert_queries(reverse("explore:explore"), 4)

    def test_place_detail(self):
        self.assert_queries(reverse("explore:place_detail", args=[self.place.pk]), 5)

    def test_about(self):
        self.assert_queries(reverse("core:about"), 0)

    def test_footer_categories_are_cached_and_refreshed_on_change(self):
        url = reverse("core:about")
        response = self.client.get(url)
        self.assertContains(response, "Cachoeiras")
        Category.objects.create(name="Trilhas", slug="trilhas")
        self.assertContains(self.client.get(url), "Trilhas")
        self.category.is_active = False
        self.category.save()
        self.assertNotContains(self.client.get(url), "Cachoeiras")
