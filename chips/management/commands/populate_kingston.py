"""
populate_kingston.py
====================
Popula o banco com as famílias eMCP Kingston e seus mapas de
decodificação posicional.

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

Regra de ouro (hierarquia de fontes — nunca quebrar):
    fabricante oficial (datasheet / semiconductor.kingston.com)
      > Octopart (PN confirmado com especificações)
        > distribuidor B2B rastreável (Puris, ssfkg, Win Source, Veswin)
          > Preduo (preduo.com — catálogo de reciclagem)
            > IA externa
              > especulação

⚠  ALERTA ARQUITETURAL — PREFIXO EMCP MORTO:
    O stub "EMCP" criado em add_chip_families.py NUNCA casa via
    pn.startswith("EMCP"), pois todos os PNs reais Kingston eMCP começam
    com dígitos: "04EMCP...", "08EMCP...", "16EMCP...", etc.
    Este populate cria as 5 famílias corretas com prefixos numéricos.
    O stub "EMCP" pode ser desativado (active=False) manualmente.

Anatomia PN Kingston eMCP:
    1  6  E  M  C  P  0  8  -  N  L  3  D  T  B  2  8
    0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16

    pn[0:2]  = código NAND (2 chars)  → KST_EMCP_NAND_CAP
    pn[2:6]  = literal "EMCP"
    pn[6:8]  = código RAM  (2 chars)  → KST_EMCP_RAM_CAP
    pn[8]    = literal "-"
    pn[9:12] = sufixo de geração RAM (NL2=LPDDR2/162ball, NL3=LPDDR3/221ball,
               EL3=LPDDR3/221ball nova revisão)

Fontes para esta família (tudo verificado em Puris.net B2B — nível 4 hierarquia):
    04EMCP04-NL2DM627  → 4GB  eMMC 5.0 + 4Gb  LPDDR2 (512MB), 162ball
    08EMCP04-NL2DT227  → 8GB  eMMC 5.0 + 4Gb  LPDDR2 (512MB), 162ball
    08EMCP08-NL2DT227  → 8GB  eMMC 5.0 + 8Gb  LPDDR2 (1GB),   162ball
    04EMCP04-NL3DM627  → 4GB  eMMC 5.0 + 4Gb  LPDDR3 (512MB), 221ball
    08EMCP04-NL3DT227  → 8GB  eMMC 5.0 + 4Gb  LPDDR3 (512MB), 221ball
    08EMCP08-NL3DT227  → 8GB  eMMC 5.0 + 8Gb  LPDDR3 (1GB),   221ball
    16EMCP08-NL3DTB28  → 16GB eMMC 5.1 + 8Gb  LPDDR3 (1GB),   221ball  ← chip físico confirmado (eMiner 2026-05-25)
    16EMCP16-EL3GTB29  → 16GB eMMC 5.1 + 16Gb LPDDR3 (2GB),   221ball
    32EMCP16-EL3GTB29  → 32GB eMMC 5.1 + 16Gb LPDDR3 (2GB),   221ball
    32EMCP24-EL3JTB29  → 32GB eMMC 5.1 + 24Gb LPDDR3 (3GB),   221ball
    64EMCP24-EL3JTA29  → 64GB eMMC 5.1 + 24Gb LPDDR3 (3GB),   221ball
    64EMCP32-EL3HTA29  → 64GB eMMC 5.1 + 32Gb LPDDR3 (4GB),   221ball

⚠  ERRO DE IA DOCUMENTADO:
    '32EMCP16-NL3DTB29' citado por IA como PN real. Verificação Puris.net:
    PN NÃO EXISTE. O real é '32EMCP16-EL3GTB29'. Sufixo foi inventado pela IA.
    Capacidade estava correta (32GB+2GB), prefixo estava correto, sufixo errado.

Uso:
    python manage.py populate_kingston
    python manage.py populate_kingston --dry-run    # mostra o que faria sem salvar
    python manage.py populate_kingston --overwrite  # atualiza entradas existentes
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação Kingston eMCP no banco."

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
            self.stdout.write(self.style.SUCCESS("\n✅  Kingston eMCP populada com sucesso."))
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
        kingston, created = Brand.objects.get_or_create(
            name="Kingston",
            defaults={
                "code": "KST",
                "notes": "EUA · Fundada 1987 · eMCP linha descontinuada (substituída por eMMC+LPDDR separados)",
            },
        )
        self._log(created, "Marca", "Kingston", dry)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: KST_EMCP_NAND_CAP — Capacidade NAND Kingston eMCP
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[0:2], comprimento 2 chars.
        # Anatomia: [nand_hi][nand_lo] E M C P [ram_hi][ram_lo] - ...
        #               0         1    2 3 4 5     6        7    8
        #
        # O código NAND (pn[0:2]) é idêntico à capacidade em GB com 0-padding:
        #   "04" = 4GB  · "08" = 8GB  · "16" = 16GB · "32" = 32GB · "64" = 64GB
        #
        # Fonte: Puris.net B2B — 12 PNs confirmados (nível 4 hierarquia) ✓
        #   04EMCP04 → 4GB  NAND ✓ · 08EMCP04 → 8GB  NAND ✓
        #   08EMCP08 → 8GB  NAND ✓ · 16EMCP08 → 16GB NAND ✓ (chip físico eMiner ✓)
        #   16EMCP16 → 16GB NAND ✓ · 32EMCP16 → 32GB NAND ✓
        #   32EMCP24 → 32GB NAND ✓ · 64EMCP24 → 64GB NAND ✓
        #   64EMCP32 → 64GB NAND ✓
        #
        # Nota: cada família tem seu próprio prefixo ("04EMCP", "08EMCP", etc.)
        # e aponta para este mesmo mapa. O engine filtra o prefixo primeiro,
        # depois fatia pn[0:2] — sem risco de ambiguidade entre famílias.
        #
        nand_cap = [
            # char_key  val_primary  val_secondary
            ("04", "4GB",  ""),  # 04EMCP04-NL2DM627 ✓ · 04EMCP04-NL3DM627 ✓ (Puris.net)
            ("08", "8GB",  ""),  # 08EMCP04-NL2DT227 ✓ · 08EMCP08-NL2DT227 ✓
                                  # 08EMCP04-NL3DT227 ✓ · 08EMCP08-NL3DT227 ✓ (Puris.net)
            ("16", "16GB", ""),  # 16EMCP08-NL3DTB28 ✓ (chip físico na esteira, eMiner 2026-05-25)
                                  # 16EMCP16-EL3GTB29 ✓ (Puris.net)
            ("32", "32GB", ""),  # 32EMCP16-EL3GTB29 ✓ · 32EMCP24-EL3JTB29 ✓ (Puris.net)
            ("64", "64GB", ""),  # 64EMCP24-EL3JTA29 ✓ · 64EMCP32-EL3HTA29 ✓ (Puris.net)
        ]
        self._bulk_map("KST_EMCP_NAND_CAP", nand_cap, kingston, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: KST_EMCP_RAM_CAP — RAM Kingston eMCP, chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[6:8], comprimento 2 chars.
        # val_primary = string COMPLETA "LPDDR3 XGB" — o engine usa diretamente
        # como emcp_ram quando _ram_cap é None (padrão Hynix-style).
        #
        # ⚠  LIMITAÇÃO: LPDDR2 vs LPDDR3 têm o MESMO código pn[6:8].
        #   Exemplo: pn[6:8]="04" pode ser LPDDR2 512MB (sufixo NL2) OU
        #   LPDDR3 512MB (sufixo NL3). O mapa padrão assume LPDDR3 por ser
        #   a geração mais comum na esteira. Chips com sufixo NL2 (LPDDR2,
        #   162ball) devem ser corrigidos via fix_known_parts com confidence=confirmed.
        #   Identificação visual: NL2 = package menor (162 balls), NL3 = 221 balls.
        #
        # ⚠  ERRO DE IA DOCUMENTADO (não repetir):
        #   '32EMCP16-NL3DTB29' não existe. Real: '32EMCP16-EL3GTB29'.
        #   IA inventou o sufixo; Puris.net B2B confirma o PN correto.
        #
        # Chave → densidade RAM → capacidade:
        #   "04" = 4Gb  LPDDR3 → 512MB   ·  "08" = 8Gb  LPDDR3 → 1GB
        #   "16" = 16Gb LPDDR3 → 2GB     ·  "24" = 24Gb LPDDR3 → 3GB
        #   "32" = 32Gb LPDDR3 → 4GB
        #
        # Fonte: Puris.net B2B — 12 PNs cruzados ✓
        #   "04"=512MB: 04EMCP04-NL2DM627 · 08EMCP04-NL2DT227
        #               04EMCP04-NL3DM627 · 08EMCP04-NL3DT227 ✓
        #   "08"=1GB:   08EMCP08-NL2DT227 · 08EMCP08-NL3DT227
        #               16EMCP08-NL3DTB28 ✓ (chip físico eMiner 2026-05-25)
        #   "16"=2GB:   16EMCP16-EL3GTB29 · 32EMCP16-EL3GTB29 ✓
        #   "24"=3GB:   32EMCP24-EL3JTB29 · 64EMCP24-EL3JTA29 ✓
        #   "32"=4GB:   64EMCP32-EL3HTA29 ✓
        #
        ram_cap = [
            # char_key  val_primary        val_secondary
            ("04", "LPDDR3 512MB", ""),  # 4Gb ÷ 8 = 512MB — NL3DM627/NL3DT227 ✓
                                          # ⚠ NL2 (LPDDR2) usa a mesma chave — ver limitação acima
            ("08", "LPDDR3 1GB",   ""),  # 8Gb ÷ 8 = 1GB — NL3DTB28 ✓ (chip físico)
                                          # ⚠ NL2 (LPDDR2) usa a mesma chave — ver limitação acima
            ("16", "LPDDR3 2GB",   ""),  # 16Gb ÷ 8 = 2GB — EL3GTB29 ✓
            ("24", "LPDDR3 3GB",   ""),  # 24Gb ÷ 8 = 3GB — EL3JTB29 · EL3JTA29 ✓
            ("32", "LPDDR3 4GB",   ""),  # 32Gb ÷ 8 = 4GB — EL3HTA29 ✓
        ]
        self._bulk_map("KST_EMCP_RAM_CAP", ram_cap, kingston, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # ChipFamilies Kingston eMCP
        # ══════════════════════════════════════════════════════════════════════
        families = self._families(kingston)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != kingston.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = kingston
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

    def _families(self, kingston):
        """Retorna lista de dicts de famílias Kingston eMCP para upsert."""
        return [

            # ═══ eMCP Kingston (04EMCP / 08EMCP / 16EMCP / 32EMCP / 64EMCP) ══
            #
            # Anatomia do PN:
            #   [nand][nand] E  M  C  P  [ram][ram] - [sufixo]
            #       0     1  2  3  4  5    6    7   8
            #
            #   pn[0:2] = capacidade NAND (decode_cap_pos=0, decode_cap_len=2)
            #             → KST_EMCP_NAND_CAP
            #   pn[6:8] = capacidade RAM  (decode_gen_pos=6, decode_gen_len=2)
            #             → KST_EMCP_RAM_CAP (val_primary = "LPDDR3 XGB" completo)
            #
            # fam.interface é usado pelo engine como nand_version:
            #   r["emcp_nand"] = f"{fam.interface} {_nand_cap}"
            #   Ex: "eMMC 5.1" + " " + "16GB" = "eMMC 5.1 16GB"
            #
            # decode_gen_map val_primary = string COMPLETA "LPDDR3 XGB" →
            #   _decoded_gen = "LPDDR3 1GB" → ram_type = "LPDDR3 1GB"
            #   _ram_cap = None (val_secondary="") → engine usa ram_type diretamente
            #   r["emcp_ram"] = ram_type = "LPDDR3 1GB" ✓
            #
            # grammar_complete requer _CAP_RE.search(_decoded_gen) → "1GB" presente ✓
            #
            # ⚠  NOTA SOBRE O STUB MORTO em add_chip_families.py:
            #   O prefixo "EMCP" cadastrado no stub nunca casa via startswith()
            #   porque todos os PNs reais começam com dígitos ("16EMCP08...").
            #   Este populate cria os 5 prefixos corretos abaixo.
            #   Desativar o stub "EMCP" com active=False se necessário.
            #
            # ⚠  NOTA SOBRE LPDDR2 (sufixo NL2, 162ball):
            #   Chips com sufixo NL2 na posição 9-11 do PN são LPDDR2, não LPDDR3.
            #   O mapa assume LPDDR3 (maioria da produção Kingston eMCP).
            #   Correções específicas para PNs NL2 devem ir para fix_known_parts.py
            #   com confidence=confirmed e emcp_ram="LPDDR2 X".
            #
            # Fonte: Puris.net B2B — 12 PNs da família completa verificados ✓
            #        Chip físico 16EMCP08-NL3DTB28 confirmado na esteira (eMiner 2026-05-25) ✓
            #

            # ── 04EMCP — 4GB eMMC 5.0 ──────────────────────────────────────
            # PNs confirmados: 04EMCP04-NL2DM627 · 04EMCP04-NL3DM627
            # Geração mais antiga (eMMC 5.0), RAM 512MB (4Gb LPDDR2 ou LPDDR3).
            # Origem: smartphones de entrada 2013–2015 (SoCs MediaTek MT6582/MT6592).
            dict(
                prefix="04EMCP",
                chip_type="eMCP", subtype="eMCP Kingston",
                interface="eMMC 5.0",
                is_emcp=True, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=0, decode_cap_len=2, decode_cap_map="KST_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="KST_EMCP_RAM_CAP",
                reasoning=(
                    "Prefixo positional Kingston eMCP 4GB. "
                    "pn[0:2]='04' casa com KST_EMCP_NAND_CAP → 4GB NAND. "
                    "pn[6:8] casa com KST_EMCP_RAM_CAP → RAM. "
                    "Fonte: Puris.net B2B ✓ (04EMCP04-NL2DM627 · 04EMCP04-NL3DM627). "
                    "⚠ NL2=LPDDR2 e NL3=LPDDR3 — mapa assume LPDDR3; NL2 → fix_known_parts."
                ),
                tip=(
                    "eMCP Kingston 4GB eMMC 5.0 (04EMCP). Chip combinado eMMC + RAM. "
                    "pn[0:2] = capacidade NAND: 04=4GB. "
                    "pn[6:8] = capacidade RAM: 04=512MB. "
                    "⚠ Dois variantes: NL2 (LPDDR2, 162ball) e NL3 (LPDDR3, 221ball). "
                    "O mapa padrão retorna LPDDR3 — verificar sufixo NL2/NL3 visualmente. "
                    "PNs confirmados: 04EMCP04-NL2DM627 (LPDDR2) · 04EMCP04-NL3DM627 (LPDDR3). "
                    "Geração mais antiga Kingston eMCP — smartphones de entrada 2013–2015. "
                    "Destino: bancada eMCP legado."
                ),
            ),

            # ── 08EMCP — 8GB eMMC 5.0 ──────────────────────────────────────
            # PNs confirmados: 08EMCP04-NL2DT227 · 08EMCP08-NL2DT227
            #                  08EMCP04-NL3DT227 · 08EMCP08-NL3DT227
            # Variações de RAM: 512MB (código "04") e 1GB (código "08").
            # Origem: smartphones de entrada/médio 2014–2016.
            dict(
                prefix="08EMCP",
                chip_type="eMCP", subtype="eMCP Kingston",
                interface="eMMC 5.0",
                is_emcp=True, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=0, decode_cap_len=2, decode_cap_map="KST_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="KST_EMCP_RAM_CAP",
                reasoning=(
                    "Prefixo positional Kingston eMCP 8GB. "
                    "pn[0:2]='08' casa com KST_EMCP_NAND_CAP → 8GB NAND. "
                    "pn[6:8] casa com KST_EMCP_RAM_CAP → RAM (04=512MB ou 08=1GB). "
                    "Fonte: Puris.net B2B ✓ (4 PNs confirmados). "
                    "⚠ NL2=LPDDR2 e NL3=LPDDR3 — mapa assume LPDDR3; NL2 → fix_known_parts."
                ),
                tip=(
                    "eMCP Kingston 8GB eMMC 5.0 (08EMCP). Chip combinado eMMC + RAM. "
                    "pn[0:2] = capacidade NAND: 08=8GB. "
                    "pn[6:8] = capacidade RAM: 04=512MB · 08=1GB. "
                    "⚠ Dois variantes: NL2 (LPDDR2, 162ball) e NL3 (LPDDR3, 221ball). "
                    "O mapa padrão retorna LPDDR3 — verificar sufixo NL2/NL3 visualmente. "
                    "PNs confirmados: 08EMCP04-NL2DT227 · 08EMCP08-NL2DT227 (LPDDR2) · "
                    "08EMCP04-NL3DT227 · 08EMCP08-NL3DT227 (LPDDR3). "
                    "Destino: bancada eMCP legado."
                ),
            ),

            # ── 16EMCP — 16GB eMMC 5.1 ─────────────────────────────────────
            # PNs confirmados: 16EMCP08-NL3DTB28 (chip físico na esteira, eMiner 2026-05-25)
            #                  16EMCP16-EL3GTB29
            # Salto para eMMC 5.1 — geração intermediária, alto volume na esteira.
            # RAM: 1GB (código "08") ou 2GB (código "16").
            dict(
                prefix="16EMCP",
                chip_type="eMCP", subtype="eMCP Kingston",
                interface="eMMC 5.1",
                is_emcp=True, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=0, decode_cap_len=2, decode_cap_map="KST_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="KST_EMCP_RAM_CAP",
                reasoning=(
                    "Prefixo positional Kingston eMCP 16GB. "
                    "pn[0:2]='16' casa com KST_EMCP_NAND_CAP → 16GB NAND. "
                    "pn[6:8] casa com KST_EMCP_RAM_CAP → RAM (08=1GB ou 16=2GB). "
                    "Fonte: chip físico 16EMCP08-NL3DTB28 confirmado na esteira (eMiner 2026-05-25) ✓ "
                    "Puris.net B2B confirma: 16GB eMMC 5.1 (HS400) + 8Gb LPDDR3 → 1GB RAM. "
                    "16EMCP16-EL3GTB29: 16GB eMMC 5.1 + 16Gb LPDDR3 → 2GB RAM (Puris.net ✓). "
                    "NL3=LPDDR3 verificado em 6 PNs cruzados da família Kingston eMCP."
                ),
                tip=(
                    "eMCP Kingston 16GB eMMC 5.1 (16EMCP). Chip combinado eMMC + RAM — geração principal. "
                    "pn[0:2] = capacidade NAND: 16=16GB. "
                    "pn[6:8] = capacidade RAM: 08=1GB LPDDR3 · 16=2GB LPDDR3. "
                    "✅ 16EMCP08-NL3DTB28 confirmado fisicamente na esteira (eMiner 2026-05-25). "
                    "⚠ Sufixo NL3 = LPDDR3 (221ball) — sem variante NL2/LPDDR2 nesta capacidade. "
                    "⚠ EL3 (ex: EL3GTB29) = nova revisão de package LPDDR3, mesma capacidade. "
                    "Ex: 16EMCP08-NL3DTB28 = eMMC 5.1 16GB + LPDDR3 1GB ✓ "
                    "Ex: 16EMCP16-EL3GTB29 = eMMC 5.1 16GB + LPDDR3 2GB ✓ "
                    "Origem: smartphones midrange 2016–2018 (Snapdragon 4xx, Helio P/G). "
                    "Destino: bancada eMCP — alto volume na esteira de reciclagem."
                ),
            ),

            # ── 32EMCP — 32GB eMMC 5.1 ─────────────────────────────────────
            # PNs confirmados: 32EMCP16-EL3GTB29 · 32EMCP24-EL3JTB29
            # RAM: 2GB (código "16") ou 3GB (código "24").
            # ⚠ '32EMCP16-NL3DTB29' NÃO EXISTE — IA inventou o sufixo.
            #    PN real: '32EMCP16-EL3GTB29' (Puris.net ✓).
            dict(
                prefix="32EMCP",
                chip_type="eMCP", subtype="eMCP Kingston",
                interface="eMMC 5.1",
                is_emcp=True, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=0, decode_cap_len=2, decode_cap_map="KST_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="KST_EMCP_RAM_CAP",
                reasoning=(
                    "Prefixo positional Kingston eMCP 32GB. "
                    "pn[0:2]='32' casa com KST_EMCP_NAND_CAP → 32GB NAND. "
                    "pn[6:8] casa com KST_EMCP_RAM_CAP → RAM (16=2GB ou 24=3GB). "
                    "Fonte: Puris.net B2B ✓ (32EMCP16-EL3GTB29 · 32EMCP24-EL3JTB29). "
                    "⚠ ERRO DE IA DOCUMENTADO: '32EMCP16-NL3DTB29' NÃO EXISTE. "
                    "IA inventou sufixo; PN real é '32EMCP16-EL3GTB29' (Puris.net ✓). "
                    "EL3=nova revisão LPDDR3 package — sem variante NL3 ou NL2 nesta capacidade."
                ),
                tip=(
                    "eMCP Kingston 32GB eMMC 5.1 (32EMCP). Chip combinado eMMC + RAM. "
                    "pn[0:2] = capacidade NAND: 32=32GB. "
                    "pn[6:8] = capacidade RAM: 16=2GB LPDDR3 · 24=3GB LPDDR3. "
                    "⚠ ERRO DE IA DOCUMENTADO: '32EMCP16-NL3DTB29' NÃO EXISTE. "
                    "PN real confirmado: '32EMCP16-EL3GTB29' (Puris.net B2B ✓). "
                    "⚠ Todos os PNs 32GB usam sufixo EL3 (nova revisão) — sem NL2/NL3. "
                    "Ex: 32EMCP16-EL3GTB29 = eMMC 5.1 32GB + LPDDR3 2GB ✓ "
                    "Ex: 32EMCP24-EL3JTB29 = eMMC 5.1 32GB + LPDDR3 3GB ✓ "
                    "Origem: smartphones premium 2017–2019. "
                    "Destino: bancada eMCP — componente de alto valor."
                ),
            ),

            # ── 64EMCP — 64GB eMMC 5.1 ─────────────────────────────────────
            # PNs confirmados: 64EMCP24-EL3JTA29 · 64EMCP32-EL3HTA29
            # RAM: 3GB (código "24") ou 4GB (código "32").
            # Teto da linha Kingston eMCP — sem 128GB confirmado.
            dict(
                prefix="64EMCP",
                chip_type="eMCP", subtype="eMCP Kingston",
                interface="eMMC 5.1",
                is_emcp=True, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=0, decode_cap_len=2, decode_cap_map="KST_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="KST_EMCP_RAM_CAP",
                reasoning=(
                    "Prefixo positional Kingston eMCP 64GB. "
                    "pn[0:2]='64' casa com KST_EMCP_NAND_CAP → 64GB NAND. "
                    "pn[6:8] casa com KST_EMCP_RAM_CAP → RAM (24=3GB ou 32=4GB). "
                    "Fonte: Puris.net B2B ✓ (64EMCP24-EL3JTA29 · 64EMCP32-EL3HTA29). "
                    "Teto confirmado da linha Kingston eMCP — sem 128GB em nenhuma fonte verificável. "
                    "EL3=nova revisão package LPDDR3 — sem variante NL2/NL3 nesta capacidade."
                ),
                tip=(
                    "eMCP Kingston 64GB eMMC 5.1 (64EMCP). Chip combinado eMMC + RAM — topo da linha. "
                    "pn[0:2] = capacidade NAND: 64=64GB. "
                    "pn[6:8] = capacidade RAM: 24=3GB LPDDR3 · 32=4GB LPDDR3. "
                    "⚠ Teto da linha Kingston eMCP — 128GB não confirmado em nenhuma fonte. "
                    "⚠ Todos os PNs 64GB usam sufixo EL3 (nova revisão) — sem NL2/NL3. "
                    "Ex: 64EMCP24-EL3JTA29 = eMMC 5.1 64GB + LPDDR3 3GB ✓ "
                    "Ex: 64EMCP32-EL3HTA29 = eMMC 5.1 64GB + LPDDR3 4GB ✓ "
                    "Origem: smartphones premium 2018–2020. "
                    "Destino: bancada eMCP — componente de alto valor, prioridade na triagem."
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
