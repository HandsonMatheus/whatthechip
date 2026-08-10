# -*- coding: utf-8 -*-
"""
fix_micron_type_from_api.py
===========================
FASE 1 da remediação Micron — o caminho BARATO E SEM ALUCINAÇÃO.

Corrige o ``chip_type`` (Problema B: eMCP/uMCP/​"MCP" trocados) usando **só o que
a API FBGA oficial da Micron devolve DIRETAMENTE**:

  - ``sub_category`` (o catálogo em que a Micron cadastra a peça) → o TIPO;
  - ``part_name``    (a string oficial)                          → a GERAÇÃO da RAM.

O que este comando **NÃO** faz (de propósito):
  - NÃO usa gramática, NÃO usa decode map, NÃO chuta (``_infer_*``);
  - NÃO preenche capacidade / emcp_nand / emcp_ram / densidade — isso é a FASE 2
    (datasheet), porque a API só dá densidade TOTAL, sem o split;
  - onde a API vem **vazia** ou **ambígua** → **NÃO TOCA** no registro.

Fonte: mesma API do ``fill_capacity_from_micron_api`` (micron.com FBGA decoder) —
reutiliza os helpers ``_query_by_fbga`` / ``_make_session`` dele.

Mapa ``sub_category`` → ``chip_type`` (só casos NÃO-ambíguos):
    *ufs-based-mcp*   → uMCP
    *emmc-based-mcp*  → eMCP
    *nand-mcp*        → eMCP  SE o part_name contém "EMMC"
                        uMCP  SE o part_name contém "UMCP"/"UFS"
                        senão → SKIP  (NAND-MCP cru legado — não forçar tipo)
    vazio / outro     → SKIP

``subtype`` (geração LPDDR) do ``part_name``, **só quando explícito**
("…/LPDDR2 36G", "…/LPDDR4X …"). "UMCP 80G" (sem geração) e "MOBILE SDR/DDR"
(pré-LPDDR2) → SKIP (não inventa a geração).

Escreve, pelo PORTÃO do modelo (``kp.save()``): ``chip_type`` (se difere e a API
deu um tipo confiável), ``subtype`` (só se estava vazio e a API deu a geração),
``notes`` (carimbo de auditoria com a fonte Tier-1). Só grava registros em que a
API deu um tipo confiável — os ambíguos/vazios ficam intactos pra Fase 2.

Dry-run por padrão. ``--commit`` grava (backup JSON p/ ``--revert``).

Uso:
    python manage.py fix_micron_type_from_api --dry-run            # (padrão) só mostra
    python manage.py fix_micron_type_from_api --dry-run --limit 40
    python manage.py fix_micron_type_from_api --fbga JZ091         # testa 1 FBGA
    python manage.py fix_micron_type_from_api --commit
    python manage.py fix_micron_type_from_api --revert
"""
import json
import os
import re
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Reutiliza a MESMA sessão/consulta do pipeline de capacidade (fonte única da API).
from chips.management.commands.fill_capacity_from_micron_api import (
    _query_by_fbga,
    _make_session,
)

_REVERT_DIR = "var/reverts"
_REVERT = os.path.join(_REVERT_DIR, "fix_micron_type_from_api_revert.json")

# Só as famílias gerenciadas onde o tipo pode estar trocado. A DRAM discreta
# (DDR/LPDDR) não tem essa ambiguidade e a API FBGA nem a cobre (volta vazio).
_MANAGED_TYPES = ["eMCP", "uMCP", "MCP", "eMMC", "UFS"]

_RAM_GEN_RE = re.compile(r'LPDDR\s?(5X|5|4X|4|3|2|1)')


def _chip_type_from_api(sub_category: str, part_name: str) -> str | None:
    """chip_type canônico a partir do sub_category (+ part_name p/ desambiguar).

    Retorna None quando ambíguo/vazio → o chamador NÃO TOCA no registro
    (é o coração do "sem alucinação")."""
    sc = (sub_category or "").lower()
    pn = (part_name or "").upper()

    if "ufs-based-mcp" in sc:
        return "uMCP"
    if "emmc-based-mcp" in sc:
        return "eMCP"
    if "nand-mcp" in sc or "nand-based-mcp" in sc:
        # O catálogo "nand-mcp" da Micron mistura eMMC-based (=eMCP) com NAND cru.
        # Desambigua pelo part_name; sem sinal claro → não força.
        if "EMMC" in pn:
            return "eMCP"
        if "UMCP" in pn or "UFS" in pn:
            return "uMCP"
        return None
    return None


def _ram_gen_from_part_name(part_name: str) -> str | None:
    """Geração LPDDR a partir do part_name, SÓ quando explícita. Senão None.

    "SLC EMMC/LPDDR2 36G" → "LPDDR2"      "UMCP 80G"        → None (sem geração)
    "…/LPDDR4X …"         → "LPDDR4X"     "MASSFLASH/MOBILE DDR" → None (não inventa)
    """
    pn = (part_name or "").upper().replace("-", "")
    m = _RAM_GEN_RE.search(pn)
    return ("LPDDR" + m.group(1)) if m else None


class Command(BaseCommand):
    help = (
        "FASE 1 (barato, sem alucinação) da remediação Micron: corrige chip_type "
        "e geração usando SÓ o que a API FBGA da Micron devolve direto. "
        "Não preenche capacidade. Dry-run por padrão."
    )

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true",
                            help="Grava as correções (padrão é dry-run).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Não grava — é o padrão. Aceito p/ ser explícito.")
        parser.add_argument("--revert", action="store_true",
                            help="Desfaz a última execução com --commit (via backup JSON).")
        parser.add_argument("--limit", type=int, default=0, metavar="N",
                            help="Processa no máximo N registros (0 = sem limite).")
        parser.add_argument("--delay", type=float, default=1.0, metavar="SEG",
                            help="Pausa entre requests à API (padrão 1.0).")
        parser.add_argument("--fbga", dest="fbga_filter", metavar="CODE",
                            help="Processa só este FBGA (teste).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart

        if opts["revert"]:
            return self._revert()

        commit = opts["commit"]
        delay  = opts["delay"]

        qs = KnownPart.objects.filter(
            brand__name__icontains="micron",
            chip_type__in=_MANAGED_TYPES,
        ).exclude(fbga_code="").exclude(fbga_code__isnull=True)

        if opts.get("fbga_filter"):
            qs = qs.filter(fbga_code=opts["fbga_filter"].upper())

        qs = qs.order_by("part_number")
        total = qs.count()
        if opts["limit"]:
            qs = qs[:opts["limit"]]
        rows = list(qs)

        self.stdout.write(
            f"Micron gerenciados com FBGA: {total}"
            + (f"  (processando {len(rows)})" if opts["limit"] else "")
        )
        if not commit:
            self.stdout.write(self.style.WARNING("⚠  DRY-RUN — nada será gravado.\n"))

        session = _make_session()
        changes = []   # (kp, before_dict, update_fields, diff_str)
        stats = {"consultados": 0, "sem_api": 0, "ambiguo": 0,
                 "tipo_corrigido": 0, "tipo_confirmado": 0, "subtype": 0}

        for idx, kp in enumerate(rows, 1):
            self.stdout.write(f"[{idx}/{len(rows)}] {kp.fbga_code}  {kp.part_number[:44]}", ending="")
            api = _query_by_fbga(kp.fbga_code, session)
            stats["consultados"] += 1
            if not api:
                stats["sem_api"] += 1
                self.stdout.write(self.style.WARNING("  → API vazia (não toca)"))
                time.sleep(delay)
                continue

            sub_cat   = api.get("sub_category", "")
            part_name = api.get("part_name", "")
            api_type  = _chip_type_from_api(sub_cat, part_name)

            if not api_type:
                stats["ambiguo"] += 1
                self.stdout.write(self.style.WARNING(
                    f"  → ambíguo (sub-cat={sub_cat!r}, part-name={part_name!r}) — não toca"))
                time.sleep(delay)
                continue

            before = {"chip_type": kp.chip_type, "subtype": kp.subtype, "notes": kp.notes}
            update_fields, diffs = [], []

            # chip_type — só grava se a API dá um tipo confiável E difere
            if kp.chip_type != api_type:
                diffs.append(f"chip_type {kp.chip_type!r}→{api_type!r}")
                kp.chip_type = api_type
                update_fields.append("chip_type")
                stats["tipo_corrigido"] += 1
            else:
                stats["tipo_confirmado"] += 1

            # subtype (geração) — só se estava vazio E a API deu a geração explícita
            gen = _ram_gen_from_part_name(part_name)
            if gen and not (kp.subtype or "").strip():
                diffs.append(f"subtype ''→{gen!r}")
                kp.subtype = gen
                update_fields.append("subtype")
                stats["subtype"] += 1

            # notes — carimbo de auditoria com a fonte Tier-1
            stamp = (f"[Micron FBGA API] tipo={api_type} "
                     f"(sub-cat: {sub_cat!r}; part-name: {part_name!r})")
            if stamp not in (kp.notes or ""):
                kp.notes = f"{(kp.notes or '').strip()}\n{stamp}".strip()
                update_fields.append("notes")

            if not update_fields:
                self.stdout.write("  → já OK")
                time.sleep(delay)
                continue

            diff_str = ", ".join(diffs) if diffs else "só notes"
            self.stdout.write(self.style.SUCCESS(f"  → {diff_str}"))
            changes.append((kp, before, update_fields, diff_str))
            time.sleep(delay)

        # ── Relatório ──
        self.stdout.write(self.style.SUCCESS(
            f"\n\nConsultados: {stats['consultados']}  ·  API vazia: {stats['sem_api']}  ·  "
            f"ambíguos (não tocados): {stats['ambiguo']}\n"
            f"Tipo CORRIGIDO: {stats['tipo_corrigido']}  ·  tipo confirmado: {stats['tipo_confirmado']}  ·  "
            f"subtype preenchido: {stats['subtype']}\n"
            f"Registros a gravar: {len(changes)}"
        ))

        if not commit:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN — nada gravado. Revise e rode com --commit."))
            return

        if not changes:
            self.stdout.write("Nada a gravar.")
            return

        # ── Grava pelo PORTÃO do modelo (kp.save valida a convenção) ──
        log = {"rows": []}
        saved, errors = 0, 0
        for kp, before, update_fields, _ in changes:
            try:
                with transaction.atomic():
                    kp.save(update_fields=update_fields)
                log["rows"].append({"pk": kp.pk, "before": {k: before[k] for k in update_fields}})
                saved += 1
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"  ✗ {kp.part_number}: {e}"))

        os.makedirs(_REVERT_DIR, exist_ok=True)
        with open(_REVERT, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1, default=str)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {saved} gravado(s)  ·  {errors} erro(s).  "
            f"Revert: python manage.py fix_micron_type_from_api --revert"))

        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
        except Exception:
            pass

    def _revert(self):
        from chips.models import KnownPart
        if not os.path.exists(_REVERT):
            raise CommandError(f"Backup de revert não encontrado: {_REVERT}")
        with open(_REVERT, encoding="utf-8") as fh:
            log = json.load(fh)
        n = 0
        for row in log["rows"]:
            kp = KnownPart.objects.filter(pk=row["pk"]).first()
            if not kp:
                continue
            for k, v in row["before"].items():
                setattr(kp, k, v)
            with transaction.atomic():
                kp.save(update_fields=list(row["before"].keys()))
            n += 1
        os.rename(_REVERT, _REVERT + ".done")
        self.stdout.write(self.style.SUCCESS(f"✅ Revertido: {n} registro(s). Log → {_REVERT}.done"))
