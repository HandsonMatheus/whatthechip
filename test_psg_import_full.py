#!/usr/bin/env python
"""
test_psg_import_full.py
=======================
Testa 100% dos PNs de todos os CSVs do PSG 2H 2014 contra o engine WhatTheChip.

Uso (da raiz do projeto, com venv ativo):
    python test_psg_import_full.py
    python test_psg_import_full.py --only-fails
    python test_psg_import_full.py --file data/psg/psg_2h2014_ddr3.csv

Conhecimentos adquiridos após leitura do populate_samsung.py:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ChipFamily.chip_type por prefixo:
    K4A  → DDR4       (antes do fix o CSV dizia "DDR" — CORRIGIDO)
    K4B  → DDR        (DDR3/DDR3L — chip_type="DDR" é correto)
    K4P  → LPDDR2
    K4E  → LPDDR3
    K3QF → LPDDR3
    K3Q  → LPDDR3
    KLM  → eMMC
    K3   → RAM  ← fallback genérico para K3x sem família específica

  Divergências PRÉ-IMPORT esperadas (grammar vs PSG):
    K3PE… → K3 generic → chip_type="RAM" (PSG correto: LPDDR2 — import vai corrigir)
    K3MF… → K3 generic → chip_type="RAM" (PSG correto: LPDDR3 — import vai corrigir)
    K3QF6… → K3QF_CAP sem chave "6" → capacity=null (import vai preencher com 3GB)

  Após o import (confidence=confirmed, grammar_wins=False), o DB sempre vence.
  Esses PNs retornarão chip_type correto via KnownPart.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import csv
import os
import sys

# ── Django setup ──────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
PSG_DIR = "data/psg"
ALL_CSVS = [
    "psg_2h2014_ddr4.csv",
    "psg_2h2014_ddr3.csv",
    "psg_2h2014_mobile_dram.csv",
    "psg_2h2014_emmc.csv",
]

# PNs cujas divergências de chip_type são ESPERADAS antes do import
# (K3 generic retorna "RAM"; o import via confidence=confirmed vai corrigir).
KNOWN_PRE_IMPORT_DIVERGENCES = {
    # prefixo → chip_type que o engine retorna via grammar (K3 fallback)
    "K3PE": "RAM",
    "K3MF": "RAM",
}

# Paleta ANSI
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def load_pns(csv_path):
    """Retorna lista de dicts com todos os PNs do CSV (100%, sem amostragem)."""
    out = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pn = (row.get("pn") or "").strip()
            if pn:
                out.append({
                    "pn":         pn,
                    "pn_raw":     row.get("pn_raw", pn),
                    "chip_type":  row.get("chip_type", ""),
                    "subtype":    row.get("subtype", ""),
                    "capacity":   row.get("capacity", ""),
                    "confidence": row.get("confidence", ""),
                    "is_base":    row.get("is_base", "no"),
                })
    return out


def _is_expected_divergence(pn, field, eng_val, exp_val):
    """
    Retorna True se a divergência é conhecida e esperada PRÉ-import.
    Essas divergências NÃO contam como falhas — serão corrigidas pelo import.
    """
    for prefix, known_eng_val in KNOWN_PRE_IMPORT_DIVERGENCES.items():
        if pn.startswith(prefix):
            if field == "chip_type" and eng_val.upper() == known_eng_val.upper():
                return True
    return False


def check(expected, result):
    """
    Compara campos esperados (CSV) com resultado do engine.
    Retorna (issues_reais, warnings_esperados).
    """
    issues = []    # divergências reais — bloqueiam o import
    warnings = []  # divergências esperadas pré-import — import vai corrigir

    pn = expected["pn"]

    # chip_type
    eng_ct = (result.get("chip_type") or "").strip()
    exp_ct = expected["chip_type"].strip()
    if exp_ct and eng_ct and eng_ct.upper() != exp_ct.upper():
        msg = f"chip_type: esperado={exp_ct!r} engine={eng_ct!r}"
        if _is_expected_divergence(pn, "chip_type", eng_ct, exp_ct):
            warnings.append(f"[pré-import esperado] {msg}")
        else:
            issues.append(msg)

    # capacity — aceita variações de formatação (512MB == 512mb, 1GB == 1gb)
    eng_cap = (result.get("capacity") or "").strip().upper().replace(" ", "")
    exp_cap = expected["capacity"].strip().upper().replace(" ", "")
    if exp_cap and eng_cap and eng_cap != exp_cap:
        issues.append(f"capacity: esperado={exp_cap!r} engine={eng_cap!r}")

    # confidence — após o import, espera-se "confirmed"
    eng_conf = result.get("confidence", "")
    if eng_conf and eng_conf not in ("confirmed", "manual"):
        issues.append(f"confidence: {eng_conf!r} (esperado confirmed ou manual)")

    return issues, warnings


def fmt_result(r):
    """Extrai campos relevantes do resultado do engine para exibição."""
    parts = []
    if r.get("chip_type"):
        parts.append(r["chip_type"])
    if r.get("subtype"):
        parts.append(r["subtype"])
    cap = r.get("capacity") or r.get("emcp_nand") or ""
    if cap:
        parts.append(cap)
    if r.get("confidence"):
        parts.append(f"[{r['confidence']}]")
    src = ""
    if r.get("known_exact"):
        src = "db_exact"
    elif r.get("from_web") is False and not r.get("known_exact"):
        src = "grammar"
    elif not r.get("known"):
        src = "NOT_FOUND"
    if src:
        parts.append(f"via={src}")
    return " | ".join(parts) if parts else "(sem resultado)"


def run(files, only_fails, verbose_ok):
    all_pns = []
    file_counts = {}
    for f in files:
        pns = load_pns(f)
        file_counts[os.path.basename(f)] = len(pns)
        all_pns.extend(pns)

    total = len(all_pns)
    ok = fail = not_found = warn = 0

    print(f"\n{BOLD}{'━'*72}{RESET}")
    print(f"{BOLD}  Samsung PSG 2H 2014 — Teste Completo (100% — {total} PNs){RESET}")
    for fname, cnt in file_counts.items():
        print(f"  {DIM}• {fname}: {cnt} PNs{RESET}")
    print(f"{BOLD}{'━'*72}{RESET}\n")

    current_file = None

    for entry in all_pns:
        pn = entry["pn"]

        # Detecta mudança de arquivo para cabeçalho visual
        src_file = None
        for f in files:
            pns_check = load_pns.__wrapped__ if hasattr(load_pns, "__wrapped__") else None
            # usa prefixo do PN para inferir arquivo (simples)
        # Cabeçalho por arquivo não é trivial sem rastrear; omitimos para clareza.

        try:
            result = classify(pn)
        except Exception as e:
            print(f"{RED}  ✗ {pn}: EXCEPTION — {e}{RESET}")
            fail += 1
            continue

        if not result.get("known"):
            not_found += 1
            flag = "base" if entry["is_base"] == "yes" else "var "
            # Não-encontrado é esperado antes do import — não é falha
            if not only_fails:
                print(f"{DIM}  ○ {pn:<30} [{flag}]  NOT FOUND (aguarda import){RESET}")
            continue

        issues, warnings = check(entry, result)
        flag = "base" if entry["is_base"] == "yes" else "var "

        if issues:
            fail += 1
            print(f"{RED}  ✗ {pn:<30} [{flag}]  {fmt_result(result)}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
        elif warnings:
            warn += 1
            # avisos sempre visíveis (inclusive com --only-fails)
            print(f"{YELLOW}  ⚠ {pn:<30} [{flag}]  {fmt_result(result)}{RESET}")
            for w in warnings:
                print(f"{YELLOW}       ↳ {w}{RESET}")
        else:
            ok += 1
            if not only_fails or verbose_ok:
                print(f"{GREEN}  ✓ {pn:<30} [{flag}]  {fmt_result(result)}{RESET}")

    print(f"\n{BOLD}{'━'*72}{RESET}")
    pct_ok = round(ok / total * 100) if total else 0
    pct_nf = round(not_found / total * 100) if total else 0

    has_real_errors = fail > 0
    status_color = GREEN if not has_real_errors else RED

    print(
        f"{status_color}{BOLD}  RESULTADO: {ok}/{total} OK ({pct_ok}%)  |  "
        f"falhas={fail}  avisos_pré-import={warn}  não_encontrados={not_found} ({pct_nf}%){RESET}"
    )

    if warn > 0:
        print(f"\n{YELLOW}{BOLD}  Avisos pré-import ({warn} PNs):{RESET}")
        print(f"{YELLOW}  Os PNs acima têm chip_type divergente apenas porque a ChipFamily{RESET}")
        print(f"{YELLOW}  genérica K3 retorna 'RAM' para K3PE/K3MF (sem família específica).{RESET}")
        print(f"{YELLOW}  Após o import (confidence=confirmed), o DB vence a grammar e{RESET}")
        print(f"{YELLOW}  classify() retornará LPDDR2/LPDDR3 corretamente.{RESET}")

    if not has_real_errors and fail == 0:
        print(f"\n{GREEN}{BOLD}  ✅ Nenhuma falha real. CSVs prontos para import.{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ❌ {fail} falha(s) real(is) encontrada(s). Revisar antes do import.{RESET}")

    print(f"{BOLD}{'━'*72}{RESET}\n")

    return fail


def main():
    parser = argparse.ArgumentParser(
        description="Testa 100%% dos PNs do PSG Samsung contra o engine WhatTheChip."
    )
    parser.add_argument(
        "--only-fails", action="store_true",
        help="Exibe só divergências e avisos (omite OK e NOT_FOUND)."
    )
    parser.add_argument(
        "--verbose-ok", action="store_true",
        help="Exibe PNs OK mesmo com --only-fails."
    )
    parser.add_argument(
        "--file", default=None,
        help="Testa só este CSV (caminho relativo ou absoluto)."
    )
    args = parser.parse_args()

    if args.file:
        path = args.file if os.path.isabs(args.file) else os.path.join(os.getcwd(), args.file)
        files = [path]
    else:
        files = [os.path.join(PSG_DIR, f) for f in ALL_CSVS]

    missing = [f for f in files if not os.path.exists(f)]
    if missing:
        print(f"{RED}Arquivos não encontrados: {missing}{RESET}")
        sys.exit(1)

    fail_count = run(files, args.only_fails, args.verbose_ok)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
