import json

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from ..models import Category, Favorite, Place, PlaceApproval, PlaceImage, PlaceReview

User = get_user_model()

# 1x1 pixel transparent GIF - smallest valid image Pillow will accept.
TINY_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def make_test_image(name="test.gif"):
    return SimpleUploadedFile(name, TINY_GIF, content_type="image/gif")


class CategoryModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Restaurants",
            slug="restaurants",
            description="Best dining spots",
            icon="🍽️",
            display_order=1,
        )

    def test_category_creation(self):
        """Test category is created correctly"""
        self.assertEqual(self.category.name, "Restaurants")
        self.assertEqual(self.category.slug, "restaurants")
        self.assertTrue(self.category.is_active)

    def test_category_string_representation(self):
        """Test category string representation"""
        self.assertEqual(str(self.category), "Restaurants")

    def test_active_places_count_property(self):
        """Test active_places_count property"""
        user = User.objects.create_user(username="creator", password="pass123")

        # Create approved place
        place1 = Place.objects.create(
            name="Test Place 1",
            description="Test description",
            address="Test address",
            created_by=user,
            is_approved=True,
            is_active=True,
        )
        place1.categories.add(self.category)

        # Create unapproved place
        place2 = Place.objects.create(
            name="Test Place 2",
            description="Test description",
            address="Test address",
            created_by=user,
            is_approved=False,
        )
        place2.categories.add(self.category)

        self.assertEqual(self.category.active_places_count, 1)

    def test_category_ordering(self):
        """Test categories are ordered by display_order and name"""
        cat2 = Category.objects.create(name="Hotels", slug="hotels", display_order=2)
        cat3 = Category.objects.create(name="Arts", slug="arts", display_order=1)

        categories = list(Category.objects.all())
        self.assertEqual(categories[0].display_order, 1)
        self.assertEqual(categories[1].display_order, 1)
        self.assertEqual(categories[2].display_order, 2)


class PlaceModelTests(TestCase):
    """Tests for Place model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.category = Category.objects.create(name="Restaurants", slug="restaurants")

    def test_place_creation(self):
        """Test place is created correctly"""
        place = Place.objects.create(
            name="Test Restaurant",
            description="Great food",
            address="123 Main St",
            created_by=self.user,
        )
        self.assertEqual(place.name, "Test Restaurant")
        self.assertFalse(place.is_approved)  # Default should be False
        self.assertTrue(place.is_active)  # Default should be True
        self.assertEqual(place.created_by, self.user)

    def test_place_string_representation(self):
        """Test place string representation"""
        place = Place.objects.create(
            name="Test Place",
            description="Test",
            address="Test address",
            created_by=self.user,
        )
        self.assertEqual(str(place), "Test Place")

    def test_place_is_pending_property(self):
        """Test is_pending property"""
        place = Place.objects.create(
            name="Test Place",
            description="Test",
            address="Test address",
            created_by=self.user,
            is_approved=False,
        )
        self.assertTrue(place.is_pending)

        place.is_approved = True
        place.save()
        self.assertFalse(place.is_pending)

    def test_place_category_relationship(self):
        """Test many-to-many relationship with categories"""
        place = Place.objects.create(
            name="Test Place",
            description="Test",
            address="Test address",
            created_by=self.user,
        )
        place.categories.add(self.category)

        self.assertEqual(place.categories.count(), 1)
        self.assertIn(self.category, place.categories.all())


class PlaceImageModelTests(TestCase):
    """Tests for PlaceImage model"""

    def setUp(self):
        self.user = User.objects.create_user(username="creator", password="pass123")
        self.place = Place.objects.create(
            name="Test Place",
            description="Test",
            address="Test address",
            created_by=self.user,
        )

    def test_place_primary_image_property(self):
        """Test primary_image property returns primary image"""
        # Note: We can't actually upload files in tests without mocking
        # So we'll just test the property exists
        self.assertIsNone(self.place.primary_image)

    def test_primary_image_uses_prefetch_cache(self):
        """Regression: primary_image used filter().first(), which always
        hits the DB and defeats prefetch_related, causing N+1 in place
        lists. Accessing it must not issue extra queries when prefetched."""
        for i in range(3):
            PlaceImage.objects.create(
                place=self.place,
                image=make_test_image(f"img{i}.gif"),
                is_primary=(i == 1),
            )

        places = Place.objects.filter(pk=self.place.pk).prefetch_related("images")
        with self.assertNumQueries(2):  # 1 for places, 1 for prefetching images
            places = list(places)
            for place in places:
                place.primary_image

        self.assertEqual(places[0].primary_image.caption, "")
        self.assertTrue(places[0].primary_image.is_primary)

    def test_primary_image_returns_none_without_primary(self):
        """No image flagged primary should mean no fallback, not a crash"""
        PlaceImage.objects.create(place=self.place, image=make_test_image())
        self.assertIsNone(self.place.primary_image)

    def test_place_image_string_representation(self):
        """Test PlaceImage string representation includes place name and id"""
        image = PlaceImage.objects.create(place=self.place, image=make_test_image())
        self.assertEqual(str(image), f"{self.place.name} - Image {image.id}")

    def test_only_one_image_stays_primary_across_sequential_saves(self):
        """Verified correct, not a bug: PlaceImage.save() demotes other
        primaries via an UPDATE before inserting/saving itself, so marking
        a second image primary always leaves exactly one primary, never
        two and never zero."""
        img1 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("a.gif"), is_primary=True
        )
        img2 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("b.gif"), is_primary=True
        )

        img1.refresh_from_db()
        img2.refresh_from_db()
        primaries = list(PlaceImage.objects.filter(place=self.place, is_primary=True))
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0].pk, img2.pk)
        self.assertFalse(img1.is_primary)


class PlaceApprovalModelTests(TestCase):
    """Tests for PlaceApproval model"""

    def setUp(self):
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.place = Place.objects.create(
            name="Test Place",
            description="Test",
            address="Test address",
            created_by=self.creator,
            is_approved=False,
        )

    def test_place_approval_creation(self):
        """Test approval record is created"""
        approval = PlaceApproval.objects.create(
            place=self.place,
            reviewer=self.admin,
            action="APPROVE",
            comments="Looks good",
        )
        self.assertEqual(approval.place, self.place)
        self.assertEqual(approval.reviewer, self.admin)
        self.assertEqual(approval.action, "APPROVE")

    def test_approval_updates_place_status(self):
        """Test that approving updates place.is_approved"""
        approval = PlaceApproval.objects.create(
            place=self.place, reviewer=self.admin, action="APPROVE"
        )
        self.place.refresh_from_db()
        self.assertTrue(self.place.is_approved)

    def test_rejection_updates_place_status(self):
        """Test that rejecting updates place status"""
        approval = PlaceApproval.objects.create(
            place=self.place,
            reviewer=self.admin,
            action="REJECT",
            comments="Needs more information",
        )
        self.place.refresh_from_db()
        self.assertFalse(self.place.is_approved)
        self.assertFalse(self.place.is_active)

    def test_place_approval_string_representation(self):
        """Test PlaceApproval string representation"""
        approval = PlaceApproval.objects.create(
            place=self.place, reviewer=self.admin, action="APPROVE"
        )
        expected = f"{self.place.name} - Aprovado by {self.admin}"
        self.assertEqual(str(approval), expected)


class ExploreViewTests(TestCase):
    """Tests for explore page views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.category = Category.objects.create(
            name="Restaurants", slug="restaurants", icon="🍽️"
        )

        # Create approved places
        for i in range(3):
            place = Place.objects.create(
                name=f"Place {i}",
                description="Test description",
                address="Test address",
                created_by=self.user,
                is_approved=True,
                is_active=True,
            )
            place.categories.add(self.category)

    def test_explore_page_loads(self):
        """Test explore page loads successfully"""
        response = self.client.get(reverse("explore:explore"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/explore.html")

    def test_explore_page_shows_categories(self):
        """Test explore page displays categories"""
        response = self.client.get(reverse("explore:explore"))
        self.assertContains(response, "Restaurants")
        self.assertIn("categories", response.context)
        self.assertEqual(response.context["categories"].count(), 1)

    def test_explore_page_shows_approved_places_only(self):
        """Test explore page only shows approved places"""
        # Create unapproved place
        Place.objects.create(
            name="Unapproved Place",
            description="Test",
            address="Test address",
            created_by=self.user,
            is_approved=False,
        )

        response = self.client.get(reverse("explore:explore"))
        self.assertNotContains(response, "Unapproved Place")
        self.assertEqual(response.context["all_places"].count(), 3)

    def test_explore_page_sorting(self):
        """Test explore page sorting functionality"""
        # Test default sorting (newest first)
        response = self.client.get(reverse("explore:explore"))
        self.assertEqual(response.context["current_sort"], "-created_at")

        # Test name sorting
        response = self.client.get(reverse("explore:explore") + "?sort=name")
        self.assertEqual(response.context["current_sort"], "name")


class LandingPageTests(TestCase):
    """Tests for landing page"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass123")

        # Create a place
        self.place = Place.objects.create(
            name="Featured Place",
            description="Test description",
            address="Test address",
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )

    def test_landing_page_loads(self):
        """Test landing page loads successfully"""
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/landing.html")

    def test_landing_page_shows_featured_places(self):
        """Test landing page shows featured places"""
        response = self.client.get(reverse("core:landing"))
        self.assertIn("featured_places", response.context)
        self.assertContains(response, "Featured Place")


class PlaceCreateViewTests(TestCase):
    """Tests for place creation functionality"""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.other_user = User.objects.create_user(
            username="other", password="pass123", is_staff=False
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.category = Category.objects.create(name="Restaurants", slug="restaurants")

    def test_place_create_view_requires_login(self):
        """Test place creation requires authentication"""
        response = self.client.get(reverse("explore:place_create"))
        # Should redirect to landing page where login modal is available
        self.assertRedirects(response, "/?next=/explore/place/create/")

    def test_all_logged_in_users_can_create_places(self):
        """Test all authenticated users can access place creation"""
        # Test with regular user
        self.client.login(username="other", password="pass123")
        response = self.client.get(reverse("explore:place_create"))
        self.assertEqual(response.status_code, 200)

        # Test with another user
        self.client.logout()
        self.client.login(username="creator", password="pass123")
        response = self.client.get(reverse("explore:place_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/place_form.html")
        self.assertContains(response, "Cadastrar lugar")

    def test_admin_user_can_access_place_create_form(self):
        """Test admin users can access place creation form"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:place_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/place_form.html")

    def test_place_creation_with_valid_data(self):
        """Test creating a place with valid data"""
        self.client.login(username="creator", password="pass123")

        form_data = {
            "name": "Test Restaurant",
            "description": "Great food and atmosphere",
            "address": "123 Main Street, Maricá, RJ",
            "categories": [self.category.id],
            # Formset management data
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }

        response = self.client.post(reverse("explore:place_create"), data=form_data)

        # Check place was created
        self.assertEqual(Place.objects.count(), 1)
        place = Place.objects.first()

        # Check place properties
        self.assertEqual(place.name, "Test Restaurant")
        self.assertEqual(place.created_by, self.creator)
        self.assertFalse(place.is_approved)  # Should start as unapproved
        self.assertTrue(place.is_active)
        self.assertIn(self.category, place.categories.all())

        # Check redirect
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": place.pk})
        )

    def test_place_creation_with_image_auto_promotes_first_as_primary(self):
        """Test uploading images without marking one primary auto-promotes the first"""
        self.client.login(username="creator", password="pass123")

        form_data = {
            "name": "Restaurant With Photos",
            "description": "Great food",
            "address": "123 Main Street",
            "categories": [self.category.id],
            "images-TOTAL_FORMS": "1",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
            "images-0-caption": "",
            "images-0-display_order": "0",
        }
        files = {"images-0-image": make_test_image("dish.gif")}

        response = self.client.post(
            reverse("explore:place_create"), data={**form_data, **files}
        )

        place = Place.objects.get(name="Restaurant With Photos")
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": place.pk})
        )
        self.assertEqual(place.images.count(), 1)
        self.assertTrue(place.images.first().is_primary)

    def test_place_creation_with_two_primary_images_keeps_only_one(self):
        """Test uploading two images both marked primary keeps only one primary"""
        self.client.login(username="creator", password="pass123")

        form_data = {
            "name": "Restaurant With Two Photos",
            "description": "Great food",
            "address": "123 Main Street",
            "categories": [self.category.id],
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
            "images-0-caption": "",
            "images-0-is_primary": "on",
            "images-0-display_order": "0",
            "images-1-caption": "",
            "images-1-is_primary": "on",
            "images-1-display_order": "0",
        }
        files = {
            "images-0-image": make_test_image("a.gif"),
            "images-1-image": make_test_image("b.gif"),
        }

        response = self.client.post(
            reverse("explore:place_create"), data={**form_data, **files}
        )

        place = Place.objects.get(name="Restaurant With Two Photos")
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": place.pk})
        )
        self.assertEqual(place.images.filter(is_primary=True).count(), 1)

    def test_place_creation_with_invalid_data(self):
        """Test place creation with invalid data"""
        self.client.login(username="creator", password="pass123")

        # Missing required fields
        form_data = {
            "name": "",  # Required field missing
            "description": "",  # Required field missing
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }

        response = self.client.post(reverse("explore:place_create"), data=form_data)

        # Should not create place and should show form with errors
        self.assertEqual(Place.objects.count(), 0)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/place_form.html")


class PlaceUpdateViewTests(TestCase):
    """Tests for place editing functionality"""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.other_user = User.objects.create_user(
            username="other", password="pass123", is_staff=False
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.category = Category.objects.create(name="Restaurants", slug="restaurants")

        self.place = Place.objects.create(
            name="Original Place",
            description="Original description",
            address="Original address",
            created_by=self.creator,
            is_approved=True,
        )
        self.place.categories.add(self.category)

    def test_place_update_requires_login(self):
        """Test place editing requires authentication"""
        response = self.client.get(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk})
        )
        # Should redirect to landing page where login modal is available
        self.assertRedirects(response, f"/?next=/explore/place/{self.place.pk}/edit/")

    def test_creator_can_edit_own_place(self):
        """Test place creator can edit their own place"""
        self.client.login(username="creator", password="pass123")
        response = self.client.get(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/place_form.html")
        self.assertContains(response, f"Editar {self.place.name}")

    def test_admin_can_edit_any_place(self):
        """Test admin users can edit any place"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/place_form.html")

    def test_other_user_cannot_edit_place(self):
        """Test other users cannot edit places they didn't create"""
        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk})
        )
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_place_update_with_valid_data(self):
        """Test updating a place with valid data"""
        self.client.login(username="creator", password="pass123")

        form_data = {
            "name": "Updated Place Name",
            "description": "Updated description",
            "address": "Updated address",
            "categories": [self.category.id],
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }

        response = self.client.post(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk}), data=form_data
        )

        # Check place was updated
        self.place.refresh_from_db()
        self.assertEqual(self.place.name, "Updated Place Name")
        self.assertEqual(self.place.description, "Updated description")
        self.assertEqual(self.place.address, "Updated address")

        # Check redirect
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_update_demotes_extra_primaries_left_over_in_db(self):
        """If two images somehow both ended up flagged primary (bypassing
        PlaceImage.save()'s normal single-primary enforcement), saving the
        place again without touching those images should demote all but
        one back to a single primary."""
        img1 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("a.gif")
        )
        img2 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("b.gif")
        )
        # Bypass save() override to force an inconsistent double-primary state
        PlaceImage.objects.filter(place=self.place).update(is_primary=True)

        self.client.login(username="creator", password="pass123")
        form_data = {
            "name": self.place.name,
            "description": self.place.description,
            "address": self.place.address,
            "categories": [self.category.id],
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "2",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
            "images-0-id": str(img1.pk),
            "images-0-caption": "",
            "images-0-is_primary": "on",
            "images-0-display_order": "0",
            "images-1-id": str(img2.pk),
            "images-1-caption": "",
            "images-1-is_primary": "on",
            "images-1-display_order": "0",
        }
        response = self.client.post(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk}), data=form_data
        )
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )
        primaries = PlaceImage.objects.filter(place=self.place, is_primary=True)
        self.assertEqual(primaries.count(), 1)

    def test_deleting_primary_image_via_formset_promotes_another(self):
        """Deleting the current primary image through the edit formset
        must leave exactly one primary image among what remains, not zero."""
        img1 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("a.gif"), is_primary=True
        )
        img2 = PlaceImage.objects.create(
            place=self.place, image=make_test_image("b.gif"), is_primary=False
        )

        self.client.login(username="creator", password="pass123")

        form_data = {
            "name": self.place.name,
            "description": self.place.description,
            "address": self.place.address,
            "categories": [self.category.id],
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "2",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
            "images-0-id": str(img1.pk),
            "images-0-caption": "",
            "images-0-display_order": "0",
            "images-0-DELETE": "on",
            "images-1-id": str(img2.pk),
            "images-1-caption": "",
            "images-1-display_order": "0",
        }

        response = self.client.post(
            reverse("explore:place_edit", kwargs={"pk": self.place.pk}), data=form_data
        )
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

        remaining = list(self.place.images.all())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].pk, img2.pk)
        self.assertTrue(remaining[0].is_primary)


class PlaceDeleteViewTests(TestCase):
    """Tests for place deletion functionality"""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.other_user = User.objects.create_user(
            username="other", password="pass123", is_staff=False
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )

        self.place = Place.objects.create(
            name="Test Place",
            description="Test description",
            address="Test address",
            created_by=self.creator,
        )

    def test_place_delete_requires_login(self):
        """Test place deletion requires authentication"""
        response = self.client.get(
            reverse("explore:place_delete", kwargs={"pk": self.place.pk})
        )
        # Should redirect to landing page where login modal is available
        self.assertRedirects(response, f"/?next=/explore/place/{self.place.pk}/delete/")

    def test_place_delete_get_redirects_to_edit(self):
        """Test GET request to delete redirects to edit page (modal handles deletion)"""
        self.client.login(username="creator", password="pass123")
        response = self.client.get(
            reverse("explore:place_delete", kwargs={"pk": self.place.pk})
        )
        # Should redirect to edit page where the delete modal is available
        self.assertRedirects(
            response, reverse("explore:place_edit", kwargs={"pk": self.place.pk})
        )

    def test_creator_can_delete_own_place(self):
        """Test place creator can delete their own place"""
        self.client.login(username="creator", password="pass123")
        response = self.client.post(
            reverse("explore:place_delete", kwargs={"pk": self.place.pk})
        )

        # Check place was deleted
        self.assertEqual(Place.objects.count(), 0)
        self.assertRedirects(response, reverse("explore:explore"))

    def test_admin_can_delete_any_place(self):
        """Test admin users can delete any place"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:place_delete", kwargs={"pk": self.place.pk})
        )

        # Check place was deleted
        self.assertEqual(Place.objects.count(), 0)
        self.assertRedirects(response, reverse("explore:explore"))

    def test_other_user_cannot_delete_place(self):
        """Test other users cannot delete places they didn't create"""
        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_delete", kwargs={"pk": self.place.pk})
        )
        # Should redirect to detail page or show error
        self.assertIn(response.status_code, [302, 403, 404])

        # Check place still exists
        self.assertEqual(Place.objects.count(), 1)


class PlaceDetailViewTests(TestCase):
    """Tests for place detail view functionality"""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.other_user = User.objects.create_user(
            username="other", password="pass123", is_staff=False
        )

        self.approved_place = Place.objects.create(
            name="Approved Place",
            description="Approved description",
            address="Approved address",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

        self.unapproved_place = Place.objects.create(
            name="Unapproved Place",
            description="Unapproved description",
            address="Unapproved address",
            created_by=self.creator,
            is_approved=False,
            is_active=True,
        )

    def test_approved_place_visible_to_all(self):
        """Test approved places are visible to all users"""
        # Anonymous user
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.approved_place.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved Place")

        # Logged in other user
        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.approved_place.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_unapproved_place_visible_to_creator_and_admin(self):
        """Test unapproved places are only visible to creator and admin"""
        # Creator can see their own unapproved place
        self.client.login(username="creator", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.unapproved_place.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unapproved Place")

        # Admin can see any unapproved place
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.unapproved_place.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_unapproved_place_hidden_from_other_users(self):
        """Test unapproved places are hidden from other users"""
        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.unapproved_place.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_approved_but_inactive_place_hidden_from_other_users(self):
        """Regression: the visibility check only looked at is_approved, so
        an approved-but-deactivated place (is_active=False, e.g. an admin
        toggled it off without going through the reject workflow) leaked
        to any logged-in non-owner/non-moderator, unlike the anonymous and
        list-view paths which both require is_approved AND is_active."""
        inactive_place = Place.objects.create(
            name="Deactivated Place",
            description="Was approved, then deactivated",
            address="Some address",
            created_by=self.creator,
            is_approved=True,
            is_active=False,
        )

        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": inactive_place.pk})
        )
        self.assertEqual(response.status_code, 404)

        # Owner and moderator can still see it
        self.client.login(username="creator", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": inactive_place.pk})
        )
        self.assertEqual(response.status_code, 200)

        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": inactive_place.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_button_shown_to_authorized_users(self):
        """Test edit button is shown to authorized users"""
        # Creator sees edit button
        self.client.login(username="creator", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.approved_place.pk})
        )
        self.assertTrue(response.context["can_edit"])

        # Admin sees edit button
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.approved_place.pk})
        )
        self.assertTrue(response.context["can_edit"])

        # Other user doesn't see edit button
        self.client.login(username="other", password="pass123")
        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.approved_place.pk})
        )
        self.assertFalse(response.context["can_edit"])


class CategoryDetailViewTests(TestCase):
    """Tests for category detail view"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass123")
        self.category = Category.objects.create(
            name="Restaurants", slug="restaurants", description="Best dining spots"
        )

        # Create approved places in category
        for i in range(3):
            place = Place.objects.create(
                name=f"Restaurant {i}",
                description="Test restaurant",
                address="Test address",
                created_by=self.user,
                is_approved=True,
                is_active=True,
            )
            place.categories.add(self.category)

        # Create unapproved place (should not appear)
        unapproved_place = Place.objects.create(
            name="Unapproved Restaurant",
            description="Test restaurant",
            address="Test address",
            created_by=self.user,
            is_approved=False,
        )
        unapproved_place.categories.add(self.category)

    def test_category_detail_page_loads(self):
        """Test category detail page loads successfully"""
        response = self.client.get(
            reverse("explore:category_detail", kwargs={"slug": "restaurants"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/category_detail.html")

    def test_category_detail_shows_only_approved_places(self):
        """Test category detail page shows only approved places"""
        response = self.client.get(
            reverse("explore:category_detail", kwargs={"slug": "restaurants"})
        )
        self.assertEqual(response.context["places"].count(), 3)
        self.assertNotContains(response, "Unapproved Restaurant")

    def test_category_detail_sorting(self):
        """Test category detail page sorting"""
        response = self.client.get(
            reverse("explore:category_detail", kwargs={"slug": "restaurants"})
            + "?sort=name"
        )
        self.assertEqual(response.context["current_sort"], "name")

    def test_nonexistent_category_returns_404(self):
        """Test accessing nonexistent category returns 404"""
        response = self.client.get(
            reverse("explore:category_detail", kwargs={"slug": "nonexistent"})
        )
        self.assertEqual(response.status_code, 404)


class PlaceReviewModelTests(TestCase):
    """Tests for PlaceReview model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="reviewer", password="pass123", is_staff=False
        )
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.place = Place.objects.create(
            name="Test Place",
            description="Test description",
            address="Test address",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_review_creation(self):
        """Test review is created correctly"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=5,
            comment="Excellent place!",
        )
        self.assertEqual(review.place, self.place)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Excellent place!")

    def test_review_string_representation(self):
        """Test review string representation"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=4,
            comment="Good place",
        )
        expected = f"{self.user.username} - {self.place.name} (4★)"
        self.assertEqual(str(review), expected)

    def test_unique_review_per_user_per_place(self):
        """Test one review per user per place constraint"""
        PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=5,
            comment="First review",
        )

        # Attempting to create second review for same user/place should fail
        with self.assertRaises(Exception):
            PlaceReview.objects.create(
                place=self.place,
                user=self.user,
                rating=3,
                comment="Second review",
            )

    def test_place_average_rating_property(self):
        """Test place average_rating property"""
        # No reviews
        self.assertIsNone(self.place.average_rating)

        # Add reviews
        user2 = User.objects.create_user(username="user2", password="pass123")
        user3 = User.objects.create_user(username="user3", password="pass123")

        PlaceReview.objects.create(
            place=self.place, user=self.user, rating=5, comment="Great!"
        )
        PlaceReview.objects.create(
            place=self.place, user=user2, rating=4, comment="Good"
        )
        PlaceReview.objects.create(place=self.place, user=user3, rating=3, comment="OK")

        # Average should be (5+4+3)/3 = 4.0
        self.assertEqual(self.place.average_rating, 4.0)

    def test_place_review_count_property(self):
        """Test place review_count property"""
        self.assertEqual(self.place.review_count, 0)

        PlaceReview.objects.create(
            place=self.place, user=self.user, rating=5, comment="Great!"
        )
        self.assertEqual(self.place.review_count, 1)

        user2 = User.objects.create_user(username="user2", password="pass123")
        PlaceReview.objects.create(
            place=self.place, user=user2, rating=4, comment="Good"
        )
        self.assertEqual(self.place.review_count, 2)


class PlaceReviewViewTests(TestCase):
    """Tests for place review functionality"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="reviewer", password="pass123", is_staff=False
        )
        self.creator = User.objects.create_user(
            username="creator", password="pass123", is_staff=False
        )
        self.admin = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.place = Place.objects.create(
            name="Test Place",
            description="Test description",
            address="Test address",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_review_create_requires_login(self):
        """Test creating a review requires authentication"""
        response = self.client.get(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_authenticated_user_can_create_review(self):
        """Test authenticated user can create a review"""
        self.client.login(username="reviewer", password="pass123")

        response = self.client.post(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk}),
            data={
                "rating": 5,
                "comment": "Excellent place!",
            },
        )

        # Check review was created
        self.assertEqual(PlaceReview.objects.count(), 1)
        review = PlaceReview.objects.first()
        self.assertEqual(review.place, self.place)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Excellent place!")

        # Should redirect to place detail
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_user_cannot_create_duplicate_review(self):
        """Test user cannot review same place twice"""
        self.client.login(username="reviewer", password="pass123")

        # Create first review
        PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=5,
            comment="First review",
        )

        # Attempt to create second review
        response = self.client.post(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk}),
            data={
                "rating": 3,
                "comment": "Second review",
            },
        )

        # Should still have only one review
        self.assertEqual(PlaceReview.objects.count(), 1)

        # Should redirect back to place detail with warning
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_user_can_edit_own_review(self):
        """Test user can edit their own review"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=4,
            comment="Original comment",
        )

        self.client.login(username="reviewer", password="pass123")

        response = self.client.post(
            reverse("explore:review_edit", kwargs={"pk": review.pk}),
            data={
                "rating": 5,
                "comment": "Updated comment",
            },
        )

        # Check review was updated
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Updated comment")

        # Should redirect to place detail
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_user_cannot_edit_others_review(self):
        """Test user cannot edit another user's review"""
        other_user = User.objects.create_user(
            username="other", password="pass123", is_staff=False
        )
        review = PlaceReview.objects.create(
            place=self.place,
            user=other_user,
            rating=4,
            comment="Other's review",
        )

        self.client.login(username="reviewer", password="pass123")

        response = self.client.get(
            reverse("explore:review_edit", kwargs={"pk": review.pk})
        )

        # Should be forbidden or redirect
        self.assertIn(response.status_code, [302, 403, 404])

    def test_admin_can_edit_any_review(self):
        """Test admin can edit any review"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=4,
            comment="Original comment",
        )

        self.client.login(username="admin", password="pass123")

        response = self.client.post(
            reverse("explore:review_edit", kwargs={"pk": review.pk}),
            data={
                "rating": 3,
                "comment": "Admin edited",
            },
        )

        # Check review was updated
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.comment, "Admin edited")

    def test_user_can_delete_own_review(self):
        """Test user can delete their own review"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=4,
            comment="My review",
        )

        self.client.login(username="reviewer", password="pass123")

        response = self.client.post(
            reverse("explore:review_delete", kwargs={"pk": review.pk})
        )

        # Check review was deleted
        self.assertEqual(PlaceReview.objects.count(), 0)

        # Should redirect to place detail
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_admin_can_delete_any_review(self):
        """Test admin can delete any review"""
        review = PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=4,
            comment="User review",
        )

        self.client.login(username="admin", password="pass123")

        response = self.client.post(
            reverse("explore:review_delete", kwargs={"pk": review.pk})
        )

        # Check review was deleted
        self.assertEqual(PlaceReview.objects.count(), 0)

    def test_place_detail_shows_reviews(self):
        """Test place detail page shows reviews"""
        PlaceReview.objects.create(
            place=self.place,
            user=self.user,
            rating=5,
            comment="Great place!",
        )

        response = self.client.get(
            reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Great place!")
        self.assertContains(response, self.user.username)
        self.assertIn("reviews", response.context)
        self.assertEqual(response.context["reviews"].count(), 1)

    def test_review_validation_requires_rating(self):
        """Test review form requires rating"""
        self.client.login(username="reviewer", password="pass123")

        response = self.client.post(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk}),
            data={
                "comment": "Comment without rating",
            },
        )

        # Should not create review
        self.assertEqual(PlaceReview.objects.count(), 0)

    def test_review_create_get_shows_empty_form(self):
        """Test GET request shows an empty review form for a place not yet reviewed"""
        self.client.login(username="reviewer", password="pass123")
        response = self.client.get(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/review_form.html")
        self.assertFalse(response.context["form"].is_bound)

    def test_review_edit_get_shows_prefilled_form(self):
        """Test GET request shows the review form prefilled for the owner"""
        review = PlaceReview.objects.create(
            place=self.place, user=self.user, rating=4, comment="Nice"
        )
        self.client.login(username="reviewer", password="pass123")
        response = self.client.get(
            reverse("explore:review_edit", kwargs={"pk": review.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["review"], review)
        self.assertEqual(response.context["form"].instance, review)

    def test_review_delete_get_shows_confirmation_for_owner(self):
        """Test GET request shows the delete confirmation page for the owner"""
        review = PlaceReview.objects.create(
            place=self.place, user=self.user, rating=4, comment="Nice"
        )
        self.client.login(username="reviewer", password="pass123")
        response = self.client.get(
            reverse("explore:review_delete", kwargs={"pk": review.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "explore/review_delete_confirm.html")
        self.assertEqual(response.context["review"], review)

    def test_review_delete_denied_for_non_owner(self):
        """Test a non-owner, non-moderator cannot access the delete confirmation"""
        other_user = User.objects.create_user(username="other2", password="pass123")
        review = PlaceReview.objects.create(
            place=self.place, user=other_user, rating=4, comment="Nice"
        )
        self.client.login(username="reviewer", password="pass123")
        response = self.client.get(
            reverse("explore:review_delete", kwargs={"pk": review.pk})
        )
        self.assertRedirects(
            response, reverse("explore:place_detail", kwargs={"pk": self.place.pk})
        )

    def test_review_validation_requires_comment(self):
        """Test review form requires comment"""
        self.client.login(username="reviewer", password="pass123")

        response = self.client.post(
            reverse("explore:review_create", kwargs={"place_pk": self.place.pk}),
            data={
                "rating": 5,
                "comment": "",  # Empty comment
            },
        )

        # Should not create review
        self.assertEqual(PlaceReview.objects.count(), 0)


# ============================================================================
# API TESTS
# ============================================================================


class MapDataAPITests(TestCase):
    """Test suite for map data API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", is_staff=False
        )
        self.category = Category.objects.create(
            name="Restaurant", slug="restaurant", icon="🍽️"
        )

        # Create approved place with coordinates
        self.approved_place = Place.objects.create(
            name="Approved Place",
            description="This is a test place with coordinates",
            address="123 Test St",
            latitude=-22.9068,
            longitude=-43.1729,
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )
        self.approved_place.categories.add(self.category)

        # Create place without coordinates (should not appear)
        self.no_coords_place = Place.objects.create(
            name="No Coords Place",
            description="Place without coordinates",
            address="456 Test Ave",
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )

        # Create unapproved place (should not appear)
        self.unapproved_place = Place.objects.create(
            name="Unapproved Place",
            description="Unapproved place",
            address="789 Test Blvd",
            latitude=-22.9068,
            longitude=-43.1729,
            created_by=self.user,
            is_approved=False,
            is_active=True,
        )

        # Create inactive place (should not appear)
        self.inactive_place = Place.objects.create(
            name="Inactive Place",
            description="Inactive place",
            address="321 Test Rd",
            latitude=-22.9068,
            longitude=-43.1729,
            created_by=self.user,
            is_approved=True,
            is_active=False,
        )

        self.url = reverse("explore:map_data_api")

    def test_api_returns_json(self):
        """Test that API returns valid JSON response"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_api_returns_only_approved_places(self):
        """Test that API only returns approved, active places with coordinates"""
        response = self.client.get(self.url)
        data = response.json()

        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["places"]), 1)
        self.assertEqual(data["places"][0]["name"], "Approved Place")

    def test_api_response_structure(self):
        """Test that API response has correct structure"""
        response = self.client.get(self.url)
        data = response.json()

        self.assertIn("places", data)
        self.assertIn("count", data)

        place_data = data["places"][0]
        required_fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "image_url",
            "category",
            "category_icon",
            "url",
            "rating",
            "review_count",
        ]
        for field in required_fields:
            self.assertIn(field, place_data)

    def test_api_coordinates_are_floats(self):
        """Test that coordinates are returned as floats"""
        response = self.client.get(self.url)
        data = response.json()

        place_data = data["places"][0]
        self.assertIsInstance(place_data["latitude"], float)
        self.assertIsInstance(place_data["longitude"], float)
        self.assertEqual(place_data["latitude"], -22.9068)
        self.assertEqual(place_data["longitude"], -43.1729)

    def test_api_truncates_long_descriptions(self):
        """Test that long descriptions are truncated to 100 chars"""
        # Create place with long description
        long_desc = "A" * 150
        long_place = Place.objects.create(
            name="Long Description Place",
            description=long_desc,
            address="111 Long St",
            latitude=-22.9068,
            longitude=-43.1729,
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )

        response = self.client.get(self.url)
        data = response.json()

        # Find the long place in response
        long_place_data = next(p for p in data["places"] if p["id"] == long_place.id)
        self.assertEqual(len(long_place_data["description"]), 103)  # 100 + '...'
        self.assertTrue(long_place_data["description"].endswith("..."))

    def test_api_includes_category_info(self):
        """Test that category name and icon are included"""
        response = self.client.get(self.url)
        data = response.json()

        place_data = data["places"][0]
        self.assertEqual(place_data["category"], "Restaurant")
        self.assertEqual(place_data["category_icon"], "🍽️")

    def test_api_handles_place_without_category(self):
        """Test that API handles places without categories"""
        # Remove category from place
        self.approved_place.categories.clear()

        response = self.client.get(self.url)
        data = response.json()

        place_data = data["places"][0]
        self.assertEqual(place_data["category"], "Outros")
        self.assertEqual(place_data["category_icon"], "📍")

    def test_api_includes_rating_and_review_count(self):
        """Test that rating and review count are included"""
        # Add review to place
        PlaceReview.objects.create(
            place=self.approved_place, user=self.user, rating=4, comment="Good place"
        )

        response = self.client.get(self.url)
        data = response.json()

        place_data = data["places"][0]
        self.assertEqual(place_data["rating"], 4.0)
        self.assertEqual(place_data["review_count"], 1)

    def test_api_handles_place_without_reviews(self):
        """Test that API handles places without reviews"""
        response = self.client.get(self.url)
        data = response.json()

        place_data = data["places"][0]
        self.assertIsNone(place_data["rating"])
        self.assertEqual(place_data["review_count"], 0)

    def test_api_only_accepts_get(self):
        """Test that API only accepts GET requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)  # Method not allowed

        response = self.client.put(self.url)
        self.assertEqual(response.status_code, 405)

    def test_api_orders_by_created_date(self):
        """Test that places are ordered by creation date (newest first)"""
        # Create another approved place
        newer_place = Place.objects.create(
            name="Newer Place",
            description="Newer place",
            address="999 New St",
            latitude=-22.9068,
            longitude=-43.1729,
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )

        response = self.client.get(self.url)
        data = response.json()

        # Newer place should be first
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["places"][0]["name"], "Newer Place")
        self.assertEqual(data["places"][1]["name"], "Approved Place")

    def test_api_query_count_does_not_scale_with_place_count(self):
        """Regression: rating/review_count/category lookups were computed
        per-place in the loop (categories.first() also bypassed the
        prefetch cache), so the query count grew with the number of
        places. It must now stay flat."""
        for i in range(5):
            place = Place.objects.create(
                name=f"Bulk Place {i}",
                description="d",
                address="a",
                latitude=-22.9,
                longitude=-43.1,
                created_by=self.user,
                is_approved=True,
                is_active=True,
            )
            place.categories.add(self.category)
            PlaceReview.objects.create(
                place=place, user=self.user, rating=5, comment="Great"
            )

        with self.assertNumQueries(3):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class PlaceAdminTests(TestCase):
    """PlaceAdmin.fieldsets must only reference real Place fields."""

    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            username="superadmin", email="super@example.com", password="pass123"
        )
        self.place = Place.objects.create(
            name="Admin Test Place",
            description="Desc",
            address="Addr",
            created_by=self.superuser,
        )

    def test_place_admin_get_form_does_not_raise(self):
        """Regression: fieldsets referenced contact_phone/email/website,
        fields that live on accounts.User, not Place - crashed add/change."""
        request = self.factory.get(f"/admin/explore/place/{self.place.pk}/change/")
        request.user = self.superuser
        place_admin = admin.site._registry[Place]
        form_class = place_admin.get_form(request, self.place)
        self.assertNotIn("contact_phone", form_class.base_fields)

    def test_place_admin_change_view_loads(self):
        self.client.login(username="superadmin", password="pass123")
        response = self.client.get(f"/admin/explore/place/{self.place.pk}/change/")
        self.assertEqual(response.status_code, 200)

    def test_approve_places_action_approves_and_logs(self):
        """Bulk 'approve_places' admin action approves places and records history"""
        pending = Place.objects.create(
            name="Pending Place",
            description="Desc",
            address="Addr",
            created_by=self.superuser,
            is_approved=False,
        )
        place_admin = admin.site._registry[Place]
        request = self.factory.get("/admin/explore/place/")
        request.user = self.superuser
        request._messages = self.client.session
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))

        place_admin.approve_places(request, Place.objects.filter(pk=pending.pk))

        pending.refresh_from_db()
        self.assertTrue(pending.is_approved)
        self.assertEqual(
            PlaceApproval.objects.filter(place=pending, action="APPROVE").count(), 1
        )

    def test_approve_places_action_skips_already_approved(self):
        """Places already approved are not re-approved or re-logged"""
        place_admin = admin.site._registry[Place]
        request = self.factory.get("/admin/explore/place/")
        request.user = self.superuser
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))

        approved = Place.objects.create(
            name="Already Approved",
            description="Desc",
            address="Addr",
            created_by=self.superuser,
            is_approved=True,
        )
        place_admin.approve_places(request, Place.objects.filter(pk=approved.pk))
        self.assertEqual(PlaceApproval.objects.filter(place=approved).count(), 0)

    def test_place_admin_save_model_sets_created_by_on_create(self):
        """Test PlaceAdmin.save_model sets created_by only when creating"""
        place_admin = admin.site._registry[Place]
        request = self.factory.post("/admin/explore/place/add/")
        request.user = self.superuser

        place = Place(name="New Place", description="d", address="a")
        place_admin.save_model(request, place, form=None, change=False)
        self.assertEqual(place.created_by, self.superuser)

    def test_place_admin_save_model_keeps_creator_on_change(self):
        """Test PlaceAdmin.save_model does not overwrite created_by when editing"""
        place_admin = admin.site._registry[Place]
        other_admin = User.objects.create_superuser(
            username="other_super", email="other@example.com", password="pass123"
        )
        request = self.factory.post(f"/admin/explore/place/{self.place.pk}/change/")
        request.user = other_admin

        place_admin.save_model(request, self.place, form=None, change=True)
        self.assertEqual(self.place.created_by, self.superuser)

    def test_place_approval_admin_save_model_sets_reviewer_on_create(self):
        """Test PlaceApprovalAdmin.save_model sets reviewer only when creating"""
        approval_admin = admin.site._registry[PlaceApproval]
        request = self.factory.post("/admin/explore/placeapproval/add/")
        request.user = self.superuser

        approval = PlaceApproval(place=self.place, action="APPROVE")
        approval_admin.save_model(request, approval, form=None, change=False)
        self.assertEqual(approval.reviewer, self.superuser)

    def test_place_review_admin_comment_preview_truncates_long_comments(self):
        """Test get_comment_preview truncates comments over 50 chars"""
        review_admin = admin.site._registry[PlaceReview]
        creator = User.objects.create_user(username="reviewer2", password="pass123")
        review = PlaceReview.objects.create(
            place=self.place,
            user=creator,
            rating=5,
            comment="A" * 60,
        )
        preview = review_admin.get_comment_preview(review)
        self.assertEqual(preview, "A" * 50 + "...")

    def test_place_review_admin_comment_preview_keeps_short_comments(self):
        """Test get_comment_preview does not alter short comments"""
        review_admin = admin.site._registry[PlaceReview]
        creator = User.objects.create_user(username="reviewer3", password="pass123")
        review = PlaceReview.objects.create(
            place=self.place, user=creator, rating=5, comment="Short"
        )
        self.assertEqual(review_admin.get_comment_preview(review), "Short")

    def test_revoke_approval_action_revokes_and_logs(self):
        """Bulk 'revoke_approval' admin action revokes approval and records history"""
        place_admin = admin.site._registry[Place]
        request = self.factory.get("/admin/explore/place/")
        request.user = self.superuser
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))

        approved = Place.objects.create(
            name="Approved Place",
            description="Desc",
            address="Addr",
            created_by=self.superuser,
            is_approved=True,
        )
        place_admin.revoke_approval(request, Place.objects.filter(pk=approved.pk))

        approved.refresh_from_db()
        self.assertFalse(approved.is_approved)
        self.assertEqual(
            PlaceApproval.objects.filter(place=approved, action="REJECT").count(), 1
        )


class BacklogViewTests(TestCase):
    """Tests for the admin backlog view (queue/history modes, filters, sorting)"""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        self.category = Category.objects.create(name="Restaurants", slug="restaurants")

        self.pending_place = Place.objects.create(
            name="Pending",
            description="d",
            address="a",
            created_by=self.regular_user,
            is_approved=False,
            is_active=True,
        )
        self.approved_place = Place.objects.create(
            name="Approved",
            description="d",
            address="a",
            created_by=self.regular_user,
            is_approved=True,
            is_active=True,
        )
        self.approved_place.categories.add(self.category)
        self.rejected_place = Place.objects.create(
            name="Rejected",
            description="d",
            address="a",
            created_by=self.regular_user,
            is_approved=False,
            is_active=False,
        )

    def test_backlog_requires_login(self):
        """Test backlog view requires authentication"""
        response = self.client.get(reverse("explore:backlog"))
        self.assertRedirects(response, "/?next=/explore/admin/backlog/")

    def test_backlog_requires_moderator(self):
        """Test non-moderators cannot access the backlog"""
        self.client.login(username="regular", password="pass123")
        response = self.client.get(reverse("explore:backlog"))
        self.assertRedirects(response, reverse("core:landing"))

    def test_backlog_default_history_mode_shows_all(self):
        """Test default (history) mode shows places of any status"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["places"].count(), 3)
        self.assertEqual(response.context["status_filter"], "all")

    def test_backlog_queue_mode_shows_only_pending(self):
        """Test queue mode shows only pending, active places"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?status=pending")
        self.assertEqual(response.context["places"].count(), 1)
        self.assertEqual(response.context["places"].first(), self.pending_place)

    def test_backlog_status_filter_approved(self):
        """Test filtering backlog by approved status"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?status=approved")
        self.assertEqual(response.context["places"].count(), 1)
        self.assertEqual(response.context["places"].first(), self.approved_place)

    def test_backlog_status_filter_pending(self):
        """Test filtering backlog by pending status in history mode"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?status=pending")
        self.assertEqual(response.context["places"].count(), 1)
        self.assertEqual(response.context["places"].first(), self.pending_place)

    def test_backlog_status_filter_rejected(self):
        """Test filtering backlog by rejected (inactive) status"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?status=rejected")
        self.assertEqual(response.context["places"].count(), 1)
        self.assertEqual(response.context["places"].first(), self.rejected_place)

    def test_backlog_category_filter(self):
        """Test filtering backlog by category slug"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?category=restaurants")
        self.assertEqual(response.context["places"].count(), 1)
        self.assertEqual(response.context["places"].first(), self.approved_place)

    def test_backlog_sorting_by_name(self):
        """Test backlog can be sorted by name"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog") + "?sort=name")
        self.assertEqual(response.context["current_sort"], "name")

    def test_backlog_status_counts(self):
        """Test backlog exposes counts for each status"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:backlog"))
        counts = {key: n for key, _l, n, *_ in response.context["status_cards"]}
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["approved"], 1)
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(counts["rejected"], 1)


class ApprovalWorkflowViewTests(TestCase):
    """Tests for approval_queue, approve_place and reject_place views"""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        self.place = Place.objects.create(
            name="Pending Place",
            description="d",
            address="a",
            created_by=self.regular_user,
            is_approved=False,
        )

    def test_approval_queue_requires_moderator(self):
        """Test approval queue redirects non-moderators"""
        self.client.login(username="regular", password="pass123")
        response = self.client.get(reverse("explore:approval_queue"))
        self.assertRedirects(response, reverse("core:landing"))

    def test_approval_queue_redirects_moderator_to_backlog_queue_view(self):
        """Regression: approval_queue_view used to concatenate the URL name
        with a query string instead of reversing it first, raising
        NoReverseMatch for every moderator who used this shortcut."""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(reverse("explore:approval_queue"))
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )

    def test_approve_place_requires_moderator(self):
        """Test only moderators can approve places"""
        self.client.login(username="regular", password="pass123")
        response = self.client.post(
            reverse("explore:approve_place", kwargs={"pk": self.place.pk})
        )
        self.assertRedirects(response, reverse("core:landing"))
        self.place.refresh_from_db()
        self.assertFalse(self.place.is_approved)

    def test_approve_place_rejects_get(self):
        """Aprovar só por POST"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:approve_place", kwargs={"pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_approve_place_post_approves_and_creates_record(self):
        """Test POST request approves the place and logs the approval"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:approve_place", kwargs={"pk": self.place.pk}),
            data={"comments": "Looks great"},
        )
        self.place.refresh_from_db()
        self.assertTrue(self.place.is_approved)

        approval = PlaceApproval.objects.get(place=self.place)
        self.assertEqual(approval.action, PlaceApproval.ActionType.APPROVE)
        self.assertEqual(approval.comments, "Looks great")
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )

    def test_reject_place_requires_moderator(self):
        """Test only moderators can reject places"""
        self.client.login(username="regular", password="pass123")
        response = self.client.post(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk}),
            data={"reason": "Spam"},
        )
        self.assertRedirects(response, reverse("core:landing"))

    def test_reject_place_without_reason_shows_error(self):
        """Remover sem motivo volta para os pendentes com erro, sem registrar nada"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk}), data={}
        )
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )
        self.assertEqual(PlaceApproval.objects.filter(place=self.place).count(), 0)

    def test_reject_place_with_outros_requires_custom_comment(self):
        """Test choosing 'Outros' without specifying a comment shows an error"""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk}),
            data={"reason": "Outros", "comments": ""},
        )
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )
        self.assertEqual(PlaceApproval.objects.filter(place=self.place).count(), 0)

    def test_reject_place_with_outros_and_comment_redirects_to_backlog_queue_view(
        self,
    ):
        """Regression: reject_place_view had the same string-concatenation
        redirect bug as approval_queue_view - the rejection applied
        correctly but the success response raised NoReverseMatch."""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk}),
            data={"reason": "Outros", "comments": "Endereço inválido"},
        )
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )
        approval = PlaceApproval.objects.get(place=self.place)
        self.assertEqual(approval.action, PlaceApproval.ActionType.REJECT)
        self.assertEqual(approval.comments, "Endereço inválido")

    def test_reject_place_with_standard_reason_redirects_to_backlog_queue_view(self):
        """Test a standard (non-'Outros') reason is used as the comment and
        the success redirect resolves correctly."""
        self.client.login(username="admin", password="pass123")
        response = self.client.post(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk}),
            data={"reason": "Conteúdo duplicado"},
        )
        self.assertRedirects(
            response,
            reverse("explore:backlog") + "?status=pending",
            fetch_redirect_response=False,
        )
        approval = PlaceApproval.objects.get(place=self.place)
        self.assertEqual(approval.comments, "Conteúdo duplicado")
        self.place.refresh_from_db()
        self.assertFalse(self.place.is_active)

    def test_reject_place_rejects_get(self):
        """Remover só por POST"""
        self.client.login(username="admin", password="pass123")
        response = self.client.get(
            reverse("explore:reject_place", kwargs={"pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 405)


class ToggleFavoriteViewTests(TestCase):
    """Tests for the toggle_favorite AJAX endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="fan", password="pass123")
        self.creator = User.objects.create_user(username="creator", password="pass123")
        self.place = Place.objects.create(
            name="Test Place",
            description="d",
            address="a",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_get_request_not_allowed(self):
        """Test GET requests are rejected with 405"""
        response = self.client.get(
            reverse("explore:toggle_favorite", kwargs={"pk": self.place.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_unapproved_place_returns_404(self):
        """Test toggling favorite on a non-approved place returns 404"""
        unapproved = Place.objects.create(
            name="Unapproved",
            description="d",
            address="a",
            created_by=self.creator,
            is_approved=False,
        )
        response = self.client.post(
            reverse("explore:toggle_favorite", kwargs={"pk": unapproved.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_authenticated_user_can_add_favorite(self):
        """Test authenticated user adding a favorite creates a Favorite record"""
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:toggle_favorite", kwargs={"pk": self.place.pk})
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_favorited"])
        self.assertEqual(data["favorites_count"], 1)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, place=self.place).exists()
        )

    def test_authenticated_user_can_remove_favorite(self):
        """Test toggling an existing favorite removes it"""
        Favorite.objects.create(user=self.user, place=self.place)
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:toggle_favorite", kwargs={"pk": self.place.pk})
        )
        data = response.json()
        self.assertFalse(data["is_favorited"])
        self.assertEqual(data["favorites_count"], 0)
        self.assertFalse(
            Favorite.objects.filter(user=self.user, place=self.place).exists()
        )

    def test_anonymous_user_gets_client_side_confirmation(self):
        """Test anonymous users get a success response without DB changes"""
        response = self.client.post(
            reverse("explore:toggle_favorite", kwargs={"pk": self.place.pk})
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(Favorite.objects.count(), 0)


class FavoritesListViewTests(TestCase):
    """Tests for the favorites list page"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="fan", password="pass123")
        self.creator = User.objects.create_user(username="creator", password="pass123")
        self.place = Place.objects.create(
            name="Test Place",
            description="d",
            address="a",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_authenticated_user_sees_their_favorites(self):
        """Test authenticated users see their own favorited places"""
        Favorite.objects.create(user=self.user, place=self.place)
        self.client.login(username="fan", password="pass123")
        response = self.client.get(reverse("explore:favorites"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_authenticated"])
        self.assertEqual(response.context["favorites_count"], 1)

    def test_anonymous_user_sees_empty_context(self):
        """Test anonymous users get an empty favorites context (client renders localStorage)"""
        response = self.client.get(reverse("explore:favorites"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_authenticated"])
        self.assertEqual(response.context["favorites_count"], 0)

    def test_anonymous_ids_render_public_places(self):
        hidden = Place.objects.create(
            name="Hidden", description="d", address="a", created_by=self.creator
        )
        response = self.client.get(
            reverse("explore:favorites"), {"ids": f"{self.place.pk},{hidden.pk},x"}
        )
        self.assertEqual(response.context["favorites_count"], 0)
        response = self.client.get(
            reverse("explore:favorites"), {"ids": f"{self.place.pk},{hidden.pk}"}
        )
        self.assertEqual(response.context["favorites"], [self.place])
        self.assertContains(response, 'data-remove-mode="true"')


class SyncFavoritesViewTests(TestCase):
    """Tests for syncing localStorage favorites to the backend"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="fan", password="pass123")
        self.creator = User.objects.create_user(username="creator", password="pass123")
        self.place = Place.objects.create(
            name="Test Place",
            description="d",
            address="a",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_sync_requires_login(self):
        """Test sync endpoint requires authentication"""
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data=json.dumps({"favorites": [self.place.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_get_request_not_allowed(self):
        """Test GET requests to sync endpoint are rejected"""
        self.client.login(username="fan", password="pass123")
        response = self.client.get(reverse("explore:sync_favorites"))
        self.assertEqual(response.status_code, 405)

    def test_sync_merges_new_favorites(self):
        """Test local favorite IDs not yet in the backend get created"""
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data=json.dumps({"favorites": [self.place.pk]}),
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["added"], 1)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, place=self.place).exists()
        )

    def test_sync_skips_already_favorited_places(self):
        """Test places already favorited are not duplicated or re-added"""
        Favorite.objects.create(user=self.user, place=self.place)
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data=json.dumps({"favorites": [self.place.pk]}),
            content_type="application/json",
        )
        data = response.json()
        self.assertEqual(data["added"], 0)
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 1)

    def test_sync_ignores_nonexistent_or_unapproved_places(self):
        """Test IDs that don't map to an approved place are silently skipped"""
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data=json.dumps({"favorites": [999999]}),
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["added"], 0)

    def test_sync_ignores_invalid_ids(self):
        """IDs que não são números são ignorados em vez de derrubar a sincronização"""
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data=json.dumps({"favorites": ["not-an-id"]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["added"], 0)

    def test_sync_rejects_invalid_json(self):
        """Test malformed JSON body returns a 400 error"""
        self.client.login(username="fan", password="pass123")
        response = self.client.post(
            reverse("explore:sync_favorites"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])


class FavoritesApiListViewTests(TestCase):
    """Tests for the favorites API list endpoint used to sync localStorage"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="fan", password="pass123")
        self.creator = User.objects.create_user(username="creator", password="pass123")
        self.place = Place.objects.create(
            name="Test Place",
            description="d",
            address="a",
            created_by=self.creator,
            is_approved=True,
            is_active=True,
        )

    def test_requires_login(self):
        """Test the endpoint requires authentication"""
        response = self.client.get(reverse("explore:favorites_api_list"))
        self.assertEqual(response.status_code, 302)

    def test_returns_favorite_place_ids(self):
        """Test the endpoint returns the current user's favorite place IDs"""
        Favorite.objects.create(user=self.user, place=self.place)
        self.client.login(username="fan", password="pass123")
        response = self.client.get(reverse("explore:favorites_api_list"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["favorites"], [self.place.pk])
        self.assertEqual(data["count"], 1)


class FavoriteModelTests(TestCase):
    """Tests for the Favorite model"""

    def test_favorite_string_representation(self):
        """Test Favorite string representation"""
        user = User.objects.create_user(username="fan", password="pass123")
        creator = User.objects.create_user(username="creator", password="pass123")
        place = Place.objects.create(
            name="Test Place", description="d", address="a", created_by=creator
        )
        favorite = Favorite.objects.create(user=user, place=place)
        self.assertEqual(str(favorite), f"{user.username} favorited {place.name}")


class PlacesByIdsAPITests(TestCase):
    """Tests for the places_by_ids_api endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass123")
        self.category = Category.objects.create(
            name="Restaurant", slug="restaurant", icon="🍽️"
        )
        self.place = Place.objects.create(
            name="Approved Place",
            description="d",
            address="a",
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )
        self.place.categories.add(self.category)
        self.url = reverse("explore:places_by_ids_api")

    def test_no_ids_returns_empty_list(self):
        """Test missing 'ids' query param returns an empty result"""
        response = self.client.get(self.url)
        data = response.json()
        self.assertEqual(data["places"], [])
        self.assertEqual(data["count"], 0)

    def test_invalid_id_format_returns_400(self):
        """Test non-numeric IDs return a 400 error"""
        response = self.client.get(self.url, {"ids": "abc,def"})
        self.assertEqual(response.status_code, 400)

    def test_returns_places_matching_ids(self):
        """Test the endpoint returns matching approved places"""
        response = self.client.get(self.url, {"ids": str(self.place.pk)})
        data = response.json()
        self.assertEqual(data["count"], 1)
        place_data = data["places"][0]
        self.assertEqual(place_data["name"], "Approved Place")
        self.assertEqual(place_data["categories"][0]["name"], "Restaurant")

    def test_excludes_unapproved_places(self):
        """Test unapproved places are excluded even if their ID is requested"""
        unapproved = Place.objects.create(
            name="Unapproved",
            description="d",
            address="a",
            created_by=self.user,
            is_approved=False,
        )
        response = self.client.get(
            self.url, {"ids": f"{self.place.pk},{unapproved.pk}"}
        )
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["places"][0]["id"], self.place.pk)


class ExplorePageSearchTests(TestCase):
    """Tests for search filtering on the explore page"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass123")
        self.category = Category.objects.create(name="Restaurants", slug="restaurants")
        self.matching_place = Place.objects.create(
            name="Pizza Place",
            description="Great pizza",
            address="a",
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )
        self.other_place = Place.objects.create(
            name="Bookstore",
            description="Lots of books",
            address="a",
            created_by=self.user,
            is_approved=True,
            is_active=True,
        )

    def test_search_query_filters_by_name(self):
        """Test the search query filters places by name"""
        response = self.client.get(reverse("explore:explore") + "?q=Pizza")
        self.assertEqual(response.context["all_places"].count(), 1)
        self.assertEqual(response.context["all_places"].first(), self.matching_place)

    def test_search_query_filters_by_description(self):
        """Test the search query also matches the description"""
        response = self.client.get(reverse("explore:explore") + "?q=books")
        self.assertEqual(response.context["all_places"].count(), 1)
        self.assertEqual(response.context["all_places"].first(), self.other_place)

    def test_search_matches_translated_name(self):
        """Visitors searching in English or Spanish find the translated name"""
        self.matching_place.translations = {
            "en": {"name": "Araçatiba Lagoon"},
            "es": {"name": "Laguna de Araçatiba"},
        }
        self.matching_place.save()
        url = reverse("explore:explore")
        for query in ("lagoon", "laguna de ara"):
            response = self.client.get(url, {"q": query})
            self.assertEqual(
                list(response.context["all_places"]), [self.matching_place]
            )
        self.assertEqual(
            self.client.get(url, {"q": "zzz"}).context["all_places"].count(), 0
        )


class CategorySearchTests(TestCase):
    """Search inside a category must filter, not list everything"""

    def setUp(self):
        user = User.objects.create_user(username="searcher", password="pass123")
        self.category = Category.objects.create(name="Praias", slug="praias-busca")
        for name in ("Praia do Sol", "Mirante Azul"):
            place = Place.objects.create(
                name=name,
                description="d",
                address="a",
                created_by=user,
                is_approved=True,
                is_active=True,
            )
            place.categories.add(self.category)
        self.url = reverse(
            "explore:category_detail", kwargs={"slug": self.category.slug}
        )

    def test_query_filters_places_in_category(self):
        response = self.client.get(self.url, {"q": "mirante"})
        self.assertContains(response, "Mirante Azul")
        self.assertNotContains(response, "Praia do Sol")

    def test_no_match_shows_search_empty_state(self):
        response = self.client.get(self.url, {"q": "zzzz"})
        self.assertContains(response, "Nenhum resultado para")
        self.assertNotContains(response, "Praia do Sol")


class BulkPlaceModerationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="mod", password="pass123", is_staff=True
        )
        self.regular = User.objects.create_user(username="reg", password="pass123")
        self.places = [
            Place.objects.create(
                name=f"Pendente {i}",
                description="d",
                address="a",
                created_by=self.regular,
            )
            for i in range(3)
        ]
        self.approved = Place.objects.create(
            name="Ja aprovado",
            description="d",
            address="a",
            created_by=self.regular,
            is_approved=True,
        )
        self.url = reverse("explore:bulk_places")

    def _post(self, ids, **extra):
        return self.client.post(self.url, {"ids": ids, **extra})

    def test_bulk_approve(self):
        self.client.login(username="mod", password="pass123")
        ids = [p.pk for p in self.places] + [self.approved.pk]
        response = self._post(ids, action="approve")
        self.assertEqual(response.status_code, 302)
        for place in self.places:
            place.refresh_from_db()
            self.assertTrue(place.is_approved)
        self.assertEqual(
            PlaceApproval.objects.filter(
                action=PlaceApproval.ActionType.APPROVE, reviewer=self.staff
            ).count(),
            3,
        )
        self.assertFalse(self.approved.approval_history.exists())
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("3 lugares aprovados", messages)

    def test_bulk_approve_single_uses_singular(self):
        self.client.login(username="mod", password="pass123")
        response = self._post([self.places[0].pk], action="approve")
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("1 lugar aprovado", messages)

    def test_non_staff_forbidden(self):
        self.client.login(username="reg", password="pass123")
        self._post([self.places[0].pk], action="approve")
        self.places[0].refresh_from_db()
        self.assertFalse(self.places[0].is_approved)
        self.assertFalse(PlaceApproval.objects.exists())

    def test_get_not_allowed(self):
        self.client.login(username="mod", password="pass123")
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_bulk_remove_requires_reason(self):
        self.client.login(username="mod", password="pass123")
        self._post([self.places[0].pk], action="remove")
        self.places[0].refresh_from_db()
        self.assertTrue(self.places[0].is_active)
        self.assertFalse(PlaceApproval.objects.exists())

    def test_bulk_remove_outros_requires_comment(self):
        self.client.login(username="mod", password="pass123")
        self._post([self.places[0].pk], action="remove", reason="Outros")
        self.places[0].refresh_from_db()
        self.assertTrue(self.places[0].is_active)

    def test_bulk_remove(self):
        self.client.login(username="mod", password="pass123")
        ids = [p.pk for p in self.places[:2]]
        self._post(ids, action="remove", reason="Duplicado")
        for place in self.places[:2]:
            place.refresh_from_db()
            self.assertFalse(place.is_active)
        self.assertEqual(
            PlaceApproval.objects.filter(
                action=PlaceApproval.ActionType.REJECT, comments="Duplicado"
            ).count(),
            2,
        )
        self.places[2].refresh_from_db()
        self.assertTrue(self.places[2].is_active)

    def test_bulk_remove_outros_uses_comment(self):
        self.client.login(username="mod", password="pass123")
        self._post(
            [self.places[0].pk], action="remove", reason="Outros", comments="Spam"
        )
        self.assertTrue(PlaceApproval.objects.filter(comments="Spam").exists())

    def test_invalid_ids_ignored(self):
        self.client.login(username="mod", password="pass123")
        response = self._post(["abc", "99999"], action="approve")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlaceApproval.objects.exists())

    def test_external_next_is_ignored(self):
        self.client.login(username="mod", password="pass123")
        response = self._post(
            [self.places[0].pk], action="approve", next="https://evil.example/"
        )
        self.assertNotIn("evil.example", response["Location"])
