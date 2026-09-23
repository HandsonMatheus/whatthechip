"""
Management command: import_chipid
==================================
Importa dados do chipid_project para o WhatTheChip.

Fontes lidas:
  1. db.sqlite3 do chipid  — Brands, ChipFamilies, DecodeMaps, KnownParts enriquecidos
  2. scripts/state/*.json  — PNs raw de todas as marcas coletadas

Uso:
    python manage.py import_chipid \\
        --sqlite /caminho/para/chipid_project/db.sqlite3 \\
        --state-dir /caminho/para/chipid_project/scripts/state

Flags:
    --skip-existing     Pula registros que já existem (padrão)
    --overwrite         Sobrescreve campos vazios em registros existentes
    --dry-run           Apenas conta o que seria importado, sem salvar

Exemplo real (a partir da pasta chipdocs/):
    python manage.py import_chipid \\
        --sqlite ../../chipid_project/db.sqlite3 \\
        --state-dir ../../chipid_project/scripts/state
"""

import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from chips.knowledge.convention import (
    bus_width_problem, notes_com_speed, split_bus_width,
)


#: Contadores do reparte de largura — impressos no fim, para que nenhum valor
#: do banco legado suma em silêncio (PLANO_BUS_WIDTH I5).
_bw_stats: dict[str, int] = {}


def _reparte_interface(interface: str, chip_type: str, notes: str) -> tuple[str, str, str]:
    """Reparte um `interface` do banco LEGADO em ``(interface, bus_width, notes)``.

    O chipid_project guardava a largura dentro do `interface` — é de lá que
    vieram os ``x16`` das 25 famílias que a Fase 4 acabou de limpar. Reimportar
    sem repartir **desfaz a Fase 4**, e no caso da `ChipFamily` desfaz EM
    SILÊNCIO: só o `KnownPart` tem `save()` que chama `full_clean()`, a família
    não — o `clean()` dela existe mas ninguém o executa no caminho deste
    comando (`update_or_create`).

    Regras, as mesmas do backfill (`normalize_convention`):

    - ``'x16'``              → largura sai, `interface` fica vazio
    - ``'x16 @ 800MHz'``     → largura sai, velocidade vai para `notes`
    - ``'eMMC 5.1'``         → intacto (é protocolo, não largura)
    - ``'x16 (2 dies)'``     → **NÃO migra**: sobra sem destino, decisão humana
    - largura em classe que não admite (eMMC/eMCP/uMCP) → **não migra**
    """
    bw, speed, resto = split_bus_width(interface or "")

    if not bw and not speed:
        return (interface or "", "", notes or "")

    if bw and resto:                                   # SOBRA SEM DESTINO
        _bw_stats["sobra sem destino"] = _bw_stats.get("sobra sem destino", 0) + 1
        return (interface or "", "", notes or "")

    if bw and bus_width_problem(chip_type, bw):        # CLASSE NÃO PERMITE
        _bw_stats["classe não permite"] = _bw_stats.get("classe não permite", 0) + 1
        return (interface or "", "", notes or "")

    if bw:
        _bw_stats["largura movida"] = _bw_stats.get("largura movida", 0) + 1
    if speed:
        _bw_stats["velocidade → notes"] = _bw_stats.get("velocidade → notes", 0) + 1

    return (resto, bw, notes_com_speed(notes or "", speed))
from django.db import transaction

from chips.models import Brand, Source, ChipFamily, DecodeMap, KnownPart


# Mapeamento de brand_id do SQLite para nome — preenchido durante a importação
_brand_id_map: dict[int, Brand] = {}


class Command(BaseCommand):
    help = "Importa dados do chipid_project (SQLite + JSONs) para o WhatTheChip"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite", type=str, required=True,
            help="Caminho para o db.sqlite3 do chipid_project"
        )
        parser.add_argument(
            "--state-dir", type=str, required=True,
            help="Caminho para a pasta scripts/state/ do chipid_project"
        )
        parser.add_argument(
            "--overwrite", action="store_true", default=False,
            help="Sobrescreve campos vazios em registros já existentes"
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Apenas conta o que seria importado, sem salvar"
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite"])
        state_dir   = Path(options["state_dir"])
        overwrite   = options["overwrite"]
        dry_run     = options["dry_run"]

        if not sqlite_path.exists():
            raise CommandError(f"SQLite não encontrado: {sqlite_path}")
        if not state_dir.exists():
            raise CommandError(f"Diretório state não encontrado: {state_dir}")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY RUN — nenhum dado será salvo\n"))

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        try:
            with transaction.atomic():
                self._import_brands(conn, dry_run)
                self._import_decodemaps(conn, dry_run)
                self._import_chipfamilies(conn, dry_run, overwrite)
                self._import_knownparts(conn, dry_run, overwrite)
                self._import_raw_pns(state_dir, dry_run)

                if dry_run:
                    # Rollback tudo em dry-run
                    transaction.set_rollback(True)
        finally:
            conn.close()

        # ── O reparte de largura, contado (I5: nada some em silêncio) ───────
        if _bw_stats:
            self.stdout.write("\n── Reparte de largura (`interface` → `bus_width`) ──")
            for motivo, n in sorted(_bw_stats.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"  {n:6d}  {motivo}")
            nao = _bw_stats.get("sobra sem destino", 0) + _bw_stats.get("classe não permite", 0)
            if nao:
                self.stdout.write(
                    f"  ⚠ {nao} registro(s) ficaram com a largura NO `interface` de propósito "
                    f"— decisão humana, não descarte."
                )

        self.stdout.write(self.style.SUCCESS("\n✅ Importação concluída!"))
        self.stdout.write(
            "Próximos passos:\n"
            "  1. Rode 'python manage.py migrate' se ainda não rodou\n"
            "  2. Acesse /admin/chips/chipfamily/ e vincule doc_page para cada família\n"
            "  3. Confirme os PNs no admin (confidence=manual) para o engine usá-los\n"
        )

    # ── Brands ────────────────────────────────────────────────────────────────

    def _import_brands(self, conn, dry_run):
        self.stdout.write("\n── Importando Brands ──")
        cur = conn.execute("SELECT id, name, code, notes FROM classifier_brand")
        rows = cur.fetchall()
        created = skipped = 0

        for row in rows:
            brand_id = row["id"]
            name     = row["name"].strip()
            code     = (row["code"] or name.upper()[:10].replace(" ", "")).strip()
            notes    = row["notes"] or ""

            if not dry_run:
                brand, was_created = Brand.objects.get_or_create(
                    name__iexact=name,
                    defaults={"name": name, "code": code, "notes": notes}
                )
                _brand_id_map[brand_id] = brand
                if was_created:
                    created += 1
                else:
                    skipped += 1
                    _brand_id_map[brand_id] = brand
            else:
                created += 1

        self.stdout.write(f"  Criados: {created}  |  Já existiam: {skipped}")

    # ── DecodeMaps ────────────────────────────────────────────────────────────

    def _import_decodemaps(self, conn, dry_run):
        self.stdout.write("\n── Importando DecodeMaps ──")
        cur = conn.execute(
            "SELECT map_name, char_key, val_primary, val_secondary, brand_id, notes "
            "FROM classifier_decodemap"
        )
        rows = cur.fetchall()
        created = skipped = 0

        for row in rows:
            brand_obj = _brand_id_map.get(row["brand_id"]) if row["brand_id"] else None

            if not dry_run:
                _, was_created = DecodeMap.objects.get_or_create(
                    map_name=row["map_name"],
                    char_key=row["char_key"],
                    brand=brand_obj,
                    defaults={
                        "val_primary":   row["val_primary"]   or "",
                        "val_secondary": row["val_secondary"] or "",
                        "notes":         row["notes"]         or "",
                    }
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            else:
                created += 1

        self.stdout.write(f"  Criados: {created}  |  Já existiam: {skipped}")

    # ── ChipFamilies ──────────────────────────────────────────────────────────

    def _import_chipfamilies(self, conn, dry_run, overwrite):
        self.stdout.write("\n── Importando ChipFamilies ──")
        cur = conn.execute(
            """SELECT brand_id, prefix, chip_type, subtype, interface,
                      decode_cap_pos, decode_cap_map, decode_gen_pos, decode_gen_map,
                      decode_density_type, is_emcp, suffix_rules, tip, reasoning,
                      priority, active
               FROM classifier_chipfamily
               ORDER BY priority, prefix"""
        )
        rows = cur.fetchall()
        created = skipped = updated = 0

        for row in rows:
            brand_obj = _brand_id_map.get(row["brand_id"])
            if not brand_obj:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠ Família '{row['prefix']}' sem brand_id={row['brand_id']} — pulando")
                )
                continue

            # ⚠ O legado guardava largura DENTRO do `interface` — reimportar sem
            #   repartir desfaz a Fase 4, e aqui desfaz em SILÊNCIO (ChipFamily
            #   não roda `full_clean()` no `save()`).
            fam_if, fam_bw, _ = _reparte_interface(
                row["interface"] or "", row["chip_type"] or "", ""
            )

            defaults = {
                "chip_type":           row["chip_type"] or "",
                "subtype":             row["subtype"] or "",
                "interface":           fam_if,
                "bus_width":           fam_bw,
                "decode_cap_pos":      row["decode_cap_pos"],
                "decode_cap_map":      row["decode_cap_map"] or "",
                "decode_gen_pos":      row["decode_gen_pos"],
                "decode_gen_map":      row["decode_gen_map"] or "",
                "decode_density_type": row["decode_density_type"] or "",
                "is_emcp":             bool(row["is_emcp"]),
                "suffix_rules":        row["suffix_rules"] or "",
                "tip":                 row["tip"] or "",
                "reasoning":           row["reasoning"] or "",
                "priority":            row["priority"] if row["priority"] is not None else 100,
                "active":              bool(row["active"]),
            }

            if not dry_run:
                fam, was_created = ChipFamily.objects.get_or_create(
                    brand=brand_obj,
                    prefix=row["prefix"],
                    defaults=defaults
                )
                if was_created:
                    created += 1
                elif overwrite:
                    for field, val in defaults.items():
                        if val and not getattr(fam, field):
                            setattr(fam, field, val)
                    fam.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                created += 1

        self.stdout.write(
            f"  Criadas: {created}  |  Atualizadas: {updated}  |  Já existiam: {skipped}"
        )
        self.stdout.write(
            self.style.WARNING(
                "  ℹ️  Lembre-se de vincular doc_page em cada família via /admin/chips/chipfamily/"
            )
        )

    # ── KnownParts enriquecidos ───────────────────────────────────────────────

    def _import_knownparts(self, conn, dry_run, overwrite):
        self.stdout.write("\n── Importando KnownParts (enriquecidos) ──")
        cur = conn.execute(
            """SELECT kp.part_number, kp.brand_id, kp.chip_type, kp.subtype,
                      kp.capacity, kp.density_gbit, kp.density_gb,
                      kp.emcp_ram, kp.emcp_nand, kp.interface, kp.device,
                      kp.notes, kp.confidence, kp.source_url
               FROM classifier_knownpart kp"""
        )
        rows = cur.fetchall()
        created = skipped = updated = 0

        chipid_source, _ = Source.objects.get_or_create(
            name="chipid_import",
            defaults={"src_type": "distributor", "url": "chipid_project"}
        ) if not dry_run else (None, None)

        for row in rows:
            brand_obj = _brand_id_map.get(row["brand_id"])
            if not brand_obj and not dry_run:
                # Tenta encontrar brand pelo nome se mapeamento falhou
                continue

            pn = row["part_number"].strip().upper()
            if not pn:
                continue

            # has_data: a linha tem specs reais? (usado só para a contagem dry-run)
            has_data = bool(
                row["capacity"] or row["emcp_ram"] or row["emcp_nand"] or row["density_gbit"]
            )

            kp_if, kp_bw, kp_notes = _reparte_interface(
                row["interface"] or "", row["chip_type"] or "", row["notes"] or ""
            )

            defaults = {
                "brand":        brand_obj,
                "chip_type":    row["chip_type"]    or "",
                "subtype":      row["subtype"]      or "",
                "capacity":     row["capacity"]     or "",
                "density_gbit": row["density_gbit"] or "",
                "density_gb":   row["density_gb"]   or "",
                "emcp_ram":     row["emcp_ram"]      or "",
                "emcp_nand":    row["emcp_nand"]     or "",
                "interface":    kp_if,
                "bus_width":    kp_bw,
                "device":       row["device"]       or "",
                "notes":        kp_notes,
                "confidence":   row["confidence"]   or "estimated",
                "source":       chipid_source,
                "source_url":   row["source_url"]   or "",
            }

            if not dry_run:
                part, was_created = KnownPart.objects.get_or_create(
                    part_number=pn, defaults=defaults
                )
                if was_created:
                    # Tenta vincular à família
                    from chips.engine import _match_family
                    fam = _match_family(pn)
                    if fam:
                        part.family = fam
                        part.save(update_fields=["family"])
                    created += 1
                elif overwrite:
                    changed = False
                    for field, val in defaults.items():
                        if field in ("brand", "source"):
                            continue
                        if val and not getattr(part, field):
                            setattr(part, field, val)
                            changed = True
                    if changed:
                        part.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                if has_data:
                    created += 1

        self.stdout.write(
            f"  Criados: {created}  |  Atualizados: {updated}  |  Já existiam: {skipped}"
        )

    # ── PNs raw dos JSONs ─────────────────────────────────────────────────────

    def _import_raw_pns(self, state_dir: Path, dry_run):
        self.stdout.write("\n── Importando PNs raw dos JSONs ──")

        json_files = sorted(state_dir.glob("*_pns.json"))
        if not json_files:
            self.stdout.write("  Nenhum arquivo *_pns.json encontrado.")
            return

        total_created = total_skipped = total_files = 0

        for json_path in json_files:
            brand_name = json_path.stem.replace("_pns", "").replace("_", " ").strip()
            # Normaliza nomes especiais
            name_fixes = {"SK Hynix": "SK Hynix", "Sandisk": "SanDisk"}
            brand_name = name_fixes.get(brand_name, brand_name)

            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ Erro ao ler {json_path.name}: {e}"))
                continue

            # Extrai lista de PNs — suporta formatos dict com chave 'pns' ou lista direta
            if isinstance(data, dict):
                pns = data.get("pns", [])
            elif isinstance(data, list):
                pns = data
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Formato inesperado em {json_path.name}"))
                continue

            if not pns:
                continue

            # Garante que a marca existe
            if not dry_run:
                brand_obj, _ = Brand.objects.get_or_create(
                    name__iexact=brand_name,
                    defaults={
                        "name": brand_name,
                        "code": brand_name.upper()[:10].replace(" ", ""),
                    }
                )
            else:
                brand_obj = None

            created = skipped = 0
            for pn_raw in pns:
                pn = str(pn_raw).strip().upper()
                if not pn or len(pn) < 4:
                    continue

                if not dry_run:
                    _, was_created = KnownPart.objects.get_or_create(
                        part_number=pn,
                        defaults={
                            "brand":  brand_obj,
                        }
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                else:
                    created += 1

            self.stdout.write(
                f"  {json_path.name}: {created} novos raw  |  {skipped} já existiam"
            )
            total_created += created
            total_skipped += skipped
            total_files   += 1

        self.stdout.write(
            f"\n  Total raw: {total_created} criados  |  {total_skipped} já existiam  "
            f"({total_files} arquivos)"
        )
