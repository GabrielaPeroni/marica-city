from django.apps import AppConfig


class ExploreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.explore"

    def ready(self):
        from django.core.cache import cache
        from django.db.models.signals import post_delete, post_save

        from apps.core.context_processors import FOOTER_CATEGORIES_KEY

        from .models import Category

        def forget(**kwargs):
            cache.delete(FOOTER_CATEGORIES_KEY)

        post_save.connect(forget, sender=Category, weak=False)
        post_delete.connect(forget, sender=Category, weak=False)
