"""Tradução automática do conteúdo (lugares, eventos, avaliações) via DeepL.

Cada modelo traduzível guarda as versões em ``translations``:
``{"en": {"name": "..."}, "es": {...}, "source": "<hash dos campos em pt>"}``.
Quando o texto em português muda, o hash deixa de bater e o item volta a
ser traduzido no próximo lote.

Só roda em lote (cron diário ou ``translate_content``), nunca durante uma visita, e
``translate_pending`` limita o gasto: nada que um visitante faça chama o DeepL.
"""

import hashlib
import json
import logging
import time
import urllib.request
from contextlib import closing
from urllib.error import URLError

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import get_language

logger = logging.getLogger(__name__)

TARGETS = {"en": "EN-US", "es": "ES"}
CONTEXT = "Tourism guide about Maricá, a city in Rio de Janeiro, Brazil."

# Duas chamadas lentas depois do prazo ainda cabem nos 30 s da função na Vercel
REQUEST_TIMEOUT = 8
RUN_SECONDS = 12


class TranslationUnavailable(Exception):
    """O DeepL recusou ou não respondeu (cota, chave, limite, rede)."""


def source_hash(obj):
    text = "\x1f".join(getattr(obj, f) or "" for f in obj.TRANSLATABLE_FIELDS)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def needs_translation(obj):
    data = obj.translations or {}
    return data.get("source") != source_hash(obj) or any(t not in data for t in TARGETS)


def translated(obj, field):
    """Campo no idioma ativo, ou o original em português."""
    lang = (get_language() or "")[:2]
    value = ((obj.translations or {}).get(lang) or {}).get(field)
    return value or getattr(obj, field)


def is_machine_translated(obj):
    lang = (get_language() or "")[:2]
    return lang in TARGETS and bool((obj.translations or {}).get(lang))


def _deepl(path, body=None):
    key = settings.DEEPL_API_KEY
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    request = urllib.request.Request(
        f"https://{host}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Authorization": f"DeepL-Auth-Key {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=REQUEST_TIMEOUT
        ) as response:
            return json.loads(response.read())
    except (URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise TranslationUnavailable(str(exc)) from exc


def _translate_texts(texts, target):
    result = _deepl(
        "/v2/translate",
        {
            "text": texts,
            "source_lang": "PT",
            "target_lang": target,
            "preserve_formatting": True,
            "context": CONTEXT,
        },
    )
    translations = result.get("translations") or []
    if len(translations) != len(texts):
        raise TranslationUnavailable("resposta incompleta")
    return [t.get("text", "") for t in translations]


def _fields(obj):
    return {f: getattr(obj, f) for f in obj.TRANSLATABLE_FIELDS if getattr(obj, f)}


def translate_object(obj, ask=None):
    ask = ask or _translate_texts
    fields = _fields(obj)
    data = {"source": source_hash(obj)}
    for lang, target in TARGETS.items():
        result = ask(list(fields.values()), target) if fields else []
        data[lang] = {k: v.strip() for k, v in zip(fields, result) if v.strip()}
    obj.translations = data
    type(obj).objects.filter(pk=obj.pk).update(translations=data)
    return data


def _daily_key():
    return f"translate:chars:{timezone.localdate().isoformat()}"


def _remaining_budget():
    """Caracteres que ainda podem ser gastos: o menor entre o teto do dia e o do mês."""
    daily = settings.TRANSLATE_DAILY_CHAR_LIMIT - (cache.get(_daily_key()) or 0)
    usage = _deepl("/v2/usage")
    ceiling = int(usage.get("character_limit", 0) * settings.TRANSLATE_USAGE_CEILING)
    return min(daily, ceiling - usage.get("character_count", 0))


def _record_spend(chars):
    key = _daily_key()
    cache.add(key, 0, 60 * 60 * 48)
    try:
        cache.incr(key, chars)
    except ValueError:
        cache.set(key, chars, 60 * 60 * 48)


def _pending():
    """Só o que é público; avaliações por último, para spam não atrasar o resto."""
    from apps.explore.models import Category, Place, PlaceReview
    from apps.news.models import News

    public_places = Place.objects.public()
    sources = (
        Category.objects.filter(is_active=True),
        public_places,
        News.objects.published(),
        PlaceReview.objects.filter(place__in=public_places),
    )
    return (
        obj
        for queryset in sources
        for obj in queryset.order_by("pk").iterator()
        if needs_translation(obj)
    )


def translate_pending(limit=200, ask=None):
    """Traduz o que falta até bater um limite. Não tenta de novo se o DeepL falhar.

    ``stopped`` diz o que encerrou o lote: not_configured, unavailable, budget,
    time ou limit; vazio quando não sobrou nada a traduzir.
    """
    summary = {"translated": 0, "skipped": 0, "chars": 0, "stopped": ""}
    if not settings.DEEPL_API_KEY and ask is None:
        summary["stopped"] = "not_configured"
        return summary
    deadline = time.monotonic() + RUN_SECONDS
    try:
        budget = _remaining_budget()
    except TranslationUnavailable as exc:
        logger.warning("DeepL indisponível: %s", exc)
        summary["stopped"] = "unavailable"
        return summary

    with closing(_pending()) as pending:
        for obj in pending:
            if summary["translated"] >= limit:
                summary["stopped"] = "limit"
                break
            if time.monotonic() > deadline:
                summary["stopped"] = "time"
                break
            length = sum(len(text) for text in _fields(obj).values())
            if length > settings.TRANSLATE_MAX_ITEM_CHARS:
                logger.warning(
                    "%s %s tem %d caracteres; fica sem tradução",
                    type(obj).__name__,
                    obj.pk,
                    length,
                )
                summary["skipped"] += 1
                continue
            cost = length * len(TARGETS)
            if cost > budget:
                summary["stopped"] = "budget"
                break
            try:
                translate_object(obj, ask=ask)
            except TranslationUnavailable as exc:
                logger.warning("DeepL indisponível: %s", exc)
                summary["stopped"] = "unavailable"
                break
            _record_spend(cost)
            budget -= cost
            summary["chars"] += cost
            summary["translated"] += 1
    return summary
