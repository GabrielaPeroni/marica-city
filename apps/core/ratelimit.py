"""Limites de requisições (django-ratelimit) com `Retry-After` para a resposta 429."""

import os
from functools import wraps

from django_ratelimit.core import get_usage
from django_ratelimit.exceptions import Ratelimited


class RateLimited(Ratelimited):
    def __init__(self, retry_after=60):
        super().__init__()
        self.retry_after = max(1, int(retry_after))


def client_ip(group, request):
    """Na Vercel o IP real vem no cabeçalho do proxy; fora dela, só o REMOTE_ADDR."""
    if os.environ.get("VERCEL"):
        forwarded = request.headers.get(
            "x-vercel-forwarded-for"
        ) or request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def limit(rate, key="ip", method="POST", when=None):
    """Barra a view quando `key` passa de `rate` ("10/h"). `method` filtra o que conta;
    `when(request)` falso não conta (ex.: só buscas com ?q=)."""
    key = client_ip if key == "ip" else key

    def decorator(view):
        group = f"{view.__module__}.{view.__qualname__}"

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if when and not when(request):
                return view(request, *args, **kwargs)
            usage = get_usage(
                request, group=group, key=key, rate=rate, method=method, increment=True
            )
            # limit == 0: o cache falhou; melhor deixar passar do que travar o site
            if usage and usage["limit"] and usage["should_limit"]:
                raise RateLimited(usage.get("time_left") or 60)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
