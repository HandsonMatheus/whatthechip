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
            self.stdout.write(self.style.SUCCESS("\n✅  Samsung populada com sucesso."))
            # Invalida caches em memória do engine para que as novas famílias
            # e mapas de decodificação sejam refletidos imediatamente nas buscas.
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
        samsung, created = Brand.objects.get_or_create(
            name="Samsung",
            defaults={"code": "SAM", "notes": "Coreia do Sul · Fundada 1969"},
        )
        self._log(created, "Marca", "Samsung", dry)

        # ── DecodeMap: capacidade Flash (eMMC + UFS) ──────────────────────────
        # Posição 3 do PN (1 char) → capacidade de armazenamento
        flash_cap = [
            ("2",  "2GB",  ""),    # legado — Smart TVs 1ª geração, modems 3G, tablets entry (~2010-2013)
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
        self._bulk_map("SAM_FLASH_CAP", flash_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade eMCP (2 chars, pos 3-4) ─────────────────────
        # val_primary = cap NAND (eMMC)  |  val_secondary = cap RAM (LPDDR)
        #
        # Samsung usa dois padrões distintos de codificação:
        #   Matriz direta (legado): dois dígitos numéricos que cruzam densidade
        #     NAND × RAM de forma literal (ex: "31" = 3ª col × 1ª linha da matriz)
        #   Alfanumérico (moderno): pares mistos como "5X", "BT", "GD"
        #
        # O mapa anterior tinha apenas 8 entradas; isso causava fallback ao Gemini
        # para a maioria dos PNs reais (ex: KMQ310006A → chave "31" não existia).
        emcp_cap = [
            # ── Matriz direta (legado, 2012-2017) ────────────────────────────
            ("11", "4GB",   "512MB"),  # 4GB NAND + 512MB RAM
            ("72", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM
            ("7U", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM   (KMK7U000VMB) — confirmado usuário
            ("82", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM
            ("IS", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM   (KMVIS000LM) — Galaxy S2 i9100, confirmado IA externa
            ("TU", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM   (KMVTU000LM) — Galaxy S3 i9300, confirmado IA externa
            ("31", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM
            ("21", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM
            ("4Z", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KMQ4Z0013MB) — confirmado Gemini
            ("41", "32GB",  "4GB"),    # 32GB NAND + 4GB RAM
            # ── Alfanumérico geração 1 (2017-2019) ───────────────────────────
            ("5X", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMQ5X·)
            ("8X", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMR8X0001M) — entrada, resíduo
            ("NW", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMRNW0001M) — entrada, resíduo
            ("N6", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMFN60012MB214) — Octopart: 8Gb LPDDR3
            ("NX", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMFNX0012M) — confirmado IA externa (Win Source/Arrow)
            ("E1", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   (KMQE10013M) — Galaxy J5/J7, Moto G
            ("BT", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   (KMQBT·)
            ("V7", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   alias BT
            ("V8", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  (KM5V8001DM-B622 — fabricante: 32Gb÷8=4GB)
            #                          # ⚠ CORRIGIDO: entrada anterior dizia 8GB (fonte: AI sem confirmação).
            #                          # KM8V8001JM também é 4GB — cap_key compartilhado.
            ("GD", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   (KMQGD·)
            ("W7", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   alias GD
            ("W8", "32GB",  "4GB"),    # 32GB NAND + 4GB RAM   (KMFW8·)
            ("X1", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KMQX10013MB — Octopart: 32GB+16Gb)
            ("H9", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   alias X1 (corrigido junto, sem PN independente)
            ("C1", "64GB",  "4GB"),    # 64GB NAND + 4GB RAM   (KMRC10014M) — Oppo R9 / mid-premium, confirmado IA externa
            ("M4", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  (KMQM4·)
            ("J2", "128GB", "6GB"),    # 128GB NAND + 6GB RAM  (KMQJ2·)
            ("P5", "256GB", "8GB"),    # 256GB NAND + 8GB RAM  (KMQP5·)
            # ── Alfanumérico geração 2 (2020-2022, padrão [X]6) ──────────────
            # Sufixo "6" identifica a geração de empacotamento (eMMC 5.1 rev B)
            # Fonte: teardowns Galaxy A21s/A31/A41/A51/A72 + KMD/KML uMCP
            ("D6", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   (KMQD6·, KMRD6·)
            ("E6", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   alias D6 (lote alt.)
            ("G6", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   (KMDG6001BM) — confirmado Gemini
            ("V6", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   alias D6 (rev)
            ("U6", "64GB",  "3GB"),    # 64GB NAND + 3GB RAM   (KMQU6·)
            ("X6", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KM4X6001KM) — confirmado Octopart; era alias especulativo U6
            ("T6", "64GB",  "4GB"),    # 64GB NAND + 4GB RAM   (KMQT6·)
            ("Y6", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  (KMQY6·)
            ("H6", "64GB",  "4GB"),    # KMRH60014A (A7 2017): H=64GB, consistente com H9
            ("P6", "64GB",  "4GB"),    # KMDP6001DA: 64GB eMMC + 32Gb (4GB) LPDDR4X
            #                          # "P" não é capacidade Flash — é código de densidade RAM.
            #                          # Confirmado: 32Gb ÷ 8 = 4GB. device "Galaxy MX6432"
            #                          # é código interno Samsung (64=eMMC, 32=Gb RAM), não celular.
            ("P9", "64GB",  "4GB"),    # KM5P9001DMB424: 64GB UFS 2.1 + 32Gb LPDDR4X-4266 (Octopart)
            #                          # 32Gb ÷ 8 = 4GB. uMCP linha numérica KM5 (mid-premium 2021+).
            # Z6: evidência insuficiente — omitido intencionalmente (vai para Gemini)
            ("L6", "256GB", "8GB"),    # 256GB NAND + 8GB RAM  (KMFL6·, uMCP S21 FE)
            # ── uMCP high-cap (2021+, LPDDR5/5X, flagships) ──────────────────
            # A partir daqui os códigos são derivados por engenharia de padrão +
            # dados de teardown. Verificar com PN real antes de usar como referência.
            ("K6", "128GB", "8GB"),    # 128GB NAND + 8GB RAM  (KML·, S21 Exynos / A73 5G)
            # ── uMCP linha numérica KM5/KM8/KM2 (confirmados pelo fabricante) ──────
            ("C7", "64GB",  "4GB"),    # KM5C7001DM-B622: 64GB UFS2.1 + 32Gb÷8=4GB LPDDR4X ✓
            ("L9", "128GB", "6GB"),    # KM2L9001CM-B518: 128GB UFS2.2 + 48Gb÷8=6GB LPDDR4X ✓
            ("F9", "256GB", "8GB"),    # KM8F9001JM-B813: 256GB UFS2.2 + 64Gb÷8=8GB LPDDR4X ✓
            ("F8", "256GB", "12GB"),   # KM8F8001MM-B813: 256GB UFS2.1 + 96Gb÷8=12GB LPDDR4X ✓
            # Gaps ainda não mapeados (vai para Gemini):
            #   512GB + 12GB (S22 Ultra 512GB, S23 Ultra)
            # Adicionar quando PN real confirmar o cap_key.
        ]
        self._bulk_map("SAM_EMCP_CAP", emcp_cap, samsung, dry, overwrite)

        # ── DecodeMap: geração RAM eMCP (pos 2, 1 char) ───────────────────────
        # Correção: R = LPDDR3, não LPDDR4/4X (erro histórico no gabarito).
        # R = LPDDR4/4X confirmado: série KMR (Galaxy A 2016-2019) é oficialmente LPDDR4.
        # Ref: KMRH60014A-B614 (A7 2017, 3GB LPDDR4), KMRY60014A (A8 2018, 4GB LPDDR4).
        emcp_gen = [
            ("J", "LPDDR2",    ""),   # KMJ: eMCP legado entrada (~2013-2015), LPDDR2
            ("K", "LPDDR2",    ""),
            ("F", "LPDDR3",    ""),
            ("N", "LPDDR3",    ""),
            ("Q", "LPDDR3",    ""),
            ("R", "LPDDR4/4X", ""),   # confirmado: KMR = LPDDR4/4X (não LPDDR3)
            ("S", "LPDDR4X",   ""),
            # uMCP
            ("D", "LPDDR4X",   ""),
            ("E", "LPDDR4/4X", ""),
            ("G", "LPDDR4X",   ""),
            ("L", "LPDDR5",    ""),
            ("V", "LPDDR5/5X", ""),
        ]
        self._bulk_map("SAM_EMCP_GEN", emcp_gen, samsung, dry, overwrite)

        # ── DecodeMap: RDRAM / Rambus (pos 3-4, 2 chars) ─────────────────────
        # K4R + NÚMERO (pn[3] dígito) = RDRAM Rambus (1999-2003).
        # Rambus usa barramento de 18 bits → densidades "quebradas" (9-bit ECC).
        # Fonte: Samsung RDRAM datasheets / análise de PNs reais do lote.
        # "27" omitido — evidência insuficiente, vai para Gemini.
        rdram_cap = [
            ("44", "144Mb", "16Mx9 por canal"),   # ex: K4R441669E
            ("88", "288Mb", "32Mx9 por canal"),   # ex: K4R881869E (PS2, PC800)
            ("76", "576Mb", "64Mx9 por canal"),   # ex: K4R760869E
        ]
        self._bulk_map("RDRAM_CAP", rdram_cap, samsung, dry, overwrite)

        # ── DecodeMap: BGA NVMe SSD (pos 3-4, 2 chars) ───────────────────────
        # Fonte: seção sam-kus do fab-samsung.html
        # KUS0X... → capacidade sequencial: 02=128GB, 03=256GB, 04=512GB, 05=1TB
        kus_cap = [
            ("02", "128GB", ""),
            ("03", "256GB", ""),
            ("04", "512GB", ""),
            ("05", "1TB",   ""),
        ]
        self._bulk_map("KUS_CAP", kus_cap, samsung, dry, overwrite)

        # ── DecodeMap: densidade DRAM PC (pos 3-4, 2 chars) ───────────────────
        dram_pc = [
            ("64",  "64Mb",  "8MB"),    # ex: K4S641632H (SDRAM)
            ("28",  "128Mb", "16MB"),   # ex: K4H280438E (DDR1)
            ("56",  "256Mb", "32MB"),   # ex: K4H560838D (DDR1)
            ("51",  "512Mb", "64MB"),
            ("1G",  "1Gb",   "128MB"),
            ("2G",  "2Gb",   "256MB"),
            ("4G",  "4Gb",   "512MB"),
            ("8G",  "8Gb",   "1GB"),
            ("AG",  "16Gb",  "2GB"),
            ("AH",  "16Gb",  "2GB"),   # DDR5
        ]
        self._bulk_map("DRAM_PC", dram_pc, None, dry, overwrite)

        # ── DecodeMap: capacidade K3QF (LPDDR3 alta-densidade, pos 4, 1 char) ──────
        # Usado pela sub-família K3QF (chips K3QFxFx0...).
        # pn[4] = contador de dies empilhados (n × 8Gb por die).
        # val_primary = GB total (operador), val_secondary = Gb total (referência).
        # Apenas entradas confirmadas por Octopart / datasheet:
        #   "1" → K3QF1F10DMAGCE000 (Octopart: 128Mx32+128Mx32 = 8Gb = 1GB) ✓
        #   "2" → K3QF2F20EM (confirmado em sessão anterior: 16Gb = 2GB) ✓
        # ⚠ F3, F4 não confirmados — K3QF3F30BM citado como "16Gb" mas isso era
        #   resultado do bug pn[3]='F' → 16Gb, NÃO de datasheet. Não mapear ainda.
        k3qf_cap = [
            ("1", "1GB", "8Gb — 1× 8Gb die. Ex: K3QF1F10DMAGCE000 (Octopart). Resíduo."),
            ("2", "2GB", "16Gb — 2× 8Gb die. Ex: K3QF2F20EM. Reacondicional seletivo."),
        ]
        self._bulk_map("K3QF_CAP", k3qf_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade LPDDR3 standalone K4E (pos 3-4, 2 chars) ─────
        # val_primary = capacidade em GB (legível para operador de bancada).
        # val_secondary = densidade em Gb (referência técnica).
        # Fonte: datasheets Samsung K4E + Galaxy Note 3 / S5 teardowns.
        k4e_cap = [
            ("8E", "1GB",  "8Gb — Galaxy entry (~2013). Sem liquidez B2B atual."),
            ("6E", "2GB",  "16Gb — Galaxy mid-range (~2014-2016)."),
            ("FE", "3GB",  "24Gb — Galaxy Note 3 / S5 (~2013-2014). Raro."),
            ("BE", "4GB",  "32Gb — Galaxy flagship (~2015). Alta demanda residual."),
        ]
        self._bulk_map("K4E_CAP", k4e_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade LPDDR4 / LPDDR4X (pos 3-4, 2 chars) ───────────
        # Usado por K4F (LPDDR4), K4U (LPDDR4X), K3U (LPDDR4X multi-channel).
        # val_primary = capacidade em GB (legível para operador de bancada).
        # val_secondary = densidade em Gb (referência técnica).
        # ⚠ Decode OBRIGATÓRIO de 2 chars — pn[3] sozinho é enganoso
        #   (ex: "6E"=2GB mas "6" isolado = 6Gb no mapa antigo de 1 char → erro).
        # Fonte: datasheets Samsung + teardowns Galaxy S/A series.
        lpddr4_cap = [
            ("2E", "1.5GB", "12Gb"),  # confirmado por datasheet Samsung
            ("4E", "512MB", "4Gb"),
            ("8E", "1GB",   "8Gb"),
            ("6E", "2GB",   "16Gb"),
            ("7E", "3GB",   "24Gb"),
            ("BE", "4GB",   "32Gb"),
            ("HE", "4GB",   "32Gb"),  # alias BE (empacotamento alternativo)
            ("H6", "4GB",   "32Gb"),  # alias BE (geração 2020+)
            ("CE", "8GB",   "64Gb"),
            ("H7", "8GB",   "64Gb"),  # alias CE (ex: K3UH7H70MM-TFCL)
            ("HD", "16GB",  "128Gb"),
        ]
        self._bulk_map("LPDDR4_CAP", lpddr4_cap, samsung, dry, overwrite)

        # ── DecodeMap: densidade DRAM Mobile (pos 3, 1 char) ─────────────────
        dram_mob = [
            ("P",  "512Mb", "64MB"),
            ("1",  "1Gb",   "128MB"),
            ("2",  "2Gb",   "256MB"),
            ("4",  "4Gb",   "512MB"),
            ("6",  "6Gb",   "768MB"),
            ("8",  "8Gb",   "1GB"),
            ("F",  "16Gb",  "2GB"),   # LPDDR3 alta densidade — ex: K3QF3F30BM (confirmado)
            ("B",  "12Gb",  "1.5GB"),  # LPDDR4/4X alta densidade — ex: K4FBE3D4HB, K4UBE3D4AB
            ("G",  "16Gb",  "2GB"),
            ("H",  "32Gb",  "4GB"),
        ]
        self._bulk_map("DRAM_MOBILE", dram_mob, None, dry, overwrite)

        # ── DecodeMap: densidade LPDDR5/5X (pos 4, 2 chars) ──────────────────
        # Codificação Samsung LPDDR5: 2 chars pós-prefixo de 4 chars (pn[4:6]).
        # Representa empilhamento de dies — valores confirmados por PNs reais de mercado.
        # Códigos não mapeados → sistema retorna None ("Desconhecido — Ler Datasheet").
        lpddr5_cap = [
            # val_primary = GB (operador), val_secondary = Gb (referência técnica) — mesma convenção LPDDR4_CAP
            ("9L", "2GB",  "16Gb — ex: K3KL9L90DMMGCU (Octopart: 512MX32)"),
            ("BK", "4GB",  "32Gb — ex: K3LKBKB0BMMGCP (Octopart: 1GX32)"),
            ("8L", "4GB",  "32Gb — ex: K3KL8L80EMMGCU (Octopart: 1GX32)"),
            ("7K", "8GB",  "64Gb — ex: K3LK7K70BM (Galaxy S22)"),
            ("CK", "8GB",  "64Gb — variante de empilhamento alternativo"),
            ("4K", "12GB", "96Gb — ex: K3LK4K40CM (Galaxy S20 Ultra)"),
            ("5L", "16GB", "128Gb — ex: K3KL5L50DM (flagships)"),
        ]
        self._bulk_map("LPDDR5_CAP", lpddr5_cap, samsung, dry, overwrite)

        # ── ChipFamilies ──────────────────────────────────────────────────────
        # Lookup por prefix apenas (sem brand) para corrigir entradas com
        # brand errado de outros populate scripts (ex: KLUDG registrado como
        # Kioxia em add_chip_families.py — Samsung KLU é UFS standalone Samsung).
        families = self._families(samsung)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            # Sempre seta brand=samsung — corrige entradas com brand errado.
            # Quando brand muda (ex: Kioxia → Samsung), zera doc_page para que
            # o engine herde a página de documentação da nova marca, em vez de
            # manter o link da marca anterior (ex: /fab-toshiba/ → /fab-samsung/).
            brand_changed = (not created) and (fam.brand_id != samsung.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None  # herda da nova marca
            if changed:
                fam.brand = samsung
            for k, v in fdata.items():
                if getattr(fam, k, None) != v:
                    setattr(fam, k, v)
                    changed = True

            if changed:
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

    def _families(self, samsung):
        """Retorna a lista de dicts de famílias para get_or_create."""
        return [

            # ═══ KM GENÉRICO (fallback eMCP — prioridade mínima) ═════════════
            # Esta entrada captura qualquer Samsung eMCP cujo prefixo específico
            # (KMQ, KMR, KMS, KMD…) ainda não esteja cadastrado no banco.
            # DEVE ter priority > que todos os prefixos específicos (KMQ/KMR = 40)
            # para que a família mais longa seja testada primeiro.
            # Se no banco existir uma entrada "KM" legada com priority baixo
            # (ex: 10), ela vai shadowing KMR/KMQ — rodar populate --overwrite
            # corrige isso atualizando para priority=90.
            dict(
                prefix="KM", chip_type="eMCP", subtype="embedded Multi-Chip Package (LPDDR + eMMC)",
                interface="", pn_length=10,
                is_emcp=True, active=True, priority=90,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "💡 KM = eMCP Samsung — RAM LPDDR + eMMC no mesmo package. "
                    "3ª letra = tipo RAM: "
                    "J/K=LPDDR2 · Q/F/N=LPDDR3 · R=LPDDR4/4X · S=LPDDR4X. "
                    "uMCPs modernos (D/G/L/V): UFS+LPDDR, classificados por prefixo específico. "
                    "Capacidade: posições 4-5 do PN (ex: X1=32GB+2GB, H6=64GB+4GB). "
                    "Destino: bancada reacondicional eMCP."
                ),
                reasoning='["K → Samsung Memory", "M → Multi-Chip Package (RAM+NAND combinados)", '
                          '"3ª letra → tipo RAM: J/K=LPDDR2 · Q/F/N=LPDDR3 · R=LPDDR4/4X · S=LPDDR4X", '
                          '"Solução compacta para smartphones entry/mid", '
                          '"NÃO tente separar os componentes — chip monolítico"]',
            ),

            # ═══ SDRAM (OBSOLETO) ════════════════════════════════════════════
            # K4S = Samsung SDRAM Synchronous. Posições 3-4 = densidade.
            # Chaves no mapa DRAM_PC: 64=64Mb, 28=128Mb, 56=256Mb, 51=512Mb.
            # Obsoleto desde ~2004 — fluxo direto para resíduo (moagem/refino).
            dict(
                prefix="K4S", chip_type="SDRAM", subtype="PC-66/100/133",
                interface="", is_emcp=False, active=True, priority=100,
                decode_density_type="pc",
                tip=(
                    "SDRAM Samsung (obsoleto, 1998–2004). "
                    "S = Synchronous DRAM. "
                    "Densidade: chars 4-5 do PN (64=64Mb, 28=128Mb, 56=256Mb, 51=512Mb). "
                    "Velocidade no sufixo: TC1H=PC-100 10ns, TC75=PC-133 7.5ns, TC70=PC-133 7.0ns. "
                    "Destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),

            # ═══ DDR DESKTOP / SERVER ════════════════════════════════════════
            # K4H = Samsung DDR1. Posições 3-4 = densidade (chaves DRAM_PC).
            # Velocidade no sufixo: TB0/TB3=DDR333, TCC/UCC=DDR400.
            # Destino: resíduo — obsoleto para reacondicional.
            dict(
                prefix="K4H", chip_type="DDR", subtype="DDR1",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR1 Samsung (2001–2007). "
                    "H = DDR1 (2.5V). "
                    "Densidade: chars 4-5 do PN (28=128Mb, 56=256Mb, 51=512Mb, 1G=1Gb). "
                    "Largura: chars 6-7 (04=x4, 08=x8, 16=x16). "
                    "Velocidade no sufixo: -TB0/-TA2=DDR266, -TB3=DDR333, -TCC/-UCC=DDR400. "
                    "Destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),
            # K4T = Samsung DDR2. Posições 3-4 = densidade (chaves DRAM_PC).
            # Largura: chars 6-7 (08=x8 DIMMs, 16=x16 embarcados).
            # Velocidade no sufixo: -CD5=DDR2-533, -CE6=DDR2-800, -CF7=DDR2-800 alt.
            dict(
                prefix="K4T", chip_type="DDR", subtype="DDR2",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR2 Samsung (2004–2010). "
                    "T = DDR2 (1.8V). "
                    "Densidade: chars 4-5 do PN (51=512Mb, 1G=1Gb, 2G=2Gb). "
                    "Largura: chars 6-7 (08=x8 DIMMs, 16=x16 embarcados). "
                    "Velocidade no sufixo: -CD5=DDR2-533, -CE6=DDR2-667, -CF7=DDR2-800. "
                    "OBSOLETO — destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),
            # K4B = Samsung DDR3/DDR3L. Posições 3-4 = densidade (chaves DRAM_PC).
            # Distinção DDR3 vs DDR3L: sufixo -BC=DDR3 1.5V | -BY=DDR3L 1.35V.
            # Ainda tem demanda no mercado de reuso — fluxo reacondicional.
            dict(
                prefix="K4B", chip_type="DDR", subtype="DDR3/DDR3L",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR3/DDR3L Samsung (2007–2016). "
                    "B = DDR3. "
                    "Densidade: chars 4-5 do PN (1G=1Gb, 2G=2Gb, 4G=4Gb, 8G=8Gb). "
                    "Largura: chars 6-7 (08=x8, 16=x16). "
                    "Tensão pelo sufixo: -BC=DDR3 padrão (1.5V) · -BY=DDR3L baixa tensão (1.35V). "
                    "NÃO misturar DDR3 com DDR3L na bancada de testes. "
                    "Destino: bancada reacondicional."
                ),
            ),
            # K4A = Samsung DDR4. Posições 3-4 = densidade (chaves DRAM_PC).
            # A = DDR4 (1.2V). Alto volume na triagem de desktops/laptops modernos.
            # Velocidade no sufixo: -BCPB=DDR4-2133, -BCRC=DDR4-2400,
            #   -BCTD=DDR4-2666, -BCWE=DDR4-3200.
            dict(
                prefix="K4A", chip_type="DDR4", subtype="DDR4",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR4 Samsung (2014–presente). "
                    "A = DDR4 (1.2V). "
                    "Densidade: chars 4-5 do PN (4G=4Gb, 8G=8Gb, AG=16Gb). "
                    "Largura: chars 6-7 (04=x4, 08=x8, 16=x16). "
                    "Velocidade no sufixo: -BCPB=DDR4-2133, -BCRC=DDR4-2400, "
                    "-BCTD=DDR4-2666, -BCWE=DDR4-3200. "
                    "Alto volume na esteira. Destino: bancada reacondicional."
                ),
            ),
            # ── K4R: PREFIXO COMPARTILHADO — bifurcação obrigatória ──────────
            # Samsung reutilizou K4R em duas eras completamente diferentes:
            #   K4R + LETRA (pn[3] = letra) → DDR5 (2021+)   → prefixo K4RA (priority=80)
            #   K4R + NÚMERO (pn[3] = dígito) → RDRAM Rambus (1999-2003) → K4R fallback (priority=100)
            # O prefixo mais longo K4RA é testado primeiro pelo engine (priority menor).
            # PNs reais RDRAM: K4R881869E (288Mb, PS2/P4), K4R760869E (576Mb), K4R441669E (144Mb).
            # PNs reais DDR5: K4RAH086VB-BCQK (16Gb x8), K4RAH165VB-BCQK (16Gb x16).

            # DDR5 — prefixo de 4 chars, vence o K4R genérico
            dict(
                prefix="K4RA", chip_type="DDR5", subtype="DDR5",
                interface="", decode_density_type="pc",
                is_emcp=False, active=True, priority=80,
                tip=(
                    "DDR5 Samsung (2021–presente). "
                    "K4RA = DDR5 (1.1V). "
                    "Densidade: chars 4-5 do PN (AH=16Gb). "
                    "Largura: chars 6-7 (08=x8, 16=x16). "
                    "Velocidade no sufixo: -BCQK=DDR5-4800 MT/s. "
                    "⚠ INCOMPATÍVEL com DDR4 — slot, tensão e protocolo diferentes. "
                    "NÃO misturar com K4A na bancada. "
                    "Destino: bancada reacondicional DDR5 (caixa separada)."
                ),
            ),

            # RDRAM Rambus — fallback para K4R + dígito
            dict(
                prefix="K4R", chip_type="RDRAM", subtype="Rambus DRAM (RDRAM)",
                interface="Rambus Channel",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="RDRAM_CAP",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "RDRAM Samsung / Rambus DRAM (1999–2003). "
                    "⚠ NÃO confundir com DDR5 (K4RA): K4R + NÚMERO = RDRAM, K4R + LETRA = DDR5. "
                    "Barramento Rambus 18-bit (16-bit dados + 2-bit ECC). "
                    "Densidade: chars 4-5 do PN (44=144Mb, 88=288Mb, 76=576Mb). "
                    "Presente em: PlayStation 2, Pentium 4 primeiros (RDRIMM). "
                    "OBSOLETO — destino: fluxo de resíduo (moagem/refino)."
                ),
            ),

            # ═══ LPDDR MOBILE ════════════════════════════════════════════════
            # K4M / K4X = LPDDR1 / Mobile DDR — obsoleto, fluxo de resíduo.
            # K4X: decode via DRAM_PC pn[3:5] — chaves: 51=512Mb(64MB), 1G=1Gb(128MB),
            #       2G=2Gb(256MB), 4G=4Gb(512MB). Teto 512MB → sem liquidez B2B atual.
            # K4P = LPDDR2 — pn[3] = densidade (DRAM_MOBILE). Reacondicional.
            # K3Q = LPDDR3 — pn[3] = densidade (DRAM_MOBILE). Reacondicional.
            dict(
                prefix="K4M", chip_type="LPDDR1", subtype="LPDDR1 / Mobile DDR (legado)",
                interface="LPDDR1", is_emcp=False, active=True, priority=100,
                tip=(
                    "⚠ LPDDR1 / Mobile DDR Samsung (obsoleto, ~2004–2010). "
                    "M = LPDDR1. Teto de capacidade incompatível com B2B atual. "
                    "Destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),
            dict(
                prefix="K4X", chip_type="LPDDR1", subtype="LPDDR1 / Mobile DDR (legado)",
                interface="LPDDR1", is_emcp=False, active=True, priority=100,
                decode_density_type="pc",
                tip=(
                    "⚠ LPDDR1 / Mobile DDR Samsung (obsoleto, ~2004–2010). "
                    "X = Mobile DDR (primeira geração LPDDR). "
                    "Densidade: pn[3:5] → 51=512Mb(64MB) · 1G=1Gb(128MB) · 2G=2Gb(256MB) · 4G=4Gb(512MB). "
                    "Teto de 512MB — incompatível com qualquer demanda B2B atual. "
                    "Destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),
            dict(
                prefix="K4P", chip_type="LPDDR2", subtype="LPDDR2 Mobile (legado)",
                interface="LPDDR2", decode_density_type="mobile",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "⚠ LPDDR2 Samsung (obsoleto, ~2010–2015). "
                    "P = LPDDR2. RAM pura — sem componente Flash. "
                    "Densidade: pn[3] → 2=2Gb(256MB) · 4=4Gb(512MB) · 8=8Gb(1GB). "
                    "Exemplos: K4P2G304EB (2Gb), K4P4G324EB (4Gb). "
                    "Arquitetura 100% obsoleta para B2B atual — independente da capacidade. "
                    "Destino: fluxo de resíduo (moagem/refino). NÃO enviar para reacondicional."
                ),
            ),
            dict(
                prefix="K3R", chip_type="LPDDR3", subtype="LPDDR3",
                interface="LPDDR3", decode_density_type="mobile",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR3 Samsung (K3R). Velocidade: até 2133 Mbps. Tensão: 1.2V. "
                    "Densidade: pn[3] → G=16Gb(2GB) · H=32Gb(4GB). "
                    "Destino: bancada reacondicional mobile."
                ),
            ),
            # ═══ K3 GENÉRICO (fallback LPDDR2/3 — prioridade mínima) ════════════
            # Captura K3Q e qualquer K3x não mapeado explicitamente (K3R tem entrada própria acima).
            # DEVE ter priority > que todos os prefixos K3x específicos (K3U/K3Q=40)
            # para que o prefixo mais longo seja testado primeiro.
            # Sem decode de densidade: variabilidade alta, Gemini/manual completa.
            dict(
                prefix="K3", chip_type="RAM", subtype="LPDDR2 / LPDDR3 (legado)",
                interface="LPDDR2/3", decode_density_type="mobile",
                is_emcp=False, active=True, priority=90,
                reasoning='["K → Samsung Memory", "3 → 3rd-gen DRAM (LPDDR2/3)", '
                          '"K3R/K3Q → LPDDR3 séries comuns", '
                          '"Velocidade: até 2133 Mbps (LPDDR3E)", '
                          '"NÃO confundir com K3U (LPDDR4X) ou K3L (LPDDR5)"]',
                tip=(
                    "💡 K3 = LPDDR2/3 legado. "
                    "ATENÇÃO: K3U=LPDDR4X e K3L=LPDDR5 têm regras próprias. "
                    "K3 genérico cobre K3R e K3Q (LPDDR3). "
                    "Destino: bancada reacondicional mobile."
                ),
            ),
            # K3QF = sub-família de K3Q para chips do tipo K3QFxFx0...
            # pn[3]='F' significa ~8Gb por die; pn[4] = número de dies.
            # Decodificação: pn[4] → K3QF_CAP (1=1GB, 2=2GB).
            # Prefixo 4 chars → vence K3Q (3 chars) ao mesmo priority=40.
            # ⚠ decode_density_type="" para suprimir DRAM_MOBILE em pn[3]='F'
            #   (que erroneamente retorna 16Gb=2GB para TODOS os K3QF).
            dict(
                prefix="K3QF", chip_type="LPDDR3", subtype="LPDDR3 Mobile",
                interface="LPDDR3", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="K3QF_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR3 Samsung alta-densidade (K3QF). "
                    "pn[4] = número de dies de 8Gb empilhados: 1=1GB · 2=2GB. "
                    "Padrão de PN: K3QFxFx0... (x repete). "
                    "⚠ 1GB (K3QF1...): LPDDR3 de baixo valor — sem liquidez B2B atual. Destino: resíduo (moagem/refino). "
                    "2GB (K3QF2...): reacondicional seletivo — checar demanda B2B antes. "
                    "Para K3QFx com x não mapeado: consultar Octopart/datasheet."
                ),
            ),
            dict(
                prefix="K3Q", chip_type="LPDDR3", subtype="LPDDR3 Mobile",
                interface="LPDDR3", decode_density_type="mobile",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR3 Samsung (~2013–2017). "
                    "Q = LPDDR3. Tensão: 1.2V. Velocidade: até 2133 Mbps. "
                    "Densidade: pn[3] → 2=2Gb(256MB) · 4=4Gb(512MB) · 8=8Gb(1GB) · G=16Gb(2GB). "
                    "⚠ K3QF... (pn[3]='F'): decodificado pela sub-família K3QF — pn[4] define o total. "
                    "Exemplos: K3Q2G30PC (256MB), K3Q8F30MB (1GB), K3QF2F20EM (2GB), K3QF1F10DM (1GB). "
                    "2GB (G): reacondicional seletivo — checar demanda B2B antes. "
                    "Destino: bancada reacondicional mobile."
                ),
            ),
            # K4E = Samsung LPDDR3 standalone (~2013-2016).
            # Capacidade: pn[3:5] — sufixo "E" identifica LPDDR3 nessa família.
            # Chaves: 8E=1GB · 6E=2GB · FE=3GB(raro) · BE=4GB.
            # 1GB (8E) → resíduo. 2GB+ → reacondicional se houver demanda.
            dict(
                prefix="K4E", chip_type="LPDDR3", subtype="LPDDR3 Mobile",
                interface="LPDDR3", is_emcp=False, active=True, priority=100,
                decode_density_type="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="K4E_CAP",
                tip=(
                    "LPDDR3 Samsung standalone (~2013–2016). "
                    "E = LPDDR3 (sufixo de geração). RAM pura — sem componente Flash. "
                    "Capacidade: pn[3:5] → 8E=1GB · 6E=2GB · FE=3GB · BE=4GB. "
                    "⚠ 1GB (8E): sem liquidez B2B atual → resíduo (moagem/refino). "
                    "2GB / 3GB / 4GB: avaliar demanda — bancada reacondicional mobile."
                ),
            ),
            dict(
                prefix="K4F", chip_type="LPDDR4", subtype="LPDDR4 Mobile",
                interface="LPDDR4", is_emcp=False, active=True, priority=100,
                decode_density_type="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="LPDDR4_CAP",
                tip=(
                    "LPDDR4 Samsung. Tensão I/O: 1.1V. RAM pura — sem componente Flash. "
                    "Capacidade: pn[3:5] → 4E=512MB · 8E=1GB · 6E=2GB · 7E=3GB · BE/HE/H6=4GB · CE/H7=8GB · HD=16GB. "
                    "⚠ 512MB e 1GB: sem liquidez B2B → resíduo (moagem/refino). "
                    "2GB+: bancada reacondicional mobile. "
                    "⚠ NÃO misturar soquetes com K4U/K3U (LPDDR4X, 0.6V) — tensão diferente."
                ),
            ),
            dict(
                prefix="K4U", chip_type="LPDDR4X", subtype="LPDDR4X Mobile",
                interface="LPDDR4X", is_emcp=False, active=True, priority=100,
                decode_density_type="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="LPDDR4_CAP",
                tip=(
                    "LPDDR4X Samsung. Tensão I/O: 0.6V. RAM pura — sem componente Flash. "
                    "Capacidade: pn[3:5] → 4E=512MB · 8E=1GB · 6E=2GB · 7E=3GB · BE/HE/H6=4GB · CE/H7=8GB · HD=16GB. "
                    "⚠ 512MB e 1GB: sem liquidez B2B → resíduo (moagem/refino). "
                    "2GB+: bancada reacondicional mobile. "
                    "⚠ NÃO misturar soquetes com K4F (LPDDR4, 1.1V) — tensão diferente."
                ),
            ),
            dict(
                prefix="K3U", chip_type="LPDDR4X", subtype="LPDDR4X Multi-Channel",
                interface="LPDDR4X", is_emcp=False, active=True, priority=40,
                decode_density_type="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="LPDDR4_CAP",
                tip=(
                    "LPDDR4X Multi-Channel Samsung. Tensão I/O: 0.6V. RAM pura — sem componente Flash. "
                    "Capacidade: pn[3:5] → BE/HE/H6=4GB · CE/H7=8GB · HD=16GB (mais comuns nesta família). "
                    "Exemplo confirmado: K3UH7H70MM-TFCL (H7=8GB). "
                    "⚠ NÃO misturar soquetes com K4F (LPDDR4, 1.1V) — tensão diferente. "
                    "Destino: bancada reacondicional mobile."
                ),
            ),
            dict(
                # K3L (3 chars) = fallback para qualquer K3L* que não seja K3KL ou K3LK.
                # priority=60 garante que K3KL e K3LK (priority=40, prefixo mais longo)
                # vencem no sort quando o PN começa com K3KL* ou K3LK*.
                prefix="K3L", chip_type="LPDDR5X", subtype="LPDDR5X",
                interface="LPDDR5X", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="LPDDR5_CAP",
                is_emcp=False, active=True, priority=60,
                tip=(
                    "LPDDR5X Samsung (família K3L). Velocidade: até 8533 Mbps. "
                    "VDDQ=0.5V — socket incompatível com LPDDR5 (0.9V). "
                    "Densidade em pn[4:6] → LPDDR5_CAP. "
                    "Destino: bancada reacondicional MOBILE. Tolerância zero para envio a resíduo."
                ),
            ),
            dict(
                prefix="K3KL", chip_type="LPDDR5", subtype="LPDDR5",
                interface="LPDDR5", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="LPDDR5_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR5 Samsung (maioria dos K3KL). VDDQ=0.9V típico — mas alguns SKUs são LPDDR5X (0.5V). "
                    "⚠ Sempre verificar sufixo/revisão antes de inserir no jig: K3KL8L/K3KL*EM podem ser LPDDR5X. "
                    "Velocidade: 6400 Mbps (sufixo CT). "
                    "Densidade em pn[4:6] → mapa LPDDR5_CAP: 9L=2GB(16Gb), 8L=4GB(32Gb), 5L=16GB(128Gb). "
                    "Códigos não mapeados: capacity=null — consultar datasheet. "
                    "Exemplos: K3KL9L90DM (2GB), K3KL8L80EM (4GB), K3KL5L50DM (16GB). "
                    "Destino: bancada reacondicional MOBILE (BGA mobile — socket diferente do DDR5 desktop)."
                ),
            ),
            dict(
                prefix="K3LK", chip_type="LPDDR5X", subtype="LPDDR5X",
                interface="LPDDR5X", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="LPDDR5_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "⚠ LPDDR5X (2021–presente). VDDQ=0.5V — RISCO DE QUEIMA no socket de LPDDR5 (0.9V). "
                    "Velocidade: 8533 Mbps (sufixo CP). Flagships Samsung (Galaxy S22+, S23, S24). "
                    "Densidade em pn[4:6] → mapa LPDDR5_CAP: BK=4GB(32Gb), 7K/CK=8GB(64Gb), 4K=12GB(96Gb). "
                    "Exemplos: K3LKBKB0BM (4GB), K3LK7K70BM (8GB), K3LK4K40CM (12GB). "
                    "Destino: bancada reacondicional MOBILE. Tolerância zero para envio a resíduo."
                ),
            ),

            # ═══ FLASH: eMMC ═════════════════════════════════════════════════
            dict(
                prefix="KLM", chip_type="eMMC", subtype="eMMC Samsung",
                interface="eMMC 5.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=50,
                tip=(
                    "eMMC Samsung — armazenamento Flash puro, sem RAM embutida. "
                    "Interface: eMMC 4.5 / 5.1. "
                    "Capacidade: pn[3] → 4=4GB, 8=8GB, A=16GB, B=32GB, C=64GB, "
                    "D=128GB, E=256GB, F=512GB, G=1TB. "
                    "Tipo NAND: pn[5] → 4=MLC, 8=TLC (TLC = maioria dos volumes modernos). "
                    "Geração eMMC: pn[6] → J=eMMC 5.1, F=eMMC 4.5. "
                    "Pacote: BGA153 ou BGA169 — verificar grid inferior. "
                    "Destino: bancada reacondicional Flash eMMC."
                ),
            ),

            # ═══ FLASH: UFS ══════════════════════════════════════════════════
            dict(
                prefix="KLU", chip_type="UFS", subtype="UFS Samsung",
                interface="UFS 3.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=50,
                tip=(
                    "UFS Samsung — armazenamento Flash puro, sem RAM embutida. "
                    "Interface serial Full-Duplex (vs eMMC paralelo) — NUNCA usar socket de eMMC. "
                    "Capacidade: pn[3] → B=32GB, C=64GB, D=128GB, E=256GB, F=512GB, G=1TB. "
                    "Versão UFS: pn[6] → V=UFS 3.1 (~2100 MB/s), U=UFS 2.1/3.0. "
                    "NAND: pn[4] → G=TLC (maioria dos volumes modernos). "
                    "Pacote: BGA153 (maioria) ou BGA254 (UFS 4.0 alta densidade). "
                    "Fisicamente idêntico ao eMMC KLM — única distinção: código a laser. "
                    "Destino: bancada reacondicional Flash UFS."
                ),
            ),

            # ── KLU*: sub-prefixos UFS Samsung (corrigem entradas com brand errado) ──
            # KLUDG foi historicamente cadastrado como Kioxia em add_chip_families.py.
            # K=Samsung, L=NAND standalone, U=UFS — a linha KLU inteira é Samsung.
            # Estes sub-prefixos (5 chars) têm priority=40 → testados antes do KLU
            # genérico (priority=50), garantindo match mais específico.
            # O upsert loop (prefix-only) migra brand=Kioxia → Samsung ao rodar --overwrite.
            dict(
                prefix="KLUDG", chip_type="UFS", subtype="UFS 2.1 Samsung",
                interface="UFS 2.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 2.1 Samsung — armazenamento Flash standalone. "
                    "⚠ NÃO confundir com Kioxia: KLU é linha Samsung (K=Samsung, L=NAND, U=UFS). "
                    "Capacidade: pn[3] → B=32GB, C=64GB, D=128GB, E=256GB, F=512GB, G=1TB. "
                    "pn[6]='U' confirma UFS 2.1/3.0 (vs V=UFS 3.1). "
                    "Interface UFS — NUNCA usar socket de eMMC. "
                    "Fisicamente similar ao KLM (eMMC) — única distinção: código a laser. "
                    "Destino: bancada reacondicional Flash UFS."
                ),
            ),
            dict(
                prefix="KLUCG", chip_type="UFS", subtype="UFS 2.0 Samsung",
                interface="UFS 2.0", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 2.0 Samsung — armazenamento Flash standalone. "
                    "K=Samsung, L=NAND, U=UFS, C=UFS 2.0. "
                    "Capacidade: pn[3] → B=32GB, C=64GB, D=128GB. "
                    "Destino: bancada reacondicional Flash UFS."
                ),
            ),
            dict(
                prefix="KLUFG", chip_type="UFS", subtype="UFS 3.1 Samsung",
                interface="UFS 3.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 3.1 Samsung — armazenamento Flash standalone, alta performance. "
                    "K=Samsung, L=NAND, U=UFS, F=UFS 3.1 (~2100 MB/s). "
                    "Capacidade: pn[3] → C=64GB, D=128GB, E=256GB, F=512GB, G=1TB. "
                    "Presente em flagships e mid-range premium (2020+). "
                    "Destino: bancada reacondicional Flash UFS."
                ),
            ),

            # ═══ eMCP: eMMC + LPDDR ══════════════════════════════════════════
            # Cada prefixo de 3 letras = geração diferente de RAM
            dict(
                prefix="KMJ", chip_type="eMCP", subtype="LPDDR2 + eMMC (legado)",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ eMCP Samsung LPDDR2 legado (~2013-2015). J = LPDDR2. "
                    "Capacidade típica: 8GB eMMC + 1GB RAM — sem valor comercial atual. "
                    "NÃO enviar para bancada reacondicional eMCP premium. "
                    "Destino: Fluxo de Resíduo (Caixa Vermelha)."
                ),
            ),
            dict(
                prefix="KMK", chip_type="eMCP", subtype="LPDDR2 + eMMC (legado)",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ eMCP Samsung LPDDR2 legado (~2010-2012). K = LPDDR2. "
                    "Capacidade típica: 8GB eMMC + 1GB RAM — sem valor comercial atual. "
                    "NÃO enviar para bancada reacondicional eMCP premium. "
                    "Destino: Fluxo de Resíduo (Caixa Vermelha)."
                ),
            ),
            dict(
                prefix="KMF", chip_type="eMCP", subtype="LPDDR3 + eMMC",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR3 + eMMC 5.1. F = LPDDR3. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP — range amplo (8GB a 128GB+). "
                    "⚠ Se o PN escaneado tiver mais de 10 chars, os últimos dígitos são "
                    "código de lote do operador (ex: -B213, AB213) — não fazem parte do PN do chip. "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),
            dict(
                prefix="KMN", chip_type="eMCP", subtype="LPDDR3 + eMMC",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR3 + eMMC 5.1. N = LPDDR3. "
                    "Família paralela ao KMQ (~2014-2017). "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),
            dict(
                prefix="KMQ", chip_type="eMCP", subtype="LPDDR3 + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR3 + eMMC 5.1. Q = LPDDR3. "
                    "Família de maior volume na esteira (~2015-2019). "
                    "Dispositivos: Galaxy J-series, A-series entrada e mid-range. "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),
            dict(
                prefix="KMR", chip_type="eMCP", subtype="LPDDR4/4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=12,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR4/4X + eMMC 5.1. "
                    "R = LPDDR4/4X confirmado (Galaxy A7 2017, A8 2018). "
                    "Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMS", chip_type="eMCP", subtype="LPDDR4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR4X + eMMC 5.1. S = LPDDR4X. "
                    "Transição KMR → KMS (~2018-2021). "
                    "Dispositivos: Galaxy A-series mid-range 2018-2020. "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),

            # ═══ eMCP LPDDR4: KM4 ════════════════════════════════════════════
            # Samsung usou o dígito '4' na 3ª posição para indicar LPDDR4
            # (vs letras nas famílias clássicas: Q=LPDDR3, R=LPDDR4/4X, S=LPDDR4X).
            # decode_gen_pos=None OBRIGATÓRIO: '4' não está em SAM_EMCP_GEN,
            # causaria "tipo '4' — consultar datasheet" (Frankenstein).
            # Engine corrigido: fallback isdigit() extrai tipo RAM do subtype.
            # Capacidade via SAM_EMCP_CAP (ex: X6=32GB+2GB, confirmado Octopart).
            dict(
                prefix="KM4", chip_type="eMCP", subtype="LPDDR4 + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR4 + eMMC 5.1. "
                    "KM4 = linha eMCP onde '4' na 3ª posição indica LPDDR4 "
                    "(não confundir com a letra R=LPDDR4/4X das séries KMR). "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP (ex: X6=32GB+2GB). "
                    "Dispositivos: smartphones mid-range Samsung e OEMs (~2018-2021). "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),

            # ═══ eMCP LPDDR4X: KMD ═══════════════════════════════════════════
            # ATENÇÃO: KMD é eMCP (eMMC + LPDDR4X), NÃO uMCP.
            # A letra D na 3ª posição indica LPDDR4X, mas o armazenamento é eMMC 5.1.
            # Samsung uMCP (UFS) começa a partir de KMG (UFS 3.1, 2020+).
            # Dispositivos confirmados: Galaxy A12 (KMDD60018M), A22/A32 (KMDH60013M).
            # Erro anterior: catalogado como UFS 2.1 → operador enviava para resíduo.
            dict(
                prefix="KMD", chip_type="eMCP", subtype="LPDDR4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR4X + eMMC 5.1. "
                    "D = LPDDR4X (Galaxy A12, A22, A32 — entrada/mid-range 2020-2022). "
                    "NÃO confundir com uMCPs KMG/KML que usam UFS. "
                    "Destino: bancada reacondicional eMCP.",
            ),

            # ═══ uMCP: UFS + LPDDR ═══════════════════════════════════════════
            # uMCP (Universal Multi-Chip Package) combina armazenamento UFS com
            # LPDDR em um único package. Interface UFS é incompatível com sockets
            # eMMC — sinalizar claramente na bancada.
            #
            # O SAM_EMCP_CAP cobre uMCPs também: Samsung reutiliza a mesma
            # codificação de capacidade em posições 3-4 para ambas as linhas.
            # Apenas a interface (UFS vs eMMC) e o tipo RAM diferem por família.
            #
            # Destino correto: bancada reacondicional uMCP — NÃO resíduo.
            # uMCPs são chips modernos com alta demanda no mercado de reparos.
            dict(
                prefix="KMG", chip_type="uMCP", subtype="UFS 3.1 + LPDDR4X",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "uMCP Samsung UFS 3.1 (~1200 MB/s) + LPDDR4X (0.6V) — mid-range 5G, 2020-2022. "
                    "G = LPDDR4X confirmado. Dispositivos: Galaxy A32/A52/A72 5G. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP (ex: D6=32GB+3GB, T6=64GB+4GB). "
                    "Socket UFS — incompatível com eMMC KLM/KLU. "
                    "Destino: bancada reacondicional uMCP."
                ),
            ),
            dict(
                prefix="KML", chip_type="uMCP", subtype="UFS 3.1 + LPDDR5",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "uMCP Samsung UFS 3.1 (~1200 MB/s) + LPDDR5 (0.9V) — high-end, 2021-2022. "
                    "L = LPDDR5 confirmado. Dispositivos: Galaxy S21 série, S21 FE. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP (ex: K6=128GB+8GB, L6=256GB+8GB). "
                    "Alta demanda no mercado de reparo — NÃO enviar para resíduo. "
                    "Destino: bancada reacondicional uMCP (Premium)."
                ),
            ),
            # ── KM + DÍGITO: uMCP linha numérica Samsung (2020+) ─────────────────
            # Samsung usa 3ª posição NUMÉRICA em uMCPs premium modernos.
            # KM1, KM2, KM5, KM8 são confirmados na esteira — NÃO são eMCP.
            #
            # Regra de ouro: KM + LETRA = eMCP/uMCP (series clássicas: KMQ, KMR…)
            #                KM + DÍGITO = uMCP premium (UFS + LPDDR4X/5X, flagships)
            #
            # decode_gen_pos=None OBRIGATÓRIO: o dígito (1/2/5/8) não é letra de
            # geração RAM — SAM_EMCP_GEN só contém letras. Sem isso o engine
            # produz "tipo '8' — consultar datasheet" (Frankenstein de texto).
            #
            # decode_cap_map=SAM_EMCP_CAP: pn[3:5] segue o mesmo esquema dos
            # eMCPs clássicos. Chaves confirmadas pelo fabricante (ver SAM_EMCP_CAP):
            #   V8=128GB+4GB · C7=64GB+4GB · L9=128GB+6GB · F9=256GB+8GB · F8=256GB+12GB.
            # Capacidades variam por sub-variante — o Gemini completa se necessário.
            #
            # ⚠ OCR ALERT: distribuidores confundem '1' (um) com 'I' (i maiúsculo).
            # Ex: KM8V700IJA na tela → correto: KM8V7001JA no chip físico.
            # Operador deve conferir o PN diretamente na peça antes de registrar.
            dict(
                prefix="KM8", chip_type="uMCP", subtype="UFS + LPDDR4X/5X (alta densidade)",
                interface="UFS", pn_length=10,
                is_emcp=True, active=True, priority=40,
                # decode_gen_pos OMITIDO: pn[2]='8' é dígito numérico da família,
                # NÃO é letra de geração RAM — SAM_EMCP_GEN só contém letras.
                # Incluir decode_gen_pos causaria fallback "tipo '8' — consultar datasheet".
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung linha numérica KM8 — chip PREMIUM. "
                    "Interface UFS (NÃO eMMC). RAM: LPDDR4X ou LPDDR5X. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP (ex: V8=128GB+4GB, F9=256GB+8GB). "
                    "ATENÇÃO OCR: robôs confundem '1' com 'I' nesses PNs — "
                    "ex: KM8V700IJA na tela pode ser KM8V7001JA no chip físico. "
                    "Conferir o PN diretamente na peça antes de registrar. "
                    "Destino: bancada reacondicional uMCP (Premium)."
                ),
            ),
            dict(
                prefix="KM5", chip_type="uMCP", subtype="UFS + LPDDR4X/5X (alta densidade)",
                interface="UFS", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung linha numérica KM5 — chip PREMIUM. "
                    "Interface UFS (NÃO eMMC). RAM: LPDDR4X ou LPDDR5X. "
                    "Alta densidade — valor comercial elevado. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP. "
                    "ATENÇÃO OCR: mesma família de KM8, mesma regra: conferir "
                    "PN físico no chip antes de registrar. "
                    "Destino: bancada reacondicional uMCP (Premium)."
                ),
            ),
            dict(
                prefix="KM2", chip_type="uMCP", subtype="UFS 3.1 + LPDDR5 (ultra-premium)",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung linha numérica KM2 — chip ULTRA-PREMIUM. "
                    "Interface UFS 3.1 (~2100 MB/s) + LPDDR5 — NUNCA eMMC. "
                    "Presente em flagships Galaxy S21/S22 e topo-de-linha Android (2021-2023). "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP (ex: V8=128GB+4GB, F9=256GB+8GB). "
                    "Valor comercial MUITO ELEVADO — NÃO enviar para resíduo ou eMMC. "
                    "ATENÇÃO OCR: '1' confundido com 'I' nesses PNs — conferir PN físico. "
                    "Destino: bancada reacondicional uMCP (Premium Tier 1)."
                ),
            ),
            dict(
                prefix="KM1", chip_type="uMCP", subtype="UFS 4.0 + LPDDR5X (ultra-premium)",
                interface="UFS 4.0", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung linha numérica KM1 — chip ULTRA-PREMIUM. "
                    "Interface UFS 4.0 (~4200 MB/s) + LPDDR5X — geração mais recente (2023+). "
                    "Presente em flagships Galaxy S23/S24. "
                    "Capacidade: pn[3:5] → mapa SAM_EMCP_CAP. "
                    "Valor comercial MUITO ELEVADO — NÃO enviar para resíduo ou eMMC. "
                    "ATENÇÃO OCR: '1' confundido com 'I' nesses PNs — conferir PN físico. "
                    "Destino: bancada reacondicional uMCP (Premium Tier 1)."
                ),
            ),

            # KMV2 e KMV3 são uMCPs flagship (UFS 4.0 + LPDDR5X).
            # Prefixo de 4 chars → priority=30 (verificado antes de KMV de 3 chars).
            # decode_gen_map obrigatório: sem ele, V cai no fallback EMCP_RAM_TYPES['V']
            # = "LPDDR2 (legado)" — erro gravíssimo para chips de 2022+.
            dict(
                prefix="KMV2", chip_type="uMCP", subtype="UFS 4.0 + LPDDR5X",
                interface="UFS 4.0", pn_length=10,
                is_emcp=True, active=True, priority=30,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung UFS 4.0 (~4200 MB/s) + LPDDR5X (0.5V) — flagship 2022+. "
                    "LPDDR5X: VDDQ=0.5V — socket incompatível com LPDDR5 (0.9V). "
                    "Dispositivos: Galaxy S22 série. "
                    "NÃO confundir com KMV legado (LPDDR2 + eMMC, 2010-2013). "
                    "Destino: bancada reacondicional uMCP (Premium)."
                ),
            ),
            dict(
                prefix="KMV3", chip_type="uMCP", subtype="UFS 4.0 + LPDDR5X",
                interface="UFS 4.0", pn_length=10,
                is_emcp=True, active=True, priority=30,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="uMCP Samsung UFS 4.0 + LPDDR5X (flagship ultra, 2022+). "
                    "Dispositivos: Galaxy S22 Ultra, S23 série. "
                    "Destino: bancada reacondicional uMCP (Premium).",
            ),

            dict(
                # KMV = eMCP legado (2010-2013): LPDDR2 + eMMC.
                # ── KMV: PREFIXO COMPARTILHADO — trava obrigatória ──────────────
                # KMV + LETRA (ex: KMVY..., KMVL...) = eMCP LEGADO LPDDR2 (~2010-2013).
                # KMV + DÍGITO (KMV2..., KMV3...) = uMCP flagship LPDDR5X (2022+).
                # KMV2/KMV3 têm priority=30 → testados ANTES deste entry (priority=40).
                # decode_gen_pos=None: SAM_EMCP_GEN['V']="LPDDR5/5X" — errado para legado.
                # RAM type documentado no tip; campo emcp_ram fica nulo (aceitável).
                # Dispositivo confirmado: KMVYL000LM (Galaxy S3 Mini, 8GB + 1GB LPDDR2).
                prefix="KMV", chip_type="eMCP", subtype="LPDDR2 + eMMC (legado)",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ KMV LEGADO — eMCP LPDDR2 + eMMC (~2010-2013). "
                    "Regra de separação: KMV + LETRA = este entry (legado LPDDR2). "
                    "KMV + DÍGITO (KMV2.../KMV3...) = uMCP flagship LPDDR5X 2022+ (entry separado). "
                    "Dispositivo de referência: Galaxy S3 Mini (KMVYL000LM — 8GB + 1GB LPDDR2). "
                    "LPDDR2 sem liquidez comercial em 2026. "
                    "Destino: Fluxo de Resíduo (Caixa Vermelha)."
                ),
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

            # ═══ FLASH BASE: NAND Raw ═════════════════════════════════════════
            # K9 = Samsung NAND Flash. 3ª letra indica tecnologia de célula:
            #   F = SLC (Single-Level Cell) — maior durabilidade, menor densidade
            #   G = MLC (Multi-Level Cell) — uso geral
            #   H = MLC (variante Large Page)
            #   K = SLC/MLC (Mixed)
            #   L = MLC / TLC (baixo custo)
            #   W = SLC (White Label / industrial)
            #   X = MLC expandido
            #   Z = MLC/TLC (especial)
            # Decode de densidade: 4ª+5ª letra indicam densidade em bits
            #   (ex: AG=16Gb, BG=32Gb, CG=64Gb). Não mapeado na gramática por
            # variabilidade — usar Gemini ou Nexar para confirmar capacidade.
            dict(
                prefix="K9F", chip_type="NAND Flash", subtype="Samsung SLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9F = Samsung NAND Flash SLC. Alta durabilidade (~100K ciclos P/E). "
                    "Capacidade: 4ª+5ª letra (ex: 1G=1Gbit=128MB, 2G=2Gbit=256MB). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9G", chip_type="NAND Flash", subtype="Samsung MLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9G = Samsung NAND Flash MLC. Uso geral. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9H", chip_type="NAND Flash", subtype="Samsung MLC NAND (Large Page)",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9H = Samsung NAND Flash MLC Large Page. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9K", chip_type="NAND Flash", subtype="Samsung SLC/MLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9K = Samsung NAND Flash (SLC/MLC misto). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9L", chip_type="NAND Flash", subtype="Samsung MLC/TLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9L = Samsung NAND Flash MLC/TLC. Custo reduzido. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9W", chip_type="NAND Flash", subtype="Samsung SLC NAND (Industrial)",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9W = Samsung NAND Flash SLC (variante industrial/white label). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9X", chip_type="NAND Flash", subtype="Samsung MLC NAND (Expandido)",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9X = Samsung NAND Flash MLC expandido. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9Z", chip_type="NAND Flash", subtype="Samsung MLC/TLC NAND (Especial)",
                interface="", is_emcp=False, active=True, priority=80,
                tip="K9Z = Samsung NAND Flash MLC/TLC variante especial. "
                    "Verificar datasheet para densidade. "
                    "Destino: bancada reacondicional Flash.",
            ),

            # ═══ FLASH BASE: NOR / Mask ROM ══════════════════════════════════
            # K5D = Samsung OneNAND — NAND Flash com interface NOR (chip monolítico).
            # NÃO é MCP nem tem SRAM separado. O "12" em K5D1G12ACD é código de
            # organização (x16 bus / 2 planos), não capacidade de segundo componente.
            # Capacidade: pn[3:5] — ex: "1G" = 1Gb = 128MB, "2G" = 2Gb = 256MB.
            # Origem: smartphones/feature phones pré-2012. Destino: resíduo.
            dict(
                prefix="K5D", chip_type="OneNAND", subtype="Samsung OneNAND Flash",
                interface="NOR (async)", is_emcp=False, active=True, priority=60,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="DRAM_PC",
                tip=(
                    "OneNAND Samsung — NAND Flash com interface NOR-compatível. "
                    "Chip monolítico: NÃO separar componentes, NÃO confundir com MCP NOR+SRAM. "
                    "Capacidade típica: 128MB (1Gb) a 1GB (8Gb). Era: 2005–2012. "
                    "Destino: fluxo de resíduo (moagem/refino). Sem liquidez B2B."
                ),
            ),
            dict(
                prefix="K5", chip_type="NOR Flash", subtype="Samsung NOR Flash",
                interface="", is_emcp=False, active=True, priority=100,
                tip="NOR Flash Samsung. Verificar demanda semanal antes de direcionar.",
            ),
            dict(
                prefix="K7", chip_type="SRAM", subtype="Samsung SRAM",
                interface="", is_emcp=False, active=True, priority=100,
                tip=(
                    "SRAM Samsung (K7). Memória estática legado — redes, DSP, embarcado (anos 90/2000). "
                    "Sem liquidez B2B para recondicionamento mobile. "
                    "Destino: fluxo de resíduo (moagem/refino)."
                ),
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
