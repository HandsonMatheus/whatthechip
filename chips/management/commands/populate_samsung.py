"""
populate_samsung.py
====================
Popula o banco com todas as famílias de chips Samsung extraídas
da página de documentação fab-samsung.

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

Uso:
    python manage.py populate_samsung
    python manage.py populate_samsung --dry-run   # mostra o que faria sem salvar
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação Samsung no banco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as operações sem salvar no banco.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        try:
            with transaction.atomic():
                self._run(dry)
                if dry:
                    raise DryRunAbort()
        except DryRunAbort:
            self.stdout.write(self.style.WARNING("\nDry run concluído. Nenhuma alteração salva."))

        if not dry:
            self.stdout.write(self.style.SUCCESS("\n✅  Samsung populada com sucesso."))

    # ──────────────────────────────────────────────────────────────────────────

    def _run(self, dry):
        from chips.models import Brand, ChipFamily, DecodeMap

        # ── Marca ─────────────────────────────────────────────────────────────
        samsung, created = Brand.objects.get_or_create(
            name="Samsung",
            defaults={"code": "SAM", "notes": "Coreia do Sul · Fundada 1969"},
        )
        self._log(created, "Marca", "Samsung", dry)

        # ── DecodeMap: capacidade Flash (eMMC + UFS) ──────────────────────────
        # Posição 3 do PN (1 char) → capacidade de armazenamento
        flash_cap = [
            ("4",  "4GB",  ""),
            ("8",  "8GB",  ""),
            ("A",  "16GB", ""),
            ("B",  "32GB", ""),
            ("C",  "64GB", ""),
            ("D",  "128GB",""),
            ("E",  "256GB",""),
            ("F",  "512GB",""),
            ("G",  "1TB",  ""),
        ]
        self._bulk_map("SAM_FLASH_CAP", flash_cap, samsung, dry)

        # ── DecodeMap: capacidade eMCP (2 chars, pos 3-4) ─────────────────────
        # val_primary = cap NAND (eMMC)  |  val_secondary = cap RAM (LPDDR)
        emcp_cap = [
            ("5X", "8GB",   "1GB"),
            ("BT", "16GB",  "2GB"),
            ("GD", "32GB",  "3GB"),
            ("X1", "64GB",  "4GB"),
            ("H9", "64GB",  "4GB"),   # alias do X1
            ("J2", "128GB", "6GB"),
            ("M4", "128GB", "8GB"),   # variante alta densidade
            ("P5", "256GB", "8GB"),   # variante premium
        ]
        self._bulk_map("SAM_EMCP_CAP", emcp_cap, samsung, dry)

        # ── DecodeMap: geração RAM eMCP (pos 2, 1 char) ───────────────────────
        emcp_gen = [
            ("K", "LPDDR2",     ""),
            ("F", "LPDDR3",     ""),
            ("N", "LPDDR3",     ""),
            ("Q", "LPDDR3",     ""),
            ("R", "LPDDR4/4X",  ""),
            ("S", "LPDDR4X",    ""),
            # uMCP
            ("D", "LPDDR4X",    ""),
            ("G", "LPDDR4X",    ""),
            ("L", "LPDDR5",     ""),
            ("V", "LPDDR5/5X",  ""),
        ]
        self._bulk_map("SAM_EMCP_GEN", emcp_gen, samsung, dry)

        # ── DecodeMap: densidade DRAM PC (pos 3-4, 2 chars) ───────────────────
        dram_pc = [
            ("28",  "256Mb", "32MB por die"),
            ("51",  "512Mb", "64MB por die"),
            ("1G",  "1Gb",   "128MB por die"),
            ("2G",  "2Gb",   "256MB por die"),
            ("4G",  "4Gb",   "512MB por die"),
            ("8G",  "8Gb",   "1GB por die"),
            ("AG",  "16Gb",  "2GB por die"),
            ("AH",  "16Gb",  "2GB por die"),   # DDR5
        ]
        self._bulk_map("DRAM_PC", dram_pc, None, dry)

        # ── DecodeMap: densidade DRAM Mobile (pos 3, 1 char) ─────────────────
        dram_mob = [
            ("P",  "512Mb", "64MB por die"),
            ("1",  "1Gb",   "128MB por die"),
            ("2",  "2Gb",   "256MB por die"),
            ("4",  "4Gb",   "512MB por die"),
            ("6",  "6Gb",   "768MB por die"),
            ("8",  "8Gb",   "1GB por die"),
            ("G",  "16Gb",  "2GB por die"),
            ("H",  "32Gb",  "4GB por die"),
        ]
        self._bulk_map("DRAM_MOBILE", dram_mob, None, dry)

        # ── ChipFamilies ──────────────────────────────────────────────────────
        families = self._families(samsung)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam, created = ChipFamily.objects.get_or_create(
                brand=samsung,
                prefix=prefix,
                defaults=fdata,
            )
            if created:
                created_count += 1
                self._log(True, "Família", f"{prefix} — {fam.chip_type}", dry)
            else:
                # Atualiza campos que possam ter mudado
                changed = False
                for k, v in fdata.items():
                    if getattr(fam, k) != v:
                        setattr(fam, k, v)
                        changed = True
                if changed:
                    fam.save()
                    updated_count += 1
                    self._log(False, "Família (atualizada)", f"{prefix} — {fam.chip_type}", dry)

        self.stdout.write(
            f"\n  Famílias: {created_count} criadas, {updated_count} atualizadas."
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _families(self, samsung):
        """Retorna a lista de dicts de famílias para get_or_create."""
        return [

            # ═══ SDRAM (OBSOLETO) ════════════════════════════════════════════
            dict(
                prefix="K4S", chip_type="SDRAM", subtype="PC-66/100/133",
                interface="", is_emcp=False, active=True, priority=100,
                tip="Obsoleto (1998–2004). Destino: fluxo de resíduo.",
            ),

            # ═══ DDR DESKTOP / SERVER ════════════════════════════════════════
            dict(
                prefix="K4H", chip_type="DDR", subtype="DDR1",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip="DDR1 (2001–2007). Destino: resíduo (capacidade obsoleta).",
            ),
            dict(
                prefix="K4T", chip_type="DDR", subtype="DDR2",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip="DDR2 (2004–2010). Destino: bancada reacondicional.",
            ),
            dict(
                prefix="K4B", chip_type="DDR", subtype="DDR3/DDR3L",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip="DDR3/DDR3L (2007–2016). Sufixo -BCx=DDR3 1.5V, -BYx=DDR3L 1.35V.",
            ),
            dict(
                prefix="K4A", chip_type="DDR4", subtype="DDR4",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip="DDR4 (2014–presente). Destino: bancada reacondicional.",
            ),
            dict(
                prefix="K4R", chip_type="DDR5", subtype="DDR5",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip="DDR5 1.1V (2021–presente). NÃO misturar com DDR4 na bancada.",
            ),

            # ═══ LPDDR MOBILE ════════════════════════════════════════════════
            dict(
                prefix="K4M", chip_type="LPDDR", subtype="LPDDR1 (legacy)",
                interface="", is_emcp=False, active=True, priority=100,
                tip="LPDDR1 / Mobile DDR (obsoleto). Destino: resíduo.",
            ),
            dict(
                prefix="K4X", chip_type="LPDDR", subtype="Mobile DDR (legacy)",
                interface="", is_emcp=False, active=True, priority=100,
                tip="Mobile DDR / LPDDR1 (obsoleto). Destino: resíduo.",
            ),
            dict(
                prefix="K4P", chip_type="LPDDR2", subtype="LPDDR2 Mobile",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip="LPDDR2 Mobile. Destino: bancada reacondicional mobile.",
            ),
            dict(
                prefix="K3Q", chip_type="LPDDR3", subtype="LPDDR3 Mobile",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip="LPDDR3 Mobile. Destino: bancada reacondicional mobile.",
            ),
            dict(
                prefix="K4F", chip_type="LPDDR4", subtype="LPDDR4 Mobile",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip="LPDDR4 (2015–presente). Destino: bancada reacondicional mobile.",
            ),
            dict(
                prefix="K4U", chip_type="LPDDR4X", subtype="LPDDR4X Mobile",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip="⚠ K4U ATENÇÃO: se extraído de placa de vídeo = GDDR4 (resíduo). "
                    "Se de smartphone/tablet = LPDDR4X (reacondicional mobile).",
            ),
            dict(
                prefix="K3U", chip_type="LPDDR4X", subtype="LPDDR4X Multi-Channel",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip="LPDDR4X base para MCP/uMCP. Destino: bancada reacondicional mobile.",
            ),
            dict(
                prefix="K3KL", chip_type="LPDDR5", subtype="LPDDR5",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=40,  # prefixo mais longo = prioridade maior
                tip="LPDDR5 (2020–presente). Destino: bancada reacondicional DRAM. "
                    "NÃO enviar para resíduo.",
            ),
            dict(
                prefix="K3LK", chip_type="LPDDR5X", subtype="LPDDR5X",
                interface="", decode_density_type="mobile",
                is_emcp=False, active=True, priority=40,
                tip="LPDDR5X otimizado (IA/5G). Topo do fluxo reacondicional. "
                    "Tolerância zero para erros de leitura.",
            ),

            # ═══ FLASH: eMMC ═════════════════════════════════════════════════
            dict(
                prefix="KLM", chip_type="eMMC", subtype="eMMC Samsung",
                interface="eMMC 5.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=50,
                tip="eMMC Samsung (sem RAM). "
                    "Capacidade = 4ª letra: A=16GB, B=32GB, C=64GB, D=128GB, E=256GB. "
                    "BGA 153 ou 169.",
            ),

            # ═══ FLASH: UFS ══════════════════════════════════════════════════
            dict(
                prefix="KLU", chip_type="UFS", subtype="UFS Samsung",
                interface="UFS 3.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=50,
                tip="UFS Samsung (sem RAM). "
                    "Capacidade = 4ª letra: B=32GB, C=64GB, D=128GB, E=256GB, F=512GB, G=1TB. "
                    "Fisicamente idêntico ao eMMC BGA 153 — ler código a laser.",
            ),

            # ═══ eMCP: eMMC + LPDDR ══════════════════════════════════════════
            # Cada prefixo de 3 letras = geração diferente de RAM
            dict(
                prefix="KMK", chip_type="eMCP", subtype="LPDDR2 + eMMC",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR2 (legado). Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMF", chip_type="eMCP", subtype="LPDDR3 + eMMC",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR3. Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMN", chip_type="eMCP", subtype="LPDDR3 + eMMC",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR3. Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMQ", chip_type="eMCP", subtype="LPDDR3 + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR3 + eMMC 5.1. Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMR", chip_type="eMCP", subtype="LPDDR4/4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=12,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR4/4X + eMMC 5.1. Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMS", chip_type="eMCP", subtype="LPDDR4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR4X + eMMC 5.1. Destino: reacondicional eMCP.",
            ),

            # ═══ uMCP: UFS + LPDDR ═══════════════════════════════════════════
            dict(
                prefix="KMD", chip_type="uMCP", subtype="UFS 2.1 + LPDDR4/4X",
                interface="UFS 2.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                tip="uMCP Samsung UFS 2.1 + LPDDR4/4X. "
                    "JAMAIS misturar com eMCP — sockets incompatíveis.",
            ),
            dict(
                prefix="KMG", chip_type="uMCP", subtype="UFS 3.1 + LPDDR4X",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                tip="uMCP Samsung UFS 3.1 + LPDDR4X. Destino: reacondicional uMCP.",
            ),
            dict(
                prefix="KML", chip_type="uMCP", subtype="UFS 3.1 + LPDDR5",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                tip="uMCP Samsung UFS 3.1 + LPDDR5. Destino: reacondicional uMCP.",
            ),
            dict(
                prefix="KMV", chip_type="uMCP", subtype="UFS 4.0 + LPDDR5/5X",
                interface="UFS 4.0", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                tip="uMCP Samsung UFS 4.0 + LPDDR5/5X. Flagships. Destino: reacondicional uMCP.",
            ),

            # ═══ GDDR (MEMÓRIA GRÁFICA) ═══════════════════════════════════════
            dict(
                prefix="K4N", chip_type="GDDR2", subtype="GDDR2 (legacy)",
                interface="", is_emcp=False, active=True, priority=100,
                tip="GDDR2 (obsoleto). Destino: resíduo.",
            ),
            dict(
                prefix="K4J", chip_type="GDDR3", subtype="GDDR3",
                interface="", is_emcp=False, active=True, priority=100,
                tip="GDDR3. Destino: bancada reacondicional GPU.",
            ),
            dict(
                prefix="K4G", chip_type="GDDR5", subtype="GDDR5/GDDR5X",
                interface="", is_emcp=False, active=True, priority=100,
                tip="GDDR5/GDDR5X. Alto volume. Destino: bancada reacondicional GPU.",
            ),
            dict(
                prefix="K4Z", chip_type="GDDR6", subtype="GDDR6/GDDR6X",
                interface="", is_emcp=False, active=True, priority=100,
                tip="GDDR6/GDDR6X (2018–presente). Destino: bancada reacondicional GPU.",
            ),

            # ═══ FLASH BASE: NAND / NOR ═══════════════════════════════════════
            dict(
                prefix="K5", chip_type="NOR Flash", subtype="Samsung NOR Flash",
                interface="", is_emcp=False, active=True, priority=100,
                tip="NOR Flash Samsung. Verificar demanda semanal antes de direcionar.",
            ),
            dict(
                prefix="K8", chip_type="NOR Flash", subtype="Samsung Mask ROM",
                interface="", is_emcp=False, active=True, priority=100,
                tip="Mask ROM / NOR Flash Samsung. Verificar demanda.",
            ),

            # ═══ EMPACOTAMENTOS ESPECIAIS ══════════════════════════════════════
            dict(
                prefix="KAT", chip_type="ePoP", subtype="eMMC + LPDDR Empilhado",
                interface="",
                is_emcp=True, active=True, priority=50,
                tip="ePoP (Package-on-Package): montado sobre o SoC. "
                    "Sockets especiais na bancada. Destino: reacondicional (NÃO enviar para resíduo).",
            ),
            dict(
                prefix="KUS", chip_type="BGA SSD", subtype="NVMe PCIe BGA",
                interface="PCIe Gen3",
                is_emcp=False, active=True, priority=50,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="KUS_CAP",
                tip="BGA NVMe SSD completo. JAMAIS misturar com eMMC ou UFS. "
                    "Destino: reacondicional BGA SSD (Premium).",
            ),

            # ═══ PROCESSADORES / SENSORES ══════════════════════════════════════
            dict(
                prefix="S5E", chip_type="SoC", subtype="Exynos CPU",
                interface="", is_emcp=False, active=True, priority=100,
                tip="Exynos SoC Samsung. Destino: bancada reacondicional SoC.",
            ),
            dict(
                prefix="S5K", chip_type="Sensor", subtype="ISOCELL Camera",
                interface="", is_emcp=False, active=True, priority=100,
                tip="ISOCELL — módulo de câmera Samsung. Destino: bancada reacondicional Sensores.",
            ),
            dict(
                prefix="S2M", chip_type="PMIC", subtype="Samsung PMIC",
                interface="", is_emcp=False, active=True, priority=100,
                tip="PMIC Samsung (gerenciamento de energia). Bancada reacondicional PMIC.",
            ),
            dict(
                prefix="S2A", chip_type="PMIC", subtype="Samsung PMIC",
                interface="", is_emcp=False, active=True, priority=100,
                tip="PMIC Samsung. Bancada reacondicional PMIC.",
            ),
            dict(
                prefix="S2D", chip_type="PMIC", subtype="Samsung PMIC",
                interface="", is_emcp=False, active=True, priority=100,
                tip="PMIC Samsung. Bancada reacondicional PMIC.",
            ),
        ]

    # ──────────────────────────────────────────────────────────────────────────

    def _bulk_map(self, map_name, entries, brand, dry):
        from chips.models import DecodeMap
        created = 0
        for char_key, val_primary, val_secondary in entries:
            obj, c = DecodeMap.objects.get_or_create(
                map_name=map_name,
                char_key=char_key,
                brand=brand,
                defaults={"val_primary": val_primary, "val_secondary": val_secondary},
            )
            if c:
                created += 1
                self._log(True, f"DecodeMap {map_name}", f"{char_key} → {val_primary}", dry)
        self.stdout.write(f"  Mapa {map_name}: {created} entradas criadas.")

    def _log(self, created, kind, name, dry):
        prefix = "[DRY] " if dry else ""
        action = "CRIADO" if created else "atualizado"
        icon = "✚" if created else "↻"
        self.stdout.write(f"  {prefix}{icon} {kind}: {name} ({action})")


class DryRunAbort(Exception):
    """Sinaliza o rollback controlado do dry run."""
    pass
