from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme


def is_speculative(request):
    """True for prefetch/prerender requests, which the visitor may never see."""
    return "prefetch" in request.headers.get("Sec-Purpose", "")


def is_cron_request(request):
    """True when the request carries `Authorization: Bearer <CRON_SECRET>`."""
    return bool(settings.CRON_SECRET) and constant_time_compare(
        request.headers.get("Authorization", ""), f"Bearer {settings.CRON_SECRET}"
    )


def local_url(request, url, default=None):
    """`url` if it is on this site, else `default` (blocks open redirects)."""
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return default


def safe_next(request, default):
    """Return the POSTed `next` URL when it is local, otherwise `default`."""
    return local_url(request, request.POST.get("next"), default)
