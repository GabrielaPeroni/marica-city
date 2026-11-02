from django.core.management.base import BaseCommand

from apps.core.content_translation import translate_pending

MESSAGES = {
    "not_configured": "DEEPL_API_KEY não definida; nada foi traduzido.",
    "unavailable": "DeepL indisponível; tente mais tarde.",
    "budget": "Limite de caracteres atingido; o resto fica para o próximo lote.",
    "time": "Tempo do lote esgotado; o resto fica para o próximo lote.",
    "limit": "Limite de itens atingido; o resto fica para o próximo lote.",
}


class Command(BaseCommand):
    help = "Traduz para inglês e espanhol o conteúdo novo ou alterado (via DeepL)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        summary = translate_pending(limit=options["limit"])
        if summary["stopped"]:
            self.stderr.write(MESSAGES[summary["stopped"]])
        self.stdout.write(
            self.style.SUCCESS(
                f"{summary['translated']} item(ns) traduzido(s), "
                f"{summary['chars']} caracteres, {summary['skipped']} ignorado(s)."
            )
        )
