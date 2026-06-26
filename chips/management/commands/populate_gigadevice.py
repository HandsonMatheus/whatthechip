"""
populate_gigadevice.py
======================
Popula o banco com as famílias de chips GigaDevice e seus mapas de
decodificação posicional.

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

Regra de ouro (hierarquia de fontes — nunca quebrar):
    fabricante (datasheet/semiconductor oficial)
      > Octopart (PN confirmado)
        > distribuidor
          > IA externa
            > especulação

Uso:
    python manage.py populate_gigadevice
    python manage.py populate_gigadevice --dry-run    # mostra o que faria sem salvar
    python manage.py populate_gigadevice --overwrite  # atualiza entradas existentes
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação GigaDevice no banco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as operações sem salvar no banco.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Atualiza entradas existentes no banco (DecodeMap + ChipFamily).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        overwrite = options["overwrite"]
        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))
        if overwrite:
            self.stdout.write(self.style.WARNING("⚠  OVERWRITE — entradas existentes serão atualizadas.\n"))

        try:
            with transaction.atomic():
                self._run(dry, overwrite)
                if dry:
                    raise DryRunAbort()
        except DryRunAbort:
            self.stdout.write(self.style.WARNING("\nDry run concluído. Nenhuma alteração salva."))

        if not dry:
            self.stdout.write(self.style.SUCCESS("\n✅  GigaDevice populada com sucesso."))
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                self.stdout.write("   🗑  Cache do engine invalidado.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    # ──────────────────────────────────────────────────────────────────────────

    def _run(self, dry, overwrite=False):
        from chips.models import Brand, ChipFamily, DecodeMap

        # ── Marca ─────────────────────────────────────────────────────────────
        giga, created = Brand.objects.get_or_create(
            name="GigaDevice",
            defaults={
                "code": "GGD",
                "notes": "China · Fundada 2005 (兆易创新 / Zhaoyi Innovation)",
            },
        )
        self._log(created, "Marca", "GigaDevice", dry)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: GD5F_NAND_CAP — Capacidade NAND Flash SPI GigaDevice
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4] (5ª posição, índice 0), comprimento 1 char.
        # Anatomia: G D 5 F [density] [series] [variant] [pkg]
        #           0 1 2 3     4         5+
        #
        # Fontes confirmadas (DigiKey + datasheets GigaDevice):
        #   GD5F1GQ4UBYIG: 1Gbit → 128MB ✓  GD5F2GQ4UBYIG: 2Gbit → 256MB ✓
        #   GD5F4GQ4UBYIG: 4Gbit → 512MB ✓  GD5F1GQ5UEYIG: 1Gbit → 128MB ✓
        #
        # Nota: '8'=8Gbit reservado — verificar datasheet antes de usar em produção.
        #
        gd5f_nand_cap = [
            # char_key  val_primary  val_secondary
            ("1", "128MB", ""),   # 1Gbit — GD5F1GQ4UBYIG, GD5F1GQ5UEYIG ✓
            ("2", "256MB", ""),   # 2Gbit — GD5F2GQ4UBYIG, GD5F2GQ5UEYIG ✓
            ("4", "512MB", ""),   # 4Gbit — GD5F4GQ4UBYIG ✓
            ("8", "1GB",   ""),   # 8Gbit — GD5F8GQ4UBYIG (reservado)
        ]
        self._bulk_map("GD5F_NAND_CAP", gd5f_nand_cap, giga, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # ChipFamilies GigaDevice
        # ══════════════════════════════════════════════════════════════════════
        families = self._families(giga)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != giga.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = giga
            for k, v in fdata.items():
                if getattr(fam, k, None) != v:
                    setattr(fam, k, v)
                    changed = True

            if changed:
                if not dry:
                    fam.save()
                if created:
                    created_count += 1
                    self._log(True, "Família", f"{prefix} — {fam.chip_type}", dry)
                else:
                    updated_count += 1
                    self._log(False, "Família (atualizada)", f"{prefix} — {fam.chip_type}", dry)

        self.stdout.write(
            f"\n  Famílias: {created_count} criadas, {updated_count} atualizadas."
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _families(self, giga):
        """Retorna lista de dicts de famílias GigaDevice para upsert."""
        return [

            # ═══ DDR4 SDRAM — Série GDQ ═══════════════════════════════════════
            #
            # Anatomia do PN (fonte: DS-00808-GDQ2BFAA-Rev1.4 — datasheet oficial):
            #   G D Q [density] [pkg] [org] [voltage] [version] - [temp][speed]
            #   0 1 2     3       4     5       6          7
            #
            #   pn[2]='Q' = DDR4 (D=DRAM; Q=DDR4)
            #   pn[3]=densidade: '2'=4Gbit (512MB) — único confirmado até Jun/2026
            #   pn[4]=pacote:    'B'=FBGA-96
            #   pn[5]=org:       'F'=×16
            #   pn[6]=tensão:    'A'=1.2V
            #   pn[7]=revisão:   'A'=2ª revisão
            #   sufixo: C/W=temp (Commercial 0-95°C / Wide -40-95°C)
            #           E/Q/J=speed (DDR4-2400 / 2666 / 3200)
            #
            # ⚠ ARMADILHA DE LEITURA LASER: pn[4]='B' (pacote FBGA-96) é
            #   facilmente lido como '6' no laser pelo operador.
            #   "GDQ26FAA" = "GDQ2BFAA" mal lido. Confirmar com datasheet físico.
            #
            # JEDEC JESD-79-4 compliant. 256Mb×16 = 4Gbit por die.
            #
            dict(
                prefix="GDQ", chip_type="RAM", subtype="DDR4",
                interface="",
                is_emcp=False, active=True, priority=100,
                pn_length=None,
                decode_cap_pos=None, decode_cap_map="",
                tip=(
                    "DDR4 SDRAM GigaDevice (GDQ), 1.2V, FBGA-96. JEDEC JESD-79-4. "
                    "Anatomia: pn[3]=densidade ('2'=4Gbit=512MB), pn[4]=pacote ('B'=FBGA-96), "
                    "pn[5]=org ('F'=×16), sufixo C/W=temp + E/Q/J=speed (2400/2666/3200). "
                    "⚠ pn[4]='B' facilmente lido como '6' no laser: "
                    "'GDQ26FAA' = 'GDQ2BFAA' mal lido — confirmar PN com datasheet físico. "
                    "Fonte Tier 1: DS-00808-GDQ2BFAA-Rev1.4 (gigadevice.com) ✓. "
                    "Destino: triagem DDR4 — slot 288-pin, 1.2V."
                ),
            ),

            # ═══ NOR Flash SPI 3V — Série GD25Q (Quad SPI padrão) ═══════════
            #
            # A mais comum no mercado de reciclagem: BIOS de placas-mãe,
            # firmware de roteadores, periféricos. Tensão 3.3V, Quad SPI.
            #
            # ⚠ DECODE DE CAPACIDADE INVIÁVEL POSICIONALMENTE:
            #   Código de capacidade tem comprimento variável e mapeamento não intuitivo.
            #   40=4Mbit · 80=8Mbit · 16=16Mbit · 32=32Mbit · 64=64Mbit ·
            #   128=128Mbit · 256=256Mbit · 512M=512Mbit
            #   "40" NÃO é 40Mbit — é 4Mbit. Decode posicional causaria erros graves.
            #   Cobrir SKUs via fix_known_parts com fonte Tier 1 verificada.
            #
            dict(
                prefix="GD25Q", chip_type="NOR Flash", subtype="SPI NOR",
                interface="SPI",
                is_emcp=False, active=True, priority=100,
                pn_length=None,
                decode_cap_pos=None, decode_cap_map="",
                tip=(
                    "NOR Flash SPI 3.3V GigaDevice, série GD25Q (Quad SPI). "
                    "Uso típico: BIOS de placa-mãe, firmware de roteadores e periféricos. "
                    "Rentabilidade: NÃO RENTÁVEL em geral (commodity de baixo valor). "
                    "⚠ CÓDIGO DE CAPACIDADE NÃO LINEAR — não confiar em decode posicional: "
                    "40=4Mbit (0,5MB) · 80=8Mbit (1MB) · 16=16Mbit (2MB) · 32=32Mbit (4MB) "
                    "· 64=64Mbit (8MB) · 128=128Mbit (16MB) · 256=256Mbit (32MB). "
                    "'40' NÃO É 40Mbit — é 4Mbit. Sempre verificar datasheet GigaDevice. "
                    "Capacidade sempre em MB no WTC (Mbit ÷ 8). "
                    "Fonte: gigadevice.com/product/flash/spi-nor-flash ✓."
                ),
            ),

            # ═══ NOR Flash SPI 3V — Série GD25B (Enhanced Quad SPI) ══════════
            #
            # Geração mais nova do GD25Q: 4I/O habilitado por padrão (GD25Q exige
            # habilitação explícita via comando de escrita). Mesmo esquema de
            # capacidade variável — decode posicional inviável da mesma forma.
            #
            dict(
                prefix="GD25B", chip_type="NOR Flash", subtype="SPI NOR",
                interface="SPI",
                is_emcp=False, active=True, priority=100,
                pn_length=None,
                decode_cap_pos=None, decode_cap_map="",
                tip=(
                    "NOR Flash SPI 3.3V GigaDevice, série GD25B (Enhanced Quad SPI — 4I/O por padrão). "
                    "Evolução do GD25Q; mesma gama de capacidades e aplicações. "
                    "Rentabilidade: NÃO RENTÁVEL em geral (commodity de baixo valor). "
                    "⚠ Mesmas armadilhas de capacidade que GD25Q: "
                    "40=4Mbit · 80=8Mbit · 16=16Mbit — '40' NÃO É 40Mbit. "
                    "Verificar datasheet GigaDevice antes de qualquer decode manual. "
                    "Fonte: gigadevice.com/product/flash/spi-nor-flash ✓."
                ),
            ),

            # ═══ NOR Flash SPI 1.8V — Série GD25LQ (Low Voltage Quad SPI) ════
            #
            # Prefixo 'L' = low voltage (1.8V). Usada em dispositivos móveis e
            # IoT. Menos frequente em reciclagem que a série 3.3V.
            #
            dict(
                prefix="GD25LQ", chip_type="NOR Flash", subtype="SPI NOR",
                interface="SPI",
                is_emcp=False, active=True, priority=80,  # prefixo mais longo → mais específico
                pn_length=None,
                decode_cap_pos=None, decode_cap_map="",
                tip=(
                    "NOR Flash SPI 1.8V GigaDevice, série GD25LQ (Low Voltage Quad SPI). "
                    "'L' = low voltage — tensão de operação 1.8V (vs 3.3V do GD25Q). "
                    "Uso: dispositivos móveis, IoT, sistemas embarcados de baixa tensão. "
                    "Rentabilidade: NÃO RENTÁVEL em geral. "
                    "⚠ Mesmas armadilhas de capacidade que GD25Q/GD25B: "
                    "40=4Mbit · 80=8Mbit — nunca assumir valor literal do código de capacidade. "
                    "Fonte: gigadevice.com/product/flash/spi-nor-flash ✓."
                ),
            ),

            # ═══ NOR Flash SPI 1.8V — Série GD25LB (Low Voltage Enhanced) ════
            #
            # Versão 1.8V do GD25B (Enhanced Quad SPI). Geração mais nova que
            # GD25LQ. Mesmas características de capacidade variável.
            #
            dict(
                prefix="GD25LB", chip_type="NOR Flash", subtype="SPI NOR",
                interface="SPI",
                is_emcp=False, active=True, priority=80,  # prefixo mais longo → mais específico
                pn_length=None,
                decode_cap_pos=None, decode_cap_map="",
                tip=(
                    "NOR Flash SPI 1.8V GigaDevice, série GD25LB (Low Voltage Enhanced Quad SPI). "
                    "'L' = low voltage 1.8V. 'B' = Enhanced (4I/O por padrão, como GD25B). "
                    "Geração mais nova que GD25LQ; mesma faixa de capacidades e aplicações. "
                    "Rentabilidade: NÃO RENTÁVEL em geral. "
                    "⚠ Mesmas armadilhas de capacidade: 40=4Mbit · 80=8Mbit. "
                    "Fonte: gigadevice.com/product/flash/spi-nor-flash ✓."
                ),
            ),

            # ═══ NAND Flash SPI — Série GD5F ══════════════════════════════════
            #
            # NAND Flash com interface SPI (não ONFI/Toggle — protocolo NOR-like).
            # Maior capacidade e valor potencial que NOR Flash.
            #
            # Anatomia: G D 5 F [density] [series] [variant] [pkg]
            #           0 1 2 3     4         5+
            #
            #   pn[4]=densidade: '1'=1Gbit=128MB · '2'=2Gbit=256MB ·
            #                    '4'=4Gbit=512MB  · '8'=8Gbit=1GB
            #   pn[5:7]=série:  GQ4 (Gen1) · GQ5 (Gen2) · GM9 (Gen3 — ECC embutido)
            #
            # Fontes confirmadas (DigiKey + datasheets GigaDevice):
            #   GD5F1GQ4UBYIG: 1Gbit=128MB ✓  GD5F2GQ4UBYIG: 2Gbit=256MB ✓
            #   GD5F4GQ4UBYIG: 4Gbit=512MB ✓  GD5F1GQ5UEYIG: 1Gbit=128MB ✓
            #
            dict(
                prefix="GD5F", chip_type="NAND Flash", subtype="SPI NAND",
                interface="SPI",
                is_emcp=False, active=True, priority=100,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="GD5F_NAND_CAP",
                tip=(
                    "NAND Flash SPI GigaDevice, série GD5F. Interface SPI/QSPI (não ONFI/paralela). "
                    "pn[4]=densidade: '1'=1Gbit (128MB) · '2'=2Gbit (256MB) · "
                    "'4'=4Gbit (512MB) · '8'=8Gbit (1GB). "
                    "pn[5:7]=série: GQ4 (Gen1) · GQ5 (Gen2) · GM9 (Gen3 — ECC embutido no chip). "
                    "⚠ NÃO confundir com GD25 (NOR Flash) — tipos de chip totalmente distintos. "
                    "⚠ NÃO é ONFI/Toggle: protocolo SPI-like, não barramento paralelo. "
                    "Rentabilidade: verificar com operador (maior valor potencial que NOR Flash). "
                    "Fontes: DigiKey + datasheets oficiais GigaDevice ✓."
                ),
            ),

        ]

    # ──────────────────────────────────────────────────────────────────────────

    def _bulk_map(self, map_name, entries, brand, dry, overwrite=False):
        from chips.models import DecodeMap
        created = updated = 0
        for char_key, val_primary, val_secondary in entries:
            obj, created_flag = DecodeMap.objects.get_or_create(
                map_name=map_name,
                char_key=char_key,
                brand=brand,
                defaults={"val_primary": val_primary, "val_secondary": val_secondary},
            )
            if created_flag:
                created += 1
                self._log(True, f"DecodeMap {map_name}", f"{char_key} → {val_primary}", dry)
            elif overwrite:
                changed = False
                if obj.val_primary != val_primary:
                    obj.val_primary = val_primary
                    changed = True
                if obj.val_secondary != val_secondary:
                    obj.val_secondary = val_secondary
                    changed = True
                if changed:
                    if not dry:
                        obj.save()
                    updated += 1
                    self._log(False, f"DecodeMap {map_name}", f"{char_key} → {val_primary} (atualizado)", dry)
        msg = f"  Mapa {map_name}: {created} criadas"
        if overwrite:
            msg += f", {updated} atualizadas"
        msg += "."
        self.stdout.write(msg)

    def _log(self, created, kind, name, dry):
        prefix = "[DRY] " if dry else ""
        action = "CRIADO" if created else "atualizado"
        icon = "✚" if created else "↻"
        self.stdout.write(f"  {prefix}{icon} {kind}: {name} ({action})")


class DryRunAbort(Exception):
    """Sinaliza o rollback controlado do dry run."""
    pass
