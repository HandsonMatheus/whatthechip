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

    # Famílias removidas da gramática mas que podem ainda existir no banco.
    # Listadas aqui para que --overwrite as apague automaticamente.
    # Adicionar sempre que uma família for removida do código.
    OBSOLETE_FAMILY_PREFIXES = [
        "KMV2",  # Removida 2026-05-13: premissa falsa (uMCP LPDDR5X). KMV2... são eMCP legado.
        "KMV3",  # Removida 2026-05-13: KMV3W000LM-B310 = Galaxy S4 eMCP (2013), não uMCP 2022+.
    ]

    # Chaves de decode map removidas do código mas que podem ainda existir no banco.
    # Tuplas (map_name, key, motivo). Removidas com --overwrite.
    OBSOLETE_DECODE_KEYS = [
        # L6 bloqueado 2026-05-28: âncora "KMFL6·/S21 FE" é falsa.
        # KMDL6001DA e KMFL6· = zero resultados em semiconductor.samsung.com.
        # S21 FE usa KM8-series (UFS uMCP), não eMCP KMF. Sem PN Tier 1 confirmado.
        ("SAM_EMCP_CAP", "L6", "Âncora KMFL6·/S21 FE falsa — KMDL6001DA inexistente em Samsung Global"),
    ]

    def _run(self, dry, overwrite=False):
        from chips.models import Brand, ChipFamily, DecodeMap

        # ── Limpeza de famílias obsoletas ─────────────────────────────────────
        if overwrite:
            for prefix in self.OBSOLETE_FAMILY_PREFIXES:
                qs = ChipFamily.objects.filter(prefix=prefix)
                if qs.exists():
                    if not dry:
                        qs.delete()
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {'[DRY] ' if dry else ''}🗑  Família obsoleta removida: {prefix}"
                        )
                    )

        # ── Limpeza de chaves de decode map obsoletas ──────────────────────────
        if overwrite:
            for map_name, key, motivo in self.OBSOLETE_DECODE_KEYS:
                qs = DecodeMap.objects.filter(map_name=map_name, char_key=key)
                if qs.exists():
                    if not dry:
                        qs.delete()
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {'[DRY] ' if dry else ''}🗑  DecodeMap obsoleto removido: {map_name}[{key!r}] — {motivo}"
                        )
                    )

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
        # O mapa anterior tinha apenas 8 entradas, deixando a maioria dos PNs sem
        # capacidade decodificada (ex: KMQ310006A → chave "31" não existia).
        emcp_cap = [
            # ── Matriz direta (legado, 2012-2017) ────────────────────────────
            ("LL", "4GB",   "1GB"),    # 4GB NAND + 1GB RAM   (KMKLL000UM-B406 — HTC EVO 3D, teardown GlobalSpec/Electronics360 Ago/2011 ✓)
            #                          # "MCP Samsung KMKLL000UM-B406: 4GB eMMC NAND + 1GB Mobile DDR" — documentado em esquema elétrico.
            #                          # KMMLL000QM-B503 usa a mesma chave LL mas com 768MB (die de 6Gb customizado).
            #                          # Conflito: mapa base mantido em 1GB (KMK, teardown verificado);
            #                          # KMMLL000QM (768MB) corrigido via fix_known_parts.py com create=True.
            ("JS", "4GB",   "512MB"),  # 4GB NAND + 512MB RAM  (KMSJS000KM — Galaxy Centura SCH-S738C 2013, LPDDR1)
            ("11", "4GB",   "512MB"),  # 4GB NAND + 512MB RAM
            ("5U", "4GB",   "512MB"),  # 4GB NAND + 512MB RAM  (KMN5U000FM-B203: 4Gb LPDDR2 — Jotrin ✓;
            #                          #                         KMK5U000VM-B309 — Censtry ✓)
            ("JW", "4GB",   "768MB"),  # 4GB NAND + 768MB RAM (6Gb LPDDR3)
            #                          # KMFJW0007M-B212 (Alibaba: "4GB+6GB 32dram MV MLC LPDDR3") ✓
            #                          # Galaxy J1 LTE (SM-J100 LTE): 768MB RAM + 4GB storage — device spec ✓
            #                          # 6Gb = densidade não-padrão. Samsung custom die para ultra entry-level.
            ("72", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM
            ("7U", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM   (KMK7U000VMB) — confirmado usuário
            ("7X", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM   (KMQ7X000SA-B315) — Preduo B2B: "8+8" ✓ (2026-05-25)
            #                          # CORRIGIDO: estava 1.5GB (12Gb) por analogia com die 6Gb de KMQ310006B — errado.
            #                          # Preduo e Alibaba confirmam 8Gb LPDDR3 = 1GB. "32dram" = barramento 32-bit.
            ("82", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM (16Gb LPDDR3)
                                       # Âncora: KMR820001M-B609 — Preduo ✓ "16+16" + Puris ✓ "16+16 221ball eMCP-D3" (2026-05-29).
                                       # Wileyfox Swift (Snapdragon 410, 2015) = 16GB + 2GB RAM — aparelho com KMR820001M-B609 ✓.
                                       # CORRIGIDO de 1GB: entrada original sem âncora documentada.
            ("IS", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM   (KMVIS000LM) — Galaxy S2 i9100, confirmado IA externa
            ("TU", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM   (KMVTU000LM) — Galaxy S3 i9300, confirmado IA externa
            ("3W", "16GB",  "512MB"), # 16GB NAND + 512MB RAM (KMV3W000LW ✓ chip físico 2026-05-13; Galaxy S4 I9500 era)
            #                          # 4Gbit LPDDR2 = 512MB. KMV3 = eMCP legado, NÃO uMCP. Destino: resíduo.
            ("31", "16GB",  "1GB"),     # 16GB NAND + 1GB RAM (8Gb)
            #                          # KMQ310013B: chip físico confirmado (eMiner esteira 2026-05-13) + AI service manual ✓
            #                          # ⚠ CONFLITO DE SHARED KEY:
            #                          #   KMQ310006B-B419 (Galaxy J3 SM-J327A): samsungparts.com "16Gb+12" = 1.5GB.
            #                          #   KMQ310013B: chip físico = 1GB.
            #                          # Mapa mantido em 1GB (KMQ310013B, mais comum na esteira).
            #                          # KMQ310006B (1.5GB) corrigido via fix_known_parts.py.
            ("21", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM
            ("4Z", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KMQ4Z0013MB) — fonte: histórico banco
            ("41", "32GB",  "4GB"),    # 32GB NAND + 4GB RAM
            # ── Alfanumérico geração 1 (2017-2019) ───────────────────────────
            # 5X: BLOQUEADO 2026-05-09. Sem PN físico confirmado ("KMQ5X·" é wildcard especulativo).
            #     ⚠ Dead-end: sem Gemini, chips com 5X ficam com capacidade nula. Adicionar quando
            #     PN físico confirmar — usar fix_known_parts com create=True como workaround pontual.
            # ("5X", "8GB",   "1GB"),
            ("8X", "16GB",  "1GB"),    # 16GB NAND + 1GB RAM   — CORRIGIDO 2026-05-09 (era 8GB)
            #                          # KMQ8X000SA-B414: 16GB eMMC 5.1 + 8Gb (1GB) LPDDR3 ✓
            #                          # KMR8X0001M-B608: 16GB eMMC + 16Gb (2GB) LPDDR3 (variante RAM)
            #                          # NAND=16GB confirmado em ambos. RAM=1GB (KMQ-base).
            #                          # KMR8X variante (2GB) tratada em fix_known_parts.py.
            ("NW", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMQNW000SM-B316) — confirmado ✓
            ("N1", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMQN10006B ✓ chip físico 2026-05-13; KMFN10012A-B214 — Censtry: 8Gb LPDDR3 ✓)
            ("N6", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMFN60012MB214) — Octopart: 8Gb LPDDR3 ✓
            ("NX", "8GB",   "1GB"),    # 8GB NAND + 1GB RAM    (KMFNX0012) — chip físico na esteira eMiner 2026-05-22 ✓
                                       # Desbloqueado: KMFNX0012 confirmado fisicamente (era pendente chip físico desde 2026-05-09).
            ("E1", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   (KMQE10013M) — Galaxy J5/J7, Moto G
            ("BT", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   (KMQBT·)
            ("V7", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   alias BT
            ("V8", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  (KM5V8001DM-B622 — fabricante: 32Gb÷8=4GB)
            #                          # ⚠ CORRIGIDO: entrada anterior dizia 8GB (fonte: AI sem confirmação).
            #                          # KM8V8001JM também é 4GB — cap_key compartilhado.
            #                          # ⚠ CONFLITO SHARED KEY 2026-05-27: KM2V8001CM-B707 = V8 mas 48Gb = 6GB!
            #                          #   KM5/KM8 com V8 = 32Gb = 4GB ✓ (Samsung Semiconductor Global)
            #                          #   KM2V8001CM com V8 = 48Gb = 6GB ✓ (Preduo "128+48", Amazon "6G-4266Mbps")
            #                          #   Mapa mantido em 4GB (âncora KM5 confirmada). KM2V8001CM → fix_known_parts.
            ("GD", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   (KMQGD·)
            ("W7", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   alias GD
            ("W8", "32GB",  "4GB"),    # 32GB NAND + 4GB RAM   (KMFW8·)
            ("X1", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KMQX10013MB — Octopart: 32GB+16Gb)
                                       # ⚠ KMR DIVERGE: família KMR usa 3GB(24Gb) para X1.
                                       #   Confirmado: KMRX1000BM-B614T07 = 3GB — Octopart ✓ + UFI Box ✓ (2026-05-29).
                                       #   Chips KMR+X1 → corrigidos individualmente em fix_known_parts.py.
            ("H9", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   alias X1 (corrigido junto, sem PN independente)
            ("C6", "64GB",  "4GB"),    # 64GB NAND + 4GB RAM   (KMDC6001DM-B625) — Samsung Semiconductor oficial ✓ (2026-05-25)
            #                          # 32Gb LPDDR4X = 4GB. Corrigido: estava 3GB (24Gb) baseado em IA+padrão — errado.
            #                          # Samsung official: semiconductor.samsung.com/mcp/model/.../kmdc6001dm-b625/
            ("C1", "64GB",  "4GB"),    # 64GB NAND + 4GB RAM   (KMRC10014M) — Oppo R9 / mid-premium, confirmado IA externa
            ("M4", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  (KMQM4·)
            ("J2", "128GB", "6GB"),    # 128GB NAND + 6GB RAM  (KMQJ2·)
            #                          # ⚠ CONFLITO KMN: para a família KMN (LPDDR2, 2011-2014) a chave "J2"
            #                          # em pn[3:5] NÃO é 128GB+6GB — é um chip entry-level de era antiga.
            #                          # Ex: KMNJ2000ZM-B207 → provavelmente 8GB eMMC + 1GB LPDDR2 (AI estima,
            #                          # sem fonte Tier 1 confirmada). NÃO alterar o mapa — âncora KMQJ2 = 128GB+6GB ✓.
            #                          # Família KMN foi corrigida: decode_cap_pos=None → não usa este mapa.
            ("P5", "256GB", "8GB"),    # 256GB NAND + 8GB RAM  (KMQP5·)
            # ── Alfanumérico geração 2 (2020-2022, padrão [X]6) ──────────────
            # Sufixo "6" identifica a geração de empacotamento (eMMC 5.1 rev B)
            # Fonte: teardowns Galaxy A21s/A31/A41/A51/A72 + KMD/KML uMCP
            ("D6", "32GB",  "3GB"),    # 32GB NAND + 3GB RAM   (KMQD60013M ✓ chip físico 2026-05-13; KMQD6·, KMRD6·)
            ("E6", "16GB",  "2GB"),    # 16GB NAND + 2GB RAM   KMQE60013M-B318 (Octopart) ✓
            #                          # ⚠ CORRIGIDO 2026-05-09: era alias de D6 (32GB+3GB) — ERRADO.
            #                          # KMQE60013M-B318 = 16GB eMMC 5.1 + 16Gb LPDDR3 → 16Gb÷8=2GB.
            # ("G6", ...),             # BLOQUEADO 2026-05-09: zero PNs confirmados em Octopart/datasheet.
            #                          # Gemini alucinava KMDG6001BM com confiança — rejeitado (fonte AI sem evidência física).
            ("V6", "128GB", "4GB"),    # 128GB NAND + 4GB RAM  KMDV6001DA-B620 (Octopart) ✓
            #                          # ⚠ CORRIGIDO 2026-05-09: era alias de D6 (32GB+3GB) — ERRADO.
            #                          # KMDV6001DA-B620: Octopart = 128GB eMMC + 32Gb LPDDR4X → 32Gb÷8=4GB ✓
            #                          # KMDV6001DB-B625: Preduo + Amazon = "128+32" (128GB+32Gb=4GB) ✓ (2026-05-26)
            #                          # Revisão A→B: controladora/package revision — capacidade idêntica.
            # ("U6", ...),             # BLOQUEADO 2026-05-09: zero PNs confirmados. Fonte era Gemini-only.
            ("X6", "32GB",  "2GB"),    # 32GB NAND + 2GB RAM   (KM4X6001KM) — confirmado Octopart; era alias especulativo U6
            # ("T6", ...),             # BLOQUEADO 2026-05-09: zero PNs confirmados. Fonte era catálogo asiático não verificado.
            # ("Y6", ...),             # BLOQUEADO 2026-05-09: zero PNs confirmados. Fonte era Gemini-only.
            ("H6", "64GB",  "4GB"),    # KMRH60014A (A7 2017, KMR): H=64GB, confirmado ✓
            #                          # + KMDH6001DM-B422 (KMD/LPDDR4X): Octopart "64GB+32Gb=4GB LPDDR4X-3733" ✓ (2026-05-25)
            ("P6", "64GB",  "4GB"),    # KMDP6001DA-B425: 64GB eMMC 5.1 + 32Gb LPDDR4X → 32Gb÷8=4GB ✓
            #                          # ⚠ REVERTIDO 2026-05-09: sessão anterior havia mudado para 3GB priorizando
            #                          # KMGP6001BM (KMG/LPDDR3, 24Gb=3GB). Confirmação agora: KMDP6001DA-B425
            #                          # (família primária KMD) = 4GB — 4GB é o valor correto para o mapa base.
            #                          # Chips KMG com P6 (LPDDR3, 3GB) são exceção rara — corrigidos via fix_known_parts (create=True).
            ("P8", "64GB",  "4GB"),    # KM5P8001DM-B424: 64GB UFS2.1 + 32Gb LPDDR4X-4266 → 32Gb÷8=4GB
            #                          # semiconductor.samsung.com/us/mcp/model/lpddr5-umcp/km5p8001dm-b424/ ✓
            ("P9", "64GB",  "4GB"),    # KM5P9001DMB424: 64GB UFS 2.1 + 32Gb LPDDR4X-4266 (Octopart)
            #                          # 32Gb ÷ 8 = 4GB. uMCP linha numérica KM5 (mid-premium 2021+).
            # Z6: BLOQUEADO — evidência insuficiente. ⚠ Dead-end sem Gemini: chips Z6 ficam com capacidade nula.
            # L6: BLOQUEADO 2026-05-28. Âncora "KMFL6·, uMCP S21 FE" é FALSA:
            #   • KMDL6001DA — zero resultados em semiconductor.samsung.com (pesquisado 2026-05-28).
            #   • KMFL6·    — zero resultados. PN âncora não existe no catálogo Samsung.
            #   • "S21 FE"  — usa KM8-series (UFS+LPDDR4X uMCP), NÃO eMCP LPDDR3 KMF.
            #   Conclusão: chave inserida com dois erros de premissa. Sem PN Tier 1 confirmado.
            #   ⚠ Dead-end: chips L6 ficam com capacidade nula até PN físico confirmar.
            # ("L6", "256GB", "8GB"),
            # ── uMCP high-cap (2021+, LPDDR5/5X, flagships) ──────────────────
            # A partir daqui os códigos são derivados por engenharia de padrão +
            # dados de teardown. Verificar com PN real antes de usar como referência.
            ("K6", "128GB", "8GB"),    # 128GB NAND + 8GB RAM  (uMCP high-cap — âncora sem PN confirmado Tier 1)
            #                          # ⚠ CORRIGIDO 2026-05-27: atribuição "KML·, S21 Exynos" era FALSA.
            #                          # KML = eMCP legado LPDDR1 (~2013-2015), NÃO uMCP moderno.
            #                          # Galaxy S21 Exynos usa KM8-series (KM8V8001LM-B813 ✓).
            #                          # K6 bloqueado como especulação até PN Tier 1 confirmar.
            # ── uMCP linha numérica KM5/KM8/KM2 (confirmados pelo fabricante) ──────
            ("C7", "64GB",  "4GB"),    # KM5C7001DM-B622: 64GB UFS2.1 + 32Gb÷8=4GB LPDDR4X ✓
            ("L9", "128GB", "8GB"),    # KM8L9001JM-B624: 128GB UFS2.2 + 64Gb÷8=8GB LPDDR4X (Samsung Electronics ✓)
            #                          # ⚠ CORRIGIDO 2026-05-09: era 6GB (fonte: KM2L9001CM-B518, "Fabricante ✓" não verificado).
            #                          # Confirmação definitiva: Samsung Electronics KM8L9001JM-B624 = 64Gb LPDDR4X-4266 → 8GB.
            #                          # ⚠ CONFLITO PROFUNDO DE SHARED KEY — quatro variantes confirmadas por fonte Tier 1:
            #                          #   KM8L9001JM-B624 = 8GB (64Gb) → base do mapa ✓ (Samsung Electronics)
            #                          #   KM2L9001CM-B518 = 6GB (48Gb) → Octopart ✓ (2026-05-25) → fix_known_parts
            #                          #   KM5L9000CM-B424 = 6GB (48Gb) → Samsung Semiconductor Global ✓ (2026-05-25) → fix_known_parts
            #                          #   KM5L9001DM-B424 = 4GB (32Gb) → Samsung Semiconductor Global ✓ (2026-05-25) → fix_known_parts
            #                          # NOTA: dentro da família KM5, mesmo cap_key "L9" → RAM diferente por variante:
            #                          #   pn[7]="0" (KM5L9000x) = 48Gb = 6GB; pn[7]="1" (KM5L9001x) = 32Gb = 4GB.
            #                          # O decode 2-char pn[3:5] NÃO distingue essas variantes. Cada PN KM5L9 é exceção pontual.
            #                          # NÃO alterar o mapa — base KM8=8GB está correta para a maioria.
            ("F9", "256GB", "8GB"),    # KM8F9001JM-B813: 256GB UFS2.2 + 64Gb÷8=8GB LPDDR4X ✓
            ("F8", "256GB", "12GB"),   # KM8F8001MM-B813: 256GB UFS2.1 + 96Gb÷8=12GB LPDDR4X ✓
            #                          # ⚠ CONFLITO SHARED KEY 2026-05-28: KM8F8001JA/JM = 256GB+8GB (64Gb)
            #                          #   KM8F8001LM = 256GB+10GB (80Gb) — todos usam F8 mas RAM diferente.
            #                          # Mapa mantido em 12GB (âncora MM = maior densidade = referência conservadora).
            #                          # JA/JM/LM corrigidos via fix_known_parts.
            # ── uMCP KM8V variantes de velocidade e densidade ────────────────
            ("V7", "128GB", "8GB"),    # KM8V7001JM-B810: 128GB UFS2.1 + 64Gb÷8=8GB LPDDR4X-3733 ✓
            #                          # Confirmado Samsung Semiconductor Global 2026-05-28.
            ("V9", "128GB", "8GB"),    # KM8V9001JM-B813: 128GB UFS2.2 + 64Gb÷8=8GB LPDDR4X-4266 ✓
            #                          # Confirmado Samsung Semiconductor Global 2026-05-28.
            # ── uMCP KM5H variantes ───────────────────────────────────────────
            ("H7", "64GB",  "4GB"),    # KM5H7001DM-B424: 64GB UFS2.1 + 32Gb÷8=4GB LPDDR4X-4266 ✓
            #                          # ⚠ CONFLITO SHARED KEY 2026-05-28: KM2H7001CM-B518 = H7 mas 48Gb=6GB.
            #                          # Mapa em 4GB (âncora KM5H7001DM). KM2H7001CM → fix_known_parts.
            ("H8", "64GB",  "3GB"),    # KM5H80018M-B424: 64GB UFS2.1 + 24Gb÷8=3GB LPDDR4X-4266 ✓
            #                          # Confirmado Samsung Semiconductor Global 2026-05-28.
            # ── uMCP KMAG/KMAS: UFS 3.1 + LPDDR5 ────────────────────────────
            ("G9", "128GB", "8GB"),    # KMAG9001PM-B814: 128GB UFS3.1 + 64Gb÷8=8GB LPDDR5-6400 ✓
            #                          # Família KMAG — flagship uMCP LPDDR5. Confirmado Samsung Global 2026-05-28.
            ("S9", "256GB", "8GB"),    # KMAS9001PM-BC02: 256GB UFS3.1 + 64Gb÷8=8GB LPDDR5-6400 ✓
            #                          # Família KMAS — variante 256GB do KMAG. Confirmado Samsung Global 2026-05-28.
            # Gaps ainda não mapeados — ⚠ Dead-end sem Gemini: capacidade nula até PN físico confirmar:
            #   512GB + 12GB (S22 Ultra 512GB, S23 Ultra)
            # Adicionar quando PN real confirmar o cap_key.
        ]
        self._bulk_map("SAM_EMCP_CAP", emcp_cap, samsung, dry, overwrite)

        # ── DecodeMap: geração RAM eMCP (pos 2, 1 char) ───────────────────────
        emcp_gen = [
            ("J", "LPDDR2",    ""),   # KMJ: eMCP legado entrada (~2013-2015), LPDDR2
            ("K", "LPDDR2",    ""),
            ("F", "LPDDR3",    ""),
            ("N", "LPDDR2",    ""),   # ⚠ CORRIGIDO 2026-05-13: era LPDDR3 (errado).
            #                          # KMN5U000FM-B203 (Jotrin: 4Gb LPDDR2) + KMN5X000ZM-B209 (Preduo: lpddr2).
            #                          # KMN = família LPDDR2 entry-level (~2011-2014), eMMC 4.4/4.5.
            ("Q", "LPDDR3",    ""),
            ("R", "LPDDR3",    ""),   # ⚠ CORRIGIDO 2026-05-26: era LPDDR4/4X — ERRADO.
            #                          # Âncora usada (KMRH60014A-B614) era ela mesma LPDDR3 — premissa falsa.
            #                          # KMRH60014A-B614: Preduo, Censtry, cpuprocessorchip ✓ → "LPDDR3-1866MHz".
            #                          # KMRX60014M-B614: Preduo (caminho /emmc-lpddr3/) ✓ → LPDDR3.
            #                          # KMR310001M, KMR4Z0001M, KMR8X0001M: todos LPDDR3 (fix_known_parts ✓).
            #                          # KMR = família eMCP LPDDR3 + eMMC 5.1 (~2015-2019). Sem exceção confirmada.
            ("S", "LPDDR4X",   ""),
            # uMCP / geração alta
            ("D", "LPDDR4X",   ""),   # KMD: eMCP LPDDR4X + eMMC 5.1 (confirmado)
            # ("E", ...),              # BLOQUEADO 2026-05-09: nenhuma família ativa com pn[2]='E'
            #                          # usa SAM_EMCP_GEN. Zero PNs confirmados para KME. Regra de ouro.
            ("G", "LPDDR3",    ""),   # KMG: entrada morta (decode_gen_pos=None → engine nunca lê aqui).
            #                          # ⚠ CORRIGIDO 2026-05-09: era LPDDR4X (errado). KMG=LPDDR3 confirmado
            #                          # via datasheet KMGP6001BM. Sem impacto funcional — KMG usa EMCP_RAM_TYPES.
            ("L", "LPDDR5",    ""),   # ⚠ KML NÃO lê esta entrada (decode_gen_pos=None — KML=LPDDR1 legado).
            #                          # CORRIGIDO 2026-05-27: KML era falsamente classificado como uMCP LPDDR5.
            #                          # Entrada mantida para eventual família futura com L=LPDDR5. Sem âncora ativa.
            ("V", "LPDDR5/5X", ""),
        ]
        self._bulk_map("SAM_EMCP_GEN", emcp_gen, samsung, dry, overwrite)

        # ── DecodeMap: geração eMMC Samsung (pos 6, 1 char) ──────────────────
        # Usado pela família KLM (eMMC standalone) para decodificar a versão
        # do protocolo embutido no chip.
        # Posição pn[6] (7º caractere): letra que identifica a revisão eMMC.
        # Fonte: catálogo oficial Samsung + esquemáticos validados.
        # Impacto comercial: compradores B2B pagam diferente por versão —
        #   eMMC 5.1 (J): Command Queuing + HS400 — alta liquidez
        #   eMMC 5.0 (E): barramento HS200 sem CQ — liquidez média
        #   eMMC 4.5 (F): HS200 sem CQ — desconto forçado vs 5.1
        # O engine usa decode_gen para is_emcp=False → r["interface"] direto.
        emmc_gen = [
            ("F", "eMMC 4.5", ""),  # legado 2012+: HS200, sem Command Queuing
            ("E", "eMMC 5.0", ""),  # transição 2014: HS200, parcialmente melhorado (200MHz DDR)
            ("W", "eMMC 5.0", ""),  # variante de processo de E: eMMC 5.0 em nó alternativo
            #                       # KLM8G1WEMB-B031 — datasheet Samsung oficial ✓ (Alldatasheet/datasheet4u, 2026-05-26)
            #                       # "e.MMC 5.0 Specification compatibility" explícito no datasheet.
            #                       # ⚠ HS200 (não HS400) — HS400 é exclusivo do eMMC 5.1.
            ("J", "eMMC 5.1", ""),  # padrão atual 2015+: HS400 + Command Queuing
            ("K", "eMMC 5.1", ""),  # variante de processo de J: eMMC 5.1 em nó mais novo
            #                       # KLMCG2KCTA-B041 — Samsung Semiconductor Global ✓ (2026-05-25)
            #                       # semiconductor.samsung.com: "KLMCG2KCTA-B041(eMMC 5.1)"
            #                       # Preduo: "eMMC 5.1, 64GB, Samsung, BGA" ✓
            #                       # pn[6]='K' não aparece em chips eMMC 4.5/5.0 → exclusivo 5.1.
            ("G", "eMMC 5.1", ""),  # geração G: nova revisão de processo pós-J/K (~2017-2019)
            #                       # KLMAG2GEND-B041, KLMCG8GEND-B041, KLM8G1GEME-B041 — Samsung Global ✓ (2026-05-28)
            #                       # pn[6]='G' → eMMC 5.1 (sem regressão para 4.5/5.0 nesta geração).
            ("R", "eMMC 5.1", ""),  # geração R: processo RCTE/REWF (~2018-2019)
            #                       # KLMCG1RCTE-B041, KLMDG2RCTE-B041, KLMEG4RCTE-B041 — Samsung Global ✓ (2026-05-28)
            ("U", "eMMC 5.1", ""),  # geração U: processo UCTA/UCTB/UERM (~2019-2021)
            #                       # KLMCG2UCTA-B041, KLMDG4UCTA-B041, KLMEG8UERM-C041 — Samsung Global ✓ (2026-05-28)
            #                       # Nota: KLMEG8UERM tem sufixo -C041 (geração ainda mais nova) — capacidade igual.
        ]
        self._bulk_map("SAM_EMMC_GEN", emmc_gen, samsung, dry, overwrite)

        # ── DecodeMap: RDRAM / Rambus (pos 3-4, 2 chars) ─────────────────────
        # K4R + NÚMERO (pn[3] dígito) = RDRAM Rambus (1999-2003).
        # Rambus usa barramento de 18 bits → densidades "quebradas" (9-bit ECC).
        # Fonte: Samsung RDRAM datasheets / análise de PNs reais do lote.
        # "27" adicionado abaixo com confirmação de datasheet Samsung ✓
        rdram_cap = [
            ("27", "128Mb", "8Mx16 (x16 org)"),  # K4R271669D-TCS8 / K4R271669F — Samsung datasheet ✓
            #                                       # 256K × 16bit × 32 banks = 128Mbit. Org x16 (sem paridade).
            #                                       # PN confirma: "16" em "1669" vs "18" em "1869" (x18 das outras).
            #                                       # Auditoria havia omitido por "falta de evidência" — datasheet Samsung confirma.
            ("44", "144Mb", "16Mx9 por canal"),   # ex: K4R441669E
            ("88", "288Mb", "32Mx9 por canal"),   # ex: K4R881869E (PS2, PC800)
            ("76", "576Mb", "64Mx9 por canal"),   # ex: K4R760869E
        ]
        self._bulk_map("RDRAM_CAP", rdram_cap, samsung, dry, overwrite)

        # ── DecodeMap: BGA NVMe SSD (pos 3-4, 2 chars) ───────────────────────
        # Fonte: seção sam-kus do fab-samsung.html
        # Samsung PM971 BGA NVMe — série completa confirmada pelo datasheet oficial:
        # KUS020203M-B000 (128GB), KUS030202M-B000 (256GB), KUS040202M-B000 (512GB).
        # Ref: PM971-NVMe-BGA-SSD-Datasheet_for-Microsoft_v1.011.pdf (samsung.com) ✓
        # Teto da série: 512GB (04). Para 1TB+, Samsung usou outras nomenclaturas (PM991).
        kus_cap = [
            ("02", "128GB", ""),   # KUS020203M-B000 (PM971, Surface/ultrafinos) ✓
            ("03", "256GB", ""),   # KUS030202M-B000 (PM971) ✓
            ("04", "512GB", ""),   # KUS040202M-B000 (PM971, Surface Laptop original) ✓
            # ("05", "1TB", ""),   # BLOQUEADO 2026-05-09: zero PNs KUS05 em circulação.
            #                      # PM971 encerrou em 512GB. Presumido por simetria — rejeitado pela regra de ouro.
            #                      # Se aparecer chip físico com KUS05, acrescentar com Octopart.
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
            ("AH",  "16Gb",  "2GB"),   # DDR5: K4RAH086VB-BCQK (16Gb x8) ✓
            ("BH",  "32Gb",  "4GB"),   # DDR5: K4RBH046VM-BCCP (32Gb) — Samsung semiconductor.com ✓
            #                           # ⚠ 2026-05-09: "BG" e "CG" propostos por IA externa SEM PN confirmado.
            #                           # Padrão A→B hexadecimal é plausível mas regra de ouro impede mapear sem evidência.
            #                           # Adicionar BG/CG apenas quando chip físico com PN K4RBG.../K4RCG... aparecer.
        ]
        self._bulk_map("DRAM_PC", dram_pc, None, dry, overwrite)

        # ── DecodeMap: capacidade K3QF (LPDDR3 alta-densidade, pos 4, 1 char) ──────
        # Usado pela sub-família K3QF (chips K3QFxFx0...).
        # pn[4] = código opaco de capacidade (NÃO é simplesmente "N × 8Gb por die").
        # Misto de dies de 8Gb (chaves 1/2/3/4) e 6Gb (chaves 5/7).
        # val_primary = GB total (operador), val_secondary = Gb total (referência).
        # Fontes confirmadas:
        #   "1" → K3QF1F10DMAGCE000 (Octopart: 8Gb = 1GB) ✓
        #   "2" → K3QF2F20EM (sessão anterior: 16Gb = 2GB) ✓
        #   "3" → K3QF3F30BM-AGCG (semiconductor.samsung.com: 16Gb = 2GB) ✓ 2026-05-09
        #   "5" → K3QF5F50MM (Galaxy S5 Mini SM-G800F/H, Exynos 3470: 1.5GB LPDDR3) ✓ 2026-05-13
        #          12Gb total = 2× 6Gb die. Mesmo tipo de die do K3QF7 (4× 6Gb).
        #   "7" → K3QF7F70DM-QGCE (distribuidores: 24Gx64 = 24Gb = 3GB;
        #          Samsung press release "3GB LPDDR3" confirm produção; Galaxy Note 3) ✓ 2026-05-09
        # Confirmadas por PSG 1H 2017 (Samsung oficial):
        #   "6" → K3QF6F60AM-FGCF (PSG 1H 2017: 24Gb = 3GB) ✓ 2026-05-27
        #          Consistente com K3QF6F60MM (PSG 2H 2014) = 3GB ✓
        #   "4" → K3QF4F40BM-FGCF / K3QF4F40BM-AGCF (PSG 1H 2017: 32Gb = 4GB) ✓ 2026-05-27
        k3qf_cap = [
            ("1", "1GB",   "8Gb — 1× 8Gb die. Ex: K3QF1F10DMAGCE000 (Octopart). Resíduo."),
            ("2", "2GB",   "16Gb — 2× 8Gb die. Ex: K3QF2F20EM. Reacondicional seletivo."),
            ("3", "2GB",   "16Gb — revisão de die (NÃO é 3GB). Ex: K3QF3F30BM-AGCG (Samsung.com ✓). Reacondicional seletivo."),
            ("5", "1.5GB", "12Gb — 2× 6Gb die. Ex: K3QF5F50MM (Galaxy S5 Mini, Exynos 3470 ✓). Reacondicional seletivo."),
            ("6", "3GB",   "24Gb — Ex: K3QF6F60AM-FGCF / K3QF6F60MM (PSG 1H 2017 + PSG 2H 2014 ✓). Reacondicional seletivo."),
            ("7", "3GB",   "24Gb — 4× 6Gb die. Ex: K3QF7F70DM-QGCE (Note 3, Samsung PR 3GB LPDDR3 ✓). Reacondicional seletivo."),
            ("4", "4GB",   "32Gb — Ex: K3QF4F40BM-FGCF / K3QF4F40BM-AGCF (PSG 1H 2017 ✓). Reacondicional seletivo."),
            ("A", "8GB",   "64Gb — K3QFAFA0CM-AGCF (Samsung Semiconductor Global ✓ 2026-05-28). Geração C. Novo key — não existia no mapa anterior."),
        ]
        self._bulk_map("K3QF_CAP", k3qf_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade LPDDR3 standalone K4E (pos 3-4, 2 chars) ─────
        # val_primary = capacidade em GB (legível para operador de bancada).
        # val_secondary = densidade em Gb (referência técnica).
        # Fonte: datasheets Samsung K4E + Galaxy Note 3 / S5 teardowns.
        k4e_cap = [
            ("2E", "1.5GB", "12Gb — Galaxy Tab E / S5 Mini (~2014-2015). Sem liquidez B2B atual. "
                            "K4E2E304EA-AGCF: Kynix/Worldway ✓. K4E2E304EE-AGCE: Alldatasheet Samsung PSG ✓ (2026-05-29). "
                            "Galaxy Tab E SM-T560 = 1.5GB RAM confirmado — GSMarena/Icecat ✓. "
                            "Chave também presente em LPDDR4_CAP (confirmado por datasheet Samsung)."),
            ("8E", "1GB",  "8Gb — Galaxy entry (~2013). Sem liquidez B2B atual."),
            ("6E", "2GB",  "16Gb — Galaxy mid-range (~2014-2016)."),
            ("FE", "3GB",  "24Gb — Galaxy Note 3 / S5 (~2013-2014). Raro."),
            ("HE", "3GB",  "24Gb — alias FE: mesmo densidade, die alternativo. K4EHE304EC-AGCF — Puris B2B ✓. Galaxy Tab A SM-P585 (Exynos 7870)."),
            ("BE", "4GB",  "32Gb — Galaxy flagship (~2015). Alta demanda residual."),
        ]
        self._bulk_map("K4E_CAP", k4e_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade LPDDR2 standalone K3PE (pos 4-5, 2 chars) ──────
        # Família K3PE = Samsung LPDDR2 Mobile DRAM (~2011-2013). Antecessor do K3QF/K4E.
        # pn[4:6] = cap_key (2 chars). Formato: K3PE[cap_key][variant][revision].
        # Organização: x32 em todos os SKUs. VDD 1.8V / VDDQ 1.2V. 533MHz / 1066 Mbps.
        # Fontes:
        #   • K3PE4E400A-XGC1: harddiskdirect "128Mx32 LPDDR2 4Gbit" ✓
        #   • K3PE7E700B-XXC1: TechInsights DPR-1110-901 "32nm 2X 4Gb/die DDP = 8Gb" ✓
        #   • K3PE0E000A-XGC2: harddiskdirect "512Mx32 LPDDR2 16Gbit" ✓
        #   • Preduo 216/220/240ball LPDDR2: listagens confirmas de todos os grupos ✓
        # ⚠ LPDDR2 → assess_profitability → NÃO RENTÁVEL (lpddr_gen=2 ≤ 2).
        k3pe_cap = [
            ("4E", "512MB", "4Gbit SDP (128Mx32) — K3PE4E400x. Galaxy entry (~2011-2012). Resíduo."),
            ("7E", "1GB",   "8Gbit DDP (2× 4Gb) — K3PE7E700x. Galaxy mid-range (~2011-2012). Resíduo."),
            ("8E", "1GB",   "8Gbit DDP — K3PE8E800M, die alternativo de 7E. Mesma densidade. Resíduo."),
            ("0E", "2GB",   "16Gbit DDP (2× 8Gb ou 512Mx32) — K3PE0E000x. Galaxy flagship (~2012-2013). Resíduo."),
        ]
        self._bulk_map("K3PE_CAP", k3pe_cap, samsung, dry, overwrite)

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
            ("JE", "6GB",   "48Gb"),  # K4UJE3Q4AA-TFCL / K4UJE3Q4AA-THCL — Samsung Semiconductor Global ✓ "(48 Gb)"
            #                         # Confirmado 2026-05-27: semiconductor.samsung.com/dram/lpddr/lpddr4x/k4uje3q4aa-tfcl/
            #                         # K4UJE3T (base PN) → pn[3:5]="JE" → 48Gb ÷ 8 = 6GB.
            ("HE", "3GB",   "24Gb"),  # alias FE/7E (24Gb) — NÃO é alias de BE (32Gb)
            #                         # CORRIGIDO 2026-05-26: era 4GB (32Gb) — ERRADO.
            #                         # K4FHE3D4HM-MHCJ: Samsung Semiconductor Global ✓ → "(24 Gb)"
            #                         # K4FHE3D4HA-THCL: Samsung Semiconductor EMEA ✓ → "(24Gb)"
            #                         # K4FBE3D4HM-MGCJ = 32Gb (4GB) — HE ≠ BE densidades distintas.
            ("H5", "4GB",   "32Gb"),  # alias BE — K3UH5H50AM-AGCL/-JGCL/-JGCR: Samsung oficial + ssfkg ✓ "32Gb LPDDR4X"
            ("H6", "4GB",   "32Gb"),  # alias BE (geração 2020+)
            # ⚠ CONFLITO H6 para K3U: PSG 1H 2017 lista K3UH6H60AM como 48Gb=6GB
            #   enquanto H6=4GB (32Gb) está confirmado para K4F/K4U por múltiplas fontes.
            #   Hipótese: em 4CH (K3RG/K3UH), o código H6 representa o total de 4 canais (48Gb),
            #   enquanto em 2CH/1CH (K4F/K4U), H6=32Gb por chip.
            #   Solução: K3UH6H60AM importado via CSV PSG 1H 2017 com capacity=6GB (DB vence grammar).
            #   Decode para PNs genéricos K3U não importados: mantém H6=4GB até evidência direta.
            #   ✓ 2026-05-27: PSG 1H 2017 confirma K3UH6H60AM=48Gb=6GB via KnownPart.
            ("CE", "8GB",   "64Gb"),
            ("H7", "8GB",   "64Gb"),  # alias CE (ex: K3UH7H70MM-TFCL)
            ("HD", "16GB",  "128Gb"),
        ]
        self._bulk_map("LPDDR4_CAP", lpddr4_cap, samsung, dry, overwrite)

        # ── DecodeMap: capacidade K3RG (LPDDR4 4CH, pos 4-5, 2 chars) ──────────
        # K3RG = LPDDR4 multi-channel 4CH x16 (≠ K3R=LPDDR3).
        # Confirmado por PSG Samsung 1H 2017:
        #   "4G" → K3RG4G40MM-MGCJ (24Gb = 3GB) ✓
        #   "2G" → K3RG2G20CA-MGCJ / K3RG2G20CM-FGCJ (32Gb = 4GB) ✓
        #   "6G" → K3RG6G60MM-MGCJ (48Gb = 6GB) ✓
        #   "3G" → K3RG3G30MM-DGCH (24Gb = 3GB) ✓ — iFixit Galaxy S6 Teardown 2015
        #          Mesmo total que "4G" (24Gb), configuração de die diferente.
        # decode_cap_pos=4, decode_cap_len=2 — prefixo K3RG = 4 chars.
        k3rg_cap = [
            ("4G", "3GB", "24Gb — K3RG4G40MM-MGCJ (PSG 1H 2017 ✓)."),
            ("3G", "3GB", "24Gb — K3RG3G30MM-DGCH (iFixit Galaxy S6 Teardown 2015 ✓). Mesma capacidade que 4G, die diferente."),
            ("2G", "4GB", "32Gb — K3RG2G20CA-MGCJ / K3RG2G20CM-FGCJ (PSG 1H 2017 ✓)."),
            ("6G", "6GB", "48Gb — K3RG6G60MM-MGCJ (PSG 1H 2017 ✓)."),
        ]
        self._bulk_map("K3RG_CAP", k3rg_cap, samsung, dry, overwrite)

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
            # Confirmados por Octopart ou Samsung.com:
            ("9L", "2GB",  "16Gb — ex: K3KL9L90DMMGCU (Octopart: 512MX32 ✓)"),
            ("BK", "4GB",  "32Gb — ex: K3LKBKB0BMMGCP (Octopart: 1GX32 ✓)"),
            ("8L", "4GB",  "32Gb — ex: K3KL8L80EMMGCU (Octopart: 1GX32 ✓)"),
            ("7K", "8GB",  "64Gb — ex: K3LK7K70BM-BGCP (Galaxy S22; Octopart: 64Gb ✓)"),
            ("CK", "8GB",  "64Gb — K3LKCKC0BM-MFCP (Samsung Global ✓). Variante de empilhamento alternativo."),
            ("4K", "12GB", "96Gb — ex: K3LK4K40CM (Galaxy S20 Ultra; Octopart: 12GB ✓). K3LK4K40CM-JFCP Samsung Global ✓."),
            ("5L", "16GB", "128Gb — K3KL5L50DM-BGCU (Samsung Global ✓)."),
            # Adicionados 2026-05-09 (distribuidores) / confirmados 2026-05-27 (Samsung Global):
            ("2K", "6GB",  "48Gb — K3LK2K20BM-BGCN (Samsung Global ✓)."),
            ("3K", "8GB",  "64Gb — K3LK3K30EM-BGCN (Samsung Global ✓)."),
            ("DK", "18GB", "144Gb — K3LKDKD0CM-BGCP (Samsung Global ✓). Flagship 2022+."),
            ("3L", "8GB",  "64Gb — K3KL3L30CM-BGCU (Samsung Global ✓)."),
            ("1L", "4GB",  "32Gb — K3KL1L10GM-JGCT (Samsung Global ✓ 2026-05-28). ⚠ CORRIGIDO: era 8GB/64Gb (bug distribuidor)."),
            ("6L", "2GB",  "16Gb — K3KL6L60GM (Samsung Global ✓ 2026-05-28). Wearable/ultra-compact, 7500 Mbps."),
            ("7L", "3GB",  "24Gb — K3KL7L70DM (Samsung Global ✓ 2026-05-28)."),
            ("2L", "6GB",  "48Gb — K3KL2L20DM (Samsung Global ✓ 2026-05-28)."),
            ("6K", "16GB", "128Gb — K3LK6K60BM-JGCP (Samsung Global ✓)."),
            ("4L", "12GB", "96Gb — K3KL4L40DM-BGCU (Samsung Global ✓ '96 Gb'). ⚠ CORRIGIDO 2026-05-27: era 16GB/128Gb (bug distribuidor)."),
            # Código DL (geração FM/EM 2023+): 48Gb=6GB via nova arquitetura de die.
            # Mesmo volume que 2L mas processo diferente — NÃO intercambiável.
            # Confirmado Samsung Semiconductor Global 2026-05-28:
            #   K3KLDLD0FM (gen FM): MUCV / MGCV / MFCV
            #   K3KLDLD0EM (gen EM): MUCU / TGCT (grau automotivo AEC-Q100)
            ("DL", "6GB",  "48Gb — K3KLDLD0FM-MUCV (Samsung Global ✓ 2026-05-28). Gen FM/EM. VDDQ=0.5V. Processo diferente do 2L (mesma capacidade)."),
        ]
        self._bulk_map("LPDDR5_CAP", lpddr5_cap, samsung, dry, overwrite)

        # ── DecodeMap: NAND Flash K9 (pos 3-4, 2 chars) ──────────────────────
        # Usado pelas 8 famílias K9 (K9F, K9G, K9H, K9K, K9L, K9W, K9X, K9Z).
        # val_primary = densidade em Gb (referência técnica)
        # val_secondary = equivalente em bytes (legível pelo operador)
        # Confirmados por datasheets Samsung:
        #   1G–8G: datasheets K9F1G/2G/4G/8G amplamente publicados ✓
        #   AG: K9GAG08U0E = 16Gb (datasheet Samsung ✓)
        #   BG: K9GBG08U0A = 32Gb (Samsung datasheet Rev.1.0, May 2010 ✓)
        #   CG: K9LCG08U1A = 64Gb (Samsung datasheet Rev.1.0, May 2010 ✓)
        #   DG: K9HDG08U5A = 128Gb (Samsung datasheet Rev.1.0, May 2010 ✓)
        nand_flash_cap = [
            ("1G", "1Gb",   "128MB"),   # K9F1G08U0E — SLC, embedded industrial
            ("2G", "2Gb",   "256MB"),   # K9F2G08U0B — SLC, roteadores/gateways
            ("4G", "4Gb",   "512MB"),   # K9F4G08U0D — SLC
            ("8G", "8Gb",   "1GB"),     # K9K8G08U0A — SLC/MLC
            ("AG", "16Gb",  "2GB"),     # K9GAG08U0E — MLC (Samsung datasheet ✓)
            ("BG", "32Gb",  "4GB"),     # K9GBG08U0A — MLC (Samsung datasheet ✓)
            ("CG", "64Gb",  "8GB"),     # K9LCG08U1A — MLC (Samsung datasheet ✓)
            ("DG", "128Gb", "16GB"),    # K9HDG08U5A — MLC (Samsung datasheet ✓)
        ]
        self._bulk_map("NAND_FLASH_CAP", nand_flash_cap, samsung, dry, overwrite)

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
            # Distinção DDR3 vs DDR3L: sufixo BC=DDR3 1.5V | BY=DDR3L 1.35V.
            # interface="DDR3": corrigido em 2026-05-08 — era "" (Octopart: "DDR3 SDRAM").
            # suffix_rules="": limpa stale data do DB — versão anterior usava pn.endswith('16')
            #   para detectar largura x16, o que é incorreto (engine faz endswith, '16' é pn[5:6]).
            # Destino por densidade: 1Gb(128MB)=resíduo · ≥2Gb(256MB)=checar demanda.
            #   Confirmado via K4B1G1646GBCK0 (Octopart: "1G-Bit 64Mx16 1.5V 96-Pin FBGA").
            dict(
                prefix="K4B", chip_type="DDR", subtype="DDR3/DDR3L",
                interface="DDR3", decode_density_type="pc",
                suffix_rules="",
                reasoning='["K → Samsung Memory", "4 → 4th-gen DRAM", '
                          '"B → DDR3 (inclui DDR3L — distinção pela tensão do sufixo)", '
                          '"Densidade: pn[3:5] via DRAM_PC — 1G=1Gb(128MB) · 2G=2Gb(256MB) · 4G=4Gb(512MB) · 8G=8Gb(1GB)", '
                          '"Largura: pn[5:7] — 08=x8 (DIMMs/SO-DIMM) · 16=x16 (embarcados)", '
                          '"Tensão: sufixo BC=DDR3 1.5V | BY=DDR3L 1.35V — NÃO misturar na bancada"]',
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR3/DDR3L Samsung (2007–2016). "
                    "B = DDR3. Densidade: pn[3:5] → 1G=1Gb(128MB) · 2G=2Gb(256MB) · 4G=4Gb(512MB) · 8G=8Gb(1GB). "
                    "Largura: pn[5:7] → 08=x8 · 16=x16. "
                    "Tensão: sufixo BC=DDR3 1.5V · BY=DDR3L 1.35V. "
                    "⚠ NÃO misturar DDR3 com DDR3L na bancada. "
                    "Destino por densidade: "
                    "1Gb (128MB) → resíduo (moagem/refino — sem liquidez B2B em 2026); "
                    "≥2Gb (256MB+) → checar demanda antes de reacondicionar."
                ),
            ),
            # K4A = Samsung DDR4. Posições 3-4 = densidade (chaves DRAM_PC).
            # A = DDR4 (1.2V). Alto volume na triagem de desktops/laptops modernos.
            # Velocidade no sufixo: -BCPB=DDR4-2133, -BCRC=DDR4-2400,
            #   -BCTD=DDR4-2666, -BCWE=DDR4-3200.
            # interface="DDR4": corrigido em 2026-05-08 — era "" (Octopart: "DDR4 DRAM").
            # Confirmado via K4A8G165WC-BCRC (Octopart: "DDR4 DRAM, 512MX16, PBGA96").
            # capacity=null intencional: decode_cap_map="DRAM_PC" colocaria "8Gb" (entry[0])
            #   em capacity — Gigabits, não GB. dram_density já exibe "8Gb = 1GB por die [✓]".
            dict(
                prefix="K4A", chip_type="DDR4", subtype="DDR4",
                interface="DDR4", decode_density_type="pc",
                reasoning='["K → Samsung Memory", "4 → 4th-gen DRAM", "A → DDR4 (1.2V)", '
                          '"Densidade: pn[3:5] via DRAM_PC — 4G=4Gb(512MB) · 8G=8Gb(1GB) · AG/AH=16Gb(2GB)", '
                          '"Largura: pn[5:7] — 04=x4 · 08=x8 · 16=x16", '
                          '"Velocidade: sufixo BCPB=DDR4-2133 · BCRC=DDR4-2400 · BCTD=DDR4-2666 · BCWE=DDR4-3200"]',
                is_emcp=False, active=True, priority=100,
                tip=(
                    "DDR4 Samsung (2014–presente). "
                    "A = DDR4 (1.2V). Densidade: pn[3:5] → 4G=4Gb(512MB) · 8G=8Gb(1GB) · AG/AH=16Gb(2GB). "
                    "Largura: pn[5:7] → 04=x4 · 08=x8 · 16=x16. "
                    "Velocidade: sufixo BCPB=DDR4-2133 · BCRC=DDR4-2400 · BCTD=DDR4-2666 · BCWE=DDR4-3200. "
                    "Destino: bancada reacondicional — alta liquidez B2B para upgrades corporativos e notebooks. "
                    "Prioridade crescente por densidade: 512MB < 1GB < 2GB por die."
                ),
            ),
            # ── K4R: PREFIXO COMPARTILHADO — bifurcação obrigatória ──────────
            # Samsung reutilizou K4R em duas eras completamente diferentes:
            #   K4R + LETRA (pn[3] = letra) → DDR5 (2021+)   → K4RA (16Gb) | K4RB (32Gb) — priority=80
            #   K4R + NÚMERO (pn[3] = dígito) → RDRAM Rambus (1999-2003) → K4R fallback — priority=100
            # Prefixos de 4 chars (K4RA, K4RB) testados ANTES do K4R genérico.
            # PNs reais RDRAM: K4R881869E (288Mb, PS2/P4), K4R760869E (576Mb), K4R441669E (144Mb).
            # PNs reais DDR5 16Gb: K4RAH086VB-BCQK (x8), K4RAH165VB-BCQK (x16).
            # PNs reais DDR5 32Gb: K4RBH046VM-BCCP, K4RBH046VM-BCWM (Samsung semiconductor.com ✓).

            # DDR5 — prefixos de 4 chars, vencem o K4R genérico (RDRAM, priority=100)
            # K4RA = 16Gb DDR5 (PNs: K4RAH086VB-BCQK, K4RAH165VB-BCQK — Samsung ✓)
            # K4RB = 32Gb DDR5 (PNs: K4RBH046VM-BCCP, K4RBH046VM-BCWM — Samsung ✓)
            # ⚠ BUG CORRIGIDO 2026-05-09: K4RA não tinha decode_cap_pos/map → capacidade ficava nula.
            #   K4RBH... cairia no K4R RDRAM (priority=100) — classificação totalmente errada.
            dict(
                prefix="K4RA", chip_type="DDR5", subtype="DDR5",
                interface="DDR5", decode_density_type="pc",
                is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="DRAM_PC",
                tip=(
                    "DDR5 Samsung 16Gb (2021–presente). "
                    "K4RA: pn[3:5]=AH → 16Gb (2GB por die). "
                    "Largura: pn[5:7] (08=x8, 16=x16, 46=x4). "
                    "Velocidade no sufixo: -BCQK=DDR5-4800 MT/s. "
                    "PNs confirmados: K4RAH086VB-BCQK (x8), K4RAH165VB-BCQK (x16). "
                    "⚠ INCOMPATÍVEL com DDR4 — slot, tensão e protocolo diferentes. "
                    "NÃO misturar com K4A na bancada. "
                    "Destino: bancada reacondicional DDR5 (caixa separada)."
                ),
            ),
            dict(
                prefix="K4RB", chip_type="DDR5", subtype="DDR5",
                interface="DDR5", decode_density_type="pc",
                is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="DRAM_PC",
                tip=(
                    "DDR5 Samsung 32Gb (2023+). "
                    "K4RB: pn[3:5]=BH → 32Gb (4GB por die). "
                    "PNs confirmados: K4RBH046VM-BCCP, K4RBH046VM-BCWM (Samsung semiconductor.com ✓). "
                    "⚠ INCOMPATÍVEL com DDR4 — slot, tensão e protocolo diferentes. "
                    "NÃO misturar com K4A ou K4RA na bancada. "
                    "Destino: bancada reacondicional DDR5 (caixa separada — alta densidade)."
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
                    "Densidade: chars 4-5 do PN (27=128Mb, 44=144Mb, 88=288Mb, 76=576Mb). "
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
            # ── K3RG = LPDDR4 multi-channel 4CH x16 ──────────────────────────────
            # ⚠ NÃO confundir com K3R (LPDDR3). K3RG é LPDDR4 — sufixo G diferencia.
            # Prefixo 4 chars + priority=40 → vence K3R (3 chars) pelo tiebreaker -prefix_len.
            # Confirmado por PSG Samsung 1H 2017 (tabela Mobile DRAM, seção LPDDR4):
            #   K3RG4G40MM-MGCJ (24Gb=3GB), K3RG2G20CA-MGCJ (32Gb=4GB), K3RG6G60MM-MGCJ (48Gb=6GB).
            # "3G" → K3RG3G30MM-DGCH = 3GB (iFixit Galaxy S6 Teardown 2015 ✓).
            #   Mesmo total que "4G" (24Gb=3GB), die diferente. Usado no Galaxy S6 (Exynos 7420 PoP).
            # decode_cap_pos=4, decode_cap_len=2 → K3RG_CAP: 4G=3GB · 3G=3GB · 2G=4GB · 6G=6GB.
            dict(
                prefix="K3RG", chip_type="LPDDR4", subtype="LPDDR4 Multi-Channel",
                interface="LPDDR4", decode_density_type="",
                is_emcp=False, active=True, priority=40,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="K3RG_CAP",
                tip=(
                    "LPDDR4 Multi-Channel Samsung (K3RG). Tensão I/O: 1.1V. "
                    "Configuração: 4CH x16 = 64-bit total — encapsulamento multi-die. "
                    "Capacidade pn[4:6] → K3RG_CAP: 4G=3GB · 3G=3GB · 2G=4GB · 6G=6GB. "
                    "Exemplos: K3RG4G40MM (3GB, PSG 1H 2017 ✓) · K3RG3G30MM-DGCH (3GB, Galaxy S6 iFixit ✓) · "
                    "K3RG2G20CA/CM (4GB, 366/432-ball) · K3RG6G60MM (6GB, 366-ball). "
                    "⚠ NÃO confundir com K3R (LPDDR3) — K3RG é LPDDR4. "
                    "⚠ NÃO misturar soquetes com K3U/K3UH (LPDDR4X, 0.6V). "
                    "Destino: bancada reacondicional mobile (2016+ era)."
                ),
            ),
            # ═══ K3 GENÉRICO (fallback LPDDR2/3 — prioridade mínima) ════════════
            # Captura K3Q e qualquer K3x não mapeado explicitamente (K3R tem entrada própria acima).
            # DEVE ter priority > que todos os prefixos K3x específicos (K3U/K3Q=40)
            # para que o prefixo mais longo seja testado primeiro.
            # Sem decode de densidade: variabilidade alta. Chips K3 genéricos ficam sem capacidade — completar via fix_known_parts.
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
            # Decodificação: pn[4] → K3QF_CAP (código opaco, não é "N×8Gb").
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
                    "pn[4] = código de capacidade: 1=1GB · 2=2GB · 3=2GB (revisão die) · 5=1.5GB · 7=3GB · 4=4GB. "
                    "⚠ chave '3' ≠ 3GB — é 16Gb/2GB como a chave '2' (mudança de revisão interna, não densidade). "
                    "⚠ chaves '5' e '7' usam dies de 6Gb (não 8Gb): 5=2×6Gb=12Gb=1.5GB · 7=4×6Gb=24Gb=3GB. "
                    "⚠ 1GB (K3QF1...): sem liquidez B2B atual. Destino: resíduo. "
                    "1.5GB (K3QF5..., Galaxy S5 Mini Exynos): reacondicional seletivo. "
                    "2GB (K3QF2/K3QF3...): reacondicional seletivo. "
                    "3GB (K3QF7..., Galaxy Note 3): reacondicional seletivo — checar demanda. "
                    "4GB (K3QF4..., Octopart ✓): reacondicional seletivo. "
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
            # K3PE = Samsung LPDDR2 multi-channel PoP (dual-channel, ~2013-2014).
            # Prefixo 4 chars — precisa vencer K3P (3 chars, priority=35, LPDDR5X).
            # Engine ordena por (priority ASC, prefix_len DESC): priority igual → prefixo
            # mais longo vence. K3PE=35 iguala K3P=35 e prefix_len tiebreaker elege K3PE.
            # ⚠ NÃO usar priority < 35 — K3P é LPDDR5X legítimo; só o tiebreaker deve decidir.
            # K3=multi-channel PoP · P=LPDDR2 · E=geração.
            # decode_density_type="" — suprime DRAM_MOBILE (pn[3]='E' sem mapeamento).
            # Chips PSG 2H 2014: K3PE7E70QM (1GB, 216/220-ball) · K3PE0E00QM (2GB, 216/220-ball).
            dict(
                prefix="K3PE", chip_type="LPDDR2", subtype="LPDDR2 Multi-Channel PoP",
                interface="LPDDR2", decode_density_type="",
                is_emcp=False, active=True, priority=35,
                tip=(
                    "LPDDR2 Multi-Channel Samsung (K3PE). "
                    "K3=multi-channel PoP · P=LPDDR2 · E=geração. "
                    "Configuração dual-channel (2CH x32) — pacote PoP empilhado. "
                    "Exemplos PSG 2H 2014: K3PE7E70QM (1GB, 216/220-ball) · K3PE0E00QM (2GB). "
                    "⚠ NÃO confundir com K4P (LPDDR2 single-channel, sem PoP). "
                    "Destino: bancada reacondicional mobile (verificar demanda B2B)."
                ),
            ),
            # K3MF = Samsung LPDDR3 multi-channel PoP (dual-channel, ~2013-2014).
            # Prefixo 4 chars → vence K3 genérico (2 chars, chip_type="RAM").
            # K3=multi-channel PoP · M=geração interna · F=sufixo LPDDR3.
            # decode_density_type="" — suprime DRAM_MOBILE: pn[3]='F' retornaria
            #   16Gb=2GB para TODOS, mas K3MF9=3GB (24Gb) — valor errado.
            # Chips PSG 2H 2014: K3MF8F80DM (2GB, 504-ball 15×15mm) · K3MF9F90MM (3GB, 504-ball).
            dict(
                prefix="K3MF", chip_type="LPDDR3", subtype="LPDDR3 Multi-Channel PoP",
                interface="LPDDR3", decode_density_type="",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR3 Multi-Channel Samsung (K3MF). "
                    "K3=multi-channel PoP · M=geração interna · F=LPDDR3. "
                    "Pacote grande: 504-ball 15×15mm — dual-channel (2CH x32). "
                    "Exemplos PSG 2H 2014: K3MF8F80DM (2GB) · K3MF9F90MM (3GB). "
                    "⚠ NÃO confundir com K3QF (também LPDDR3 multi-channel, prefixo K3Q). "
                    "⚠ decode_density_type='' — pn[3]='F' via DRAM_MOBILE erraria K3MF9=3GB. "
                    "Destino: bancada reacondicional mobile (PoP LPDDR3 — checar demanda)."
                ),
            ),
            # K3PE = Samsung LPDDR2 Mobile standalone (~2011-2013).
            # Antecessor do K3QF (LPDDR3). Todos NÃO RENTÁVEL — LPDDR2 sem liquidez B2B.
            # pn[4:6] = cap_key (decode_cap_pos=4, decode_cap_len=2).
            # Chaves: 4E=512MB · 7E/8E=1GB · 0E=2GB.
            # Fontes: harddiskdirect ✓, TechInsights ✓, Preduo ✓ (2026-05-29).
            dict(
                prefix="K3PE", chip_type="LPDDR2", subtype="LPDDR2 Mobile",
                interface="LPDDR2", is_emcp=False, active=True, priority=100,
                decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="K3PE_CAP",
                tip=(
                    "LPDDR2 Samsung standalone (~2011-2013). "
                    "K3PE = prefixo família LPDDR2 mobile (antecessor do K3QF/LPDDR3). "
                    "Capacidade: pn[4:6] → 4E=512MB · 7E/8E=1GB · 0E=2GB. "
                    "533MHz / 1066 Mbps. VDD 1.8V / VDDQ 1.2V. Organização x32. "
                    "⚠ LPDDR2: sem liquidez B2B em 2026 → NÃO RENTÁVEL (moagem/refino). "
                    "Exemplos: K3PE4E400A (512MB), K3PE7E700B (1GB), K3PE0E000A (2GB)."
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
                    "Capacidade: pn[3:5] → 2E=1.5GB · 8E=1GB · 6E=2GB · FE=3GB · HE=3GB · BE=4GB. "
                    "⚠ FE e HE são aliases de 3GB (24Gb) — die diferente, mesma densidade. "
                    "⚠ 1.5GB (2E): Galaxy Tab E SM-T560 / S5 Mini — sem liquidez B2B atual → resíduo. "
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
                    "Capacidade: pn[3:5] → 4E=512MB · 8E=1GB · 6E=2GB · 7E/HE=3GB · BE/H5/H6=4GB · JE=6GB · CE/H7=8GB · HD=16GB. "
                    "⚠ HE=3GB (24Gb) — NÃO confundir com BE=4GB (32Gb). "
                    "⚠ JE=6GB (48Gb) — Samsung Semiconductor Global ✓ (confirmado 2026-05-27). "
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
                    "Capacidade: pn[3:5] → 4E=512MB · 8E=1GB · 6E=2GB · 7E/HE=3GB · BE/H5/H6=4GB · JE=6GB · CE/H7=8GB · HD=16GB. "
                    "⚠ HE=3GB (24Gb) — NÃO confundir com BE=4GB (32Gb). "
                    "⚠ JE=6GB (48Gb) — Samsung Semiconductor Global ✓ (confirmado 2026-05-27). "
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
                    "Capacidade: pn[3:5] → HE=3GB · BE/H5/H6=4GB · CE/H7=8GB · HD=16GB (mais comuns nesta família). "
                    "⚠ HE=3GB (24Gb) — NÃO confundir com BE=4GB (32Gb). "
                    "Exemplos confirmados: K3UH5H50AM-AGCL (H5=32Gb=4GB, Samsung oficial ✓) · K3UH7H70MM-TFCL (H7=8GB). "
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
                prefix="K3KL", chip_type="LPDDR5X", subtype="LPDDR5X",
                interface="LPDDR5X", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="LPDDR5_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR5X Samsung (K3KL). VDDQ=0.5V — RISCO DE QUEIMA no socket de LPDDR5 (VDDQ=0.9V). "
                    "⚠ CORRIGIDO 2026-05-27: era classificado como LPDDR5 — ERRADO. "
                    "Samsung Global categoriza K3KL em /lpddr5x/ (K3LK vai para /lpddr5/). "
                    "Velocidade: até 8533 Mbps (gen DM/EM/FM). Flagships Samsung (Galaxy S22+ S23 S24). "
                    "Densidade em pn[4:6] → LPDDR5_CAP: 6L/9L=2GB · 1L/8L=4GB · 7L=3GB · 2L/DL=6GB · 3L=8GB · 4L=12GB · 5L=16GB. "
                    "Gerações pn[8]: DM (2021-22) · CM/EM (2022-23) · FM (2023+). "
                    "Exemplos Samsung Global: K3KL3L30CM-BGCT (8GB) · K3KL4L40FM-BGCV (12GB) · K3KL5L50DM-BGCU (16GB) · K3KLDLD0FM-MUCV (6GB DL). "
                    "Destino: bancada reacondicional MOBILE. Verificar VDDQ antes de inserir no jig."
                ),
            ),
            dict(
                prefix="K3LK", chip_type="LPDDR5", subtype="LPDDR5",
                interface="LPDDR5", decode_density_type="",
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="LPDDR5_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "LPDDR5 Samsung (K3LK). VDDQ=0.9V típico. "
                    "⚠ CORRIGIDO 2026-05-27: era classificado como LPDDR5X — ERRADO. "
                    "Samsung Global categoriza K3LK em /lpddr5/ (não /lpddr5x/). "
                    "K3KL=LPDDR5X (VDDQ=0.5V) — NÃO confundir sockets: incompatíveis, risco de queima. Ambas corrigidas 2026-05-27. "
                    "Velocidade: até 6400 Mbps. Flagships Samsung (Galaxy S21, S22, S23, S24). "
                    "Densidade em pn[4:6] → LPDDR5_CAP: BK=4GB · 7K/CK/3K=8GB · 4K=12GB · 6K/DK=16-18GB. "
                    "Exemplos Samsung Global: K3LKBKB0BM (4GB) · K3LK7K70BM (8GB) · K3LK4K40CM (12GB) · K3LKDKD0CM (18GB). "
                    "Destino: bancada reacondicional MOBILE. Verificar subtype antes de inserir no jig."
                ),
            ),

            # ═══ FLASH: eMMC ═════════════════════════════════════════════════
            # decode_gen_pos=6: engine lê pn[6] → SAM_EMMC_GEN → r["interface"].
            # interface="eMMC" é fallback para PNs curtos / letras não mapeadas.
            # Chips com pn[6] reconhecido exibem "eMMC 4.5", "eMMC 5.0" ou "eMMC 5.1"
            # automaticamente — impacto direto no preço B2B (5.1 > 5.0 > 4.5).
            dict(
                prefix="KLM", chip_type="eMMC", subtype="eMMC Samsung",
                interface="eMMC", pn_length=10,
                decode_gen_pos=6, decode_gen_map="SAM_EMMC_GEN",
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=50,
                tip=(
                    "eMMC Samsung — armazenamento Flash puro, sem RAM embutida. "
                    "Geração automática: pn[6] → F=eMMC 4.5 | E/W=eMMC 5.0 | J/K=eMMC 5.1. "
                    "⚠ Separe por geração na bancada: 5.1 (J/K) vale ~15-25% a mais que 4.5 (F). "
                    "Capacidade: pn[3] → 4=4GB · 8=8GB · A=16GB · B=32GB · C=64GB · "
                    "D=128GB · E=256GB · F=512GB · G=1TB. "
                    "Tipo NAND: pn[5] → 4=MLC · 8=TLC (TLC = maioria dos volumes modernos). "
                    "Pacote: BGA153 ou BGA169 — verificar grid inferior. "
                    "Destino: bancada reacondicional Flash eMMC (separar por geração)."
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
            # KLUBG: UFS 2.0 32GB — primeira geração UFS Samsung (Galaxy S6 era, 2015).
            # Samsung Semiconductor Global lista KLUBG4G1CE-B0B1 sob "UFS 2.0" ✓
            # (mesmo prefixo KLUBG, variante de sufixo BD/CE = lotes de produção).
            # Família estava ausente → engine caía para KLU genérico (UFS 3.1, ERRADO).
            dict(
                prefix="KLUBG", chip_type="UFS", subtype="UFS 2.0 Samsung",
                interface="UFS 2.0", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 2.0 Samsung — armazenamento Flash standalone, 1ª geração UFS. "
                    "K=Samsung, L=NAND, U=UFS, B=32GB. "
                    "Presente no Galaxy S6 / S6 Edge / S6 Edge Plus (2015). "
                    "Interface UFS — NUNCA usar socket de eMMC (BGA153, mesmo footprint físico que eMMC). "
                    "Velocidade: ~700 MB/s (leitura teórica UFS 2.0). "
                    "Destino: bancada reacondicional Flash UFS (valor comercial: lote legacy)."
                ),
            ),
            dict(
                prefix="KLUCG", chip_type="UFS", subtype="UFS 2.0 Samsung",
                interface="UFS 2.0", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 2.0 Samsung — armazenamento Flash standalone. "
                    "K=Samsung, L=NAND, U=UFS, C=64GB. "
                    "Capacidade: pn[3] → B=32GB, C=64GB. "
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
            dict(
                prefix="KLUEG", chip_type="UFS", subtype="UFS 3.1 Samsung",
                interface="UFS 3.1", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "UFS 3.1 Samsung — 256GB standalone (K=Samsung, L=NAND, U=UFS, E=256GB). "
                    "Sufixos UHY/UHD = UFS 3.1. Presente em Samsung Galaxy S21/S22/S23 256GB. "
                    "⚠ Variante legado: KLUEG8U1EM = UFS 2.1 (PSG 1H 2017 — KnownPart confirmado). "
                    "⚠ Variante UFS 4.0: KLUEG4RHHD/F/HF (2023+) — KnownPart confirmado. "
                    "Capacidade: pn[3] → E=256GB (SAM_FLASH_CAP). "
                    "Destino: bancada reacondicional Flash UFS alta capacidade."
                ),
            ),
            # KLUGG: UFS 4.0/4.1 1TB — família flagship 2023+.
            # Confirmado Samsung Semiconductor Global: KLUGG8NHHB, KLUGG8NHKB,
            # KLUGGARHHD, KLUGGARHUF, KLUGGGRHKF (UFS 4.1).
            # Sem esta entrada, engine cai para KLU genérico (UFS 3.1 — ERRADO).
            dict(
                prefix="KLUGG", chip_type="UFS", subtype="UFS Samsung (1TB)",
                interface="UFS", pn_length=10,
                decode_cap_pos=3, decode_cap_len=1, decode_cap_map="SAM_FLASH_CAP",
                is_emcp=False, active=True, priority=40,
                tip=(
                    "Samsung UFS 1TB standalone — família KLUGG abrange UFS 3.0 e 4.0+. "
                    "K=Samsung, L=NAND, U=UFS, G=1TB (SAM_FLASH_CAP). "
                    "⚠ Versão UFS exata (3.0/4.0/4.1) determinada pelo KnownPart — não confiar no grammar. "
                    "Sem esta entrada o engine caia para KLU genérico (pn_length=10 não bate). "
                    "Destino: bancada reacondicional Flash UFS alta capacidade (valor premium)."
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
                # ⚠ CORRIGIDO 2026-05-13: subtype era "LPDDR3 + eMMC" — ERRADO.
                # KMN5U000FM-B203 (Jotrin: 4Gb LPDDR2) + KMN5X000ZM-B209 (Preduo: lpddr2).
                # KMN = família LPDDR2 entry-level (~2011-2014). eMMC 4.4/4.5.
                # Interface removida: "eMMC 5.1" era imprecisa para chips de 2011-2014.
                #
                # ⚠ CORRIGIDO 2026-05-25: decode_cap_pos DESLIGADO (era 3, decode_cap_map=SAM_EMCP_CAP).
                # Problema: pn[3:5]="J2" no SAM_EMCP_CAP → 128GB+6GB (âncora moderna KMQJ2·) — ERRADO.
                # Para chips KMN de 2011-2014, pn[3:5] tem codificação de era diferente (densidades muito menores).
                # Exemplo: KMNJ2000ZM sistema mostrava "eMMC 128GB + LPDDR2 6GB" — fisicamente impossível.
                # Sem decode_cap_pos, o engine não decodifica capacidade → campos ficam em branco.
                # Isso é correto: destino é Caixa Vermelha de qualquer forma; capacidade exata não muda rota.
                # PNs específicos com capacidade verificada → adicionar via fix_known_parts.py.
                prefix="KMN", chip_type="eMCP", subtype="LPDDR2 + eMMC",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=None, decode_cap_len=0, decode_cap_map="",
                tip=(
                    "eMCP Samsung LPDDR2 + eMMC (~2011-2014). N = LPDDR2. "
                    "Família entry-level legada. Baixa liquidez em 2026. "
                    "Destino: Fluxo de Resíduo (Caixa Vermelha)."
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
                prefix="KMR", chip_type="eMCP", subtype="LPDDR3 + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,  # todos os PNs KMR são 10 chars (ex: KMRH60014A, KMR310001M)
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=2, decode_gen_map="SAM_EMCP_GEN",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip="eMCP Samsung LPDDR3 + eMMC 5.1. "
                    "R = LPDDR3 (2026-05-26: corrigido de LPDDR4/4X — âncora anterior era falsa). "
                    "Exemplos: KMRH60014A (64GB+4GB LPDDR3-1866), KMRX60014M (32GB+4GB LPDDR3). "
                    "Destino: reacondicional eMCP.",
            ),
            dict(
                prefix="KMS", chip_type="eMCP", subtype="LPDDR1 + eMMC",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                # decode_gen_pos=None: 'S' na posição 2 é o próprio identificador
                # de família — não é um campo de geração variável. Se apontasse
                # para SAM_EMCP_GEN, 'S' → LPDDR4X (ERRADO). Engine usa fallback
                # isdigit() / extrai geração direto do subtype.
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR1 + eMMC — família LEGADO (~2012-2013). "
                    "Chips típicos: 4GB NAND + 512MB RAM (LPDDR1). "
                    "Exemplo: KMSJS000KM = Galaxy Centura (SCH-S738C, 2013). "
                    "Pinout incompatível com sockets modernos de bancada. "
                    "⚑ DESTINO: Caixa Vermelha — resíduo eletrônico. Sem viabilidade comercial."
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

            # ═══ eMCP LPDDR4X: KM3P ═══════════════════════════════════════════
            # Família Samsung eMCP geração 2022+ confirmada (Glochip/Indasina).
            # KM3P6001CM-B517 = 64GB eMMC 5.1 + 48Gb LPDDR4X = 6GB.
            # decode_gen_pos=None: '3' em pn[2] é dígito numérico de geração,
            #   NÃO é letra de tipo RAM — SAM_EMCP_GEN não cobre dígitos.
            # ⚠ ATENÇÃO cap_key: pn[3:5]='P6' → SAM_EMCP_CAP['P6'] = 64GB + 4GB
            #   (âncora KMD/KMDP6001DA). KM3P6001CM tem 6GB RAM (48Gb).
            #   Shared key conflict → tratar via fix_known_parts.py.
            dict(
                prefix="KM3P", chip_type="eMCP", subtype="LPDDR4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR4X + eMMC 5.1 (família KM3P, geração 2022+). "
                    "K=Samsung · M=MCP · 3=geração numérica · P=LPDDR4X. "
                    "Confirmado: KM3P6001CM-B517 = 64GB eMMC 5.1 + 48Gb÷8=6GB LPDDR4X (Glochip/Indasina ✓). "
                    "⚠ cap_key pn[3:5]='P6' → SAM_EMCP_CAP = 64GB+4GB (âncora KMD); "
                    "KM3P6001CM tem 6GB RAM — exceção: corrigir via fix_known_parts. "
                    "Status 2022+: Sample → aparição crescente prevista. "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),

            # ═══ eMCP LPDDR4X: KM3H ═══════════════════════════════════════════
            # Família Samsung eMCP geração 2022+ — variante de velocidade 3733 Mbps.
            # KM3H6001CA-B515 = 64GB eMMC 5.1 + 48Gb LPDDR4X-3733 = 6GB.
            # 'H' = LPDDR4X a 3733 Mbps (vs 'P' = 4266 Mbps na família KM3P).
            # priority=38: mais específico que KMD (3 chars, priority=40).
            # ⚠ cap_key H6 → SAM_EMCP_CAP H6=64GB+4GB (âncora KMD). KM3H6001CA tem 6GB.
            #   Shared key conflict → tratar via fix_known_parts.
            dict(
                prefix="KM3H", chip_type="eMCP", subtype="LPDDR4X + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=38,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR4X-3733 + eMMC 5.1 (família KM3H — variante velocidade). "
                    "K=Samsung · M=MCP · 3=geração numérica · H=LPDDR4X 3733 Mbps (vs P=4266 Mbps). "
                    "Confirmado: KM3H6001CA-B515 = 64GB eMMC 5.1 + 48Gb÷8=6GB LPDDR4X-3733 ✓. "
                    "⚠ cap_key pn[3:5]='H6' → SAM_EMCP_CAP = 64GB+4GB (âncora KMD); "
                    "KM3H6001CA tem 6GB RAM — exceção: corrigir via fix_known_parts. "
                    "Status 2022+: geração nova — aparição crescente prevista no mercado secundário. "
                    "Destino: bancada reacondicional eMCP."
                ),
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
            # ═══ KMG — eMCP LPDDR3 + eMMC 5.1 (CORRIGIDO 2026-05-09) ═════════════
            # ATENÇÃO: KMG NÃO é uMCP. Classificação anterior estava ERRADA.
            # Datasheet KMGP6001BM confirma: KMG = eMCP eMMC 5.1 + LPDDR3 (~2016-2019).
            # A letra G em EMCP_RAM_TYPES (engine.py) = "LPDDR3" — correto para este fallback.
            # decode_gen_pos=None obrigatório: usar SAM_EMCP_GEN daria G=LPDDR4X — ERRADO.
            # O fix_known_parts.py corrigiu KMGD6001BM de volta para eMCP+LPDDR3.
            dict(
                prefix="KMG", chip_type="eMCP", subtype="LPDDR3 + eMMC 5.1",
                interface="eMMC 5.1", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",  # "" obrigatório: limpa SAM_EMCP_GEN antigo do DB.
                # G = LPDDR3 via EMCP_RAM_TYPES fallback (Caminho 3 do engine).
                # Com decode_gen_map="" → engine ignora Caminho 2 → usa EMCP_RAM_TYPES['G']='LPDDR3'.
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "eMCP Samsung LPDDR3 + eMMC 5.1 — linha legacy, ~2016-2019. "
                    "G = LPDDR3 (via EMCP_RAM_TYPES fallback — decode_gen_pos=None por design). "
                    "Capacidade: pn[3:5] → SAM_EMCP_CAP (ex: D6=32GB+3GB, P6=64GB+3GB). "
                    "Interface eMMC 5.1 — NÃO confundir com uMCP KML/KM5 que usam UFS. "
                    "Destino: bancada reacondicional eMCP."
                ),
            ),
            # ── KML: eMCP legado LPDDR1 (~2013-2015) ─────────────────────────────
            # ⚠ CORRIGIDO 2026-05-27: era classificado como "uMCP UFS 3.1 + LPDDR5" — ERRADO.
            # Evidências:
            #   • KML7X000HM-B507: eetgroup.com → "8GB+8GB, EMMC+LPDD" (eMMC, NÃO UFS 3.1)
            #   • KML5U000HM-B505: Puris → "4+8 153ball eMCP-D1" → categoria "eMMC+LPDDR" (LPDDR1)
            #   • emmc-ufs.com: KML7X000HM possui página de firmware eMMC (NÃO UFS)
            #   • Aparece em Galaxy Core i8262 (2013) — era incompatível com UFS 3.1 + LPDDR5
            #   • uMCPs modernos Samsung são KM8-series (ex: KM8V8001LM-B813 Galaxy S21 ✓)
            # eMCP-D1 (Puris nomenclatura): D = geração DRAM, 1 = LPDDR1.
            # decode_gen_pos=None obrigatório: SAM_EMCP_GEN['L']="LPDDR5" é ERRADO para KML.
            # Engine usará Caminho 3 (subtype) para extrair "LPDDR1".
            dict(
                prefix="KML", chip_type="eMCP", subtype="LPDDR2 + eMMC (legado)",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",  # L=LPDDR5 no SAM_EMCP_GEN é errado; engine usa subtype.
                # LPDDR version: Puris "eMCP-D1" / categoria "eMMC+LPDDR" (sem nº) é ambíguo.
                # LPDDR2 adotado: Exynos 4212 (Galaxy Core i8262) suporta LPDDR2 (NÃO LPDDR1).
                # LPDDR1 era obsoleto em smartphones desde ~2012. Era 2013-2015 = KMJ/KMN = LPDDR2.
                # ⚠ Sem confirmação Tier 1 explícita para versão LPDDR — inferência de era+SoC.
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ eMCP Samsung LPDDR2 + eMMC legado (~2013-2015). "
                    "NÃO confundir com uMCP moderno: KML NÃO usa UFS 3.1 + LPDDR5 (erro corrigido 2026-05-27). "
                    "Puris: KML5U000HM-B505 = 'eMCP-D1', categoria eMMC+LPDDR — versão LPDDR ambígua. "
                    "LPDDR2 inferido: era 2013-2015 + Exynos 4212 compatível com LPDDR2. "
                    "Galaxy S21 Exynos usa KM8-series (KM8V8001LM-B813), NÃO KML. "
                    "Capacidade: pn[3:5] → SAM_EMCP_CAP (ex: 7X=8GB+1GB via fix_known_parts). "
                    "Destino: legado — valor comercial baixo, apenas reacondicional entry-level."
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
            # Capacidades variam por sub-variante — cap_keys não mapeados ficam com capacidade nula. Completar via fix_known_parts.
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
            # ── KM2L: UFS 2.2 + LPDDR4X ─────────────────────────────────────────
            # pn[2]='L' → subfamília intermediária (UFS 2.2, LPDDR4X).
            # Confirmado: KM2L9001CM-B518 = 128GB UFS 2.2 + 6GB LPDDR4X.
            # Fontes: Samsung Semiconductor + Preduo (categoria "UFS+LPDDR4x").
            # ATENÇÃO: KM2L9001CM tem cap_key "L9" = 8GB no mapa SAM_EMCP_CAP
            #   (base KM8L9001JM com 8GB RAM). KM2L9001CM usa 6GB (48Gb÷8).
            #   Corrigir via fix_known_parts — exceção de shared key.
            # priority=35: mais específico que KM2 genérico (priority=40).
            dict(
                prefix="KM2L", chip_type="uMCP", subtype="UFS 2.2 + LPDDR4X (intermediário)",
                interface="UFS 2.2", pn_length=10,
                is_emcp=True, active=True, priority=35,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "uMCP Samsung KM2L — INTERMEDIÁRIO. "
                    "Interface UFS 2.2 (~1200 MB/s) + LPDDR4X — NÃO é UFS 3.1/LPDDR5. "
                    "pn[2]='L' identifica esta subfamília (L = UFS 2.2 + LPDDR4X). "
                    "Presente em mid-range/upper-mid Galaxy e Android de terceiros (2021-2023). "
                    "Capacidade: pn[3:5] → SAM_EMCP_CAP. "
                    "⚠ Atenção ao cap_key 'L9': mapa base = 8GB RAM (KM8); "
                    "KM2L9001CM usa 6GB — confirmar via fix_known_parts. "
                    "Valor comercial ELEVADO mas inferior a KM2V (UFS 3.1 + LPDDR5). "
                    "ATENÇÃO OCR: '1' confundido com 'I' — conferir PN físico no chip. "
                    "Destino: bancada reacondicional uMCP (Intermediário/Alta liquidez)."
                ),
            ),
            # ── KM2P: UFS 2.1/2.2 + LPDDR4X (64GB — densidade intermediária) ──────
            # pn[2]='2', pn[3]='P' → subfamília 64GB UFS + 6GB LPDDR4X.
            # Confirmado: KM2P8001CM-B518 = 64GB UFS 2.1 + 6GB LPDDR4X-4266.
            #             KM2P9001CM-B518 = 64GB UFS 2.2 + 6GB LPDDR4X-4266.
            # priority=38: mais específico que KM2 genérico (priority=40).
            # ⚠ cap_key: P8 → SAM_EMCP_CAP P8=64GB+4GB (âncora KM5P). KM2P usa 6GB.
            #   Shared key conflict → tratar via fix_known_parts.
            dict(
                prefix="KM2P", chip_type="uMCP", subtype="UFS + LPDDR4X (64GB intermediário)",
                interface="UFS", pn_length=10,
                is_emcp=True, active=True, priority=38,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "uMCP Samsung KM2P — 64GB UFS 2.1/2.2 + LPDDR4X-4266. "
                    "pn[3]='P' identifica 64GB storage (vs KM2L=128GB, KM2V=128GB). "
                    "Confirmado: KM2P8001CM-B518 = 64GB UFS2.1 + 6GB LPDDR4X ✓. "
                    "  KM2P9001CM-B518 = 64GB UFS2.2 + 6GB LPDDR4X ✓. "
                    "⚠ cap_key P8→4GB e P9→4GB no mapa base (âncora KM5P); "
                    "KM2P usa 6GB — corrigir via fix_known_parts. "
                    "Valor comercial ELEVADO — NÃO enviar para resíduo. "
                    "Destino: bancada reacondicional uMCP (Intermediário)."
                ),
            ),
            # ── KM2 genérico: cobre KM2V (UFS 3.1 + LPDDR5) e outras subfamílias ──
            # pn[2]='V' → UFS 3.1 + LPDDR5 (ex: KM2V7001CM-B706 flagship). Confirmado.
            # pn[2]='F' → alta capacidade (KM2F8001CM-B707 = 256+48 LPDDR4X per Preduo).
            #   ⚠ KM2F NÃO é necessariamente LPDDR5 — aguardar confirmação adicional.
            # KM2L é tratado pela subfamília acima (priority=35, mais específica).
            # ⚠ CORRIGIDO 2026-05-27: "KM2V=UFS 3.1+LPDDR5" era ERRADO.
            # KM2V8001CM-B707 (âncora confirmada): UFS 2.1 + LPDDR4X-4266 + 6GB (48Gb).
            #   Preduo: categoria "UFS+LPDDR4x", "128+48". Amazon: "KM2V8001CM-6G-4266Mbps".
            #   ssfkg.com: "UFS 2.1 SAMSUNG". Speed 4266 Mbps = LPDDR4X (LPDDR5 ≥ 6400 Mbps).
            # Samsung Semiconductor Global redireciona a página do chip para seção "LPDDR5 uMCP"
            # — parece categorização do site, NÃO reflete a velocidade real (4266 Mbps = LPD4X).
            # Subtype atualizado para "UFS + LPDDR4X" como base até PN LPDDR5 real ser confirmado.
            dict(
                prefix="KM2", chip_type="uMCP", subtype="UFS + LPDDR4X (premium)",
                interface="UFS", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung linha numérica KM2 — chip PREMIUM. NÃO eMMC. "
                    "Subfamílias: KM2L=UFS 2.2+LPDDR4X (coberto pela família KM2L com priority=35). "
                    "KM2V=UFS 2.1+LPDDR4X (CORRIGIDO 2026-05-27: era LPDDR5 — ERRADO). "
                    "  Âncora: KM2V8001CM-B707 = 128GB UFS 2.1 + 48Gb÷8=6GB LPDDR4X-4266 ✓. "
                    "  Speed 4266 Mbps confirma LPDDR4X (LPDDR5 mínimo ≥ 6400 Mbps). "
                    "KM2F=alta capacidade — verificar via fix_known_parts. "
                    "⚠ cap_key V8: KM2V8001CM=6GB (48Gb) vs KM5/KM8 V8=4GB (32Gb) — shared key conflict. "
                    "Se o PN começa com KM2L, família KM2L (priority=35) tem precedência. "
                    "Capacidade: pn[3:5] → SAM_EMCP_CAP (atenção a conflitos de shared key). "
                    "Valor comercial ELEVADO — NÃO enviar para resíduo ou eMMC. "
                    "ATENÇÃO OCR: '1' confundido com 'I' — conferir PN físico. "
                    "Destino: bancada reacondicional uMCP (Premium)."
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

            # ── KMV2 / KMV3 REMOVIDOS 2026-05-13 ────────────────────────────────
            # Premissa original: KMV + DÍGITO = uMCP LPDDR5X flagship (S22/S23).
            # REFUTADO por evidência real:
            #   • KMV3W000LM-B310 = eMCP Galaxy S4 I9500 (FBGA-153, 16G eMCP, 2013).
            #     iFixit S22 Ultra: usa K3LK7K70BM-BGCP (LPDDR5 standalone) +
            #     KLUDG4UHDC-B0E1 (UFS 3.1 standalone) — sem uMCP.
            #   • Nenhum PN KMV2.../KMV3... encontrado no Octopart ou Samsung semiconductor.
            # Chips KMVx... → cobertos pela família KMV (3 chars, priority=40) abaixo.

            # ── KMAG: uMCP UFS 3.1 + LPDDR5 (128GB) ─────────────────────────────
            # pn[2]='A', pn[3]='G' → subfamília 128GB UFS 3.1 + 8GB LPDDR5.
            # Confirmado: KMAG9001PM-B814 = 128GB UFS 3.1 + 8GB LPDDR5-6400. 297 FBGA.
            # SAM_EMCP_CAP G9=128GB+8GB (entrada adicionada 2026-05-28).
            # priority=38: mais específico que KM (2 chars, priority=90).
            dict(
                prefix="KMAG", chip_type="uMCP", subtype="LPDDR5 + UFS 3.1 (128GB flagship)",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=38,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung KMAG — FLAGSHIP. UFS 3.1 (~2400 MB/s) + LPDDR5-6400. "
                    "Confirmado: KMAG9001PM-B814 = 128GB UFS 3.1 + 64Gb÷8=8GB LPDDR5 ✓. "
                    "297-ball FBGA. SAM_EMCP_CAP G9=128GB+8GB. "
                    "⚠ VDDQ=0.6V (LPDDR5 — diferente do LPDDR4X). NÃO confundir na bancada. "
                    "Destinado a flagships Galaxy 2022+. Valor comercial MUITO ELEVADO. "
                    "Destino: bancada reacondicional uMCP (Flagship Tier)."
                ),
            ),
            # ── KMAS: uMCP UFS 3.1 + LPDDR5 (256GB) ─────────────────────────────
            # pn[2]='A', pn[3]='S' → subfamília 256GB UFS 3.1 + 8GB LPDDR5.
            # Confirmado: KMAS9001PM-BC02 = 256GB UFS 3.1 + 8GB LPDDR5-6400. 297 FBGA.
            # SAM_EMCP_CAP S9=256GB+8GB (entrada adicionada 2026-05-28).
            # priority=38: mais específico que KM (2 chars, priority=90).
            dict(
                prefix="KMAS", chip_type="uMCP", subtype="LPDDR5 + UFS 3.1 (256GB flagship)",
                interface="UFS 3.1", pn_length=10,
                is_emcp=True, active=True, priority=38,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ uMCP Samsung KMAS — FLAGSHIP 256GB. UFS 3.1 (~2400 MB/s) + LPDDR5-6400. "
                    "Confirmado: KMAS9001PM-BC02 = 256GB UFS 3.1 + 64Gb÷8=8GB LPDDR5 ✓. "
                    "297-ball FBGA. SAM_EMCP_CAP S9=256GB+8GB. Sufixo -BC02 (geração C, mais nova). "
                    "⚠ VDDQ=0.6V (LPDDR5). NÃO confundir KMAS com KMDX (eMCP LPDDR4X). "
                    "Destinado a flagships Galaxy 2022+. Valor comercial MUITO ELEVADO. "
                    "Destino: bancada reacondicional uMCP (Flagship Tier)."
                ),
            ),

            dict(
                # KMV = eMCP legado (2010-2013): LPDDR2 + eMMC.
                # ⚠ NÃO confundir com KM2V / KM3V (uMCP flagship LPDDR5X 2022+).
                #   A ordem importa: KMV3 = legado (V depois do K); KM3V = moderno (V no fim).
                # KMV2.../KMV3... são eMCP legado também — removidas famílias separadas (2026-05-13).
                # decode_gen_pos=None: SAM_EMCP_GEN['V']="LPDDR5/5X" — errado para legado.
                # RAM type documentado no tip; campo emcp_ram fica nulo (aceitável).
                # Dispositivos confirmados: KMVYL000LM (Galaxy S3 Mini), KMV3W000LW (Galaxy S4 era).
                prefix="KMV", chip_type="eMCP", subtype="LPDDR2 + eMMC (legado)",
                interface="eMMC", pn_length=10,
                is_emcp=True, active=True, priority=40,
                decode_gen_pos=None, decode_gen_map="",
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="SAM_EMCP_CAP",
                tip=(
                    "⚠ KMV LEGADO — eMCP LPDDR2 + eMMC (~2010-2013). "
                    "Toda a família KMV (incluindo KMV2.../KMV3...) é eMCP da era Galaxy S3/S4. "
                    "NÃO confundir com KM2V/KM3V (flagship 2022+ — dígito ANTES do V). "
                    "Dispositivos: Galaxy S3 Mini (KMVYL000LM — 8GB+1GB), Galaxy S4 era (KMV3W — 16GB+512MB). "
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
            # ── K4W = gDDR3 (Graphics DDR3) ──────────────────────────────────
            # NÃO é DDR3L ultrabook (erro da auditoria anterior).
            # gDDR3 é DDR3 com timing/empacotamento otimizado para VRAM dedicada
            # em GPUs de entrada e notebooks com vídeo discreto soldado.
            # PNs confirmados por esquemáticos e Octopart (2026-05-09):
            #   K4W1G1646D-EC12: 1Gb (128MB), 64Mx16 — ATI Radeon HD 4550
            #   K4W2G1646C-HC11: 2Gb (256MB) — Dell N4110 VRAM (+1.5V_GFX)
            #   K4W4G1646:       4Gb (512MB) — mercado secundário VRAM GPU
            # Decode: pn[3:5] via DRAM_PC (1G=1Gb · 2G=2Gb · 4G=4Gb) ✓
            dict(
                prefix="K4W", chip_type="GDDR3", subtype="gDDR3 (Graphics DDR3)",
                interface="gDDR3", decode_density_type="pc",
                is_emcp=False, active=True, priority=100,
                tip=(
                    "gDDR3 Samsung (Graphics DDR3) — VRAM dedicada em GPUs de entrada "
                    "e notebooks com vídeo discreto soldado (~2008-2013). "
                    "W = gDDR3; NÃO confundir com K4B (DDR3 de sistema). "
                    "Densidade: pn[3:5] → DRAM_PC: 1G=1Gb(128MB) · 2G=2Gb(256MB) · 4G=4Gb(512MB). "
                    "Chips confirmados: K4W1G1646D-EC12 (ATI Radeon HD 4550), "
                    "K4W2G1646C-HC11 (Dell N4110 VRAM). "
                    "Tensão diferente do DDR3 sistema — NÃO misturar na bancada. "
                    "Destino: bancada reacondicional GPU (junto com K4J/K4G)."
                ),
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
            # variabilidade — usar Nexar/Octopart para confirmar capacidade. Adicionar via fix_known_parts.
            dict(
                prefix="K9F", chip_type="NAND Flash", subtype="Samsung SLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9F = Samsung NAND Flash SLC. Alta durabilidade (~100K ciclos P/E). "
                    "Densidade: pn[3:5] → 1G=1Gb(128MB) · 2G=2Gb(256MB) · 4G=4Gb(512MB) · 8G=8Gb(1GB). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9G", chip_type="NAND Flash", subtype="Samsung MLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9G = Samsung NAND Flash MLC. "
                    "Densidade: pn[3:5] → AG=16Gb(2GB) · BG=32Gb(4GB). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9H", chip_type="NAND Flash", subtype="Samsung MLC NAND (Large Page)",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9H = Samsung NAND Flash MLC Large Page. "
                    "Densidade: pn[3:5] → DG=128Gb(16GB) e anteriores via NAND_FLASH_CAP. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9K", chip_type="NAND Flash", subtype="Samsung SLC/MLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9K = Samsung NAND Flash (SLC/MLC misto). "
                    "Densidade: pn[3:5] → 8G=8Gb(1GB) e outras via NAND_FLASH_CAP. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9L", chip_type="NAND Flash", subtype="Samsung MLC/TLC NAND",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9L = Samsung NAND Flash MLC/TLC. Custo reduzido. "
                    "Densidade: pn[3:5] → CG=64Gb(8GB) e outras via NAND_FLASH_CAP. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9W", chip_type="NAND Flash", subtype="Samsung SLC NAND (Industrial)",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9W = Samsung NAND Flash SLC industrial/white label. "
                    "Densidade: pn[3:5] → NAND_FLASH_CAP (1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB). "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9X", chip_type="NAND Flash", subtype="Samsung MLC NAND (Expandido)",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9X = Samsung NAND Flash MLC expandido. "
                    "Densidade: pn[3:5] → NAND_FLASH_CAP. "
                    "Destino: bancada reacondicional Flash.",
            ),
            dict(
                prefix="K9Z", chip_type="NAND Flash", subtype="Samsung MLC/TLC NAND (Especial)",
                interface="", is_emcp=False, active=True, priority=80,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="NAND_FLASH_CAP",
                tip="K9Z = Samsung NAND Flash MLC/TLC variante especial. "
                    "Densidade: pn[3:5] → NAND_FLASH_CAP. "
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
            # ── K5W — MCP NOR Flash + Mobile SDRAM ───────────────────────────────
            # Samsung MCP da era feature phone (Nokia, Sony-Ericsson, ~2005-2012).
            # Combina NOR Flash (boot/código) + Mobile SDRAM (RAM de trabalho) num único BGA.
            # pn[3:5] → DRAM_PC: capacidade do componente NOR.
            #   Ex: K5W1G12ACM → "1G" → DRAM_PC → 1Gb = 128MB NOR.
            # O segundo componente (SDRAM) NÃO é decodificável pelo PN sem datasheet.
            # Fonte: teardown + Censtry (K5W1G12ACM-BL60TNO classificado como SRAM/MCP) ✓
            # Destino: fluxo de resíduo. Zero liquidez B2B em 2026.
            dict(
                prefix="K5W", chip_type="MCP", subtype="NOR Flash + Mobile SDRAM (legado)",
                interface="NOR (async) + SDRAM", is_emcp=False, active=True, priority=55,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="DRAM_PC",
                tip=(
                    "MCP Samsung NOR + Mobile SDRAM — era feature phone (~2005-2012). "
                    "NOR Flash (código/boot) + SDRAM (RAM de trabalho) num único BGA. "
                    "Capacidade exibida = NOR Flash (pn[3:5]). SDRAM não decodificável pelo PN. "
                    "Aparelhos: Nokia S60/S40, Sony-Ericsson, Samsung proprietary. "
                    "⚠ Destino: Caixa Vermelha — sem liquidez B2B. Moagem/refino."
                ),
            ),
            # ── K5L — MCP NOR Flash + UtRAM (micro SRAM) ─────────────────────────
            # Samsung MCP NOR + UtRAM (ultra-thin RAM = SRAM de baixo consumo).
            # Confirmado: K5L2731CAA-D770 = 128Mb NOR + 32Mb UtRAM (Jotrin ✓).
            #             K5L5563CAA-D770 = 256Mb NOR + 64Mb UtRAM (padrão K5L ✓).
            # pn[3:5]: os dois primeiros dígitos podem não mapear 1:1 com DRAM_PC.
            #   K5L2731: "27" → não está em DRAM_PC (próximo de "28"=128Mb — encoding próprio).
            #   Capacidade = "parcial" — gramática reconhece família mas não decodifica cap.
            # Destino: fluxo de resíduo. Zero liquidez B2B em 2026.
            dict(
                prefix="K5L", chip_type="MCP", subtype="NOR Flash + UtRAM (legado)",
                interface="NOR (async) + SRAM", is_emcp=False, active=True, priority=55,
                tip=(
                    "MCP Samsung NOR + UtRAM (micro SRAM) — era feature phone (~2003-2010). "
                    "NOR Flash (código/boot) + UtRAM (SRAM ultra-fino de baixo consumo). "
                    "Exemplos confirmados: K5L2731=128Mb NOR+32Mb UtRAM, K5L5563=256Mb NOR+64Mb UtRAM. "
                    "⚠ Destino: Caixa Vermelha — sem liquidez B2B. Moagem/refino."
                ),
            ),
            # ── K5N — MCP NOR Flash + PSRAM ───────────────────────────────────────
            # Samsung MCP NOR + PSRAM (Pseudo-SRAM = DRAM com interface SRAM).
            # Confirmado: K5N1229ACC-BQ12 (Jotrin) — família K5N existente.
            # Capacidade não decodificável sem datasheet — encoding proprietário.
            # Destino: fluxo de resíduo. Zero liquidez B2B em 2026.
            dict(
                prefix="K5N", chip_type="MCP", subtype="NOR Flash + PSRAM (legado)",
                interface="NOR (async) + PSRAM", is_emcp=False, active=True, priority=55,
                tip=(
                    "MCP Samsung NOR + PSRAM (Pseudo-SRAM) — era feature phone (~2004-2011). "
                    "NOR Flash (código/boot) + PSRAM (DRAM com interface SRAM). "
                    "⚠ Destino: Caixa Vermelha — sem liquidez B2B. Moagem/refino."
                ),
            ),
            # ── K5 (fallback) — NOR Flash Samsung genérico ────────────────────────
            # Captura qualquer K5xx não mapeado pelas subfamílias específicas acima.
            # Subfamílias conhecidas: K5D=OneNAND · K5W=NOR+SDRAM · K5L=NOR+UtRAM · K5N=NOR+PSRAM
            # K5E = MCP NAND+DDR (era diferente, não NOR — raro na esteira).
            dict(
                prefix="K5", chip_type="NOR Flash", subtype="Samsung NOR Flash",
                interface="NOR", is_emcp=False, active=True, priority=100,
                tip=(
                    "NOR Flash Samsung (K5). Subfamílias comuns na esteira: "
                    "K5W=NOR+SDRAM · K5L=NOR+UtRAM · K5N=NOR+PSRAM · K5D=OneNAND. "
                    "Todos são chips da era feature phone (~2003-2012). "
                    "⚠ Destino: Caixa Vermelha — sem liquidez B2B em 2026."
                ),
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
                tip="BGA NVMe SSD Samsung PM971 — capacidades: 02=128GB, 03=256GB, 04=512GB. "
                    "Série encerra em 512GB (PM971). 1TB+ usa outras famílias (PM991). "
                    "JAMAIS misturar com eMMC ou UFS. "
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
