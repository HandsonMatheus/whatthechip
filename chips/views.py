"""
WhatTheChip — Chips API views
GET  /chips/search/?pn=XXXX   →  JSON com resultado de classificação  [PLATAFORMA]
GET  /chips/decode/?pn=XXXX   →  HTML parcial (HTMX) com decode card  [PLATAFORMA]
POST /chips/report/            →  Registra solicitação de correção
POST /chips/submit/            →  Recebe envio colaborativo ("Adicionar chip")

⚠ CONSULTA DE PN É SUPERFÍCIE DE PLATAFORMA (decisão do dono, 2026-08-05).
O WhatTheChip deixou de ser busca pública — "o Google dos chips" saiu do modelo
de negócio. Decode é o ATIVO, não vitrine. Ver `platform_only` abaixo.
"""
import json
import re
from functools import wraps
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .engine import classify
from .labels import profitability_label, source_label
from .models import KnownPart, SearchLog, UnknownChip, CorrectionRequest, ChipSubmission


# Rótulos de confiança EXIBIDOS no rodapé do decode card (i18n — I18N.md §5).
# Lazy: o dict é módulo-level, mas o texto resolve no idioma da request.
# A CHAVE ('confirmed'…) é canônica — a lógica/CSS usa a chave, nunca o rótulo.
_CONF_LABEL = {
    'confirmed':   _lazy('✅ Confirmado'),
    'manual':      _lazy('✏️ Manual'),
    'distributor': _lazy('🏪 Distribuidor'),
    'grammar':     _lazy('📐 Gramática'),
    'estimated':   _lazy('~ Estimado'),
}


def platform_only(*, as_json: bool):
    """Portão de PLATAFORMA para os endpoints de CONSULTA de PN.

    Decisão do dono em 2026-08-05: ninguém consulta PN por estes endpoints a não
    ser a plataforma. Nem anônimo, nem comprador (`Buyer.users`), nem
    operador/gerente/admin de empresa-cliente.

    ⚠ Por que `is_unmasked` (superuser) e NÃO `role_required('operator')` — esta
    é a parte que engana: um gate de PAPEL barraria só o anônimo, e o operador
    de uma empresa-cliente PASSARIA. Só que `search_api` devolve o `classify()`
    inteiro (subtype, densidade, capacidade, fonte, confiança e o veredito
    RENTÁVEL/NÃO RENTÁVEL) — seria entregar por URL exatamente aquilo que a
    máscara v3.1 esconde da tela dele. Gate de papel aqui = furo na F12.

    **Fonte única do critério:** `tenancy.access.is_unmasked` — o MESMO que
    bancada/tabela/export/OV/fatura usam. Não inventar lógica de máscara aqui
    (regra do `access.py`); se a v3.1 mudar, este portão acompanha sozinho.

    **A bancada NÃO passa por aqui:** o operador classifica via
    `estoque:preview` (`estoque.views.preview_chip`), que já aplica a máscara.
    Fechar estes dois não tira capacidade de ninguém que trabalha.

    Import tardio de `tenancy`: mantém `chips` sem dependência de app no load
    (mesmo padrão do `_price_quotes_for_admin` com o `pricing`).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            from tenancy.access import is_unmasked
            if not is_unmasked(request):
                if as_json:
                    return JsonResponse(
                        {"error": _("Consulta restrita.")}, status=403)
                # HTMX: 4xx não faz swap por padrão — o alvo fica intacto em
                # vez de exibir um card meio-vazio que pareceria bug.
                return HttpResponse(
                    '<span class="dc-denied">'
                    + _("Consulta restrita.") + '</span>', status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _effective_conf(result: dict) -> str:
    """Retorna a chave de confiança efetiva para exibição.
    Chips grammar_complete com confidence='estimated' mostram 'grammar' —
    a gramática com mapa verificado é mais confiável que um resultado parcial."""
    if result.get("grammar_complete") and result.get("confidence") == "estimated":
        return "grammar"
    return result.get("confidence", "estimated")


@require_GET
@platform_only(as_json=True)
def search_api(request):
    """
    Classifica um Part Number e retorna JSON. **Plataforma apenas** (403 para
    todo o resto — ver `platform_only`).

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
          ...
        }
    """
    pn = request.GET.get("pn", "").strip()

    if not pn:
        return JsonResponse({"error": _("Parâmetro 'pn' obrigatório")}, status=400)

    if len(pn) < 4:
        return JsonResponse({"error": _("PN muito curto — mínimo 4 caracteres")}, status=400)

    result = classify(pn)

    # F5-bis (PRECIFICACAO §7): a home renderiza o card em JS a partir DESTE
    # JSON — o preço entra aqui, e SÓ para papel admin (o gate é do servidor;
    # para os demais a chave "prices" nem existe na resposta).
    quotes = _price_quotes_for_admin(request, result)
    if quotes:
        from pricing.engine import serialize_quote
        result["prices"] = [serialize_quote(b, q) for b, q in quotes]

    return JsonResponse(result)


def _price_quotes_for_admin(request, result):
    """Bloco de preço do card (F5 — PRECIFICACAO §7): SÓ para papel ADMIN da
    empresa. Delegado à fonte única `pricing.engine.quotes_for_admin` (import
    lazy: o chips não depende do pricing no load do app).
    ⚠ É um HELPER, não view — sem @require_GET (o decorator devolveria um
    HttpResponseNotAllowed no lugar da lista se um fluxo POST o chamasse)."""
    from pricing.engine import quotes_for_admin
    return quotes_for_admin(request, result)


def _fx_info_for_card(request):
    """Carimbo da taxa de mercado p/ o card (PLANO_FX Fase A) — só quando
    o preço aparece (mesmo gate do quotes_for_admin)."""
    user = getattr(request, 'user', None)
    pode = bool((user is not None and user.is_authenticated
                 and user.is_superuser)
                or getattr(request, 'company_role', None) == 'admin')
    if not pode:
        return None
    from pricing.engine import fx_display
    return fx_display()


@platform_only(as_json=False)
def decode_html(request):
    """
    Classifica um Part Number e retorna HTML parcial para o HTMX.
    **Plataforma apenas** (403 para todo o resto — ver `platform_only`).

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

    # family_undocumented: extraído explicitamente do result e passado como variável
    # de contexto de primeiro nível — evita ambiguidade na resolução de template Django
    # (result.family_undocumented envolve lookup aninhado que pode falhar silenciosamente).
    family_undocumented = bool(result.get("family_undocumented", False))

    _PROFIT_KEY = {
        "RENTÁVEL":      "rentavel",
        "NÃO RENTÁVEL":  "nao-rentavel",
        "INDETERMINADO": "indeterminado",
    }
    profitable     = result.get("profitable", "INDETERMINADO")   # valor canônico (lógica)
    profitable_key = _PROFIT_KEY.get(profitable, "indeterminado")  # chave CSS
    profitable_label = profitability_label(profitable)             # rótulo traduzido (exibição)

    context = {
        "result":              result,
        "result_json":         json.dumps(result, ensure_ascii=False),
        "confidence_label":    _CONF_LABEL.get(
            _effective_conf(result), result.get("confidence", "")
        ),
        "confidence_key":      _effective_conf(result),
        "show_source":         bool(result.get("source_url")),
        "family_undocumented": family_undocumented,
        "profitable":          profitable,        # canônico — só p/ retrocompat de lógica
        "profitable_key":      profitable_key,    # chave estável — usar na lógica do template
        "profitable_label":    profitable_label,  # rótulo traduzido — usar na EXIBIÇÃO
        # Fonte de classificação: canônico fica no result (lógica); rótulo p/ exibir.
        "classification_source_label": source_label(result.get("classification_source", "")),
        # F5 (PRECIFICACAO §7): preço do comprador — lista VAZIA para quem não
        # é admin da empresa (operador/gerente/anônimo nunca veem preço).
        "price_quotes":        _price_quotes_for_admin(request, result),
        "fx_info":             _fx_info_for_card(request),
    }

    return render(request, "chips/partials/decode_card.html", context)


@csrf_exempt
@require_POST
def report_error(request):
    """
    Registra uma solicitação de correção enviada pelo usuário.

    Body (form ou JSON):
        pn              — Part Number com erro (obrigatório)
        chip_type       — Tipo exibido no momento do reporte
        capacity        — Capacidade exibida no momento do reporte

    Resposta:
        HTML parcial com mensagem de confirmação (inserido via HTMX).
    """
    pn        = (request.POST.get("pn") or "").strip().upper()
    pn        = re.sub(r"[^A-Z0-9]", "", pn)
    chip_type = (request.POST.get("chip_type") or "").strip()[:100]
    capacity  = (request.POST.get("capacity")  or "").strip()[:100]

    if not pn or len(pn) < 4:
        return HttpResponse('<span class="dc-report-err">' + _('PN inválido.') + '</span>')

    CorrectionRequest.objects.create(
        part_number         = pn,
        reported_chip_type  = chip_type,
        reported_capacity   = capacity,
    )

    return HttpResponse(
        '<span class="dc-report-ok">✓ ' + _('Reporte recebido — obrigado!') + '</span>'
    )


@require_GET
def stats_api(request):
    """Estatísticas rápidas do banco — usadas na página inicial."""
    return JsonResponse({
        # Opção 2: só conta o catálogo VISÍVEL (approved) — submitted/rejected não são catálogo.
        "total_parts":    KnownPart.objects.filter(review_status="approved").count(),
        "confirmed":      KnownPart.objects.filter(review_status="approved",
                                                   confidence__in=("confirmed", "manual")).count(),
        "total_searches": SearchLog.objects.count(),
        "unknown_count":  UnknownChip.objects.count(),
    })


@csrf_exempt
@require_POST
def submit_chip(request):
    """
    Recebe um envio colaborativo de PN não catalogado — feature "Adicionar chip".

    Disparado de dois pontos da index:
      • card vermelho "Chip não identificado" → botão "Enviar para análise"
      • link "Adicionar chip" no menu principal / rodapé

    Body (multipart/form-data):
        pn       — Part Number (obrigatório, mín. 3 chars)
        photo    — foto do chip (opcional, ImageField)
        context  — contexto livre: origem, aparelho, observações (opcional)
        email    — e-mail para retorno (opcional)

    Resposta JSON:
        {"ok": true}                       — envio registrado
        {"ok": false, "error": "mensagem"} — PN inválido
    """
    pn = (request.POST.get("pn") or "").strip().upper()
    pn = re.sub(r"[^A-Z0-9\-]", "", pn)

    if not pn or len(pn) < 3:
        return JsonResponse(
            {"ok": False, "error": _("Informe um Part Number válido (mín. 3 caracteres).")},
            status=400,
        )

    context = (request.POST.get("context") or "").strip()[:2000]
    email   = (request.POST.get("email") or "").strip()[:254]
    photo   = request.FILES.get("photo")

    ChipSubmission.objects.create(
        part_number     = pn,
        context         = context,
        submitter_email = email,
        photo           = photo,
    )

    return JsonResponse({"ok": True})
