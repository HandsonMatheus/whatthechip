#!/usr/bin/env python
"""
test_psg_import.py
==================
Testa ~50% dos PNs importados do PSG 2H 2014 contra o engine.

Uso (da raiz do projeto, com venv ativo):
    python test_psg_import.py
    python test_psg_import.py --pct 30       # testa 30% dos PNs
    python test_psg_import.py --only-fails   # exibe só divergências
    python test_psg_import.py --file data/psg/psg_2h2014_ddr3.csv  # só um CSV
"""

import argparse
import csv
import os
import random
import sys

# ── Django setup ──────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402 (após django.setup)

# ── Config ────────────────────────────────────────────────────────────────────
PSG_DIR = "data/psg"
ALL_CSVS = [
    "psg_2h2014_ddr4.csv",
    "psg_2h2014_ddr3.csv",
    "psg_2h2014_mobile_dram.csv",
    "psg_2h2014_emmc.csv",
]

# Paleta ANSI
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def load_pns(csv_path):
    """Retorna lista de dicts {pn, chip_type, capacity, confidence, subtype}."""
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


def check(expected, result):
    """
    Compara campos esperados (CSV) com resultado do engine.
    Retorna lista de strings com divergências.
    """
    issues = []

    # chip_type
    eng_ct = (result.get("chip_type") or "").strip()
    exp_ct = expected["chip_type"].strip()
    if exp_ct and eng_ct and eng_ct.upper() != exp_ct.upper():
        issues.append(f"chip_type: esperado={exp_ct!r} engine={eng_ct!r}")

    # capacity — aceita variações de formatação (512MB == 512mb, 1GB == 1gb)
    eng_cap = (result.get("capacity") or "").strip().upper().replace(" ", "")
    exp_cap = expected["capacity"].strip().upper().replace(" ", "")
    if exp_cap and eng_cap and eng_cap != exp_cap:
        issues.append(f"capacity: esperado={exp_cap!r} engine={eng_cap!r}")

    # confidence — deve ser 'confirmed' após import
    eng_conf = result.get("confidence", "")
    if eng_conf and eng_conf not in ("confirmed", "manual"):
        issues.append(f"confidence: {eng_conf!r} (esperado confirmed)")

    return issues


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


def run(files, pct, only_fails):
    random.seed(42)  # reprodutível

    all_pns = []
    for f in files:
        pns = load_pns(f)
        sample = random.sample(pns, max(1, int(len(pns) * pct / 100)))
        all_pns.extend(sample)

    total = len(all_pns)
    ok = fail = not_found = 0

    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  Samsung PSG Import — Teste {pct}% dos PNs  ({total} amostras){RESET}")
    print(f"{BOLD}{'─'*70}{RESET}\n")

    for entry in all_pns:
        pn = entry["pn"]
        try:
            result = classify(pn)
        except Exception as e:
            print(f"{RED}  ✗ {pn}: EXCEPTION — {e}{RESET}")
            fail += 1
            continue

        if not result.get("known"):
            not_found += 1
            if not only_fails:
                flag = "base" if entry["is_base"] == "yes" else "var"
                print(f"{YELLOW}  ? {pn:<28} [{flag}]  NOT FOUND{RESET}")
            else:
                flag = "base" if entry["is_base"] == "yes" else "var"
                print(f"{YELLOW}  ? {pn:<28} [{flag}]  NOT FOUND{RESET}")
            continue

        issues = check(entry, result)
        flag = "base" if entry["is_base"] == "yes" else "var "

        if issues:
            fail += 1
            print(f"{RED}  ✗ {pn:<28} [{flag}]  {fmt_result(result)}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
        else:
            ok += 1
            if not only_fails:
                print(f"{GREEN}  ✓ {pn:<28} [{flag}]  {fmt_result(result)}{RESET}")

    print(f"\n{BOLD}{'─'*70}{RESET}")
    pct_ok = round(ok / total * 100) if total else 0
    status_color = GREEN if fail == 0 and not_found == 0 else (YELLOW if ok > fail else RED)
    print(f"{status_color}{BOLD}  RESULTADO: {ok}/{total} OK ({pct_ok}%)  |  "
          f"falhas={fail}  não_encontrados={not_found}{RESET}")
    print(f"{BOLD}{'─'*70}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Testa PNs do PSG contra o engine WhatTheChip.")
    parser.add_argument("--pct",        type=int, default=50,  help="%% dos PNs a testar (padrão: 50)")
    parser.add_argument("--only-fails", action="store_true",   help="Exibe só divergências e não-encontrados")
    parser.add_argument("--file",       default=None,          help="Testa só este CSV (caminho relativo ou absoluto)")
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

    run(files, args.pct, args.only_fails)


if __name__ == "__main__":
    main()
