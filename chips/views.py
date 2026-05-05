"""
WhatTheChip — Chips API views
GET /chips/search/?pn=XXXX   →  JSON com resultado de classificação
GET /chips/decode/?pn=XXXX   →  HTML parcial (HTMX) com decode card
"""
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page

from .engine import classify
from .models import KnownPart, SearchLog, UnknownChip


_CONF_LABEL = {
    'confirmed':   '✅ Confirmado',
    'manual':      '✏️ Manual',
    'distributor': '🏪 Distribuidor',
    'ai_high':     '🤖 IA — Alta',
    'ai_medium':   '🤖 IA — Média',
    'ai_low':      '🤖 IA — Baixa',
    'estimated':   '~ Estimado',
}


@require_GET
def search_api(request):
    """
    Classifica um Part Number e retorna JSON.

    Parâmetros:
        pn  — Part Number a classificar (obrigatório, mín. 4 chars)

    Resposta (sucesso):
        {
          "pn": "K4B4G16E",
          "known": true,
          "known_exact": false,
          "chip_type": "RAM",
          "subtype": "DDR3 SDRAM",
          "brand": "Samsung",
          "family_prefix": "K4B",
          "dram_density": "4Gb = 512MB por die [✓]",
          "capacity": null,
          "is_emcp": false,
          "confidence": "estimated",
          "doc_url": "/fab-samsung/",
          "remarked_flag": false,
          ...
        }
    """
    pn = request.GET.get("pn", "").strip()

    if not pn:
        return JsonResponse({"error": "Parâmetro 'pn' obrigatório"}, status=400)

    if len(pn) < 4:
        return JsonResponse({"error": "PN muito curto — mínimo 4 caracteres"}, status=400)

    result = classify(pn)
    return JsonResponse(result)


@require_GET
def decode_html(request):
    """
    Classifica um Part Number e retorna HTML parcial para o HTMX.

    Parâmetros:
        pn  — Part Number a classificar (obrigatório, mín. 4 chars)

    Resposta:
        HTML do decode card pronto para inserção via HTMX swap.
        Retorna string vazia se o PN for muito curto — HTMX limpa o target.
    """
    pn = request.GET.get("pn", "").strip()

    if not pn or len(pn) < 4:
        return HttpResponse("")   # HTMX limpa #dc-result

    result = classify(pn)

    context = {
        "result": result,
        "confidence_label": _CONF_LABEL.get(
            result.get("confidence", ""), result.get("confidence", "")
        ),
        "show_source": bool(
            result.get("source_url") and
            not result.get("source_url", "").startswith("gemini:")
        ),
    }

    return render(request, "chips/partials/decode_card.html", context)


@require_GET
def stats_api(request):
    """Estatísticas rápidas do banco — usadas na página inicial."""
    return JsonResponse({
        "total_parts":   KnownPart.objects.count(),
        "enriched":      KnownPart.objects.filter(status="enriched").count(),
        "raw":           KnownPart.objects.filter(status="raw").count(),
        "total_searches": SearchLog.objects.count(),
        "unknown_count": UnknownChip.objects.count(),
    })
