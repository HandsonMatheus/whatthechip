"""
populate_micron_mcp.py
======================
Popula o banco com as famílias Micron MCP (eMCP e uMCP) e o mapa de
decodificação de capacidade MIC_MCP_CAP.

Padrão idêntico ao populate_samsung.py — idempotente, aceita --dry-run e
--overwrite.

Cobertura:
  MT29VZZZ*  →  eMCP/uMCP LPDDR4 (eMMC 5.1 ou UFS 2.2)
  MT30AZZZ*  →  uMCP LPDDR5 (UFS 3.1)

Estrutura do Part Number Micron MCP:
  MT29VZZZ [AD8] GQFSL-046 W.9R8
            ^^^
            Posições 8-10 (3 chars): chave de decodificação
              pos 8  (1 char) = código RAM:  7=3GB · A=4GB · B=6GB · C=8GB · D=12GB · E=16GB
              pos 9-10 (2 chars) = código NAND: D8=64GB · D9=128GB · DA=256GB · DB=512GB

  Verificação com MT29VZZZAD8GQFSL (COMPONENT DENSITY="544Gb"):
    RAM : A = 4GB  → 32 Gb
    NAND: D8 = 64GB → 512 Gb
    Total: 32 + 512 = 544 Gb ✓

Uso:
    python manage.py populate_micron_mcp
    python manage.py populate_micron_mcp --dry-run
    python manage.py populate_micron_mcp --overwrite
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class DryRunAbort(Exception):
    pass


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação Micron MCP no banco."

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
        dry      = options["dry_run"]
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
            self.stdout.write(self.style.SUCCESS("\n✅  Micron MCP populada com sucesso."))
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
        micron, created = Brand.objects.get_or_create(
            name="Micron",
            defaults={"code": "MIC", "notes": "Micron Technology · Boise, Idaho · Fundada 1978"},
        )
        self._log(created, "Marca", "Micron", dry)

        # ── DecodeMap: capacidade MCP Micron (pos 8, 3 chars) ─────────────────
        #
        # Chave de 3 chars em pn[8:11]:
        #   pos 8  (1 char) = código RAM  → val_secondary
        #   pos 9-10 (2 chars) = código NAND → val_primary
        #
        # val_primary  = capacidade NAND (GB) — convenção do engine para eMCP
        # val_secondary = capacidade RAM (GB)
        #
        # Verificação total por COMPONENT DENSITY do CSV Micron:
        #   NAND (Gb) = NAND (GB) × 8    |    RAM (Gb) = RAM (GB) × 8
        #   densidade_total = NAND_Gb + RAM_Gb
        #
        # Tabela de chaves confirmadas pelos CSVs da Micron (2026-05):
        #   7D8 → 536Gb  = 512+24  ✓  (MT29VZZZ7D8x / MT29VZZZ7D81)
        #   AD8 → 544Gb  = 512+32  ✓  (MT29VZZZAD8x — chip do bug "68GB")
        #   BD8 → 560Gb  = 512+48  ✓  (MT29VZZZBD81SLSL)
        #   AD9 → 1056Gb = 1024+32 ✓  (MT29VZZZAD9GUFSM)
        #   BD9 → 1072Gb = 1024+48 ✓  (MT29VZZZBD9x / MT29VZZZBD91 / MT30AZZZBD9x)
        #   CD9 → 1088Gb = 1024+64 ✓  (MT29VZZZCD9x / MT30AZZZCD9x)
        #   BDA → 2096Gb = 2048+48 ✓  (MT29VZZZBDA1)
        #   CDA → 2112Gb = 2048+64 ✓  (MT30AZZZCDA0)
        #   DDA → 2144Gb = 2048+96 ✓  (MT29VZZZDDA2 / MT30AZZZDDA0)
        #   EDA → 2176Gb = 2048+128 ✓ (MT30AZZZEDA0)
        #   CDB → 4160Gb = 4096+64 ✓  (MT30AZZZCDB0)
        #   DDB → 4192Gb = 4096+96 ✓  (MT30AZZZDDB0)
        #   EDB → 4224Gb = 4096+128 ✓ (MT30AZZZEDB0)
        mcp_cap = [
            # (3-char key, NAND capacity, RAM capacity)
            # val_primary=NAND, val_secondary=RAM — convenção engine
            #
            # ── MT29VZZZ / MT30AZZZ Gen B (LPDDR4/LPDDR5) — estrutura padrão ──
            # Posição 8 = código RAM (letra), posições 9-10 = código NAND (2 chars).
            ("7D8", "64GB",  "3GB"),    # 7→3GB RAM (24Gb) + D8→64GB NAND (512Gb) = 536Gb ✓
            ("AD8", "64GB",  "4GB"),    # A→4GB RAM (32Gb) + D8→64GB NAND (512Gb) = 544Gb ✓
            ("BD8", "64GB",  "6GB"),    # B→6GB RAM (48Gb) + D8→64GB NAND (512Gb) = 560Gb ✓
            ("AD9", "128GB", "4GB"),    # A→4GB RAM (32Gb) + D9→128GB NAND (1024Gb) = 1056Gb ✓
            ("BD9", "128GB", "6GB"),    # B→6GB RAM (48Gb) + D9→128GB NAND (1024Gb) = 1072Gb ✓
            ("CD9", "128GB", "8GB"),    # C→8GB RAM (64Gb) + D9→128GB NAND (1024Gb) = 1088Gb ✓
            ("BDA", "256GB", "6GB"),    # B→6GB RAM (48Gb) + DA→256GB NAND (2048Gb) = 2096Gb ✓
            ("CDA", "256GB", "8GB"),    # C→8GB RAM (64Gb) + DA→256GB NAND (2048Gb) = 2112Gb ✓
            ("DDA", "256GB", "12GB"),   # D→12GB RAM (96Gb) + DA→256GB NAND (2048Gb) = 2144Gb ✓
            ("EDA", "256GB", "16GB"),   # E→16GB RAM (128Gb) + DA→256GB NAND (2048Gb) = 2176Gb ✓
            ("CDB", "512GB", "8GB"),    # C→8GB RAM (64Gb) + DB→512GB NAND (4096Gb) = 4160Gb ✓
            ("DDB", "512GB", "12GB"),   # D→12GB RAM (96Gb) + DB→512GB NAND (4096Gb) = 4192Gb ✓
            ("EDB", "512GB", "16GB"),   # E→16GB RAM (128Gb) + DB→512GB NAND (4096Gb) = 4224Gb ✓
            #
            # ── MT29TZZZ Gen A (LPDDR2/LPDDR3) — estrutura legada ──────────────
            # Convenção confirmada por 5 pontos de dados cruzados (Micron FBGA API, 2026-05):
            #   pn[8]  = código RAM (dígito): '4'→512MB · '5'→2GB · '8'→1GB
            #   pn[9]  = 'D' (constante na maioria dos chips Gen A)
            #   pn[10] = código NAND (dígito): '4'→4GB(32Gb) · '5'→8GB(64Gb) · '6'→16GB(128Gb)
            #
            # Verificações (Micron FBGA API total Gbit):
            #   4D4 → 36Gb  = 32Gb NAND + 4Gb RAM   ✓  "EMCP 36G VFBGA"            (1 chip)
            #   8D4 → 40Gb  = 32Gb NAND + 8Gb RAM   ✓  "MLC EMMC/LPDDR2 40G VFBGA"
            #   8D5 → 72Gb  = 64Gb NAND + 8Gb RAM   ✓  "MLC EMMC/LPDDR2 72G VFBGA" ← JWA60/JY941
            #   5D6 → 144Gb = 128Gb NAND + 16Gb RAM ✓  "EMCP 144G VFBGA"            (11 chips)
            #   8D6 → 136Gb = 128Gb NAND + 8Gb RAM  ✓  "MLC EMMC/LPDDR3 136G VFBGA"
            #
            # ⚠ Ambiguidade tipo RAM: 8D5→LPDDR2 e 8D6→LPDDR3 (API explícito).
            #   pn[8]='8' = 1GB para ambos, mas o tipo depende de pn[10], não apenas pn[8].
            #   MIC_TZZZ_GEN ('8'→LPDDR2) fica impreciso para 8D6 — refinamento futuro.
            ("4D4", "4GB",   "512MB"),  # 4→512MB RAM (4Gb)  + D4→4GB NAND (32Gb)   = 36Gb  ✓
            ("8D4", "4GB",   "1GB"),    # 8→1GB RAM (8Gb)    + D4→4GB NAND (32Gb)   = 40Gb  ✓ LPDDR2
            ("8D5", "8GB",   "1GB"),    # 8→1GB RAM (8Gb)    + D5→8GB NAND (64Gb)   = 72Gb  ✓ LPDDR2
            ("5D6", "16GB",  "2GB"),    # 5→2GB RAM (16Gb)   + D6→16GB NAND (128Gb) = 144Gb ✓ tipo?
            ("8D6", "16GB",  "1GB"),    # 8→1GB RAM (8Gb)    + D6→16GB NAND (128Gb) = 136Gb ✓ LPDDR3
        ]
        self._bulk_map("MIC_MCP_CAP", mcp_cap, micron, dry, overwrite)

        # ── DecodeMap: geração RAM para MT29TZZZ (Gen A vs Gen B) ─────────────
        #
        # Problema: MT29TZZZ cobre duas sub-gerações com diferentes tipos de RAM:
        #   Gen A (legado pré-2015): pn[8] = dígito → LPDDR2
        #     Ex: MT29TZZZ[8]D5BKFAH → '8' = código NAND (64Gb), RAM = LPDDR2
        #   Gen B (moderno 2015+):   pn[8] = letra  → LPDDR3
        #     Ex: MT29TZZZ[A]D8DKKFB → 'A' = código RAM (4GB), NAND = 64GB
        #
        # O engine usa decode_gen_pos=8, decode_gen_len=1 para determinar
        # o tipo RAM da família via este mapa.
        #
        # ⚠ POLÍTICA: SOMENTE entradas confirmadas via API oficial Micron.
        #   Não adicionar entradas hipotéticas ou inferidas de outras famílias (ex: MT29VZZZ).
        #   Para enumerar a família completa e descobrir novas chaves verificadas, usar:
        #     python manage.py collect_micron_catalog --strategy seed
        #     python manage.py analyze_micron_mcp_keys --prefix MT29TZZZ
        #
        # Confirmados até 2026-05-28 (part-name verificado via API Micron):
        #   '8' (Gen A): FBGA JWA60/JY941
        #     part-name "MLC EMMC/LPDDR2 72G VFBGA"
        #     72 Gbit total → pn[8:11]="8D5" → NAND=64Gb(8GB) + DRAM=8Gb(1GB) ✓
        tzzz_gen = [
            # (1-char key, RAM type, unused_secondary)
            ("8", "LPDDR2", ""),   # Gen A confirmado (pn[8]='8') — JWA60/JY941, API Micron ✓
            # ADICIONAR AQUI somente após verificação via analyze_micron_mcp_keys
        ]
        self._bulk_map("MIC_TZZZ_GEN", tzzz_gen, micron, dry, overwrite)

        # ── ChipFamilies ──────────────────────────────────────────────────────
        families = self._families(micron)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != micron.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = micron
            for k, v in fdata.items():
                if overwrite or getattr(fam, k, None) != v:
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

    def _families(self, micron):
        return [
            # ═══ MT29VZZZ — eMCP / uMCP LPDDR4 ═══════════════════════════════
            #
            # Cobertura: todos os Micron MCP baseados em LPDDR4, tanto
            # eMMC-based (MT29VZZZxxxGx...) quanto UFS-based (MT29VZZZxxxFx...).
            #
            # Decode: 3 chars em pn[8:11] → mapa MIC_MCP_CAP
            #   val_primary  = cap NAND    (ex: "64GB")
            #   val_secondary = cap RAM    (ex: "4GB")
            #
            # Tipo RAM: pn[2]='2' (dígito) → engine usa Path 3 com isdigit() →
            #           extrai LPDDR4 direto de fam.subtype. Não precisa de
            #           decode_gen_map — o engine já trata esse caso.
            #
            # Interface: "eMMC 5.1" é o padrão da família, mas a família cobre
            # AMBOS os tipos:
            #   - emmc-based-mcp (pn[11]='G'): eMCP / eMMC 5.1
            #   - ufs-based-mcp  (pn[11]='F'): uMCP / UFS 2.2
            #
            # A distinção eMMC vs UFS é feita pelo engine via BUG-3 fix:
            # source_url da API FBGA da Micron (ufs-based-mcp vs emmc-based-mcp)
            # sobrepõe o interface da família para cada chip individual.
            # Ver também: fix_micron_mcp_classification.py para corrigir chip_type no DB.
            dict(
                prefix="MT29VZZZ",
                chip_type="eMCP",
                subtype="LPDDR4",
                interface="eMMC 5.1",
                is_emcp=True,
                active=True,
                priority=50,
                decode_gen_pos=None,
                decode_gen_map="",
                decode_cap_pos=8,
                decode_cap_len=3,
                decode_cap_map="MIC_MCP_CAP",
                tip=(
                    "💡 Micron eMCP/uMCP LPDDR4. "
                    "Prefixo fixo MT29VZZZ (8 chars). "
                    "Capacidade: pn[8:11] via MIC_MCP_CAP — "
                    "pos 8=RAM (7=3GB · A=4GB · B=6GB · C=8GB · D=12GB · E=16GB), "
                    "pos 9-10=NAND (D8=64GB · D9=128GB · DA=256GB · DB=512GB). "
                    "Ex: AD8 → eMMC 5.1 64GB + LPDDR4 4GB. "
                    "Destino: bancada eMCP — verificar se UFS ou eMMC antes de rotear."
                ),
                reasoning='["MT → Micron Technology", "29 → MCP série (NAND+RAM combinados)", '
                          '"VZZZ → bloco fixo identificador da família MCP moderna", '
                          '"pn[8] → código de densidade RAM (A=4GB, B=6GB, C=8GB…)", '
                          '"pn[9:11] → código de capacidade NAND (D8=64GB, D9=128GB, DA=256GB, DB=512GB)", '
                          '"Solução compacta para smartphones mid-range"]',
            ),

            # ═══ MT29TZZZ — eMCP LPDDR3 (eMMC 4.x / 5.0, geração anterior) ════
            #
            # Família mais antiga que MT29VZZZ. Comum em dispositivos 2014–2018.
            # Duas sub-gerações coexistem:
            #
            # Gen A (legacy, pré-2016): pn[8] = dígito (código NAND antigo)
            #   Ex: MT29TZZZ8D5BKFAH → '8'=64Gb NAND (8GB) / 'D5'=8Gb DRAM (1GB)
            #   → MIC_MCP_CAP contém a chave "8D5" (confirmado: 72Gb total ✓)
            #   → MIC_TZZZ_GEN: pn[8]='8' → LPDDR2 (decode correto para Gen A)
            #
            # Gen B (moderna, 2015+): pn[8:11] = chave MIC_MCP_CAP (mesmo esquema MT29VZZZ)
            #   Ex: MT29TZZZAD8DKKFB → 'AD8' → 64GB NAND + 4GB LPDDR3 = 544Gb ✓
            #   → MIC_TZZZ_GEN: pn[8]='A' → LPDDR3 (decode correto para Gen B)
            #
            # Tipo RAM: decode_gen_map="MIC_TZZZ_GEN" (pos 8, 1 char) distingue:
            #   pn[8] = dígito ('4','8') → LPDDR2 (Gen A)
            #   pn[8] = letra ('7','A','B','C','D','E') → LPDDR3 (Gen B)
            # Subtype "LPDDR3" é o fallback quando o código não estiver no mapa.
            dict(
                prefix="MT29TZZZ",
                chip_type="eMCP",
                subtype="LPDDR3",
                interface="eMMC 5.0",
                is_emcp=True,
                active=True,
                priority=50,
                decode_gen_pos=8,
                decode_gen_len=1,
                decode_gen_map="MIC_TZZZ_GEN",
                decode_cap_pos=8,
                decode_cap_len=3,
                decode_cap_map="MIC_MCP_CAP",
                tip=(
                    "💡 Micron eMCP (geração anterior ao MT29VZZZ). "
                    "Prefixo fixo MT29TZZZ (8 chars). "
                    "RAM: pn[8] via MIC_TZZZ_GEN — dígito=LPDDR2 (Gen A), letra=LPDDR3 (Gen B). "
                    "Capacidade: pn[8:11] via MIC_MCP_CAP. "
                    "Ex Gen A: '8D5' → eMMC 5.0 8GB + LPDDR2 1GB. "
                    "Ex Gen B: 'AD8' → eMMC 5.0 64GB + LPDDR3 4GB. "
                    "Verificar interface real antes de rotear — pode ser eMMC 4.5 ou 5.0."
                ),
                reasoning='["MT → Micron Technology", "29 → MCP série (NAND+RAM combinados)", '
                          '"TZZZ → bloco fixo família MCP Gen1/2 (anterior ao VZZZ)", '
                          '"Gen B: pn[8]=RAM code (letra), pn[9:11]=NAND code — igual ao MT29VZZZ", '
                          '"Gen A: pn[8]=NAND code (dígito), pn[9:11]=DRAM code — chave ex: 8D5=8GB NAND+1GB LPDDR2", '
                          '"RAM: MIC_TZZZ_GEN distingue LPDDR2 (Gen A) de LPDDR3 (Gen B)", '
                          '"Dispositivos típicos: 2014-2018 (Qualcomm MSM8909, MT6737)"]',
            ),

            # ═══ MT30AZZZ — uMCP LPDDR5 (UFS 3.1) ════════════════════════════
            #
            # Família de geração mais recente: UFS 3.1 + LPDDR5.
            # Mesmo mapa MIC_MCP_CAP — a convenção de codificação de capacidade
            # é idêntica ao MT29VZZZ, apenas com RAM de geração superior.
            #
            # pn[2]='3' (dígito) → mesmo path que MT29VZZZ: engine usa subtype
            # para extrair "LPDDR5".
            dict(
                prefix="MT30AZZZ",
                chip_type="uMCP",
                subtype="LPDDR5",
                interface="UFS 3.1",
                is_emcp=True,
                active=True,
                priority=50,
                decode_gen_pos=None,
                decode_gen_map="",
                decode_cap_pos=8,
                decode_cap_len=3,
                decode_cap_map="MIC_MCP_CAP",
                tip=(
                    "💡 Micron uMCP LPDDR5 + UFS 3.1 (geração mais recente). "
                    "Prefixo fixo MT30AZZZ (8 chars). "
                    "Capacidade: pn[8:11] via MIC_MCP_CAP — "
                    "pos 8=RAM (B=6GB · C=8GB · D=12GB · E=16GB), "
                    "pos 9-10=NAND (D9=128GB · DA=256GB · DB=512GB). "
                    "Ex: CDA → UFS 3.1 256GB + LPDDR5 8GB. "
                    "Destino: bancada uMCP premium — chipset flagship."
                ),
                reasoning='["MT → Micron Technology", "30 → MCP UFS série (geração 3.x)", '
                          '"AZZZ → bloco fixo identificador da família uMCP LPDDR5", '
                          '"pn[8] → código de densidade RAM (B=6GB, C=8GB, D=12GB, E=16GB)", '
                          '"pn[9:11] → código de capacidade NAND (D9=128GB, DA=256GB, DB=512GB)", '
                          '"Interface UFS 3.1 (~2400 MB/s sequencial)"]',
            ),
        ]

    # ──────────────────────────────────────────────────────────────────────────

    def _bulk_map(self, map_name: str, entries: list, brand, dry: bool, overwrite: bool):
        from chips.models import DecodeMap

        created_c = updated_c = 0
        for char_key, val_primary, val_secondary in entries:
            obj = DecodeMap.objects.filter(map_name=map_name, char_key=char_key).first()
            created = obj is None
            if created:
                obj = DecodeMap(map_name=map_name, char_key=char_key)
            changed = created
            for field, val in [("val_primary", val_primary), ("val_secondary", val_secondary), ("brand", brand)]:
                if overwrite or getattr(obj, field, None) != val:
                    if getattr(obj, field, None) != val:
                        setattr(obj, field, val)
                        changed = True
            if changed:
                if not dry:
                    obj.save()
                if created:
                    created_c += 1
                else:
                    updated_c += 1

        self.stdout.write(
            f"  DecodeMap {map_name!r}: {created_c} criadas, {updated_c} atualizadas."
        )

    def _log(self, created: bool, kind: str, name: str, dry: bool):
        prefix = "[DRY] " if dry else ""
        verb   = "criado" if created else "encontrado"
        self.stdout.write(f"  {prefix}{kind} {verb}: {name}")
