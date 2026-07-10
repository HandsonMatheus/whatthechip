"""
import_samsung_psg.py
=====================
Importa Part Numbers do Samsung Product Selection Guide (PSG) a partir de
arquivos CSV gerados pelo script gen_psg_csv.py.

Os CSVs ficam em:  chipdocs/data/psg/psg_2h2014_*.csv

Cada linha do CSV representa um KnownPart:
  - is_base=yes  → PN base sem código de velocidade (ex: K4B4G1646QHC)
  - is_base=no   → variante de velocidade (ex: K4B4G1646QHCK0)

O comando NUNCA sobrescreve registros com confidence acima de "estimated".
Essa garantia vem do filtro _SAFE_TO_UPDATE: apenas registros com
confidence in ("estimated", "distributor")
são atualizados. Registros "manual" ou "confirmed" existentes são preservados.

Uso:
    python manage.py import_samsung_psg --file data/psg/psg_2h2014_ddr3.csv
    python manage.py import_samsung_psg --file data/psg/psg_2h2014_ddr3.csv --dry-run
    python manage.py import_samsung_psg --file data/psg/psg_2h2014_ddr3.csv --only-update
    python manage.py import_samsung_psg --file data/psg/psg_2h2014_ddr3.csv --only-create
    python manage.py import_samsung_psg --file data/psg/psg_2h2014_ddr3.csv --limit 10
    python manage.py import_samsung_psg --all   # importa todos os CSVs do diretório padrão
"""

import csv
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Ordem de confiança: quanto maior o índice, maior a prioridade.
# Import PSG só atualiza registros com confiança abaixo de "confirmed"/"manual".
_CONF_PRIORITY = {
    "estimated":   0,
    "distributor": 1,
    "manual":      2,
    "confirmed":   3,
}

# Confidence máxima que pode ser sobrescrita por este import.
# "distributor" e abaixo = sobrescrevível. "manual" e "confirmed" = protegidos.
_MAX_OVERWRITABLE = _CONF_PRIORITY["distributor"]

# Diretório padrão dos CSVs (relativo à BASE_DIR do projeto Django).
_PSG_CSV_DIR = "data/psg"

# CSVs incluídos no --all
_ALL_CSV_FILES = [
    # PSG 2H 2014
    "psg_2h2014_ddr4.csv",
    "psg_2h2014_ddr3.csv",
    "psg_2h2014_mobile_dram.csv",
    "psg_2h2014_emmc.csv",
    # PSG 1H 2017
    "psg_1h2017_mobile_dram.csv",
    "psg_1h2017_ufs.csv",
    "psg_1h2017_emmc.csv",
    # Samsung Semiconductor Global — LPDDR4/LPDDR4X gen S/D (2017-2020)
    "samsung_global_lpddr4_2017_2020.csv",
    # Samsung Semiconductor Global — LPDDR5/LPDDR5X (2020-2023)
    "samsung_global_lpddr5_2020_2023.csv",
    # Samsung Semiconductor Global — UFS 3.0/3.1 (2020-2023)
    "samsung_global_ufs_3x.csv",
    # Samsung Semiconductor Global — eMMC pós-PSG 2017 (gerações G/R/U, 8-256GB)
    "samsung_global_emmc_post2017.csv",
    # Samsung Semiconductor Global — LPDDR5X K3KL variantes 2-6GB (2022-2024)
    "samsung_global_lpddr5x_k3kl_extended.csv",
    # Samsung Semiconductor Global — LPDDR5X K3KL variantes 8-16GB + código DL (2022-2024)
    "samsung_global_lpddr5x_k3kl_large.csv",
    # Samsung Semiconductor Global — eMCP LPDDR3: REMOVIDO 2026-07-09 (CSV apagado). ⚠ Este import
    #   grava `capacity` e NÃO seta emcp_ram/emcp_nand → errado pra eMCP (convenção Opção 1); a RAM
    #   vivia só na prosa das notes. Pra eMCP/uMCP use `submit_known_parts` com specs estruturados.
    #   (Os outros eMCP/uMCP abaixo têm o MESMO problema — mantidos por ora, mas idem: não confiar.)
    # Samsung Semiconductor Global — eMCP LPDDR4X (KMD/KM3P/KM3H 2020-2023)
    "samsung_global_emcp_lpddr4x.csv",
    # Samsung Semiconductor Global — uMCP LPDDR4X (KM5/KM8/KM2H/KM2L/KM2P/KM2V 2020-2024)
    "samsung_global_umcp_lpddr4x.csv",
    # Samsung Semiconductor Global — uMCP LPDDR5 (KMAG/KMAS UFS 3.1 2022-2024)
    "samsung_global_umcp_lpddr5.csv",
    # Samsung Semiconductor Global — UFS 2.0/2.1/2.2 (KLUBG/KLUCG/KLUDG/KLUEG/KLUFG/KLUGG 2015-2022)
    "samsung_global_ufs_2x.csv",
    # Samsung Semiconductor Global — UFS 4.0/4.1 (KLUEG/KLUFG/KLUGG 2023+)
    "samsung_global_ufs_4x.csv",
    # Samsung Semiconductor Global — LPDDR5 K3LK variantes v2 (novos bases 2K/3K/4K/6K/7K/CK 2023-2025)
    "samsung_global_lpddr5_k3lk_v2.csv",
    # Samsung Semiconductor Global — LPDDR3 standalone (K3QF multi-channel PoP + K4E standalone 2013-2019)
    "samsung_global_lpddr3.csv",
]

# Mapeamento de chip_type CSV → chip_type no banco
_CHIP_TYPE_MAP = {
    "DDR":     "DDR",
    "LPDDR2":  "LPDDR2",
    "LPDDR3":  "LPDDR3",
    "LPDDR4":  "LPDDR4",
    "LPDDR4X": "LPDDR4X",
    "LPDDR5":  "LPDDR5",
    "LPDDR5X": "LPDDR5X",
    "eMMC":    "eMMC",
    "UFS":     "UFS",
    "eMCP":    "eMCP",
    "uMCP":    "uMCP",
}


def _resolve_path(file_arg):
    """Resolve o path do arquivo CSV relativo ao BASE_DIR do Django."""
    if os.path.isabs(file_arg):
        return file_arg
    # Tenta relativo ao cwd (onde o manage.py é invocado)
    cwd_path = os.path.join(os.getcwd(), file_arg)
    if os.path.exists(cwd_path):
        return cwd_path
    # Tenta relativo ao diretório do manage.py
    base_path = os.path.join(os.path.dirname(sys.argv[0]), file_arg)
    if os.path.exists(base_path):
        return base_path
    return cwd_path  # devolve o caminho cwd mesmo que não exista (erro tratado no caller)


def _load_csv(path):
    """Lê o CSV e retorna lista de dicts. Valida colunas obrigatórias."""
    required = {"pn", "chip_type", "subtype", "capacity", "interface",
                "confidence"}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return []
    missing = required - set(rows[0].keys())
    if missing:
        raise CommandError(
            f"CSV '{path}' sem colunas obrigatórias: {', '.join(sorted(missing))}"
        )
    return rows


def _get_or_create_source(source_name, source_url=""):
    """
    Obtém ou cria o registro Source para o PSG.
    src_type='datasheet' — documento oficial do fabricante.
    """
    from chips.models import Source
    src, created = Source.objects.get_or_create(
        name=source_name,
        defaults={
            "src_type": "datasheet",
            "url": source_url,
        },
    )
    return src


def _get_brand(brand_name="Samsung"):
    from chips.models import Brand
    try:
        return Brand.objects.get(name=brand_name)
    except Brand.DoesNotExist:
        return None


def _match_family(pn):
    """Igual à lógica do engine — encontra a ChipFamily com maior prefixo."""
    from chips.models import ChipFamily
    best = None
    best_len = 0
    for fam in ChipFamily.objects.filter(active=True).select_related("brand"):
        if pn.startswith(fam.prefix) and len(fam.prefix) > best_len:
            best = fam
            best_len = len(fam.prefix)
    return best


def _import_row(row_dict, brand, source, dry, only_update, only_create, verbosity):
    """
    Processa uma linha do CSV.

    Retorna: ("created"|"updated"|"skipped"|"protected"|"error", msg)
    """
    from chips.models import KnownPart

    pn = (row_dict.get("pn") or "").strip().upper()
    if not pn:
        return "skipped", "PN vazio"

    chip_type   = _CHIP_TYPE_MAP.get(row_dict.get("chip_type", ""), row_dict.get("chip_type", ""))
    subtype     = (row_dict.get("subtype")     or "").strip()
    capacity    = (row_dict.get("capacity")    or "").strip()
    density_gbit = (row_dict.get("density_gbit") or "").strip()
    density_gb  = (row_dict.get("density_gb")  or "").strip()
    interface   = (row_dict.get("interface")   or "").strip()
    org         = (row_dict.get("organization") or "").strip()
    voltage     = (row_dict.get("voltage")     or "").strip()
    speed       = (row_dict.get("speed_mbps")  or "").strip()
    pkg_pins    = (row_dict.get("package_pins") or "").strip()
    pkg_size    = (row_dict.get("package_size") or "").strip()
    pkg_type    = (row_dict.get("package_type") or "").strip()
    notes_csv   = (row_dict.get("notes")       or "").strip()
    confidence  = (row_dict.get("confidence")  or "confirmed").strip()
    pn_raw      = (row_dict.get("pn_raw")      or pn).strip()

    # Monta nota composta com dados técnicos do PSG para referência futura
    note_parts = []
    if org:
        note_parts.append(f"org={org}")
    if voltage:
        note_parts.append(f"V={voltage}")
    if speed:
        note_parts.append(f"speed={speed}Mbps")
    if pkg_pins:
        note_parts.append(f"{pkg_pins}-ball {pkg_type or 'FBGA'}")
    if pkg_size:
        note_parts.append(pkg_size)
    if notes_csv:
        note_parts.append(notes_csv)
    note_parts.append("Samsung PSG 2H 2014")
    notes_final = " | ".join(note_parts)

    # Tenta encontrar família no banco
    family = _match_family(pn)

    try:
        existing = KnownPart.objects.get(part_number=pn)
    except KnownPart.DoesNotExist:
        existing = None

    # ── Criar novo registro ──────────────────────────────────────────────────
    if existing is None:
        if only_update:
            return "skipped", f"{pn}: não existe no banco (--only-update)"

        if not dry:
            try:
                with transaction.atomic():
                    kp = KnownPart(
                        part_number  = pn,
                        brand        = brand,
                        family       = family,
                        chip_type    = chip_type,
                        subtype      = subtype,
                        capacity     = capacity,
                        density_gbit = density_gbit,
                        density_gb   = density_gb,
                        interface    = interface,
                        notes        = notes_final,
                        confidence   = confidence,
                        source       = source,
                        source_url   = f"psg_2h2014:{pn_raw}",
                    )
                    kp.save()
            except Exception as e:
                return "error", f"{pn}: {e}"

        return "created", pn

    # ── Atualizar registro existente ─────────────────────────────────────────
    if only_create:
        return "skipped", f"{pn}: já existe no banco (--only-create)"

    existing_prio = _CONF_PRIORITY.get(existing.confidence, 0)
    if existing_prio > _MAX_OVERWRITABLE:
        # Registro protegido (manual ou confirmed) — não sobrescreve
        return "protected", f"{pn}: confidence={existing.confidence} protegida"

    new_prio = _CONF_PRIORITY.get(confidence, 0)

    # Modo de atualização:
    #   force_overwrite=True  → PSG (confirmed) sobrescreve TODOS os campos com valor,
    #                           independente do que estava no banco antes.
    #                           Usado quando o import está promovendo para "confirmed".
    #   force_overwrite=False → preenche apenas campos vazios (modo conservador).
    #                           Usado quando a nova confidence não supera a existente.
    force_overwrite = (new_prio >= _CONF_PRIORITY["confirmed"])

    changed = {}

    def _set(field, new_val):
        """Marca campo para atualização: force=sempre; conservador=só se vazio."""
        if not new_val:
            return
        old_val = getattr(existing, field, None)
        # Para FKs (family), compara por pk
        if hasattr(new_val, "pk"):
            if force_overwrite or old_val is None:
                if old_val != new_val:
                    changed[field] = new_val
        else:
            if force_overwrite or not old_val:
                if old_val != new_val:
                    changed[field] = new_val

    _set("chip_type",    chip_type)
    _set("subtype",      subtype)
    _set("capacity",     capacity)
    _set("density_gbit", density_gbit)
    _set("density_gb",   density_gb)
    _set("interface",    interface)
    _set("family",       family)

    # Promove a confidence se o CSV tem valor mais alto
    if new_prio > existing_prio:
        changed["confidence"] = confidence

    # Atualiza source sempre que promovendo para confirmed
    if force_overwrite or existing.source is None:
        if existing.source != source:
            changed["source"] = source
    if force_overwrite or not existing.source_url:
        new_url = f"psg_2h2014:{pn_raw}"
        if existing.source_url != new_url:
            changed["source_url"] = new_url

    if not changed:
        return "skipped", f"{pn}: já correto"

    if not dry:
        try:
            with transaction.atomic():
                for field, val in changed.items():
                    setattr(existing, field, val)
                existing.save(update_fields=list(changed.keys()) + ["last_updated"])
        except Exception as e:
            return "error", f"{pn}: {e}"

    return "updated", f"{pn}: {list(changed.keys())}"


class Command(BaseCommand):
    help = "Importa Part Numbers do Samsung PSG 2H 2014 a partir de CSVs."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--file",
            metavar="PATH",
            help="Caminho do CSV a importar (relativo ao manage.py ou absoluto).",
        )
        group.add_argument(
            "--all",
            action="store_true",
            help=f"Importa todos os CSVs em {_PSG_CSV_DIR}/.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Simula sem gravar no banco.",
        )
        parser.add_argument(
            "--only-update", action="store_true",
            help="Só atualiza registros já existentes — não cria novos.",
        )
        parser.add_argument(
            "--only-create", action="store_true",
            help="Só cria registros novos — não atualiza existentes.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Limita o número de linhas processadas (útil para testes).",
        )
        parser.add_argument(
            "--brand", default="Samsung",
            help="Nome da marca no banco (padrão: Samsung).",
        )

    def handle(self, *args, **options):
        from chips.engine import clear_engine_cache

        dry         = options["dry_run"]
        only_update = options["only_update"]
        only_create = options["only_create"]
        limit       = options["limit"]
        brand_name  = options["brand"]
        verbosity   = options["verbosity"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # Resolve arquivos a processar
        if options["all"]:
            base_dir = _resolve_path(_PSG_CSV_DIR)
            files = [os.path.join(base_dir, f) for f in _ALL_CSV_FILES]
        else:
            files = [_resolve_path(options["file"])]

        # Valida arquivos
        for f in files:
            if not os.path.exists(f):
                raise CommandError(f"Arquivo não encontrado: {f}")

        # Carrega dependências do banco
        brand = _get_brand(brand_name)
        if brand is None:
            raise CommandError(
                f"Brand '{brand_name}' não encontrada no banco. "
                f"Execute populate_samsung primeiro."
            )

        source = _get_or_create_source(
            "Samsung PSG 2H 2014",
            "https://datasheet.chipset.com.tr/datasheet/vram/samsung/psg.pdf",
        )

        # Totais cumulativos
        total_created = total_updated = total_skipped = total_protected = total_errors = 0

        for csv_path in files:
            self.stdout.write(f"\n📄 {os.path.basename(csv_path)}")
            rows = _load_csv(csv_path)
            if limit:
                rows = rows[:limit]

            created = updated = skipped = protected = errors = 0

            for row_dict in rows:
                outcome, msg = _import_row(
                    row_dict, brand, source, dry, only_update, only_create, verbosity
                )
                if outcome == "created":
                    created += 1
                    if verbosity >= 2:
                        self.stdout.write(self.style.SUCCESS(f"  ✚ {msg}"))
                elif outcome == "updated":
                    updated += 1
                    if verbosity >= 2:
                        self.stdout.write(self.style.SUCCESS(f"  ↺ {msg}"))
                elif outcome == "protected":
                    protected += 1
                    if verbosity >= 2:
                        self.stdout.write(self.style.WARNING(f"  🔒 {msg}"))
                elif outcome == "error":
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {msg}"))
                else:
                    skipped += 1
                    if verbosity >= 3:
                        self.stdout.write(f"  — {msg}")

            prefix = "[DRY] " if dry else ""
            self.stdout.write(
                f"  {prefix}criados={created} atualizados={updated} "
                f"pulados={skipped} protegidos={protected} erros={errors}"
            )
            total_created   += created
            total_updated   += updated
            total_skipped   += skipped
            total_protected += protected
            total_errors    += errors

        if len(files) > 1:
            self.stdout.write(
                f"\n{'[DRY] ' if dry else ''}TOTAL: "
                f"criados={total_created} atualizados={total_updated} "
                f"pulados={total_skipped} protegidos={total_protected} "
                f"erros={total_errors}"
            )

        if not dry and (total_created + total_updated) > 0:
            try:
                clear_engine_cache()
                self.stdout.write(self.style.SUCCESS("\n✅  Cache do engine limpo."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"\n⚠  Cache não limpo: {e}"))

        if not dry and total_created + total_updated > 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅  Import concluído: {total_created} criados, {total_updated} atualizados."
            ))
