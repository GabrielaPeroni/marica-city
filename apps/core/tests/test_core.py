from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import User
from apps.core.views import calculate_percentage_change
from apps.explore.models import Category, Place, PlaceImage, PlaceReview
from apps.news.models import News, NewsCategory


class LandingPageTests(TestCase):
    """Teste suite pra funcionalidade da pagina inicial"""

    def setUp(self):
        """Prepara a data"""
        self.client = Client()
        self.url = reverse("core:landing")

        # Cria as categorias de teste
        self.category1 = Category.objects.create(
            name="Restaurantes", slug="restaurantes", icon="🍽️"
        )
        self.category2 = Category.objects.create(
            name="Natureza", slug="natureza", icon="🌳"
        )

    def test_landing_page_loads(self):
        """Testa que a pagina inicial carrega"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/landing.html")

    def test_landing_page_shows_categories(self):
        """Testa que a pagina inicial mostra categorias"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Restaurantes")
        self.assertContains(response, "Natureza")
        self.assertContains(response, "🍽️")
        self.assertContains(response, "🌳")

    def test_landing_page_shows_title(self):
        """Testa que a pagina inicial mostra o titulo correto"""
        response = self.client.get(self.url)
        self.assertContains(response, "MaricaCity")
        self.assertContains(response, "Descubra")

    def test_landing_page_has_cta_buttons(self):
        """Test that landing page has call-to-action buttons"""
        response = self.client.get(self.url)
        self.assertContains(response, "Explorar")
        self.assertContains(response, "Cadastre-se")

    def test_landing_page_shows_hero_section(self):
        """Testa que a pagina inicial tem o carrosel"""
        response = self.client.get(self.url)
        self.assertContains(response, "hero-section")
        self.assertContains(response, "swiper")

    @override_settings(GOOGLE_MAPS_API_KEY="")
    def test_landing_map_uses_leaflet_without_api_key(self):
        """O mapa usa Leaflet + OpenStreetMap e não depende da chave do Google"""
        response = self.client.get(self.url)
        self.assertContains(response, "landing-map")
        self.assertContains(response, "Navegue pelos Lugares")
        self.assertContains(response, "js/components/lazy_assets.js")
        self.assertContains(response, "js/pages/landing_map.js")
        self.assertNotContains(response, "unpkg.com/leaflet")
        self.assertNotContains(response, "maps.googleapis.com")


class LandingCategoryTileTests(TestCase):
    """Cada categoria mostra a foto do seu lugar público mais recente, sem N+1"""

    def setUp(self):
        from unittest import mock

        self.owner = User.objects.create_user(username="dono", password="x")
        for name in ("thumbnail_url", "placeholder_uri"):
            patcher = mock.patch(
                f"apps.core.templatetags.thumbs.{name}", autospec=True, return_value=""
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    def _category_with_place(self, slug, approved=True):
        category = Category.objects.create(name=slug.title(), slug=slug)
        place = Place.objects.create(
            name=f"Lugar {slug}",
            description="d",
            address="a",
            created_by=self.owner,
            is_approved=approved,
        )
        place.categories.add(category)
        PlaceImage.objects.create(
            place=place, image=f"places/{slug}.jpg", is_primary=True
        )
        return category

    def test_each_category_gets_its_own_cover(self):
        self._category_with_place("praias")
        self._category_with_place("lagoas")
        self._category_with_place("trilhas", approved=False)
        categories = self.client.get(reverse("core:landing")).context["categories"]
        covers = {c.slug: c.cover and c.cover.image.name for c in categories}
        self.assertEqual(covers["praias"], "places/praias.jpg")
        self.assertEqual(covers["lagoas"], "places/lagoas.jpg")
        self.assertIsNone(covers["trilhas"])

    def test_query_count_does_not_grow_with_categories(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._category_with_place("praias")
        with CaptureQueriesContext(connection) as one:
            self.client.get(reverse("core:landing"))
        for slug in ("lagoas", "trilhas", "cultura"):
            self._category_with_place(slug)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("core:landing"))
        self.assertEqual(len(many), len(one))


class AboutPageTests(TestCase):
    """Teste suite pra funcionalidade da pagina Sobre"""

    def setUp(self):
        """Prepara a data"""
        self.client = Client()
        self.url = reverse("core:about")

    def test_about_page_loads(self):
        """Testa que a pagina Sobre carrega"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/about.html")

    def test_about_page_contains_info(self):
        """Testa que a pagina Sobre contem informacoes"""
        response = self.client.get(self.url)
        self.assertContains(response, "Sobre")


class AdminDashboardTests(TestCase):
    """Teste suite pra funcionalidade do admin dashboard"""

    def setUp(self):
        """Prepara a data"""
        self.client = Client()
        self.url = reverse("core:admin_dashboard")

        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regularuser", password="testpass123", is_staff=False
        )

        self.category = Category.objects.create(
            name="Restaurantes", slug="restaurantes", icon="🍽️"
        )

        self.approved_place = Place.objects.create(
            name="Approved Place",
            description="An approved place",
            address="123 Test St",
            created_by=self.regular_user,
            is_approved=True,
        )

        self.pending_place = Place.objects.create(
            name="Pending Place",
            description="A pending place",
            address="456 Test Ave",
            created_by=self.regular_user,
            is_approved=False,
        )

    def test_admin_dashboard_requires_login(self):
        """Testa que o admin dash requer autenticacao"""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/?next={self.url}")

    def test_admin_dashboard_requires_staff_permission(self):
        """Testa que o admin dash requer permissao de staff (is_staff=True)"""
        # Try with regular user - should be denied access
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(self.url)
        # Should either return 403 or redirect (both are valid)
        self.assertIn(response.status_code, [302, 403])

    def test_admin_dashboard_loads_for_staff(self):
        """Testa que o admin dash carrega para staff"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/admin_dashboard.html")

    def test_admin_dashboard_shows_statistics(self):
        """Testa que o that admin dash mostra statisticas"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)

        self.assertEqual(response.context["pending_places"], 1)
        self.assertEqual(response.context["places_this_week"], 2)
        self.assertEqual(response.context["users_this_week"], 2)

    def test_admin_dashboard_shows_content(self):
        """Testa que o that admin dash mostra conteudo relevante"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)

        self.assertContains(response, "Visão geral")


class HealthViewTests(TestCase):
    """Testa a probe de liveness/readiness"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("healthz")

    def test_health_endpoint_returns_ok(self):
        """Testa que o endpoint de health retorna status ok"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(ALLOWED_HOSTS=["example.com"], SECURE_SSL_REDIRECT=True)
    def test_health_endpoint_answers_internal_probes(self):
        """Sondas internas (127.0.0.1, http) recebem 200, sem 400 de host nem 301"""
        response = self.client.get(self.url, HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_rejects_post(self):
        """Testa que o endpoint de health só aceita GET"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class CalculatePercentageChangeTests(TestCase):
    """Testes unitários para a função utilitária calculate_percentage_change"""

    def test_increase_from_positive_previous(self):
        """Testa cálculo normal de aumento percentual"""
        self.assertEqual(calculate_percentage_change(15, 10), 50.0)

    def test_decrease_from_positive_previous(self):
        """Testa cálculo normal de diminuição percentual"""
        self.assertEqual(calculate_percentage_change(5, 10), -50.0)

    def test_zero_previous_with_positive_current_returns_100(self):
        """Testa que ir de 0 para um valor positivo retorna 100%"""
        self.assertEqual(calculate_percentage_change(5, 0), 100)

    def test_zero_previous_with_zero_current_returns_zero(self):
        """Testa que 0 para 0 não é tratado como aumento"""
        self.assertEqual(calculate_percentage_change(0, 0), 0)


class AdminNewsListViewTests(TestCase):
    """Testes para a listagem administrativa de notícias"""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regularuser", password="testpass123", is_staff=False
        )
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.published = News.objects.create(
            title="Published Item",
            content="Content",
            author=self.staff_user,
            category=self.category,
            status=News.PUBLISHED,
        )
        self.draft = News.objects.create(
            title="Draft Item",
            content="Content",
            author=self.staff_user,
            category=self.category,
            status=News.DRAFT,
        )
        self.url = reverse("core:admin_news_list")

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem ver a lista"""
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:landing"))

    def test_loads_with_counts(self):
        """Testa que a página carrega com contagens corretas"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        counts = {key: n for key, _l, n, *_ in response.context["status_cards"]}
        self.assertEqual(counts["all"], 2)
        self.assertEqual(counts["published"], 1)
        self.assertEqual(counts["draft"], 1)

    def test_filter_by_status(self):
        """Testa filtro por status de publicação"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url + "?status=" + News.PUBLISHED)
        titles = {n.title for n in response.context["news_list"]}
        self.assertEqual(titles, {"Published Item"})

    def test_filter_by_search_query(self):
        """Testa filtro por busca no título"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url + "?q=Draft")
        titles = {n.title for n in response.context["news_list"]}
        self.assertEqual(titles, {"Draft Item"})


class AdminNewsCreateViewTests(TestCase):
    """Testes para a criação de notícias pelo admin"""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regularuser", password="testpass123", is_staff=False
        )
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.url = reverse("core:admin_news_create")

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem acessar a criação"""
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:landing"))

    def test_get_shows_form(self):
        """Testa que GET exibe o formulário de criação"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/admin/news_form.html")

    def test_valid_post_creates_news(self):
        """Testa que POST válido cria a notícia com o autor correto"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(
            self.url,
            data={
                "title": "Brand New Article",
                "category": self.category.pk,
                "content": "Some content",
                "excerpt": "",
                "status": News.DRAFT,
            },
        )
        self.assertRedirects(response, reverse("core:admin_news_list"))
        news = News.objects.get(title="Brand New Article")
        self.assertEqual(news.author, self.staff_user)

    def test_invalid_post_shows_errors(self):
        """Testa que POST inválido não cria a notícia e reexibe o formulário"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(self.url, data={"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(News.objects.count(), 0)


class AdminNewsEditViewTests(TestCase):
    """Testes para a edição de notícias pelo admin"""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regularuser", password="testpass123", is_staff=False
        )
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.news = News.objects.create(
            title="Original Title",
            content="Original content",
            author=self.staff_user,
            category=self.category,
            status=News.DRAFT,
        )
        self.url = reverse("core:admin_news_edit", kwargs={"pk": self.news.pk})

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem editar"""
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:landing"))

    def test_get_shows_prefilled_form(self):
        """Testa que GET exibe o formulário preenchido"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original Title")

    def test_valid_post_updates_news(self):
        """Testa que POST válido atualiza a notícia"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(
            self.url,
            data={
                "title": "Updated Title",
                "category": self.category.pk,
                "content": "Updated content",
                "excerpt": "",
                "status": News.DRAFT,
            },
        )
        self.assertRedirects(response, reverse("core:admin_news_list"))
        self.news.refresh_from_db()
        self.assertEqual(self.news.title, "Updated Title")

    def test_nonexistent_news_returns_404(self):
        """Testa que editar notícia inexistente retorna 404"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(
            reverse("core:admin_news_edit", kwargs={"pk": 999999})
        )
        self.assertEqual(response.status_code, 404)


class AdminNewsDeleteViewTests(TestCase):
    """Testes para a exclusão de notícias pelo admin"""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regularuser", password="testpass123", is_staff=False
        )
        self.category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        self.news = News.objects.create(
            title="To Be Deleted",
            content="Content",
            author=self.staff_user,
            category=self.category,
        )
        self.url = reverse("core:admin_news_delete", kwargs={"pk": self.news.pk})

    def test_requires_moderator_permission(self):
        """Testa que apenas moderadores podem excluir"""
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:landing"))
        self.assertTrue(News.objects.filter(pk=self.news.pk).exists())

    def test_get_shows_confirmation(self):
        """Testa que GET exibe a página de confirmação"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/admin/news_delete_confirm.html")

    def test_post_deletes_news(self):
        """Testa que POST exclui a notícia"""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("core:admin_news_list"))
        self.assertFalse(News.objects.filter(pk=self.news.pk).exists())


class ErrorPageTests(TestCase):
    """Unknown URLs render the branded 404 page"""

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_branded_404(self):
        response = self.client.get("/pagina-que-nao-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertContains(response, reverse("explore:explore"), status_code=404)


class LandingLoginPromptTests(TestCase):
    """Anonymous visitors bounced from a protected page are told why"""

    def test_next_param_shows_login_prompt(self):
        response = self.client.get(
            reverse("core:landing"), {"next": "/explore/place/create/"}
        )
        self.assertContains(response, "crie uma conta gratuita")

    def test_no_prompt_without_next(self):
        response = self.client.get(reverse("core:landing"))
        self.assertNotContains(response, "crie uma conta gratuita")


class LanguageSwitcherTests(TestCase):
    """Interface in pt-br by default, switchable to English and Spanish"""

    def test_switcher_is_on_every_page(self):
        for url in (reverse("core:landing"), reverse("news:news_list")):
            response = self.client.get(url)
            self.assertContains(response, 'class="lang-switcher"', count=2)
            self.assertContains(response, 'value="es"')

    def test_default_language_is_portuguese(self):
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, '<html lang="pt-br">')
        self.assertContains(response, "Explorar")

    def test_switching_to_english_translates_the_interface(self):
        self.client.post(
            reverse("set_language"), {"language": "en", "next": "/"}, follow=True
        )
        response = self.client.get(reverse("news:news_list"))
        self.assertContains(response, '<html lang="en">')
        self.assertContains(response, "Upcoming events")
        self.assertNotContains(response, "Próximos eventos")

    def test_switching_to_spanish(self):
        self.client.post(reverse("set_language"), {"language": "es", "next": "/"})
        response = self.client.get(reverse("news:news_list"))
        self.assertContains(response, '<html lang="es">')
        self.assertContains(response, "Próximos eventos")  # mesma grafia em espanhol
        self.assertContains(response, "Explorar lugares")

    def test_javascript_catalog_is_served(self):
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        response = self.client.get(reverse("javascript-catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Remove from favorites")


class ContentTranslationTests(TestCase):
    """Conteúdo traduzido aparece no idioma escolhido, com fallback"""

    def setUp(self):
        from apps.core.content_translation import translate_object

        self.translate_object = translate_object
        self.category = Category.objects.create(
            name="Praias", slug="praias", description="As melhores praias"
        )

    def _fake(self, texts, target):
        return {
            "EN-US": ["Beaches", "The best beaches"],
            "ES": ["Playas", "Las mejores playas"],
        }[target]

    def test_translations_are_stored_per_language(self):
        data = self.translate_object(self.category, ask=self._fake)
        self.category.refresh_from_db()
        self.assertEqual(self.category.translations["en"]["name"], "Beaches")
        self.assertEqual(data["es"]["description"], "Las mejores playas")

    def test_pages_show_translation_and_fall_back_to_portuguese(self):
        self.translate_object(self.category, ask=self._fake)
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Praias")
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Beaches")
        Category.objects.create(name="Lagoas", slug="lagoas")
        self.assertContains(self.client.get(reverse("core:landing")), "Lagoas")

    def test_editing_the_source_marks_translation_stale(self):
        from apps.core.content_translation import needs_translation

        self.translate_object(self.category, ask=self._fake)
        self.category.refresh_from_db()
        self.assertFalse(needs_translation(self.category))
        self.category.description = "Outra descrição"
        self.assertTrue(needs_translation(self.category))


class AdminNewsFilterTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="editor", password="pass123", is_staff=True
        )
        category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.NEWS)
        for title, status in (("Pub", News.PUBLISHED), ("Rasc", News.DRAFT)):
            News.objects.create(
                title=title,
                content="c",
                category=category,
                author=self.staff,
                status=status,
            )
        self.client.login(username="editor", password="pass123")

    def test_status_tabs_filter_the_list(self):
        url = reverse("core:admin_news_list")
        published = self.client.get(url + "?status=published").context["news_list"]
        drafts = self.client.get(url + "?status=draft").context["news_list"]
        self.assertEqual([n.title for n in published], ["Pub"])
        self.assertEqual([n.title for n in drafts], ["Rasc"])


class VisitPageTests(TestCase):
    def test_visit_info_lives_on_the_about_page(self):
        landing = self.client.get(reverse("core:landing"))
        self.assertContains(landing, reverse("core:about") + "#visite")
        self.assertRedirects(
            self.client.get("/planeje-sua-visita/"),
            "/sobre/#visite",
            status_code=301,
            fetch_redirect_response=False,
        )
        response = self.client.get(reverse("core:about"))
        self.assertContains(response, "Vermelhinhos")
        self.assertContains(response, "<strong>192</strong>", html=False)


class AdminNewsBulkTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regularuser", password="testpass123"
        )
        category, _ = NewsCategory.objects.get_or_create(name=NewsCategory.EVENT)
        self.items = [
            News.objects.create(
                title=f"Item {i}",
                content="Content",
                author=self.staff,
                category=category,
                status=News.DRAFT,
            )
            for i in range(3)
        ]
        self.url = reverse("core:admin_news_bulk")

    def _post(self, ids, action):
        return self.client.post(self.url, {"ids": ids, "action": action})

    def test_bulk_publish(self):
        self.client.login(username="staffuser", password="testpass123")
        self._post([i.pk for i in self.items[:2]], "publish")
        statuses = [News.objects.get(pk=i.pk).status for i in self.items]
        self.assertEqual(statuses, [News.PUBLISHED, News.PUBLISHED, News.DRAFT])
        self.assertIsNotNone(News.objects.get(pk=self.items[0].pk).publish_date)

    def test_bulk_archive(self):
        self.client.login(username="staffuser", password="testpass123")
        self._post([i.pk for i in self.items], "archive")
        self.assertEqual(News.objects.filter(status=News.ARCHIVED).count(), 3)

    def test_bulk_delete(self):
        self.client.login(username="staffuser", password="testpass123")
        self._post([self.items[0].pk, self.items[1].pk], "delete")
        self.assertEqual(News.objects.count(), 1)

    def test_already_archived_ignored_in_count(self):
        self.client.login(username="staffuser", password="testpass123")
        self.items[0].status = News.ARCHIVED
        self.items[0].save()
        response = self._post([self.items[0].pk, self.items[1].pk], "archive")
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("1 evento arquivado", messages)

    def test_non_staff_forbidden(self):
        self.client.login(username="regularuser", password="testpass123")
        self._post([self.items[0].pk], "delete")
        self.assertEqual(News.objects.count(), 3)

    def test_invalid_action_changes_nothing(self):
        self.client.login(username="staffuser", password="testpass123")
        self._post([self.items[0].pk], "explode")
        self.assertEqual(News.objects.filter(status=News.DRAFT).count(), 3)

    def test_list_page_has_checkboxes(self):
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(reverse("core:admin_news_list"))
        self.assertContains(response, "data-bulk-item", count=3)


class IconTagTests(TestCase):
    """{% icon %}: SVG Lucide inline e decorativo"""

    def render(self, source, **context):
        from django.template import engines

        template = engines["django"].from_string("{% load icons %}" + source)
        return template.render(context)

    def test_renders_inline_svg(self):
        html = self.render('{% icon "map-pin" class="size-4" %}')
        self.assertTrue(html.startswith("<svg "))
        self.assertIn('class="lucide lucide-map-pin size-4"', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('stroke="currentColor"', html)
        self.assertIn("<path", html)

    def test_extra_attributes_pass_through(self):
        html = self.render('{% icon "heart" data_icon="heart" aria_label="Favorito" %}')
        self.assertIn('data-icon="heart"', html)
        self.assertIn('aria-label="Favorito"', html)
        self.assertIn('role="img"', html)
        self.assertNotIn("aria-hidden", html)

    def test_attributes_are_escaped(self):
        html = self.render('{% icon "x" title=value %}', value="<b>")
        self.assertIn('title="&lt;b&gt;"', html)

    def test_missing_icon_fails_loudly(self):
        from django.template import TemplateSyntaxError

        with self.assertRaises(TemplateSyntaxError):
            self.render('{% icon "no-such-icon" %}')


class CottonComponentTests(TestCase):
    """Componentes de templates/cotton renderizam com dados reais"""

    def setUp(self):
        user = User.objects.create_user(username="owner", password="pass12345")
        self.category = Category.objects.create(name="Praias", slug="praias")
        self.place = Place.objects.create(
            name="Praia Teste",
            description="Descrição",
            address="Rua 1, Maricá",
            created_by=user,
            is_approved=True,
        )
        self.place.categories.add(self.category)

    def render(self, source, **context):
        from django.template import engines

        from django_cotton.compiler_regex import CottonCompiler

        compiled = CottonCompiler().process(source)
        with translation.override("pt-br"):
            return engines["django"].from_string(compiled).render(context)

    def test_place_card(self):
        html = self.render('<c-place-card :place="place" />', place=self.place)
        self.assertIn(f'href="/explore/place/{self.place.pk}/"', html)
        self.assertIn("Praia Teste", html)
        self.assertIn("Praias", html)
        self.assertIn(f'data-place-id="{self.place.pk}"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn("data-favorite-item", html)

    def test_place_card_remove_mode(self):
        html = self.render(
            '<c-place-card :place="place" remove="true" />', place=self.place
        )
        self.assertIn('data-remove-mode="true"', html)
        self.assertIn('aria-pressed="true"', html)

    def test_event_card(self):
        category = NewsCategory.objects.first()
        event = News.objects.create(
            title="Festa",
            slug="festa",
            content="Texto",
            category=category,
            author=User.objects.get(username="owner"),
            status="PUBLISHED",
        )
        html = self.render('<c-event-card :event="event" lead />', event=event)
        self.assertIn('href="/eventos/festa/"', html)
        self.assertIn("Festa", html)
        self.assertIn("md:flex-row", html)

    def test_simple_components(self):
        html = self.render(
            '<c-button variant="outline" href="/x/">Ir</c-button>'
            '<c-badge variant="brand">Novo</c-badge>'
            '<c-section-heading title="Em alta" href="/explore/" />'
            '<c-empty-state title="Nada" />'
            '<c-skeleton variant="card" />'
            '<c-rating :value="4.5" :count="2" />'
            '<c-dialog id="d1" title="Remover?">Corpo</c-dialog>'
            '<c-card title="Card">Conteúdo</c-card>'
        )
        self.assertIn('<a href="/x/" class="btn " data-variant="outline"', html)
        self.assertIn('data-variant="brand"', html)
        self.assertIn("Ver todos", html)
        self.assertIn('class="empty', html)
        self.assertIn('aria-label="Nota 4,5 de 5"', html)
        self.assertIn('<dialog id="d1" class="dialog', html)
        self.assertIn("data-dialog-close", html)
        self.assertIn('<div class="card', html)

    def test_form_field(self):
        from apps.explore.forms import PlaceReviewForm

        form = PlaceReviewForm(data={})
        form.is_valid()
        html = self.render(
            '<c-form-field :field="form.comment" /><c-form-field :field="form.rating" />',
            form=form,
        )
        self.assertIn('data-invalid="true"', html)
        self.assertIn('class="textarea"', html)
        self.assertNotIn("form-control", html)
        self.assertIn('<fieldset class="field', html)
        self.assertIn('role="alert"', html)


class VercelAnalyticsTests(TestCase):
    @override_settings(VERCEL_ANALYTICS=True)
    def test_script_loads_on_vercel(self):
        self.assertContains(
            self.client.get(reverse("core:landing")), "/_vercel/insights/script.js"
        )

    @override_settings(VERCEL_ANALYTICS=False)
    def test_script_absent_elsewhere(self):
        self.assertNotContains(
            self.client.get(reverse("core:landing")), "/_vercel/insights/"
        )


class LandingReviewsTests(TestCase):
    """'Quem visitou conta' mostra avaliações boas e com texto, uma por lugar"""

    def setUp(self):
        owner = User.objects.create_user(username="dono", password="x")
        self.place = Place.objects.create(
            name="Lagoa",
            description="d",
            address="a",
            created_by=owner,
            is_approved=True,
        )
        for i, (rating, comment) in enumerate(
            [(5, "Vista linda"), (2, "Fraco"), (5, "")]
        ):
            PlaceReview.objects.create(
                place=self.place,
                user=User.objects.create_user(username=f"v{i}", password="x"),
                rating=rating,
                comment=comment,
            )

    def test_shows_good_reviews_with_text_once_per_place(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(
            [r.comment for r in response.context["reviews"]], ["Vista linda"]
        )
        self.assertContains(response, "Quem visitou conta")
