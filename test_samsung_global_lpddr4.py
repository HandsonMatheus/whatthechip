#!/usr/bin/env python
"""
test_samsung_global_lpddr4.py
==============================
Testa todos os PNs do samsung_global_lpddr4_2017_2020.csv contra o engine WhatTheChip.

Uso (da raiz do projeto, com venv ativo):
    python test_samsung_global_lpddr4.py
    python test_samsung_global_lpddr4.py --only-fails

Fluxo recomendado antes de rodar:
    1. python manage.py populate_samsung --overwrite
    2. python manage.py import_samsung_psg --file data/psg/samsung_global_lpddr4_2017_2020.csv
    3. python test_samsung_global_lpddr4.py

Chips cobertos neste arquivo:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  LPDDR4 (K4F) — gerações S e D:
    K4F8E3S4** (1GB)     — gen S/D, 8Gb die
    K4F6E3S4** (2GB)     — gen S, 16Gb die
    K4FHE3D4** (3GB)     — gen D, 24Gb (HM + HA variants)
    K4FBE3D4** (4GB)     — gen D, 32Gb (HB + HM variants)

  LPDDR4X (K4U) — gerações S e D:
    K4U6E3S4AA/AB (2GB)  — gen S, 16Gb
    K4U6E3S4AM-GUCL (2GB) — gen S, 16Gb (sufixo padrão)
    K4U6E3S4AM-GFCL (3GB) — EXCEÇÃO: 24Gb (grammar daria 2GB)
    K4U6E3S4AM-GHCL (4GB) — EXCEÇÃO: 32Gb (grammar daria 2GB)
    K4U8E3S4AD** (1.5GB)  — EXCEÇÃO: 12Gb (grammar daria 1GB)
    K4UBE3D4AA/AB/AM-TH/TF (4GB) — gen D, 32Gb
    K4UBE3D4AM-GFCL (3GB) — EXCEÇÃO: 24Gb (grammar daria 4GB)
    K4UBE3D4AM-GHCL (6GB) — EXCEÇÃO: 48Gb (grammar daria 4GB)
    K4UCE3Q4** (8GB)     — gen D, 64Gb
    K4UJE3Q4/D4** (6GB)  — gen D, 48Gb

  LPDDR4X Multi-Channel (K3UH):
    K3UH6H60AM-THCL (6GB) — EXCEÇÃO: 48Gb (grammar daria 4GB)
    K3UH6H60BM** (6GB)    — EXCEÇÃO: 48Gb gen B (grammar daria 4GB)

⚠ PNs marcados como EXCEÇÃO dependem de import no DB para acerto.
  Sem import, grammar retorna capacidade errada para esses chips.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import csv
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402

CSV_PATH = "data/psg/samsung_global_lpddr4_2017_2020.csv"

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
                    "notes":     row.get("notes", ""),
                })
    return out


def is_exception(entry):
    """Retorna True se o PN é uma exceção (grammar dá resposta errada)."""
    return "EXCEÇÃO" in entry.get("notes", "")


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


def run(csv_path, only_fails):
    all_pns = load_pns(csv_path)
    total = len(all_pns)
    ok = fail = not_found = 0
    exceptions_ok = exceptions_fail = 0

    print(f"\n{BOLD}{'━'*72}{RESET}")
    print(f"{BOLD}  Samsung Global LPDDR4/LPDDR4X 2017-2020 — Teste Completo ({total} PNs){RESET}")
    print(f"  {DIM}Fonte: {csv_path}{RESET}")
    print(f"{BOLD}{'━'*72}{RESET}\n")

    for entry in all_pns:
        pn = entry["pn"]
        flag = "base" if entry["is_base"] == "yes" else "var "
        exc_flag = " [EXC]" if is_exception(entry) else ""

        try:
            result = classify(pn)
        except Exception as e:
            print(f"{RED}  ✗ {pn}: EXCEPTION — {e}{RESET}")
            fail += 1
            continue

        if not result.get("known"):
            not_found += 1
            if not only_fails:
                print(f"{DIM}  ○ {pn:<40} [{flag}]{exc_flag}  NOT FOUND{RESET}")
            continue

        issues = check(entry, result)

        if issues:
            fail += 1
            if is_exception(entry):
                exceptions_fail += 1
            print(f"{RED}  ✗ {pn:<40} [{flag}]{exc_flag}  {fmt_result(result)}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
        else:
            ok += 1
            if is_exception(entry):
                exceptions_ok += 1
            if not only_fails:
                print(f"{GREEN}  ✓ {pn:<40} [{flag}]{exc_flag}  {fmt_result(result)}{RESET}")

    print(f"\n{BOLD}{'━'*72}{RESET}")
    pct_ok = round(ok / total * 100) if total else 0
    pct_nf = round(not_found / total * 100) if total else 0
    status_color = GREEN if fail == 0 else RED

    print(
        f"{status_color}{BOLD}  RESULTADO: {ok}/{total} OK ({pct_ok}%)  |  "
        f"falhas={fail}  não_encontrados={not_found} ({pct_nf}%){RESET}"
    )

    if exceptions_ok or exceptions_fail:
        exc_total = exceptions_ok + exceptions_fail
        exc_color = GREEN if exceptions_fail == 0 else RED
        print(
            f"{exc_color}  Exceções (grammar errada): {exceptions_ok}/{exc_total} OK via DB  |  "
            f"{exceptions_fail} falha(s){RESET}"
        )
        if exceptions_fail > 0:
            print(f"{YELLOW}  ↳ Exceções com falha geralmente indicam que o import ainda não foi rodado.{RESET}")

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
        description="Testa PNs do Samsung Global LPDDR4/LPDDR4X 2017-2020 contra o engine WhatTheChip."
    )
    parser.add_argument("--only-fails", action="store_true")
    parser.add_argument("--file", default=None)
    args = parser.parse_args()

    path = args.file or CSV_PATH
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    if not os.path.exists(path):
        print(f"{RED}Arquivo não encontrado: {path}{RESET}")
        sys.exit(1)

    fail_count = run(path, args.only_fails)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
