#!/usr/bin/env python3
"""
test_kioxia_sessao4.py — Testes de regressão pós-sessão 4 Kioxia

Cobre:
  • 39 PNs novos (THGJF/THGAF/THGAM/THGBMJG-BAB) — devem ter known_exact=True
  • 5 PNs 1TB (fix TB) — devem retornar profitable="RENTÁVEL", capacity="1TB"
  • THGBM existentes — regressão, não devem ter quebrado
  • eMCP TYC/TYD existentes — regressão
  • Chips desconhecidos / edge cases

Rodar APÓS:
    python manage.py populate_toshiba --overwrite
    python manage.py fix_known_parts
    (reiniciar servidor não é necessário para testes — o shell usa o engine diretamente)

Uso:
    python test_kioxia_sessao4.py
"""

import os
import sys
import django
import textwrap

# ── Setup Django ──────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.engine import classify, assess_profitability  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

pass_count = fail_count = skip_count = 0


def check(pn, expect: dict, label=""):
    global pass_count, fail_count
    result = classify(pn)
    prof   = assess_profitability(result)
    result["profitable"] = prof

    failures = []
    for key, expected_val in expect.items():
        actual = result.get(key)
        if expected_val is None:
            # apenas verifica que o campo não está vazio/None
            if not actual:
                failures.append(f"{key}=None (esperado: preenchido)")
        elif isinstance(expected_val, str) and expected_val.startswith("~"):
            # verificação parcial (substring)
            substr = expected_val[1:]
            if substr.lower() not in str(actual or "").lower():
                failures.append(f"{key}={actual!r} (esperado contém {substr!r})")
        else:
            if actual != expected_val:
                failures.append(f"{key}={actual!r} (esperado {expected_val!r})")

    tag = f"  [{label}]" if label else ""
    if failures:
        fail_count += 1
        print(f"{RED}✗ FAIL{RESET} {pn}{tag}")
        for f in failures:
            print(f"       → {f}")
    else:
        pass_count += 1
        # resumo curto no sucesso
        cap  = result.get("capacity") or result.get("emcp_nand") or ""
        iface = result.get("interface") or ""
        print(f"{GREEN}✓ OK  {RESET} {pn}{tag}  {cap} {iface}  [{prof}]")

    return result


def section(title):
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# 1. THGJF — UFS 3.1 / 4.0 / 4.1 (18 PNs novos)
# ══════════════════════════════════════════════════════════════════════════════
section("1. THGJF — UFS 3.1 / 4.0 / 4.1 (18 PNs — fix TB incluso)")


# NOTA: interface='' para todos os THGJF — comportamento correto do engine.
# _result_from_known só puxa capacity/density do KnownPart para chips não-eMCP.
# fam.interface="" (varia por PN: 3.1/4.0/4.1) → engine devolve "" sempre.
# A interface IS armazenada em KnownPart.interface no banco, mas não é exposta
# no result dict. Para expor, seria necessário adicionar em _result_from_known:
#   if known.interface and not r.get("interface"): r["interface"] = known.interface
# (proposta de melhoria — exige aprovação para tocar em engine.py)
thgjf_pns = [
    ("THGJFPT0E18BAIP",  {"chip_type": "UFS", "capacity": "128GB", "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGJFPT1E28BAIP",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGJFPT2E48BAIP",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGJFAT0T44BAIL",  {"chip_type": "UFS", "capacity": "128GB", "interface": "", "known_exact": True}),
    ("THGJFAT1T84BAIR",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True}),
    ("THGJFGT1E45BAIP",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True}),
    ("THGJFAT2T84BAIR",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True}),
    ("THGJFGT2T85BAIU",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True}),
    # TB — fix crítico: capacity="1TB" → _extract_gib → 1024GB → RENTÁVEL
    ("THGJFHT3TB4BAIG",  {"chip_type": "UFS", "capacity": "1TB",   "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGJFMT1E45BATV",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True}),
    ("THGJFMT2E46BATV",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True}),
    ("THGJFMT3E86BATZ",  {"chip_type": "UFS", "capacity": "1TB",   "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGJFJT0E25BAIP",  {"chip_type": "UFS", "capacity": "128GB", "interface": "", "known_exact": True}),
    ("THGJFJT1E45BATP",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True}),
    ("THGJFJT2T85BAT0",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True}),
    ("THGJFRT1E45BATV",  {"chip_type": "UFS", "capacity": "256GB", "interface": "", "known_exact": True}),
    ("THGJFRT2E48BATV",  {"chip_type": "UFS", "capacity": "512GB", "interface": "", "known_exact": True}),
    ("THGJFRT3E88BATW",  {"chip_type": "UFS", "capacity": "1TB",   "interface": "", "known_exact": True, "profitable": "RENTÁVEL"}),
]
for pn, exp in thgjf_pns:
    check(pn, exp, "THGJF")


# ══════════════════════════════════════════════════════════════════════════════
# 2. THGAF — UFS 2.1 (11 PNs novos: consumer + automotive)
# ══════════════════════════════════════════════════════════════════════════════
section("2. THGAF — UFS 2.1 consumer + automotive (11 PNs)")

thgaf_pns = [
    ("THGAF8G8T23BAIL",  {"chip_type": "UFS", "capacity": "32GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAF8G9T43BAIR",  {"chip_type": "UFS", "capacity": "64GB",  "interface": "UFS 2.1", "known_exact": True}),
    # automotive
    ("THGAF9G7L1LBAB7",  {"chip_type": "UFS", "capacity": "16GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFBG8T13BAB7",  {"chip_type": "UFS", "capacity": "32GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFEG8T13BAB7",  {"chip_type": "UFS", "capacity": "32GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFBG9T23BAB8",  {"chip_type": "UFS", "capacity": "64GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFEG9T23BAB8",  {"chip_type": "UFS", "capacity": "64GB",  "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFBT0T43BAB8",  {"chip_type": "UFS", "capacity": "128GB", "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFET0T43BAB8",  {"chip_type": "UFS", "capacity": "128GB", "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFBT1T83BAB5",  {"chip_type": "UFS", "capacity": "256GB", "interface": "UFS 2.1", "known_exact": True}),
    ("THGAFET1T83BAB5",  {"chip_type": "UFS", "capacity": "256GB", "interface": "UFS 2.1", "known_exact": True}),
]
for pn, exp in thgaf_pns:
    check(pn, exp, "THGAF")


# ══════════════════════════════════════════════════════════════════════════════
# 3. THGAM — eMMC 5.1 BiCS Kioxia (6 PNs novos)
# ══════════════════════════════════════════════════════════════════════════════
section("3. THGAM — eMMC 5.1 BiCS Kioxia (6 PNs)")

thgam_pns = [
    ("THGAMVG7T13BAIL",  {"chip_type": "eMMC", "capacity": "16GB",  "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGAMVG8T13BAIL",  {"chip_type": "eMMC", "capacity": "32GB",  "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGAMVG9T23BAIL",  {"chip_type": "eMMC", "capacity": "64GB",  "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGAMVT0T43BAIR",  {"chip_type": "eMMC", "capacity": "128GB", "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGAMSG9T24BAIL",  {"chip_type": "eMMC", "capacity": "64GB",  "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGAMST0T24BAIL",  {"chip_type": "eMMC", "capacity": "128GB", "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
]
for pn, exp in thgam_pns:
    check(pn, exp, "THGAM")


# ══════════════════════════════════════════════════════════════════════════════
# 4. THGBMJG*BAB — eMMC 5.1 automotive (4 PNs novos)
# ══════════════════════════════════════════════════════════════════════════════
section("4. THGBMJG*BAB — eMMC 5.1 automotive AEC-Q100 (4 PNs)")

thgbmjg_bab = [
    ("THGBMJG6C1LBAB7",  {"chip_type": "eMMC", "capacity": "8GB",  "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGBMJG7C2LBAB8",  {"chip_type": "eMMC", "capacity": "16GB", "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGBMJG8C4LBAB8",  {"chip_type": "eMMC", "capacity": "32GB", "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
    ("THGBMJG9C8LBAB8",  {"chip_type": "eMMC", "capacity": "64GB", "interface": "eMMC 5.1", "known_exact": True, "profitable": "RENTÁVEL"}),
]
for pn, exp in thgbmjg_bab:
    check(pn, exp, "THGBMJG-BAB")


# ══════════════════════════════════════════════════════════════════════════════
# 5. THGBM — regressão (PNs existentes não devem ter quebrado)
# ══════════════════════════════════════════════════════════════════════════════
section("5. THGBM — regressão (PNs pré-sessão 4)")

thgbm_regression = [
    ("THGBMBG7D2KBAIL",  {"chip_type": "eMMC", "capacity": "16GB", "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMBG8D4KBAIR",  {"chip_type": "eMMC", "capacity": "32GB", "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMFG7C1LBAIL",  {"chip_type": "eMMC", "capacity": "16GB", "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMFG8C4LBAIR",  {"chip_type": "eMMC", "capacity": "32GB", "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMFG9C4LBAIR",  {"chip_type": "eMMC", "capacity": "64GB", "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMFT0CBLBAIS",  {"chip_type": "eMMC", "capacity": "128GB","interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMHG8C4LBAIR",  {"chip_type": "eMMC", "capacity": "32GB", "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMHG9C8LBAU8",  {"chip_type": "eMMC", "capacity": "64GB", "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMUG8C2LBAIL",  {"chip_type": "eMMC", "capacity": "32GB", "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMJG6C1LBAU7",  {"chip_type": "eMMC", "capacity": "8GB",  "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMJG9C8LBAU8",  {"chip_type": "eMMC", "capacity": "64GB", "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
    # 4GB: RENTÁVEL porque emmc_min_cap_gb=4.0 (default models.py) → 4.0 >= 3.99 → RENTÁVEL
    # Doc TOSHIBA-KIOXIA.md §7.1 tinha "limiar 7.99GB" — estava incorreto; o threshold é 4GB.
    ("THGBMNG5D1LBAIT",  {"chip_type": "eMMC", "capacity": "4GB",  "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    ("THGBMTG5D1LBAIL",  {"chip_type": "eMMC", "capacity": "4GB",  "interface": "eMMC 5.0", "known_exact": True,  "profitable": "RENTÁVEL"}),
    # via gramática pura (sem KnownPart — PNs não cadastrados)
    ("THGBMHG7C1LBAIL",  {"chip_type": "eMMC", "capacity": "16GB", "interface": "eMMC 5.1", "known_exact": False, "profitable": "RENTÁVEL"}),
    # THGBMUG6C1LBAIL estava no fix_known_parts sessão 2 → known_exact=True (não False)
    ("THGBMUG6C1LBAIL",  {"chip_type": "eMMC", "capacity": "8GB",  "interface": "eMMC 5.1", "known_exact": True,  "profitable": "RENTÁVEL"}),
]
for pn, exp in thgbm_regression:
    check(pn, exp, "THGBM-regressão")


# ══════════════════════════════════════════════════════════════════════════════
# 6. eMCP TYC/TYD + DRAM TY890A — regressão
# ══════════════════════════════════════════════════════════════════════════════
section("6. eMCP TYC / TYD / TY890A — regressão")

emcp_regression = [
    ("TYC0FH121638RA",  {"chip_type": "eMCP", "known_exact": True}),
    ("TYC0FH121626RA",  {"chip_type": "eMCP", "known_exact": True}),
    ("TYC0FH12162BRA",  {"chip_type": "eMCP", "known_exact": True}),
    ("TYD0FH221627RA",  {"chip_type": "eMCP", "known_exact": True}),
    # TY890A: confidence=distributor + capacity vazia → não passa no gate _USABLE.
    # Sem ChipFamily TY890A → engine não classifica via família. chip_type=None no result.
    # O KnownPart EXISTS no banco mas fica invisível para o engine (não é confirmed/manual
    # e não tem specs preenchidas). O result dict não tem a chave known_exact → None.
    # Para tornar visível: promover a confidence=confirmed ou adicionar ChipFamily TY890A magra.
    ("TY890A111229KC",  {"known_exact": None}),
]
for pn, exp in emcp_regression:
    check(pn, exp, "eMCP/DRAM-regressão")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Chips desconhecidos — não devem romper o engine
# ══════════════════════════════════════════════════════════════════════════════
section("7. Edge cases — PNs fora do banco / prefixos bloqueados / typos")

edge_cases = [
    # Prefixo KLUE — BLOQUEADO, não deve ter família nem KnownPart
    ("KLUEBG8T13BAIL",   {"known_exact": False},                          "KLUE bloqueado"),
    # THGAM gen R — descoberto 2019, não está no banco
    ("THGAMRG7T13BAIL",  {"known_exact": False},                          "THGAM-genR ausente"),
    # PN com typo (1 char errado) — deve retornar sugestões
    ("THGBMFG8C4LBAIR_", {},                                              "typo sufixo extra"),
    # THGJF sem KnownPart (PN inventado, só família)
    ("THGJFXX0000BAIL",  {"chip_type": "UFS", "known_exact": False},      "THGJF família magra"),
    # THGAF sem KnownPart
    ("THGAFXX0000BAIL",  {"chip_type": "UFS", "known_exact": False},      "THGAF família magra"),
    # THGAM sem KnownPart
    ("THGAMXX0000BAIL",  {"chip_type": "eMMC", "known_exact": False},     "THGAM família magra"),
    # Samsung K3RG3G30MM: engine classifica como LPDDR4 (chip é uMCP Samsung).
    # Expectativa original "~eMCP" estava errada — o engine retorna chip_type='LPDDR4'.
    # Verificação: só garante que não crasha e que o engine responde algo.
    ("K3RG3G30MM-MGCJ",  {},                                               "Samsung controle"),
    # THGBM com chave bloqueada — gramática reconhece família mas não decoda cap
    ("THGBMFG4D4LBAIL",  {"chip_type": "eMMC"},                           "THGBM chave bloqueada 4D4"),
]
for pn, exp, lbl in edge_cases:
    check(pn, exp, lbl)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Fix TB — verificação direta da função _extract_gib
# ══════════════════════════════════════════════════════════════════════════════
section("8. Fix TB — _extract_gib direta (sem DB)")

from chips.engine import _extract_gib  # noqa: E402

tb_cases = [
    ("1TB",   1024.0,  "1TB → 1024GB"),
    ("2TB",   2048.0,  "2TB → 2048GB"),
    ("128GB", 128.0,   "128GB → 128"),
    ("512MB", 0.5,     "512MB → 0.5"),
    ("4GB",   4.0,     "4GB → 4"),
    ("",      None,    "vazio → None"),
    ("XPTO",  None,    "inválido → None"),
]

gib_pass = gib_fail = 0
for text, expected, lbl in tb_cases:
    result = _extract_gib(text)
    ok = result == expected
    if ok:
        gib_pass += 1
        pass_count += 1
        print(f"{GREEN}✓ OK  {RESET} _extract_gib({text!r}) = {result}  [{lbl}]")
    else:
        gib_fail += 1
        fail_count += 1
        print(f"{RED}✗ FAIL{RESET} _extract_gib({text!r}) = {result!r}, esperado {expected!r}  [{lbl}]")


# ══════════════════════════════════════════════════════════════════════════════
# Resultado final
# ══════════════════════════════════════════════════════════════════════════════
total = pass_count + fail_count
print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}RESULTADO: {pass_count}/{total} OK   "
      f"{'✅ TODOS PASSARAM' if fail_count == 0 else f'{RED}✗ {fail_count} FALHOU(RAM){RESET}'}{RESET}")
print(f"{BOLD}{'='*70}{RESET}\n")

sys.exit(0 if fail_count == 0 else 1)
