from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

TAG = Template("{% load navigation %}{% back_url '/default/' %}")


def render(request):
    return TAG.render(Context({"request": request}))


class BackUrlTagTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_uses_referer_from_same_site(self):
        request = self.rf.get(
            "/explore/place/1/edit/",
            HTTP_REFERER="http://testserver/explore/admin/backlog/?status=pending",
        )
        self.assertEqual(render(request), "/explore/admin/backlog/?status=pending")

    def test_posted_next_wins_after_validation_error(self):
        request = self.rf.post(
            "/explore/place/1/edit/",
            {"next": "/painel-admin/"},
            HTTP_REFERER="http://testserver/explore/place/1/edit/",
        )
        self.assertEqual(render(request), "/painel-admin/")

    def test_ignores_external_and_same_page(self):
        external = self.rf.get("/form/", HTTP_REFERER="https://evil.example/")
        same = self.rf.get("/form/", HTTP_REFERER="http://testserver/form/")
        self.assertEqual(render(external), "/default/")
        self.assertEqual(render(same), "/default/")
