#!/usr/bin/env python
"""
test_samsung_global_lpddr5_ufs.py
===================================
Testa os PNs LPDDR5/LPDDR5X e UFS 3.x do Samsung Semiconductor Global
contra o engine WhatTheChip.

Uso (da raiz do projeto, com venv ativo):
    python test_samsung_global_lpddr5_ufs.py
    python test_samsung_global_lpddr5_ufs.py --only-fails

Fluxo recomendado antes de rodar:
    1. python manage.py populate_samsung --overwrite
    2. python manage.py import_samsung_psg --file data/psg/samsung_global_lpddr5_2020_2023.csv
    3. python manage.py import_samsung_psg --file data/psg/samsung_global_ufs_3x.csv
    4. python test_samsung_global_lpddr5_ufs.py

Chips cobertos:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  LPDDR5 (K3LK) — Samsung Global /lpddr5/:
    4GB (32Gb) · 6GB (48Gb) · 8GB (64Gb, múltiplos dies) ·
    12GB (96Gb) · 16GB (128Gb) · 18GB (144Gb)
    ⚠ chip_type=LPDDR5, VDDQ=0.9V — NÃO confundir com LPDDR5X (0.5V)

  LPDDR5X (K3KL) — Samsung Global /lpddr5x/:
    8GB (64Gb) · 12GB (96Gb) · 16GB (128Gb)
    ⚠ chip_type=LPDDR5X, VDDQ=0.5V

  Correções de grammar confirmadas via Samsung Global:
    - K3LK chip_type: LPDDR5 (era LPDDR5X — bug corrigido 2026-05-27)
    - LPDDR5_CAP "4L": 12GB/96Gb (era 16GB/128Gb — bug distribuidor)
    - LPDDR5_CAP "3K" e "DK": novos códigos adicionados

  UFS 3.x (KLUFG/KLUEG/KLUDG/KLUCG):
    512GB (UFS 3.1) · 256GB (UFS 3.1) · 128GB (UFS 3.0/3.1) · 64GB (UFS 3.1)
    Nova família KLUEG adicionada à grammar (UFS 3.1 Samsung)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import csv
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402

ALL_CSVS = [
    "data/psg/samsung_global_lpddr5_2020_2023.csv",
    "data/psg/samsung_global_ufs_3x.csv",
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def load_pns(csv_path):
    out = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pn = (row.get("pn") or "").strip()
            if pn:
                out.append({
                    "pn":        pn,
                    "chip_type": row.get("chip_type", ""),
                    "capacity":  row.get("capacity", ""),
                    "subtype":   row.get("subtype", ""),
                    "is_base":   row.get("is_base", "no"),
                })
    return out


def check(expected, result):
    issues = []
    eng_ct = (result.get("chip_type") or "").strip()
    exp_ct = expected["chip_type"].strip()
    if exp_ct and eng_ct and eng_ct.upper() != exp_ct.upper():
        issues.append(f"chip_type: esperado={exp_ct!r} engine={eng_ct!r}")
    eng_cap = (result.get("capacity") or "").strip().upper().replace(" ", "")
    exp_cap = expected["capacity"].strip().upper().replace(" ", "")
    if exp_cap and eng_cap and eng_cap != exp_cap:
        issues.append(f"capacity: esperado={exp_cap!r} engine={eng_cap!r}")
    return issues


def fmt_result(r):
    parts = []
    if r.get("chip_type"):
        parts.append(r["chip_type"])
    if r.get("subtype"):
        parts.append(r["subtype"])
    cap = r.get("capacity") or ""
    if cap:
        parts.append(cap)
    if r.get("confidence"):
        parts.append(f"[{r['confidence']}]")
    src = "grammar"
    if r.get("known_exact"):
        src = "db_exact"
    elif r.get("gemini_found"):
        src = "gemini"
    elif not r.get("known"):
        src = "NOT_FOUND"
    parts.append(f"via={src}")
    return " | ".join(parts) if parts else "(sem resultado)"


def run(files, only_fails):
    all_pns = []
    file_counts = {}
    for f in files:
        pns = load_pns(f)
        file_counts[os.path.basename(f)] = len(pns)
        all_pns.extend(pns)

    total = len(all_pns)
    ok = fail = not_found = 0

    print(f"\n{BOLD}{'━'*72}{RESET}")
    print(f"{BOLD}  Samsung Global LPDDR5/LPDDR5X/UFS 3.x — Teste Completo ({total} PNs){RESET}")
    for fname, cnt in file_counts.items():
        print(f"  {DIM}• {fname}: {cnt} PNs{RESET}")
    print(f"{BOLD}{'━'*72}{RESET}\n")

    for entry in all_pns:
        pn = entry["pn"]
        flag = "base" if entry["is_base"] == "yes" else "var "

        try:
            result = classify(pn)
        except Exception as e:
            print(f"{RED}  ✗ {pn}: EXCEPTION — {e}{RESET}")
            fail += 1
            continue

        if not result.get("known"):
            not_found += 1
            if not only_fails:
                print(f"{DIM}  ○ {pn:<42} [{flag}]  NOT FOUND{RESET}")
            continue

        issues = check(entry, result)

        if issues:
            fail += 1
            print(f"{RED}  ✗ {pn:<42} [{flag}]  {fmt_result(result)}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
        else:
            ok += 1
            if not only_fails:
                print(f"{GREEN}  ✓ {pn:<42} [{flag}]  {fmt_result(result)}{RESET}")

    print(f"\n{BOLD}{'━'*72}{RESET}")
    pct_ok = round(ok / total * 100) if total else 0
    pct_nf = round(not_found / total * 100) if total else 0
    status_color = GREEN if fail == 0 else RED

    print(
        f"{status_color}{BOLD}  RESULTADO: {ok}/{total} OK ({pct_ok}%)  |  "
        f"falhas={fail}  não_encontrados={not_found} ({pct_nf}%){RESET}"
    )

    if fail == 0:
        if not_found == 0:
            print(f"\n{GREEN}{BOLD}  ✅ 100% — todos os PNs encontrados e corretos.{RESET}")
        else:
            print(f"\n{YELLOW}{BOLD}  ⚠ {not_found} PNs ainda não importados. Rode o import e re-teste.{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ❌ {fail} falha(s). Revisar antes de confiar no banco.{RESET}")

    print(f"{BOLD}{'━'*72}{RESET}\n")
    return fail


def main():
    parser = argparse.ArgumentParser(
        description="Testa PNs LPDDR5/LPDDR5X/UFS 3.x do Samsung Global."
    )
    parser.add_argument("--only-fails", action="store_true")
    args = parser.parse_args()

    files = []
    for f in ALL_CSVS:
        path = f if os.path.isabs(f) else os.path.join(os.getcwd(), f)
        if not os.path.exists(path):
            print(f"{RED}Arquivo não encontrado: {path}{RESET}")
            sys.exit(1)
        files.append(path)

    fail_count = run(files, args.only_fails)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
