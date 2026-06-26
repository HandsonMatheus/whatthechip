#!/usr/bin/env python
"""
Diagnóstico de UI — WhatTheChip
================================
Testa os elementos que os testes de terminal NÃO cobrem:
  1. Serialização JSON do resultado de classify() (exatamente o que JsonResponse faz)
  2. Endpoint HTTP /chips/search/ via urllib (só se servidor estiver rodando)
  3. Template decode_card.html para resultado FBGA unknown
  4. Múltiplos PNs reais para detectar TypeError silencioso

Por que isso importa:
  test_fase1.py chama classify(pn) e verifica o dict — mas NÃO testa json.dumps(result).
  Um campo não-serializável (ex: objeto Django, Decimal, datetime) passa em todos os
  testes de terminal mas quebra JsonResponse na view, retornando 500 para o browser.

Uso:
    cd /caminho/para/chipdocs
    python scripts/test_ui.py

Pré-requisito: migrate + fix_known_parts já aplicados (Fase 0 + Fase 1 OK).
"""

import os
import sys
import json
import django
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.engine import classify

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"
WARN = "⚠️  WARN"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f"\n         └─ {detail}" if detail else ""))
        errors.append(label)

def json_safe(result):
    """Replica exatamente o que JsonResponse(result) faz."""
    try:
        return json.dumps(result, ensure_ascii=False), None
    except (TypeError, ValueError) as e:
        return None, str(e)

print()
print("=" * 65)
print("  DIAGNÓSTICO DE UI — Serialização JSON + Endpoint")
print("=" * 65)

# ── 1. Serialização JSON para PNs comuns ────────────────────────────────
print("\n[1] JsonResponse(classify(pn)) — serialização completa")

TEST_PNS = [
    ("KLM8G1GETF-B041",  "Samsung eMCP"),
    ("H9TQ08AGDTMCUR",   "SK Hynix UFS"),
    ("MT53B512M64D4TX",  "Micron LPDDR4 (KnownPart)"),
    ("KLMCGUCTA-B041",   "Samsung eMCP 2"),
    ("KMR310002M-B609",  "Samsung eMCP 3"),
    ("H9TQ64ABMMAECNK",  "SK Hynix eMCP"),
]

for pn, desc in TEST_PNS:
    try:
        result = classify(pn)
        payload, err = json_safe(result)
        if err:
            check(
                f"json.dumps(classify('{pn}'))  [{desc}]",
                False,
                f"TypeError: {err}\nValores no resultado:\n" +
                "\n".join(f"  {k}: {type(v).__name__} = {repr(v)[:80]}"
                          for k, v in result.items()
                          if not isinstance(v, (str, int, float, bool, list, dict, type(None))))
            )
        else:
            parsed = json.loads(payload)
            check(
                f"json.dumps(classify('{pn}'))  [{desc}]",
                True,
            )
            # Verifica que campos essenciais estão no JSON
            for field in ("pn", "known"):
                if field not in parsed:
                    check(f"  Campo '{field}' presente no JSON ({pn})", False, f"chaves: {list(parsed.keys())[:10]}")
    except Exception as exc:
        check(
            f"classify('{pn}') sem exceção",
            False,
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-400:]}"
        )

# ── 2. Caso FBGA desconhecido ────────────────────────────────────────────
print("\n[2] FBGA desconhecido — serialização do resultado fbga_unknown")
try:
    r = classify("D9ZZZ")
    payload, err = json_safe(r)
    check("json.dumps(classify('D9ZZZ')) OK", not err, f"Erro: {err}")
    if not err:
        check("fbga_unknown=True preservado no JSON", json.loads(payload).get("fbga_unknown") is True)
except Exception as exc:
    check("classify('D9ZZZ') sem exceção", False, f"{exc}")

# Limpeza
try:
    from chips.models import UnknownChip
    UnknownChip.objects.filter(part_number="D9ZZZ").delete()
except Exception:
    pass

# ── 3. Template decode_card.html: gap para FBGA unknown ─────────────────
print("\n[3] Template decode_card.html — branch FBGA unknown")
try:
    from django.test import RequestFactory
    from chips.views import decode_html

    factory = RequestFactory()

    # 3a. PN normal (known=True) → deve renderizar o card completo
    req = factory.get("/chips/decode/", {"pn": "KLM8G1GETF"})
    resp = decode_html(req)
    html_known = resp.content.decode("utf-8")
    check(
        "decode_html('KLM8G1GETF') retorna HTML não-vazio",
        len(html_known.strip()) > 50,
        f"HTML retornado: {html_known[:200]!r}"
    )

    # 3b. PN desconhecido (não-FBGA) → deve renderizar algo
    req2 = factory.get("/chips/decode/", {"pn": "ZZZZZZZZZ"})
    resp2 = decode_html(req2)
    html_unk = resp2.content.decode("utf-8")
    check(
        "decode_html('ZZZZZZZZZ') retorna HTML não-vazio",
        len(html_unk.strip()) > 10,
        f"⚠️  Template não cobre resultado known=False (sem família)\n"
        f"         HTML retornado: {html_unk[:200]!r}"
    )

    # 3c. FBGA desconhecido → pode ser vazio se template não tiver branch fbga_unknown
    req3 = factory.get("/chips/decode/", {"pn": "D9ZZZ"})
    resp3 = decode_html(req3)
    html_fbga = resp3.content.decode("utf-8")
    has_content = len(html_fbga.strip()) > 10
    if has_content:
        print(f"  {PASS}  decode_html('D9ZZZ') tem conteúdo")
    else:
        print(f"  {WARN}  decode_html('D9ZZZ') retorna HTML vazio (FBGA unknown sem branch no template)")
        print(f"         ↳ Isso só afeta o endpoint /chips/decode/, NÃO a página principal")
        print(f"         ↳ A página principal usa /chips/search/ + JS — não é afetada")

    try:
        UnknownChip.objects.filter(part_number="D9ZZZ").delete()
    except Exception:
        pass

except Exception as exc:
    print(f"  {WARN}  Teste de template falhou: {exc}")
    print(f"         ↳ Isso não necessariamente indica problema na UI")

# ── 4. Teste HTTP do endpoint (se servidor estiver rodando) ──────────────
print("\n[4] Teste HTTP /chips/search/?pn=KLM8G1GETF")
try:
    from urllib import request as urllib_request
    from urllib.error import URLError
    import json as _json

    try:
        with urllib_request.urlopen(
            "http://127.0.0.1:8000/chips/search/?pn=KLM8G1GETF",
            timeout=3
        ) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
            try:
                data = _json.loads(body)
                check(
                    "GET /chips/search/?pn=KLM8G1GETF → JSON 200",
                    status == 200 and "pn" in data,
                    f"status={status}, known={data.get('known')}"
                )
            except Exception as je:
                check(
                    "GET /chips/search/?pn=KLM8G1GETF → JSON válido",
                    False,
                    f"JSON parse error: {je}\nBody: {body[:300]!r}"
                )
    except URLError as ue:
        print(f"  {INFO}  Servidor não está rodando em 127.0.0.1:8000 — {ue.reason}")
        print(f"         ↳ Inicie com: python manage.py runserver")
        print(f"         ↳ Depois execute este script novamente para confirmar endpoint OK")
    except Exception as he:
        print(f"  {WARN}  Erro HTTP inesperado: {he}")

except Exception as exc:
    print(f"  {WARN}  Teste HTTP falhou: {exc}")

# ── 5. Verificação de migrações pendentes ───────────────────────────────
print("\n[5] Migrações pendentes")
try:
    from django.db.migrations.executor import MigrationExecutor
    from django.db import connection

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        pending = [f"{app}.{name}" for ((app, name), _) in plan]
        check("Sem migrações pendentes", False, f"Pendentes: {pending}")
    else:
        check("Sem migrações pendentes", True)
except Exception as exc:
    print(f"  {WARN}  Não foi possível verificar migrações: {exc}")

# ── 6. Checklist de reinicialização ────────────────────────────────────
print("\n[6] Checklist de servidor")
try:
    from chips.models import KnownPart
    kp_count = KnownPart.objects.count()
    check(f"Banco acessível ({kp_count} KnownParts)", True)
except Exception as exc:
    check("Banco acessível", False, str(exc))

# ── Resultado ──────────────────────────────────────────────────────────
print()
print("=" * 65)
if errors:
    print(f"  RESULTADO: {len(errors)} FALHA(S) encontrada(s)")
    print()
    print("  ── Causas prováveis do 'nada acontece' na UI ──")
    if any("json.dumps" in e for e in errors):
        print()
        print("  🔴 CAUSA PROVÁVEL: resultado de classify() tem campo não-serializável.")
        print("     JsonResponse(result) lança TypeError → Django retorna 500.")
        print("     O browser recebe HTML (não JSON) → .catch() do fetch é ativado,")
        print("     mas a mensagem 'Erro de conexão' pode ser invisível dependendo do")
        print("     estado da hint (ex: foco fora do campo).")
        print()
        print("  Correção:")
        print("    1. Veja acima qual campo tem tipo não-serializável")
        print("    2. Converta para str/int/float/bool/list/dict/None em engine.py")
    print()
    for e in errors:
        print(f"    - {e}")
else:
    print("  RESULTADO: TODOS OS TESTES PASSARAM ✅")
    print()
    print("  Serialização JSON OK. Se a UI ainda não funciona, a causa provável é:")
    print()
    print("  1. Servidor Django precisa de reinicialização:")
    print("     → Pare o servidor (Ctrl+C) e reinicie:")
    print("       python manage.py runserver")
    print()
    print("  2. Cache de compilação Python desatualizado:")
    print("     → find . -name '*.pyc' -not -path '*/venv/*' -delete")
    print("     → find . -name '__pycache__' -not -path '*/venv/*' -exec rm -rf {} + 2>/dev/null")
    print("     → python manage.py runserver")
    print()
    print("  3. Browser com estado travado:")
    print("     → Abra DevTools (F12) → aba Console → procure erros em vermelho")
    print("     → Abra aba Network → clique Decodificar → veja se requisição aparece")
    print("     → Tente Ctrl+Shift+R (hard refresh) para limpar cache do browser")

print("=" * 65)
print()
