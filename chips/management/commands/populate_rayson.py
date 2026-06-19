"""
populate_rayson.py
==================
Popula o banco com as famílias de chips Rayson (晶存科技) e seus prefixos reais.

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

ATENÇÃO — DECISÃO OPERACIONAL CRÍTICA:
    Rayson é um fabricante chinês de baixo custo (Shenzhen, fundado 2016).
    Chips Rayson NÃO têm mercado de reacondicionamento em celulares/notebooks premium.
    O objetivo do sistema ao identificar Rayson é:
      1. Nomear corretamente o tipo e capacidade para o laudo de triagem
      2. Sinalizar SEGREGAÇÃO EM LOTE SEPARADO (nunca misturar com Samsung/Hynix/Micron)
      3. Orientar para sucata ou reposição de equipamentos entry-level

ESTRUTURA REAL DOS PNs RAYSON (verificada em LCSC/Indasina/JLCPCB 2026-05):
    LPDDR3:   RS[N]32LD3[dies][pkg]-[speed]
              N = densidade por die (256M=8Gb=1GB · 512M=16Gb=2GB)
    LPDDR4/4X: RS[N]32L[gen][dies][pkg]-[speed]
              N = 512M(2GB) · 1G(4GB) · 2G(8GB) — gen: M4/F4/O4/V4=LPDDR4/4X
    eMMC:     RS70B[cap][gen][S][rev]
              cap: 08G=8GB · 16G=16GB · 32G=32GB · 64G=64GB · T7G=128GB

PREFIXOS QUE NÃO EXISTEM (não implementar):
    RS512MD3 · RS1GD3 · RS2GD3 · RSLPD3 · RSLPD4 · RSEMC · EM6
    Estes eram hipóteses sem base em fonte real. Nenhum PN Rayson real
    foi encontrado com esses prefixos (LCSC, Indasina, JLCPCB, szrayson.com).

Uso:
    python manage.py populate_rayson
    python manage.py populate_rayson --dry-run    # mostra o que faria sem salvar
    python manage.py populate_rayson --overwrite  # atualiza entradas existentes
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação Rayson no banco."

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
            self.stdout.write(self.style.SUCCESS("\n✅  Rayson populada com sucesso."))
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                self.stdout.write("   🗑  Cache do engine invalidado.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    # ──────────────────────────────────────────────────────────────────────────

    def _run(self, dry, overwrite=False):
        from chips.models import Brand, ChipFamily, DecodeMap  # noqa: F401 (DecodeMap importado para uso futuro)

        # ── Marca ─────────────────────────────────────────────────────────────
        rayson, created = Brand.objects.get_or_create(
            name="Rayson",
            defaults={
                "code": "RAY",
                "notes": (
                    "Rayson HI-TECH (SZ) Co., Ltd. — Shenzhen, China · Fundada 2016. "
                    "Também comercializada como 晶存科技. "
                    "Fabricante de memória de baixo custo (LPDDR3/4/4X/5, eMMC, UFS, eMCP, MCP). "
                    "Produtos não aceitos como substitutos de Samsung/Hynix/Micron no mercado B2B premium. "
                    "Destino padrão na reciclagem: lote segregado Rayson/budget."
                ),
            },
        )
        self._log(created, "Marca", "Rayson", dry)

        # ── DecodeMaps ────────────────────────────────────────────────────────
        # Embora a Rayson codifique capacidade literalmente no prefixo,
        # precisamos de DecodeMaps para que o engine preencha capacity e
        # grammar_complete=True — sem isso o engine chama Gemini e a UI
        # mostra "⚠ PN não confirmado" mesmo quando a família é reconhecida.
        #
        # Três mapas posicionais:
        #   RAY_LPDDR_4CHAR_CAP  (pos=2, len=4): RS[256M]32L··· / RS[512M]32L···
        #   RAY_LPDDR_2CHAR_CAP  (pos=2, len=2): RS[1G]32L···   / RS[2G]32L···
        #   RAY_EMMC_CAP         (pos=5, len=3): RS70B[08G]···  / RS70B[T7G]···

        # LPDDR3/4 com densidade de 4 chars (256M, 512M)
        self._bulk_map(
            "RAY_LPDDR_4CHAR_CAP",
            [
                ("256M", "1GB",  "8Gb = 256M×32bit"),
                ("512M", "2GB",  "16Gb = 512M×32bit"),
            ],
            rayson, dry, overwrite,
        )

        # LPDDR4/4X com densidade de 2 chars (1G, 2G)
        self._bulk_map(
            "RAY_LPDDR_2CHAR_CAP",
            [
                ("1G",   "4GB",  "32Gb = 1G×32bit"),
                ("2G",   "8GB",  "64Gb = 2G×32bit"),
            ],
            rayson, dry, overwrite,
        )

        # eMMC série RS70B — capacidade nos chars 6-8 (pos=5, len=3)
        self._bulk_map(
            "RAY_EMMC_CAP",
            [
                ("08G", "8GB",   ""),
                ("16G", "16GB",  ""),
                ("32G", "32GB",  ""),
                ("64G", "64GB",  ""),
                ("T7G", "128GB", "128GB — código interno Rayson (foge do padrão numérico)"),
            ],
            rayson, dry, overwrite,
        )

        # ── Famílias ──────────────────────────────────────────────────────────
        families = self._families(rayson)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != rayson.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = rayson
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

    def _families(self, rayson):
        """Retorna a lista de dicts de famílias Rayson confirmadas com PN âncora."""

        _TIP_SEGREGAR = (
            "⚠ RAYSON — chip de baixo custo. "
            "Segregar em LOTE RAYSON/BUDGET. "
            "NÃO misturar com Samsung / SK Hynix / Micron. "
            "Sem mercado de reacondicionamento em celular ou notebook premium."
        )

        return [

            # ══════════════════════════════════════════════════════════════════
            # LPDDR3 standalone
            # ──────────────────────────────────────────────────────────────────
            # Anatomia: RS [256M|512M] 32 L D3 [D1|D2] [pkg] - [speed]
            #   • 256M = 256M endereços × 32 bits = 8 Gb = 1 GB
            #   • 512M = 512M endereços × 32 bits = 16 Gb = 2 GB
            #   • 32  = bus de 32 bits
            #   • L   = Low Power (LPDDR)
            #   • D3  = DDR3 generation
            #   • D1  = single die  |  D2 = dual die
            # Package: FBGA178, 11.0×11.5mm, 0.65mm pitch
            # Tensão: VDD1=1.8V, VDDQ=1.2V
            # Presença na esteira: set-top boxes Android ~2014-2019, car stereo entry,
            #   tablets genéricos, roteadores budget
            # ══════════════════════════════════════════════════════════════════

            dict(
                # PN âncora: RS256M32LD3D1LMZ-125BT — LCSC C2840152 ✓ (2026-05-25)
                # 256M × 32bit = 8Gb = 1GB · single die (D1) · FBGA178
                prefix="RS256M32LD3",
                chip_type="LPDDR3",
                subtype="LPDDR3",
                interface="",
                decode_cap_pos=2, decode_cap_len=4, decode_cap_map="RAY_LPDDR_4CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "LPDDR3 Rayson 1GB (RS256M32LD3···). "
                    "8Gb por die, single die (D1), FBGA178, 1.2V VDDQ. "
                    "Velocidade típica: 1600 Mbps. "
                    "Origem: set-top boxes Android de entrada, car stereo, tablets ~2014-2019. "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncora: RS512M32LD3D2LMZ-125BT — LCSC C2840153 ✓ (2026-05-25)
                # Datasheet título confirma: "16Gb(x32)" · dual die (D2) · FBGA178
                # 512M × 32bit = 16Gb = 2GB
                prefix="RS512M32LD3",
                chip_type="LPDDR3",
                subtype="LPDDR3",
                interface="",
                decode_cap_pos=2, decode_cap_len=4, decode_cap_map="RAY_LPDDR_4CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "LPDDR3 Rayson 2GB (RS512M32LD3···). "
                    "16Gb total (512M×32), dual die (D2), FBGA178, 1.2V VDDQ. "
                    "Velocidade típica: 1600 Mbps. "
                    "Origem: Android boxes, tablets mid-range entry, car head units ~2015-2020. "
                    + _TIP_SEGREGAR
                ),
            ),

            # ══════════════════════════════════════════════════════════════════
            # LPDDR4 / LPDDR4X standalone
            # ──────────────────────────────────────────────────────────────────
            # Anatomia: RS [512M|1G|2G] 32 L [gen] [D1|D2|D4] [pkg] - [speed]
            #   • 512M = 512M × 32bit = 16Gb = 2GB
            #   • 1G   = 1G × 32bit = 32Gb = 4GB
            #   • 2G   = 2G × 32bit = 64Gb = 8GB
            #   • gen variantes observados: M4, F4 (LPDDR4) · O4, V4, X4 (LPDDR4X)
            # Package: FBGA200, 0.65mm pitch
            # Tensão: VDD=1.8V, VDDQ=1.1V (LPDDR4) / 0.6V (LPDDR4X)
            # Velocidade: até 4266 Mbps (conforme datasheet Rayson)
            # Presença na esteira: Android boxes 2018+, tablets mid-range, car stereo recente
            #
            # ESTRATÉGIA DE PREFIXO:
            #   Usamos "RS512M32L" (9 chars) como fallback para LPDDR4/4X 2GB.
            #   O prefixo "RS512M32LD3" (11 chars, LPDDR3) tem priority=50 e é mais
            #   longo — o engine testa prefixos na ordem do banco (priority asc), e
            #   como "RS512M32LD3" é mais específico, ele vence para chips LPDDR3.
            #   "RS512M32L" (priority=55) só casa se nenhum prefixo mais longo der match.
            # ══════════════════════════════════════════════════════════════════

            dict(
                # PN âncora físico: RS256M32LZ4... — chip na esteira eMiner (2026-05-26) ✓
                # 256M × 32bit = 8Gb = 1GB · variante Z4 = LPDDR4/4X (não é D3/LPDDR3)
                # Prefixo mais longo "RS256M32LD3" (LPDDR3, priority=50) vence para chips D3.
                # Este entry (priority=55) cobre Z4 e quaisquer outros variantes LPDDR4/4X de 1GB.
                prefix="RS256M32L",
                chip_type="LPDDR4",
                subtype="LPDDR4/4X",
                interface="",
                decode_cap_pos=2, decode_cap_len=4, decode_cap_map="RAY_LPDDR_4CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=55,
                tip=(
                    "LPDDR4/4X Rayson 1GB (RS256M32L···). "
                    "8Gb total (256M×32), FBGA200. "
                    "Variante observada na esteira: Z4. "
                    "Capacidade muito baixa para B2B atual — mesma regra operacional dos outros Rayson. "
                    "Origem: dispositivos entry-level (IoT, Android box ultra-budget, car stereo). "
                    "⚠ RAYSON — chip de baixo custo. "
                    "Segregar em LOTE RAYSON/BUDGET. "
                    "NÃO misturar com Samsung / SK Hynix / Micron. "
                    "Sem mercado de reacondicionamento em celular ou notebook premium."
                ),
            ),

            dict(
                # PN âncoras:
                #   RS512M32LM4D2BDS-53BT — LCSC C2840158 ✓ (LPDDR4, 2GB, 2026-05-25)
                #   RS512M32LO4D1BDS-53BT — Indasina ✓ ("2GB LPDDR4X", 2026-05-25)
                # Cobre variantes: LM4 (LPDDR4) · LO4, LV4, LX4, LF4 (LPDDR4X)
                # Prefixo mais longo "RS512M32LD3" (LPDDR3) tem priority=50 e vence
                # para chips D3 — este entry (priority=55) só pega o que sobrar.
                prefix="RS512M32L",
                chip_type="LPDDR4",
                subtype="LPDDR4/4X",
                interface="",
                decode_cap_pos=2, decode_cap_len=4, decode_cap_map="RAY_LPDDR_4CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=55,
                tip=(
                    "LPDDR4/4X Rayson 2GB (RS512M32L···). "
                    "16Gb total (512M×32), FBGA200. "
                    "Variantes: LM4/LF4=LPDDR4 (1.1V VDDQ) · LO4/LV4/LX4=LPDDR4X (0.6V VDDQ). "
                    "Velocidade: até 3733 Mbps. "
                    "Origem: Android boxes 2019+, tablets, car stereo. "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncoras:
                #   RS1G32LF4D2BDS-53BT — LCSC C2840160 / JLCPCB ✓ ("4GB LPDDR4", 2026-05-25)
                #   RS1G32LO4D2BDS-53BT — Indasina/JLCPCB ✓ ("4GB LPDDR4/4X", 2026-05-25)
                #   RS1G32LV4D2BDS-53BT — Indasina ✓ ("4GB LPDDR4/4X", 2026-05-25)
                # 1G × 32bit = 32Gb = 4GB · dual die (D2) · FBGA200
                prefix="RS1G32L",
                chip_type="LPDDR4",
                subtype="LPDDR4/4X",
                interface="",
                decode_cap_pos=2, decode_cap_len=2, decode_cap_map="RAY_LPDDR_2CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "LPDDR4/4X Rayson 4GB (RS1G32L···). "
                    "32Gb total (1G×32), dual die (D2), FBGA200. "
                    "Variantes: LF4=LPDDR4 · LO4/LV4=LPDDR4X. "
                    "Velocidade: até 4266 Mbps. "
                    "Origem: Android boxes mid-range, tablets 2019+. "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncoras:
                #   RS2G32LF4D4BDT-53BT — Glochip / Indasina ✓ ("8GB LPDDR4", 2026-05-25)
                #   RS2G32LV4D4BDT-53BT — Indasina ✓ ("8GB LPDDR4/4X", 2026-05-25)
                # 2G × 32bit = 64Gb = 8GB · quad die (D4) · FBGA200
                prefix="RS2G32L",
                chip_type="LPDDR4",
                subtype="LPDDR4/4X",
                interface="",
                decode_cap_pos=2, decode_cap_len=2, decode_cap_map="RAY_LPDDR_2CHAR_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "LPDDR4/4X Rayson 8GB (RS2G32L···). "
                    "64Gb total (2G×32), quad die (D4), FBGA200. "
                    "Variantes: LF4=LPDDR4 · LV4=LPDDR4X. "
                    "Velocidade: até 4266 Mbps. "
                    "Origem: Android boxes topo-de-linha, tablets/chromebooks entry 2020+. "
                    + _TIP_SEGREGAR
                ),
            ),

            # ══════════════════════════════════════════════════════════════════
            # eMMC — série RS70B
            # ──────────────────────────────────────────────────────────────────
            # Anatomia: RS70B [cap] [gen] S [rev]
            #   • cap: 08G=8GB · 16G=16GB · 32G=32GB · 64G=64GB · T7G=128GB
            #   • gen: 3=eMMC geração anterior · 4=eMMC 5.1 (predominante)
            #   • S = single die (Storage)
            #   • rev = revisão de firmware/package (03F, 06F, 10F, 15G, 16G...)
            # Package: TFBGA153, 11.5×13mm, 0.5mm pitch
            # Interface: JEDEC eMMC 5.1, HS400 até 400MB/s
            # Tensão: VCC 2.7-3.6V, VCCQ 1.7-1.95V
            # Presença na esteira: TV boxes (Android/IPTV), roteadores budget,
            #   set-top boxes de operadora, leitores de DVD com Android
            #
            # NOTA sobre revisões de sufixo:
            #   O sufixo após a capacidade (3S03F, 4S15G, 4S16G etc.) indica
            #   revisão de package/firmware — NÃO altera capacidade nem interface.
            #   O prefixo RS70B08G cobre RS70B08G3S03F, RS70B08G4S..., etc.
            # ══════════════════════════════════════════════════════════════════

            dict(
                # PN âncora: RS70B08G3S03F — LCSC C22364054 ✓ (eMMC 5.1, 8GB, TFBGA153, 2026-05-25)
                # Indasina confirma: "eMMC5.1 8GB" ✓
                prefix="RS70B08G",
                chip_type="eMMC",
                subtype="eMMC 5.1 8GB",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 Rayson 8GB (RS70B08G···). "
                    "TFBGA153 (11.5×13mm), HS400 até 400MB/s. "
                    "Reacondicionamento em celular/tablet premium: INVIÁVEL (não aceito no mercado B2B). "
                    "Uso: reposição em equipamento de entrada idêntico ao de origem (TV box, roteador). "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncoras:
                #   RS70B16G4S06F — Indasina ✓ ("eMMC 16GB", 2026-05-25)
                #   RS70B16G4S10F — Indasina ✓ ("eMMC 5.1 16GB", 2026-05-25)
                #   RS70B16G4S15G — LCSC C41368088 ✓ (eMMC 5.1, 16GB, TFBGA153, 2026-05-25)
                prefix="RS70B16G",
                chip_type="eMMC",
                subtype="eMMC 5.1 16GB",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 Rayson 16GB (RS70B16G···). "
                    "TFBGA153 (11.5×13mm), HS400 até 400MB/s. "
                    "Reacondicionamento em celular/tablet premium: INVIÁVEL. "
                    "Uso: reposição em equipamento de entrada idêntico (TV box, set-top box). "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncora: RS70B32G4S15G — LCSC C22375657 ✓ (eMMC 5.1, 32GB, TFBGA153, 2026-05-25)
                prefix="RS70B32G",
                chip_type="eMMC",
                subtype="eMMC 5.1 32GB",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 Rayson 32GB (RS70B32G···). "
                    "TFBGA153 (11.5×13mm), HS400 até 400MB/s. "
                    "Reacondicionamento em celular/tablet premium: INVIÁVEL. "
                    "Uso: reposição em equipamento de entrada idêntico (TV box, set-top box). "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncora: RS70B64G4S16G — LCSC C41368089 ✓ (eMMC 5.1, 64GB, TFBGA153, 2026-05-25)
                # Indasina confirma: "eMMC 5.1 64GB" ✓
                prefix="RS70B64G",
                chip_type="eMMC",
                subtype="eMMC 5.1 64GB",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 Rayson 64GB (RS70B64G···). "
                    "TFBGA153 (11.5×13mm), HS400 até 400MB/s. "
                    "Reacondicionamento em celular/tablet premium: INVIÁVEL. "
                    "Uso: reposição em equipamento de entrada idêntico. "
                    + _TIP_SEGREGAR
                ),
            ),

            dict(
                # PN âncora: RS70BT7G4S16G — LCSC C41368090 ✓ (eMMC 5.1, 128GB, TFBGA153, 2026-05-25)
                # Indasina: "eMMC5.1, 512Gb×2 = 128GB" ✓
                # NOTA: "T7G" é código interno Rayson para 128GB (foge do padrão 08G/16G/32G/64G).
                prefix="RS70BT7G",
                chip_type="eMMC",
                subtype="eMMC 5.1 128GB",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 Rayson 128GB (RS70BT7G···). "
                    "⚠ 'T7G' é código interno Rayson para 128GB — foge do padrão numérico da série RS70B. "
                    "TFBGA153 (11.5×13mm), HS400 até 400MB/s. "
                    "Reacondicionamento em celular/tablet premium: INVIÁVEL. "
                    "Uso: reposição em equipamento de entrada idêntico (Android box high-end, tablet). "
                    + _TIP_SEGREGAR
                ),
            ),

            # ══════════════════════════════════════════════════════════════════
            # FALLBACK GENÉRICO RS70B
            # ──────────────────────────────────────────────────────────────────
            # Captura qualquer RS70B* não coberto pelos prefixos de 8 chars acima.
            # Exemplos: novas capacidades (4GB, 256GB) confirmadas no futuro,
            # ou revisões com prefixo levemente diferente.
            # DEVE ter priority > que todos os RS70B específicos (priority=50).
            # ══════════════════════════════════════════════════════════════════

            dict(
                # Fallback: cobre RS70B* que não case com RS70B08G/16G/32G/64G/T7G
                prefix="RS70B",
                chip_type="eMMC",
                subtype="eMMC Rayson (capacidade a identificar)",
                interface="eMMC 5.1",
                decode_cap_pos=5, decode_cap_len=3, decode_cap_map="RAY_EMMC_CAP",
                pn_length=None,
                is_emcp=False,
                active=True,
                priority=70,
                tip=(
                    "eMMC Rayson — prefixo RS70B genérico. "
                    "Capacidade não decodificada automaticamente (PN fora do mapa atual). "
                    "Leia os caracteres 6-7 do PN para a capacidade: 08G=8GB · 16G=16GB · "
                    "32G=32GB · 64G=64GB · T7G=128GB. "
                    "Se for nova capacidade (ex: 4GB, 256GB): reportar para adicionar ao populate_rayson.py. "
                    + _TIP_SEGREGAR
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
