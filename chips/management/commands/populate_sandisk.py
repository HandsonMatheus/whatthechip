"""
populate_sandisk.py
====================
Popula o banco com as famílias de chips SanDisk / Western Digital.

Idempotente: usa get_or_create + upsert em tudo. Pode ser rodado múltiplas vezes.

Regra de ouro (hierarquia de fontes — nunca quebrar):
    fabricante (westerndigital.com, wdc.com, datasheet)
      > Octopart (PN confirmado com especificações)
        > distribuidor B2B rastreável (Puris, ssfkg, Win Source, Veswin)
          > Preduo (preduo.com — catálogo de reciclagem)
            > IA externa
              > especulação

Nota sobre nomenclatura:
    SanDisk foi adquirida pela Western Digital (WD) em 2016.
    O nome "SanDisk" persiste nos PNs dos chips; a fonte autoritativa é
    westerndigital.com / wdc.com.

Peculiaridade crítica da nomenclatura SanDisk:
    A capacidade NÃO fica numa posição fixa do PN — fica no SUFIXO após o traço:
        SD7DP24C  -  4G  →  capacidade declarada: 4GB
        ^^^^^^^^     ^^
        Família      Sufixo (declaração de fábrica)

    O engine strip espaços e não-alfanuméricos: "SD7DP24C-4G" → "SD7DP24C4G".
    O sufixo fica sempre no FINAL do PN processado, mas em posição variável
    porque o die code intermediário pode ter comprimentos distintos.

    Consequência: decode posicional (decode_cap_pos/decode_cap_map) NÃO funciona
    de forma confiável para capacidade na maioria das famílias SanDisk.
    A abordagem correta é fix_known_parts.py para PNs físicos confirmados.

Uso:
    python manage.py populate_sandisk
    python manage.py populate_sandisk --dry-run    # mostra o que faria sem salvar
    python manage.py populate_sandisk --overwrite  # atualiza entradas existentes
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias de chips SanDisk / Western Digital no banco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as operações sem salvar no banco.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Atualiza entradas existentes no banco (ChipFamily).",
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
            self.stdout.write(self.style.SUCCESS("\n✅  SanDisk populada com sucesso."))
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                self.stdout.write("   🗑  Cache do engine invalidado.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    # ──────────────────────────────────────────────────────────────────────────

    def _run(self, dry, overwrite=False):
        from chips.models import Brand, ChipFamily

        # ── Marca ─────────────────────────────────────────────────────────────
        # SanDisk foi adquirida pela WD em 2016. O nome "SanDisk" persiste nos
        # PNs físicos gravados nos chips. O import_chipid normaliza "Sandisk"→"SanDisk".
        sandisk, created = Brand.objects.get_or_create(
            name="SanDisk",
            defaults={
                "code":  "SDK",
                "notes": "EUA · Adquirida pela Western Digital (WD) em 2016 · Documentação em westerndigital.com / wdc.com",
            },
        )
        self._log(created, "Marca", "SanDisk", dry)

        # ══════════════════════════════════════════════════════════════════════
        # Nota sobre decode maps SanDisk
        # ══════════════════════════════════════════════════════════════════════
        #
        # SanDisk usa SUFIXO DECLARATIVO para capacidade (ex: -4G, -8G, -16G),
        # diferentemente de Samsung e SK Hynix que usam posição fixa no PN.
        #
        # Tentativa de decode posicional:
        #   Ex: SD7DP24C-4G → engine strip → SD7DP24C4G (10 chars)
        #   Sufixo "4G" ficaria em pos=8, len=2. Funciona para 4G e 8G.
        #   Mas "-16G" → "16G" em pos=8, len=3 — comprimento diferente.
        #   → Decode por len fixo falha para 16GB, 32GB, 64GB.
        #
        # Solução adotada: sem decode maps. A tip documenta a convenção.
        # Chips confirmados fisicamente → fix_known_parts.py (create=True).
        # Isso garante capacidade correta sem risco de colisão de chaves.
        #
        # ══════════════════════════════════════════════════════════════════════
        # ChipFamilies SanDisk
        # ══════════════════════════════════════════════════════════════════════
        families = self._families(sandisk)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != sandisk.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = sandisk
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

    def _families(self, sandisk):
        """Retorna lista de dicts de famílias SanDisk para upsert."""
        return [

            # ═══ eMMC iNAND 7 Series (SD7DP) ════════════════════════════════
            #
            # Linha iNAND de sétima geração da SanDisk (pré-WD).
            # eMMC 5.1 standalone — NÃO contém RAM (não confundir com SD7D eMCP antigo).
            # Capacidade no sufixo: -4G=4GB · -8G=8GB · -16G=16GB · -32G=32GB · -64G=64GB.
            #
            # Anatomia: S  D  7  D  P  [die_code]  - [cap]
            #   Ex:     S  D  7  D  P  2  4  C  -  4  G
            #           0  1  2  3  4  5  6  7     (sufixo após traço)
            #
            # Die code (ex: 24C) mapeado nos catálogos Western Digital — identifica
            # o processo de fabricação, não a capacidade.
            #
            # Fonte confirmada:
            #   - Western Digital iNAND 7 Series datasheet (westerndigital.com) ✓
            #   - Ex: SD7DP24C-4G = 4GB eMMC 5.1 ✓ (sufixo -4G = declaração de fábrica)
            #
            # ⚠ SD7DP já existia em add_chip_families.py — este populate supersede
            #   e atualiza a entrada com tip mais detalhada.
            #
            dict(
                prefix="SD7DP",
                chip_type="eMMC",
                subtype="eMMC standalone (iNAND 7 Series)",
                interface="eMMC 5.1",
                is_emcp=False,
                active=True,
                priority=50,
                pn_length=None,  # comprimento variável (sufixo -4G ou -16G etc.)
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMMC SanDisk iNAND 7 Series (SD7DP). eMMC 5.1 standalone — sem RAM. "
                    "Capacidade declarada no sufixo após o traço: "
                    "-4G=4GB · -8G=8GB · -16G=16GB · -32G=32GB · -64G=64GB. "
                    "Die code intermediário (ex: 24C, 25F) identifica o processo WD — não é capacidade. "
                    "⚠ Sufixo truncado pelo OCR → chip aparece sem capacidade. "
                    "Usar fix_known_parts por PN específico para confirmar capacidade. "
                    "Fonte: Western Digital datasheet (westerndigital.com) ✓. "
                    "Destino: bancada eMMC."
                ),
            ),

            # ═══ iNAND eMMC legacy (SDIN...) ════════════════════════════════
            #
            # Família clássica SanDisk iNAND — prefixo mais comum no mercado de
            # reciclagem de smartphones. Geração anterior ao SD7DP.
            #
            # Abrange múltiplas gerações (eMMC 4.5, 5.0, 5.1) e variantes:
            #   SDINBAG, SDINFBNH, SDINBDG, SDINFEG, SDINBEG, etc.
            #
            # Sub-famílias UFS (prefixo mais longo = maior prioridade):
            #   SDINB... — variante UFS OEM (ex: SDINBDG4-128G UFS 2.1)
            #   O prefixo SDINB é cadastrado separadamente abaixo com priority=40.
            #
            # Capacidade: sempre no sufixo (-4G, -8G, -16G, -32G, -64G, -128G).
            # Sem decode posicional — usar fix_known_parts para PNs confirmados.
            #
            # Fonte: fab-sandisk.html (WhatTheChip doc) · catálogos WD/SanDisk ✓
            #
            dict(
                prefix="SDIN",
                chip_type="eMMC",
                subtype="eMMC iNAND (legado)",
                interface="eMMC 4.5 / 5.0 / 5.1",
                is_emcp=False,
                active=True,
                priority=80,   # prioridade menor — prefixo genérico (4 chars)
                               # SDINB (7 chars, priority=40) bate primeiro para UFS
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMMC SanDisk iNAND legado (SDIN...). Família mais comum na esteira. "
                    "Cobre múltiplas gerações: eMMC 4.5, 5.0 e 5.1. "
                    "Capacidade no sufixo após o traço: -4G=4GB · -8G=8GB · -16G=16GB · -32G=32GB · -64G=64GB · -128G=128GB. "
                    "Sub-famílias: SDINBDG4 / SDINBDD4 / SDINBDA4 = iNAND 7250/7350/7550 (eMMC 5.1). "
                    "UFS real usa prefixos SDINDDH / SDINEDK / SDINFD (famílias distintas). "
                    "⚠ SDINB... (prefixo mais longo) tem prioridade — engine bate nele antes deste. "
                    "⚠ Sufixo OCR truncado → chip sem capacidade. "
                    "Confirmar via fix_known_parts por PN específico. "
                    "Destino: bancada eMMC (verificar geração antes de precificar)."
                ),
            ),

            # ═══ iNAND eMMC 5.1 (SDINB...) ══════════════════════════════════
            #
            # ⚠ CORRIGIDO jun/2026: SDINB* é eMMC 5.1, NÃO UFS.
            #   Fontes primárias: product briefs oficiais SanDisk/WD
            #     PB01-iNAND-7350 (SDINBDD4), PB02-iNAND-7250 (SDINBDG4),
            #     PB04-iNAND-7550 (SDINBDA4).
            #   Os verdadeiros UFS SanDisk usam prefixos SDINDDH / SDINEDK / SDINFD
            #   (famílias próprias mais abaixo neste arquivo).
            #
            # Variantes confirmadas (eMMC 5.1 HS400):
            #   SDINBDG4 — iNAND 7250  X2 MLC  (8..64GB)
            #   SDINBDD4 — iNAND 7350  3D NAND (32..256GB)
            #   SDINBDA4 — iNAND 7550  Gen4 SmartSLC (32..256GB)
            #   SDINBEG4/5 — classificação pendente (BGA153 11.5×13mm)
            #
            # Capacidade: sufixo declarativo (-8G, -16G, -32G, -64G, -128G, -256G).
            # Todos standalone eMMC — NOT eMCP (zero RAM).
            # BGA153 11.5×13mm.
            #
            dict(
                prefix="SDINB",
                chip_type="eMMC",
                subtype="",
                interface="eMMC 5.1",
                is_emcp=False,
                active=True,
                priority=40,   # menor número = maior prioridade → bate antes do SDIN genérico (80)
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMMC 5.1 SanDisk iNAND (SDINB...). HS400; BGA153 11.5×13mm. "
                    "Sub-linhas: SDINBDG4=iNAND7250 · SDINBDD4=iNAND7350(3D) · SDINBDA4=iNAND7550(SmartSLC). "
                    "Capacidade: -8G=8GB · -16G=16GB · -32G=32GB · -64G=64GB · -128G=128GB · -256G=256GB. "
                    "⚠ NÃO é UFS — corrigido jun/2026 (product briefs PB01/PB02/PB04). "
                    "⚠ Prioridade 40: bate antes do SDIN genérico (priority=80). "
                    "Confirmar capacidade via fix_known_parts por PN específico. "
                    "Destino: bancada eMMC."
                ),
            ),

            # ═══ eMMC iNAND variante SDMAG ════════════════════════════════════
            #
            # Variante iNAND com prefixo SDMAG — citada no fab-sandisk.html
            # como família eMMC recorrente em smartphones mid-range.
            # Documentação pública escassa; classificar como eMMC até confirmação.
            #
            # ⚠ PENDENTE CONFIRMAÇÃO FÍSICA NA ESTEIRA.
            #   Entra no sistema para reconhecimento de marca — sem decode de capacidade.
            #   Quando PN físico confirmar, adicionar em fix_known_parts (create=True).
            #
            dict(
                prefix="SDMAG",
                chip_type="eMMC",
                subtype="eMMC iNAND (variante MAG)",
                interface="eMMC 5.1",
                is_emcp=False,
                active=True,
                priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMMC SanDisk iNAND variante SDMAG. "
                    "Capacidade no sufixo: -4G=4GB · -8G=8GB · -16G=16GB · -32G=32GB · -64G=64GB. "
                    "⚠ PENDENTE: sem confirmação física na esteira ainda. "
                    "Confirmar capacidade e geração via fix_known_parts quando PN real aparecer. "
                    "Destino provisório: bancada eMMC — aguardar confirmação."
                ),
            ),

            # ═══ eMCP SanDisk (SDEM...) ════════════════════════════════════════
            #
            # eMCP SanDisk — híbrido eMMC + LPDDR3 / LPDDR4.
            # Citado no fab-sandisk.html como geração mais recente de eMCP SanDisk.
            # BGA retangular visivelmente maior que os eMMC standalone.
            #
            # ⚠ PENDENTE CONFIRMAÇÃO FÍSICA NA ESTEIRA.
            #   Sem PN físico confirmado — não há decode de capacidade.
            #   is_emcp=True: engine exibe campos emcp_ram / emcp_nand.
            #   Quando PN físico chegar, adicionar em fix_known_parts com:
            #     create=True, emcp_nand="eMMC 5.1 XGB", emcp_ram="LPDDR3/4 YGB".
            #
            dict(
                prefix="SDEM",
                chip_type="eMCP",
                subtype="eMCP (eMMC + LPDDR3/LPDDR4)",
                interface="eMMC + LPDDR3/LPDDR4",
                is_emcp=True,
                active=True,
                priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMCP SanDisk (SDEM...). Híbrido eMMC + RAM LPDDR3 ou LPDDR4. "
                    "BGA retangular maior que os eMMC standalone. "
                    "Capacidade: sufixo declarativo — verificar física do chip. "
                    "⚠ PENDENTE: sem PN físico confirmado na esteira. "
                    "Confirmar via fix_known_parts (create=True) com emcp_nand e emcp_ram. "
                    "Destino provisório: bancada eMCP — aguardar confirmação de capacidade."
                ),
            ),

            # ═══ eMCP SanDisk variante SDAD ════════════════════════════════════
            #
            # eMCP SanDisk — variante mais recente, citada no fab-sandisk.html.
            # Possível uso com LPDDR3 ou LPDDR4.
            #
            # ⚠ PENDENTE CONFIRMAÇÃO FÍSICA NA ESTEIRA.
            #
            dict(
                prefix="SDAD",
                chip_type="eMCP",
                subtype="eMCP (eMMC + LPDDR)",
                interface="eMMC + LPDDR",
                is_emcp=True,
                active=True,
                priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMCP SanDisk variante SDAD. Híbrido eMMC + LPDDR. "
                    "⚠ PENDENTE: sem PN físico confirmado na esteira. "
                    "Confirmar via fix_known_parts (create=True) com emcp_nand e emcp_ram. "
                    "Destino provisório: bancada eMCP — aguardar confirmação."
                ),
            ),

            # ═══ eMMC SanDisk legado SD5DH (era 2012-2013) ════════════════════
            #
            # Família eMMC SanDisk de baixa capacidade, era 2012-2013.
            # Prefixo SD5DH = SanDisk (SD) + produto 5ª geração / série (5) + DH.
            # Die code: 24 = 24nm; letra A/C = revisão do die.
            # Capacidade declarativa no sufixo: -4G=4GB · -8G=8GB.
            #
            # Dispositivos confirmados (serviceemmc.com, Tier 3):
            #   SD5DH24C-4G → Samsung S5301 (Galaxy Pocket 2) / S6810 (Galaxy Fame)
            #   SD5DH24A-4G → Samsung S6802 (Galaxy S Advance)
            #
            # Interface: eMMC 4.3 / 4.4 estimada pela era (2012-2013).
            # ⚠ Sem datasheet Tier 1 confirmado para interface exata.
            # ⚠ PNs específicos confirmados via fix_known_parts (create=True).
            #   Família gramatical cobre variantes não mapeadas com chip_type correto.
            #
            dict(
                prefix="SD5DH",
                chip_type="eMMC",
                subtype="",
                interface="eMMC 4.3 / 4.4",
                is_emcp=False,
                active=True,
                priority=30,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "eMMC SanDisk legado (SD5DH...). Era 2012-2013. Capacidade típica: 4GB-8GB. "
                    "Die code: 24=24nm · A/C/F=revisão. Sufixo declarativo: -4G=4GB · -8G=8GB. "
                    "Dispositivos: S5301 (Galaxy Pocket 2), S6810 (Galaxy Fame), S6802 (S Advance). "
                    "⚠ Interface eMMC 4.3/4.4 estimada — sem datasheet Tier 1 confirmado. "
                    "Confirmar capacidade via fix_known_parts por PN específico."
                ),
            ),

            # ═══ UFS standalone SDHQB ══════════════════════════════════════════
            #
            # UFS standalone SanDisk — prefixo SDHQB citado no fab-sandisk.html.
            # Interface serial de alta velocidade para aparelhos modernos.
            #
            # ⚠ PENDENTE CONFIRMAÇÃO FÍSICA NA ESTEIRA.
            #
            dict(
                prefix="SDHQB",
                chip_type="UFS",
                subtype="UFS standalone",
                interface="UFS 2.1 / 3.1",
                is_emcp=False,
                active=True,
                priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "UFS standalone SanDisk (SDHQB...). Armazenamento serial alta velocidade. "
                    "⚠ PENDENTE: sem PN físico confirmado na esteira. "
                    "Confirmar capacidade e geração UFS via fix_known_parts. "
                    "Destino provisório: bancada UFS — preço premium vs eMMC."
                ),
            ),

            # ═══ UFS 2.1 iNAND 8521 / IX EU312 (SDINDDH) ══════════════════════
            #
            # Linha UFS real SanDisk — confirmada por product brief PB03-iNAND-8521
            # (Mouser Tier 1). Gear3 2-lane; ~500MB/s read; TFBGA-153 11.5×13mm.
            # SDINDDH4 = iNAND 8521 (consumer); SDINDDH6 = iNAND IX EU312 (industrial).
            # Capacidade: sufixo declarativo (-32G=32GB … -256G=256GB).
            # Adicionado jun/2026 (corrigido do antigo SDINB=UFS que era incorreto).
            #
            dict(
                prefix="SDINDDH",
                chip_type="UFS",
                subtype="",
                interface="UFS 2.1",
                is_emcp=False,
                active=True,
                priority=30,   # bate antes de SDINB (40) e SDIN (80)
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "UFS 2.1 SanDisk iNAND 8521 / IX EU312 (SDINDDH...). "
                    "Gear3 2-lane; ~500MB/s leitura; TFBGA-153 11.5×13mm. "
                    "SDINDDH4=consumer · SDINDDH6=industrial (-25..85°C, TLC). "
                    "Capacidade: -32G=32GB · -64G=64GB · -128G=128GB · -256G=256GB. "
                    "Confirmar por PN específico via fix_known_parts. "
                    "Destino: bancada UFS."
                ),
            ),

            # ═══ UFS 3.0 iNAND MC EU511 (SDINEDK) ══════════════════════════════
            #
            # SanDisk iNAND Mobile Commerce EU511 — UFS 3.0 Gear4 2-lane.
            # SmartSLC Gen6; seq write ~800MB/s. Confirmado via SanDisk PDP.
            # TFBGA-153 (estimado — mesmo form factor). Capacidade: 128–512GB.
            # Adicionado jun/2026 (pesquisa Opus 4 extended thinking).
            #
            dict(
                prefix="SDINEDK",
                chip_type="UFS",
                subtype="",
                interface="UFS 3.0",
                is_emcp=False,
                active=True,
                priority=30,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "UFS 3.0 SanDisk iNAND MC EU511 (SDINEDK...). "
                    "Gear4 2-lane; SmartSLC Gen6; ~800MB/s seq write. "
                    "Capacidade: -128G=128GB · -256G=256GB · -512G=512GB. "
                    "Confirmar por PN específico via fix_known_parts. "
                    "Destino: bancada UFS (geração moderna — premium)."
                ),
            ),

            # ═══ UFS 3.1 iNAND MC EU551 / AT EU552 (SDINFD) ═══════════════════
            #
            # Linha UFS 3.1 SanDisk — três prefixos sob a mesma família:
            #   SDINFDK4  — iNAND MC EU551 consumer (Avnet/Arrow, Octopart Tier 2)
            #   SDINFDO4  — iNAND MC EU551 variante (SanDisk PDP)
            #   SDINFDQ6  — iNAND AT EU552 automotivo AEC-Q100 (-40..105°C)
            # WriteBooster 2ª geração; Gear4. Capacidade: 64–512GB.
            # Adicionado jun/2026 (pesquisa Opus 4 extended thinking).
            #
            dict(
                prefix="SDINFD",
                chip_type="UFS",
                subtype="",
                interface="UFS 3.1",
                is_emcp=False,
                active=True,
                priority=30,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                decode_gen_pos=None, decode_gen_len=1, decode_gen_map="",
                tip=(
                    "UFS 3.1 SanDisk iNAND (SDINFD...). Gear4; WriteBooster 2ª geração. "
                    "SDINFDK4=EU551 consumer · SDINFDO4=EU551 variante · SDINFDQ6=EU552 automotivo AEC. "
                    "Capacidade: -64G=64GB · -128G=128GB · -256G=256GB · -512G=512GB. "
                    "Sufixo automotivo: -XA1 / -ZA1 = AEC grade (-40..105°C). "
                    "Confirmar por PN específico via fix_known_parts. "
                    "Destino: bancada UFS (geração mais recente — maior valor)."
                ),
            ),

        ]

    # ──────────────────────────────────────────────────────────────────────────

    def _log(self, created, kind, name, dry):
        prefix = "[DRY] " if dry else ""
        action = "CRIADO" if created else "atualizado"
        icon = "✚" if created else "↻"
        self.stdout.write(f"  {prefix}{icon} {kind}: {name} ({action})")


class DryRunAbort(Exception):
    """Sinaliza o rollback controlado do dry run."""
    pass
