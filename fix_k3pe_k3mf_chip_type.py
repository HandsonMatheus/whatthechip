#!/usr/bin/env python
"""
fix_k3pe_k3mf_chip_type.py
===========================
Corrige dois problemas nos registros K3PE/K3MF do banco:

  1. chip_type="RAM" → "LPDDR2" (K3PE) ou "LPDDR3" (K3MF)
     (O banco já tem os valores corretos para esses chips — verificado em dry-run anterior)

  2. family FK = K3 genérico → família correta K3PE / K3MF
     Causa raiz dos 4 avisos restantes no teste: o engine usa kp.family.chip_type
     diretamente. Antes da família K3PE existir, esses registros receberam
     family=K3 (chip_type="RAM"). Agora que K3PE existe, a FK precisa ser atualizada.

Esses PNs estão no banco com confidence=confirmed (protection ativa no import).
Este script é a correção cirúrgica dos 6 registros afetados.

Uso (da raiz do projeto, com venv ativo):
    python fix_k3pe_k3mf_chip_type.py           # dry-run (padrão seguro)
    python fix_k3pe_k3mf_chip_type.py --apply   # aplica a correção

Registros afetados (PSG 2H 2014, mobile_dram):
    K3PE7E70QMBGC2  family: K3→K3PE  chip_type: verificado
    K3PE7E70QMCGC2  family: K3→K3PE  chip_type: verificado
    K3PE0E00QMBGC2  family: K3→K3PE  chip_type: verificado
    K3PE0E00QMCGC2  family: K3→K3PE  chip_type: verificado
    K3MF8F80DMMGCE  family: K3→K3MF  chip_type: verificado
    K3MF9F90MMMGCE  family: K3→K3MF  chip_type: verificado
"""

import argparse
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.models import KnownPart, ChipFamily  # noqa: E402

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# (part_number, chip_type_correto, prefixo_família_correta)
FIXES = [
    ("K3PE7E70QMBGC2", "LPDDR2", "K3PE"),
    ("K3PE7E70QMCGC2", "LPDDR2", "K3PE"),
    ("K3PE0E00QMBGC2", "LPDDR2", "K3PE"),
    ("K3PE0E00QMCGC2", "LPDDR2", "K3PE"),
    ("K3MF8F80DMMGCE", "LPDDR3", "K3MF"),
    ("K3MF9F90MMMGCE", "LPDDR3", "K3MF"),
]


def _get_family(prefix):
    try:
        return ChipFamily.objects.get(prefix=prefix)
    except ChipFamily.DoesNotExist:
        return None


def run(apply: bool):
    dry = not apply
    tag = "[DRY] " if dry else ""

    print(f"\n{BOLD}{'─'*68}{RESET}")
    print(f"{BOLD}  {tag}Correção family FK + chip_type K3PE/K3MF  ({len(FIXES)} registros){RESET}")
    print(f"{BOLD}{'─'*68}{RESET}\n")

    # Pré-carrega famílias
    families = {}
    for _, _, fam_prefix in FIXES:
        if fam_prefix not in families:
            fam = _get_family(fam_prefix)
            if fam is None:
                print(f"{RED}  ✗ ChipFamily '{fam_prefix}' não encontrada no banco.{RESET}")
                print(f"{RED}    Execute: python manage.py populate_samsung --overwrite{RESET}")
                sys.exit(1)
            families[fam_prefix] = fam
            print(f"  ℹ  Família {fam_prefix}: chip_type={fam.chip_type!r} (id={fam.pk})")
    print()

    ok = skip = err = 0

    for pn_str, correct_ct, fam_prefix in FIXES:
        try:
            obj = KnownPart.objects.get(part_number=pn_str)
        except KnownPart.DoesNotExist:
            print(f"{YELLOW}  ? {pn_str}: não encontrado no banco — pulando{RESET}")
            skip += 1
            continue

        target_fam = families[fam_prefix]
        current_fam_prefix = obj.family.prefix if obj.family else None
        current_ct = obj.chip_type or ""

        changes = []
        if current_fam_prefix != fam_prefix:
            changes.append(f"family: {current_fam_prefix!r} → {fam_prefix!r}")
        if current_ct != correct_ct:
            changes.append(f"chip_type: {current_ct!r} → {correct_ct!r}")

        if not changes:
            print(f"{GREEN}  = {pn_str}: já correto (family={fam_prefix!r}, chip_type={correct_ct!r}){RESET}")
            skip += 1
            continue

        change_str = "  +  ".join(changes)
        print(f"  {'→' if not dry else '~'} {pn_str}:  {change_str}")

        if not dry:
            try:
                fields_to_save = []
                if current_fam_prefix != fam_prefix:
                    obj.family = target_fam
                    fields_to_save.append("family")
                if current_ct != correct_ct:
                    obj.chip_type = correct_ct
                    fields_to_save.append("chip_type")
                obj.save(update_fields=fields_to_save)
                ok += 1
            except Exception as e:
                print(f"{RED}    ↳ ERRO ao salvar: {e}{RESET}")
                err += 1
        else:
            ok += 1  # "seriam corrigidos"

    print(f"\n{BOLD}{'─'*68}{RESET}")
    if dry:
        print(
            f"{YELLOW}{BOLD}  DRY RUN — nada foi salvo.{RESET}\n"
            f"  Seriam corrigidos: {ok}  |  já corretos: {skip}  |  erros: {err}\n"
            f"{YELLOW}  Rode com --apply para aplicar as correções.{RESET}"
        )
    else:
        color = GREEN if err == 0 else RED
        print(f"{color}{BOLD}  Corrigidos: {ok}  |  já corretos: {skip}  |  erros: {err}{RESET}")
        if ok > 0 and err == 0:
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                print(f"{GREEN}  ✅ Cache do engine limpo.{RESET}")
            except Exception as e:
                print(f"{YELLOW}  ⚠ Cache não limpo: {e}{RESET}")
    print(f"{BOLD}{'─'*68}{RESET}\n")

    return err


def main():
    parser = argparse.ArgumentParser(
        description="Corrige family FK e chip_type de K3PE/K3MF (RAM → LPDDR2/LPDDR3)."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Aplica as correções no banco. Sem --apply, apenas simula (dry-run)."
    )
    args = parser.parse_args()

    if not args.apply:
        print(f"{YELLOW}⚠  Modo dry-run (padrão). Passe --apply para salvar.{RESET}")

    err = run(apply=args.apply)
    sys.exit(0 if err == 0 else 1)


if __name__ == "__main__":
    main()
