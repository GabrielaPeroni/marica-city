from math import ceil

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext


def wants_json(request):
    """fetch/XHR recebe JSON; navegação do navegador recebe a página."""
    return (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("Sec-Fetch-Dest") == "empty"
    )


def _wait_text(seconds):
    if seconds < 90:
        return ngettext("%(n)s segundo", "%(n)s segundos", seconds) % {"n": seconds}
    minutes = ceil(seconds / 60)
    return ngettext("%(n)s minuto", "%(n)s minutos", minutes) % {"n": minutes}


def ratelimited_error(request, exception):
    """429 com `Retry-After`: JSON para o JS, página amigável para o navegador."""
    retry_after = getattr(exception, "retry_after", 60)
    wait = _wait_text(retry_after)
    message = _(
        "Muitas tentativas em pouco tempo. Aguarde %(wait)s e tente de novo."
    ) % {"wait": wait}
    if wants_json(request):
        response = JsonResponse(
            {"success": False, "error": message, "retry_after": retry_after},
            status=429,
        )
    else:
        response = render(
            request, "429.html", {"wait": wait, "retry_after": retry_after}, status=429
        )
    response["Retry-After"] = str(retry_after)
    return response
