from django.core.management.base import BaseCommand

from apps.core import demo_snapshot
from apps.explore.models import Place


class Command(BaseCommand):
    help = (
        "Cria o conteúdo de demonstração num banco sem lugares, acrescenta eventos e "
        "traduções novas do snapshot e envia ao armazenamento as fotos que faltam."
    )

    def handle(self, *args, **options):
        if Place.objects.exists():
            self.stdout.write("Já há lugares no banco; nada a carregar.")
        else:
            created = demo_snapshot.load()
            self.stdout.write(
                self.style.SUCCESS(f"{created} lugares de demonstração criados.")
            )
        events, places = demo_snapshot.sync()
        if events or places:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{events} evento(s) criado(s), {places} tradução(ões) de lugar."
                )
            )
        uploaded = demo_snapshot.restore_media()
        if uploaded:
            self.stdout.write(self.style.SUCCESS(f"{uploaded} foto(s) restaurada(s)."))
