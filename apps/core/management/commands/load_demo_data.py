from django.core.management.base import BaseCommand

from apps.core import demo_snapshot
from apps.explore.models import Place


class Command(BaseCommand):
    help = (
        "Cria o conteúdo de demonstração num banco sem lugares e envia ao armazenamento "
        "as fotos do snapshot que estiverem faltando."
    )

    def handle(self, *args, **options):
        if Place.objects.exists():
            self.stdout.write("Já há lugares no banco; nada a carregar.")
        else:
            created = demo_snapshot.load()
            self.stdout.write(
                self.style.SUCCESS(f"{created} lugares de demonstração criados.")
            )
        uploaded = demo_snapshot.restore_media()
        if uploaded:
            self.stdout.write(self.style.SUCCESS(f"{uploaded} foto(s) restaurada(s)."))
