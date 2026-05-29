#!/usr/bin/env python
"""
test_psg_1h2017.py
==================
Testa todos os 33 PNs do PSG Samsung 1H 2017 contra o engine WhatTheChip.

Uso (da raiz do projeto, com venv ativo):
    python test_psg_1h2017.py
    python test_psg_1h2017.py --only-fails

Fluxo recomendado antes de rodar:
    1. python manage.py populate_samsung --overwrite
    2. python manage.py import_samsung_psg --file data/psg/psg_1h2017_mobile_dram.csv
    3. python manage.py import_samsung_psg --file data/psg/psg_1h2017_ufs.csv
    4. python manage.py import_samsung_psg --file data/psg/psg_1h2017_emmc.csv
    5. python test_psg_1h2017.py

Novidades do PSG 1H 2017 vs 2H 2014:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  K4F  → LPDDR4 standalone (1GB, 2GB, 3GB)
  K3RG → LPDDR4 multi-channel 4CH (3GB, 4GB, 6GB) ← NOVA família
  K3UH → LPDDR4X multi-channel 4CH (4GB, 6GB) via K3U
  K4EHE, K4EBE → LPDDR3 3GB / 4GB (novas densidades)
  K3QF4F40, K3QF6F60AM → LPDDR3 4GB / 3GB (novas variantes)
  KLM*JETD/UERM → eMMC 5.1 (nova geração)
  KLU* → UFS 2.0/2.1 standalone (NOVO tipo no DB)

Correções de grammar aplicadas nesta sessão:
  - K3QF_CAP: adicionada chave "6" → 3GB (K3QF6F60AM confirmado)
  - K3RG: nova ChipFamily LPDDR4 (priority=40, decode K3RG_CAP)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import csv
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402

PSG_DIR = "data/psg"
ALL_CSVS = [
    "psg_1h2017_mobile_dram.csv",
    "psg_1h2017_ufs.csv",
    "psg_1h2017_emmc.csv",
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
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
                    "confidence": row.get("confidence", ""),
                    "is_base":   row.get("is_base", "no"),
                })
    return out


def check(expected, result):
    issues = []

    pn = expected["pn"]

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
    cap = r.get("capacity") or r.get("emcp_nand") or ""
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
    print(f"{BOLD}  Samsung PSG 1H 2017 — Teste Completo ({total} PNs){RESET}")
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
                print(f"{DIM}  ○ {pn:<35} [{flag}]  NOT FOUND (aguarda import){RESET}")
            continue

        issues = check(entry, result)

        if issues:
            fail += 1
            print(f"{RED}  ✗ {pn:<35} [{flag}]  {fmt_result(result)}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
        else:
            ok += 1
            if not only_fails:
                print(f"{GREEN}  ✓ {pn:<35} [{flag}]  {fmt_result(result)}{RESET}")

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
            print(f"\n{YELLOW}{BOLD}  ⚠ {not_found} PNs ainda não importados (NOT_FOUND). Rode o import e re-teste.{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ❌ {fail} falha(s) real(is). Revisar antes de confiar no banco.{RESET}")

    print(f"{BOLD}{'━'*72}{RESET}\n")
    return fail


def main():
    parser = argparse.ArgumentParser(
        description="Testa PNs do PSG Samsung 1H 2017 contra o engine WhatTheChip."
    )
    parser.add_argument("--only-fails", action="store_true")
    parser.add_argument("--file", default=None)
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

    fail_count = run(files, args.only_fails)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
