"""
populate_toshiba.py
====================
Popula o banco com as famílias de chips Toshiba / Kioxia (eMMC THGBM*).

Contexto histórico
------------------
  Em 2019 a divisão de memória da Toshiba foi separada e renomeada para
  Kioxia. O prefixo THGBM continuou sendo usado em ambas as eras:
    • Chips físicos gravados "Toshiba" → THGBM produzidos até ~2019.
    • Chips físicos gravados "KIOXIA"  → THGBM produzidos de 2019 em diante.
  Como o PN e a estrutura de decodificação são idênticos, a família THGBM
  é cadastrada sob a Brand "Toshiba" (origem histórica). Os chips Kioxia
  chegam com o mesmo prefixo e são decodificados pela mesma gramática.
  Ambas as marcas são criadas no banco para uso futuro (famílias KLUE/UFS).

Metodologia de decodificação THGBM
------------------------------------
  PN canônico = 15 chars: T-H-G-B-M-[5]-G-[7]-[8]-[9]-[10]-B-A-[I|U]-[R|L|8|7]
  Posições (0-based):
    pn[5]      → código de geração NAND/versão eMMC  (THGBM_GEN)
    pn[7:10]   → chave composta 3-chars de capacidade (THGBM_CAP)
                   pn[7] = densidade por die (16Gb/32Gb/64Gb/128Gb…)
                   pn[8] = tipo de stack (C/D/A/J…)
                   pn[9] = número de dies (1/2/4/8…)
    pn[6]='G'  → constante identificadora (sem decode)
    pn[10]     → tier de qualidade / organização (L/K/E/J…) — sem decode

Regra de Confiança
-------------------
  Tier 1: kioxia.com, toshiba.semicon-storage.com (fontes primárias)
  Tier 2: Mouser, DigiKey, Octopart                (distribuidores)
  Tier 3: utmel, censtry, neven7.eu, iiic.cc        (B2B / catalogadores)
  Tier 4: Alibaba, OLX, listagens sem datasheet     (estimado — add=NEVER)

  BLOQUEIOS: Nunca adicionar uma chave de capacidade sem PN âncora verificado.
  Nunca adicionar spec UFS KLUE sem verificação em kioxia.com.

Uso:
    python manage.py populate_toshiba
    python manage.py populate_toshiba --dry-run
    python manage.py populate_toshiba --overwrite
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação Toshiba / Kioxia no banco."

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
            self.stdout.write(self.style.SUCCESS("\n✅  Toshiba / Kioxia populada com sucesso."))
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                self.stdout.write("   🗑  Cache do engine invalidado.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    # ──────────────────────────────────────────────────────────────────────────

    # Famílias removidas da gramática mas que podem ainda existir no banco.
    OBSOLETE_FAMILY_PREFIXES: list[str] = [
        # add_chip_families.py criou sub-prefixos THGBMFG e THGBMHG (2025) com
        # interface='eMMC 5.1' hardcoded e sem decode maps. Como o engine ordena
        # por prefix_len DESC, esses sub-prefixos interceptavam o match antes de
        # THGBM, bloqueando a gramática completa. A família THGBM cobre todos os
        # PNs desses sub-prefixos com decodificação posicional correta.
        "THGBMFG",
        "THGBMHG",
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

        # ── Marcas ────────────────────────────────────────────────────────────
        toshiba, created = Brand.objects.get_or_create(
            name="Toshiba",
            defaults={
                "code": "TOS",
                "notes": (
                    "Japão · Divisão de Memória Toshiba. "
                    "Em 2019 a divisão foi separada e renomeada Kioxia. "
                    "Chips pré-2019 fisicamente gravados 'Toshiba'; "
                    "pós-2019 gravados 'KIOXIA'. Prefixo THGBM coexiste nas duas eras. "
                    "Novos prefixos exclusivos Kioxia (THGJF/THGAF/THGAM) cadastrados sob Brand Kioxia."
                ),
            },
        )
        self._log(created, "Marca", "Toshiba", dry)

        kioxia, created = Brand.objects.get_or_create(
            name="Kioxia",
            defaults={
                "code": "KIO",
                "notes": (
                    "Japão · Ex-divisão de Memória Toshiba, renomeada em 2019. "
                    "Fab BiCS4/5/6 TLC NAND. "
                    "Prefixo UFS stand-alone: KLUE (verificar kioxia.com antes de cadastrar)."
                ),
            },
        )
        self._log(created, "Marca", "Kioxia", dry)

        # ── DecodeMap: THGBM capacidade total (pn[7:10], len=3) ──────────────
        #
        # A chave de 3 chars combina três campos do PN:
        #   pn[7] = código de densidade por die
        #           '4' = 16 Gbit/die (2 GB/die)   eMMC 4.x era
        #           '5' = 32 Gbit/die (4 GB/die)   eMMC 5.0 era (19nm 2nd gen, ~2013)
        #           '6' = 64 Gbit/die (8 GB/die)   eMMC 5.0/5.1 era (15nm, ~2014-2016)
        #           '7' = 128 Gbit/die (16 GB/die)  eMMC 5.0/5.1 alta densidade
        #           '8' = 64 Gbit/die (8 GB/die)   eMMC 5.1 BiCS3/4 (Toshiba Memory/Kioxia)
        #           '9' = 64 Gbit/die (8 GB/die)   eMMC 5.1 multi-die alta densidade
        #           '0' = 128 Gbit/die (16 GB/die)  eMMC 5.0 alta densidade (128GB produto)
        #   pn[8] = tipo de stack (C / D / A / J / B…)  — sem significado de capacidade
        #   pn[9] = número de dies empilhados (1 / 2 / 4 / 8 / B…)
        #
        #   Capacidade total = densidade(pn[7]) × dies(pn[9])
        #   A chave de 3 chars serve como índice único sem necessidade de cálculo no engine.
        #
        # ⚠️ Nota sobre pn[6]: normalmente 'G' (constante de processo), mas pn[6]='T' em
        #    THGBMFT0CBLBAIS (128GB Supreme). O engine NÃO lê pn[6] — só pn[5] e pn[7:10].
        #
        # Chaves confirmadas (Tier 1 = kioxia.com / toshiba.semicon-storage.com):
        #
        #   "4D1" = 2GB   → THGBM4G4D1HBAIR         censtry.com Tier 3 ✓
        #   "5D1" = 4GB   → THGBMNG5D1LBAIL          Kioxia product brief 2023 Tier 1 ✓ (N=eMMC 5.0)
        #                 → THGBMTG5D1LBAIL          Kioxia product brief 2023 Tier 1 ✓ (T=eMMC 5.0)
        #                 → THGBM4G5D1HBAIR          datasheet4u / Octopart ✓ (4-GByte e-MMC datasheet)
        #   "5D2" = 8GB   → THGBMDG5D2HBAIL          AIChipLink Tier 3 ✓
        #   "6C1" = 8GB   → THGBMHG6C1LBAU6          kioxia.com 2017 Tier 1 ✓ (8GB industrial)
        #                 → THGBMJG6C1LBAU7          Kioxia product brief 2023 Tier 1 ✓
        #   "6D1" = 8GB   → THGBMBG6D1KBAIL          Puris A19nm eMMC 5.0 Tier 3 ✓ (cross-valida 6C1)
        #   "7C1" = 16GB  → THGBMFG7C1LBAIL          Mouser/Kioxia America Tier 1 ✓; Octopart 11 distrib. Tier 2 ✓
        #   "7C2" = 16GB  → THGBMFG7C2LBAIL          kioxia.com 2014 Tier 1 ✓ (Supreme 16GB 15nm)
        #                 → THGBMHG7C2LBAU7          kioxia.com 2017 Tier 1 ✓ (16GB industrial)
        #   "7D2" = 16GB  → THGBMBG7D2KBAIL          kioxia.com 2013 Tier 1 ✓ (19nm 2nd gen eMMC 5.0)
        #   "8C4" = 32GB  → THGBMFG8C4LBAIR          kioxia.com 2014 Tier 1 ✓ (Supreme 32GB 15nm)
        #                 → THGBMHG8C4LBAU7          kioxia.com 2017 Tier 1 ✓ (32GB industrial)
        #                 → THGBMHG8C4LBAIR          Octopart Tier 2 ✓ (32G-byte VFBGA)
        #   "8C2" = 32GB  → THGBMFG8C2LBAIL          kioxia.com 2014 Tier 1 ✓ (Premium 32GB 15nm)
        #                 → THGBMUG8C2LBAIL          Kioxia product brief 2023 Tier 1 ✓ (eMMC 5.1)
        #   "8D4" = 32GB  → THGBMBG8D4KBAIR          kioxia.com 2013 Tier 1 ✓ ("four 64Gbit chips" = 4×8GB=32GB)
        #   "9C8" = 64GB  → THGBMHG9C8LBAU8          kioxia.com 2017 Tier 1 ✓ (64GB industrial)
        #                 → THGBMJG9C8LBAU8          Kioxia product brief 2023 Tier 1 ✓; Mouser Tier 2 ✓
        #   "9C4" = 64GB  → THGBMFG9C4LBAIR          kioxia.com 2014 Tier 1 ✓ (Premium 64GB 15nm)
        #   "0CB" = 128GB → THGBMFT0CBLBAIS          kioxia.com 2014 Tier 1 ✓ (Supreme 128GB 15nm)
        #
        # Chaves BLOQUEADAS (padrão matemático confirmado mas sem fonte primária para âncora):
        #   "4D4" → 8GB  ? (THGBM4G4D4LBAIR — usuário estimou ~4GB, mas 4×2GB=8GB pelo padrão)
        #   "6A2" → 16GB ? (THGBM5G6A2JBAIR — ovaga.com: JS-rendered, estimativa do AI incorreta)
        #   "6A4" → 32GB ? (THGBM5G6A4JBAIR — não encontrado em fonte verificável)
        #   "8D2" → 16GB ? (THGBMBG8D2KBAIG — padrão: 2×8GB=16GB, mas sem âncora confirmatória)
        #   "6JA" / outras → identificadas em PNs de campo mas mal formadas ou abreviadas
        #
        # NÃO adicionar chaves BLOQUEADAS sem nova pesquisa com âncora de PN + fonte Tier 2.
        thgbm_cap = [
            # (char_key,  val_primary,  val_secondary)
            ("4D1",   "2GB",  ""),  # THGBM4G4D1HBAIR — censtry.com Tier 3 ✓
            ("5D1",   "4GB",  ""),  # THGBMNG5D1LBAIT + THGBMTG5D1LBAIL — Kioxia product brief 2023 Tier 1 ✓
            ("5D2",   "8GB",  ""),  # THGBMDG5D2HBAIL — AIChipLink Tier 3 ✓
            ("6C1",   "8GB",  ""),  # THGBMHG6C1LBAU6 — kioxia.com 2017 Tier 1 ✓; THGBMJG6C1LBAU7 — product brief 2023 Tier 1 ✓
            ("6D1",   "8GB",  ""),  # THGBMBG6D1KBAIL — Puris A19nm eMMC 5.0 Tier 3 ✓ (cross-valida 6C1)
            ("7C1",  "16GB",  ""),  # THGBMFG7C1LBAIL — Mouser/Kioxia America Tier 1 ✓ + Octopart 11 distrib. Tier 2 ✓
            ("7C2",  "16GB",  ""),  # THGBMFG7C2LBAIL — kioxia.com 2014 Tier 1 ✓; THGBMHG7C2LBAU7 — kioxia.com 2017 Tier 1 ✓
            ("7D2",  "16GB",  ""),  # THGBMBG7D2KBAIL — kioxia.com 2013 Tier 1 ✓ (19nm 2nd gen, eMMC 5.0)
            ("8C4",  "32GB",  ""),  # THGBMFG8C4LBAIR + THGBMHG8C4LBAU7 — kioxia.com 2014/2017 Tier 1 ✓; THGBMHG8C4LBAIR — Octopart Tier 2 ✓
            ("8C2",  "32GB",  ""),  # THGBMFG8C2LBAIL — kioxia.com 2014 Tier 1 ✓; THGBMUG8C2LBAIL — product brief 2023 Tier 1 ✓
            ("8D4",  "32GB",  ""),  # THGBMBG8D4KBAIR — kioxia.com 2013 Tier 1 ✓ ("four 64Gbit chips"=4×8GB=32GB)
            ("9C8",  "64GB",  ""),  # THGBMHG9C8LBAU8 — kioxia.com 2017 Tier 1 ✓; THGBMJG9C8LBAU8 — Mouser Tier 2 ✓
            ("9C4",  "64GB",  ""),  # THGBMFG9C4LBAIR — kioxia.com 2014 Tier 1 ✓ (Premium 64GB 15nm)
            ("0CB", "128GB",  ""),  # THGBMFT0CBLBAIS — kioxia.com 2014 Tier 1 ✓ (Supreme 128GB 15nm; pn[6]='T' nesta chave)
        ]
        self._bulk_map("THGBM_CAP", thgbm_cap, toshiba, dry, overwrite)

        # ── DecodeMap: THGBM geração eMMC (pn[5], len=1) ──────────────────────
        #
        # pn[5] codifica a geração do processo NAND / versão eMMC:
        #   Letra = variante de processo NAND e velocidade eMMC.
        #   O engine usa val_primary para exibir a versão eMMC ao operador.
        #
        # Cronologia das gerações (confirmado por press releases Tier 1):
        #   N/T → eMMC 5.0 (THGBMNG/TG — Kioxia product brief 2023 Tier 1 ✓)
        #   F   → eMMC 5.0 (THGBMFG — kioxia.com 2014 Tier 1 ✓, processo 15nm)
        #   B   → eMMC 5.0 (THGBMBG — kioxia.com 2013 Tier 1 ✓, processo 19nm 2nd gen)
        #   H   → eMMC 5.1 (THGBMHG — kioxia.com 2017 Tier 1 ✓, industrial -40°C to +105°C)
        #   J   → eMMC 5.1 (THGBMJG — Kioxia product brief 2023 Tier 1 ✓, industrial)
        #   U   → eMMC 5.1 (THGBMUG — Kioxia product brief 2023 Tier 1 ✓, consumer)
        #
        # Chaves BLOQUEADAS (sem fonte explícita para versão eMMC):
        #   "D" → provável eMMC 5.0 (THGBMDG5D2HBAIL — AIChipLink menciona mas sem versão)
        #   "4" → eMMC 4.41 (THGBM4G... — lógico pelo prefixo mas sem fonte primária)
        #   "G","M" → identificados em PNs de campo, versão não verificada
        #
        # NÃO adicionar chaves BLOQUEADAS sem fonte Tier 2+ com versão eMMC explícita.
        thgbm_gen = [
            # (char_key,  val_primary,    val_secondary)
            ("N",  "eMMC 5.0",  ""),  # THGBMNG5D1LBAIT — Kioxia product brief 2023 Tier 1 ✓
            ("T",  "eMMC 5.0",  ""),  # THGBMTG5D1LBAIL — Kioxia product brief 2023 Tier 1 ✓
            ("F",  "eMMC 5.0",  ""),  # THGBMFG* — kioxia.com 2014 Tier 1 ✓ (15nm process launch)
            ("B",  "eMMC 5.0",  ""),  # THGBMBG* — kioxia.com 2013 Tier 1 ✓ (19nm 2nd gen launch)
            ("H",  "eMMC 5.1",  ""),  # THGBMHG* — kioxia.com 2017 Tier 1 ✓ (industrial, -40°C to +105°C)
            ("J",  "eMMC 5.1",  ""),  # THGBMJG* — Kioxia product brief 2023 Tier 1 ✓ (industrial)
            ("U",  "eMMC 5.1",  ""),  # THGBMUG* — Kioxia product brief 2023 Tier 1 ✓ (consumer)
        ]
        self._bulk_map("THGBM_GEN", thgbm_gen, toshiba, dry, overwrite)

        # ── ChipFamilies ──────────────────────────────────────────────────────
        # Cada dict pode conter "brand" explícito (ex: kioxia para THGAM/THGJF/THGAF).
        # Famílias sem "brand" no dict usam toshiba (default — backward compatible).
        families = self._families(toshiba, kioxia)
        created_count = updated_count = 0
        for fdata in families:
            prefix       = fdata.pop("prefix")
            family_brand = fdata.pop("brand", toshiba)   # per-family brand
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != family_brand.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = family_brand
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

    def _families(self, toshiba, kioxia):
        """
        Retorna a lista de dicts de famílias Toshiba / Kioxia.

        Famílias implementadas:
          THGBM  — eMMC MLC/TLC (família principal, alta frequência na esteira)
          TYC    — eMCP LPDDR2 legado (magra, sem decode)
          TYD    — eMCP LPDDR3 BGA-221 (magra, sem decode)
          THGAM  — eMMC 5.1 BiCS Kioxia (magra, sem decode) — adicionada 2026-06-26
          THGJF  — UFS 3.1/4.0/4.1 Kioxia (magra, sem decode) — adicionada 2026-06-26
          THGAF  — UFS 2.1 Kioxia (magra, sem decode) — adicionada 2026-06-26

        Famílias BLOQUEADAS (pesquisa pendente):
          KLUE   — UFS Kioxia (requer verificação em kioxia.com antes de cadastrar)
          TH58   — NAND standalone Toshiba (baixa prioridade operacional)
        """
        return [

            # ═══ eMMC: THGBM ══════════════════════════════════════════════════
            #
            # Família principal Toshiba/Kioxia na esteira de reciclagem.
            # Presente em smartphones Android mid-range e entry-level (~2013–2023).
            # Dispositivos comuns: Galaxy J/A series (OEM Toshiba), Redmi, Realme,
            #   feature phones MediaTek, tablets de entrada.
            #
            # Estrutura do PN (15 chars, todos os exemplos confirmados):
            #   T  H  G  B  M  [5]  G  [7]  [8]  [9]  [10] B  A  [13] [14]
            #   0  1  2  3  4   5   6   7    8    9    10   11 12  13   14
            #
            #   pn[0:5]  = "THGBM" (prefixo fixo da família)
            #   pn[5]    = geração NAND/versão eMMC  → THGBM_GEN
            #              N/T/F/B = eMMC 5.0 · H/J/U = eMMC 5.1
            #   pn[6]    = geralmente 'G' (processo de gravação — sem decode); excepcionalmente
            #              'T' em THGBMFT0CBLBAIS (128GB Supreme 2014) — NÃO decodificado.
            #   pn[7:10] = chave composta de capacidade → THGBM_CAP
            #              pn[7] = densid./die · pn[8] = stack type · pn[9] = die count
            #   pn[10]   = tier de qualidade/organização (L/K/E/J…)
            #   pn[11:13]= "BA" constante (package type BGA153)
            #   pn[13]   = grau: I = consumer/commercial · U = industrial
            #   pn[14]   = variante de bin/temperatura:
            #              L = comercial padrão (11.5×13mm)
            #              R = bin alternativo (ex.: 32/64GB Supreme 11.5×13mm)
            #              W/T/X/G/S = package 11×10mm ou 128GB variant
            #              6/7/8 = extended temp industrial (-40°C a +105°C)
            #
            # Decode implementado:
            #   decode_cap_pos=7, decode_cap_len=3  → THGBM_CAP → capacity
            #   decode_gen_pos=5, decode_gen_len=1  → THGBM_GEN → interface (versão eMMC)
            #
            # Nota Toshiba→Kioxia: chips físicos com silkscreen "KIOXIA" também
            # usam prefixo THGBM (post-2019). O engine classifica todos como
            # "Toshiba" — correto para chips pré-2019; aceitável para pós-2019
            # dado que a gramática e especificações são idênticas.
            #
            # PNs de referência (anchor set):
            #   THGBMNG5D1LBAIT  — 4GB  eMMC 5.0 · Kioxia product brief 2023 Tier 1 ✓
            #   THGBMTG5D1LBAIL  — 4GB  eMMC 5.0 · Kioxia product brief 2023 Tier 1 ✓
            #   THGBMBG7D2KBAIL  — 16GB eMMC 5.0 · kioxia.com 2013 Tier 1 ✓ (19nm 2nd gen)
            #   THGBMBG8D4KBAIR  — 32GB eMMC 5.0 · kioxia.com 2013 Tier 1 ✓ (19nm 2nd gen)
            #   THGBMFG7C1LBAIL  — 16GB eMMC 5.0 · Mouser/Kioxia America Tier 1 + Octopart Tier 2 ✓
            #   THGBMFG7C2LBAIL  — 16GB eMMC 5.0 · kioxia.com 2014 Tier 1 ✓ (15nm Supreme)
            #   THGBMFG8C2LBAIL  — 32GB eMMC 5.0 · kioxia.com 2014 Tier 1 ✓ (15nm Premium; âncora 8C2)
            #   THGBMFG8C4LBAIR  — 32GB eMMC 5.0 · kioxia.com 2014 Tier 1 ✓ (15nm Supreme)
            #   THGBMFG9C4LBAIR  — 64GB eMMC 5.0 · kioxia.com 2014 Tier 1 ✓ (15nm Premium; âncora 9C4)
            #   THGBMFT0CBLBAIS  — 128GB eMMC 5.0 · kioxia.com 2014 Tier 1 ✓ (15nm; âncora 0CB)
            #   THGBMHG8C4LBAIR  — 32GB eMMC 5.1 · Octopart Tier 2 ✓ (causa bug "desconhecido" resolvida)
            #   THGBMHG8C4LBAU7  — 32GB eMMC 5.1 industrial · kioxia.com 2017 Tier 1 ✓
            #   THGBMUG8C2LBAIL  — 32GB eMMC 5.1 consumer · Kioxia product brief 2023 Tier 1 ✓
            #   THGBMJG9C8LBAU8  — 64GB eMMC 5.1 industrial · Kioxia product brief 2023 Tier 1 ✓ + Mouser Tier 2 ✓
            dict(
                prefix="THGBM",
                chip_type="eMMC",
                subtype="eMMC Toshiba/Kioxia MLC/TLC",
                interface="eMMC",
                pn_length=15,
                decode_cap_pos=7,
                decode_cap_len=3,
                decode_cap_map="THGBM_CAP",
                decode_gen_pos=5,
                decode_gen_len=1,
                decode_gen_map="THGBM_GEN",
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC Toshiba / Kioxia — armazenamento Flash puro, sem RAM embutida. "
                    "Prefixo THGBM cobre chips pré-2019 (Toshiba) e pós-2019 (Kioxia). "
                    "Geração automática: pn[5] → N/T/F/B=eMMC 5.0 | H/J/U=eMMC 5.1. "
                    "⚠ Separe por geração: 5.1 (H/J/U) vale ~15-25% a mais que 5.0 (N/T/F/B). "
                    "Capacidade: pn[7:10] → chave 3-chars → THGBM_CAP: "
                    "5D1=4GB · 5D2=8GB · 6C1=8GB · 6D1=8GB · 7C1=16GB · 7C2=16GB · 7D2=16GB · "
                    "8C2=32GB · 8C4=32GB · 8D4=32GB · 9C4=64GB · 9C8=64GB · 0CB=128GB. "
                    "⚠ Chaves não mapeadas (ex: 4D4, 6A2, 8D2) ficam com capacity=null — "
                    "confirmar via Octopart/distribuidor e adicionar ao THGBM_CAP. "
                    "Pacote: BGA153 (11.5×13mm). "
                    "Interface paralela eMMC — NUNCA confundir com socket UFS (THGJF/THGAF/KLUE). "
                    "Destino: bancada reacondicional Flash eMMC (separar por geração)."
                ),
                reasoning=(
                    '["T=Toshiba · H=NAND tipo H · G=geração G · B=bus 8-bit · M=mobile", '
                    '"pn[5]: código de geração NAND — N/T/F/B=eMMC 5.0 · H/J/U=eMMC 5.1", '
                    '"pn[6]=G: constante identificadora de processo (sem decode)", '
                    '"pn[7:10]: chave composta 3-chars → capacidade total (ver THGBM_CAP)", '
                    '"pn[7]: densidade/die — 5=32Gb(4GB) · 6=64Gb(8GB) · 7=128Gb(16GB) · 8=64Gb(8GB) · 9=64Gb(8GB)", '
                    '"pn[8]: tipo de stack — C/D/A/J/K (sem impacto na capacidade total)", '
                    '"pn[9]: número de dies — 1/2/4/8", '
                    '"pn[10]: tier de qualidade (L/K/E/J) — sem decode de capacidade", '
                    '"pn[11:13]=BA: package BGA153", '
                    '"pn[13]: I/O voltage — I=1.8V · U=dual-voltage 1.8/3.3V"]'
                ),
            ),

            # ═══ eMCP: TYC ════════════════════════════════════════════════════
            #
            # Família eMCP Toshiba legada (~2012-2016): eMMC 4.5 + LPDDR2, BGA-162.
            # Presente em smartphones entry-level e feature phones (~2013-2016).
            # Dispositivos comuns: Alcatel, Micromax, Wiko, modelos MediaTek básicos.
            #
            # Por que NÃO tem decode map:
            #   A família TYC* (~2012-2016) não tem press releases ou datasheets
            #   públicos em Tier 1 (kioxia.com / toshiba.semicon-storage.com).
            #   As posições de decode (capacidade NAND, RAM) foram parcialmente
            #   inferidas por Tier 2-3, mas sem fonte primária suficiente para
            #   criar um DecodeMap confiável. Famílias "magras" sem decode são
            #   reconhecidas pelo prefixo mas retornam capacity=None.
            #
            # Rentabilidade sem decode:
            #   assess_profitability() verifica LPDDR2 no `subtype` (combined)
            #   antes do guard de capacidade vazia → retorna NÃO RENTÁVEL.
            #   (FIX 2026-06-26: engine.py, bloco eMCP, lpddr_gen_sub check.)
            #   Todos os TYC* são LPDDR2 → is_dead_by_generation=True → descarte.
            #
            # Estrutura parcialmente conhecida (Tier 2-3, sem confirmação Tier 1):
            #   pn[0:3]  = "TYC"  → família eMCP LPDDR2 (TYD = LPDDR3)
            #   pn[3:5]  = capacidade NAND: '0F'=4GB · '0G'=8GB
            #   pn[5]    = provavelmente sub-geração RAM ('H'→LPDDR2 512MB?)
            #   pn[6:8]  = desconhecido (constante "12" nos exemplos conhecidos)
            #   pn[8:12] = código de lote/batch (ex.: 1638, 1626, 162B)
            #   pn[12:14]= sufixo (ex.: RA)
            #
            # PNs de referência (âncoras Tier 2):
            #   TYC0FH121638RA — 4GB eMMC 4.5 + 512MB LPDDR2 · Octopart Tier 2 ✓
            #   TYC0FH121626RA — 4GB eMMC 4.5 + 512MB LPDDR2 · Âncora 1638RA ✓
            #   TYC0FH12162BRA — 4GB eMMC 4.5 + 512MB LPDDR2 · Inferência estrutural
            #
            # Prefixo TYD (LPDDR3/BGA-221) é família separada — ver bloco TYD abaixo.
            #
            dict(
                prefix="TYC",
                chip_type="eMCP",
                subtype="eMCP Toshiba LPDDR2 (legado)",
                interface="",
                pn_length=14,
                decode_cap_pos=None,
                decode_cap_len=1,      # NOT NULL no DB; map="" → engine não decodifica
                decode_cap_map="",
                decode_gen_pos=None,
                decode_gen_map="",
                is_emcp=True,
                active=True,
                priority=50,
                tip=(
                    "eMCP Toshiba legado: eMMC 4.5 + LPDDR2, package BGA-162. "
                    "Família sem decode gramatical — capacity/specs dependem de KnownPart manual. "
                    "Rentabilidade: sempre NÃO RENTÁVEL (LPDDR2 abaixo do threshold). "
                    "Subprefixos: TYC0F*=4GB NAND · TYC0G*=8GB NAND. "
                    "RAM: LPDDR2 512MB em todos os exemplos confirmados. "
                    "Cluster de lote: TYC0FH12[XXXX]RA = mesmas specs, só lote diferente. "
                    "Distinguir de TYD* (LPDDR3, BGA-221) — família magra ativa, ver bloco TYD."
                ),
                reasoning=(
                    '["TYC = Toshiba eMCP LPDDR2 legado (TYD = LPDDR3/BGA-221)", '
                    '"pn[3:5]: capacidade NAND — 0F=4GB · 0G=8GB (Tier 2-3, sem Tier 1)", '
                    '"pn[5]: provavelmente sub-geração RAM — H=LPDDR2 512MB (não confirmado Tier 1)", '
                    '"pn[8:12]: código de lote/batch — não encode specs (confirmado cluster Tier 2)", '
                    '"Família magra adicionada 2026-06-26: reconhecimento por prefixo sem decode posicional"]'
                ),
            ),

            # ═══ eMCP: TYD ════════════════════════════════════════════════════
            #
            # Família eMCP Toshiba LPDDR3 (~2015-2020): eMMC 4.5 + LPDDR3, BGA-221.
            # Mais recente que TYC (LPDDR2/BGA-162): chip maior, mais pinos (221 vs 162).
            # Presente em smartphones mid-range (~2016-2020), especialmente MediaTek Helio.
            #
            # Por que NÃO tem decode map:
            #   A família TYD* (~2015-2020) não tem datasheets ou press releases públicos
            #   em Tier 1 (kioxia.com / toshiba.semicon-storage.com). A estrutura posicional
            #   foi confirmada apenas via Tier 3 (Preduo) — decode map exigiria âncora Tier 2.
            #   Família "magra": reconhecida pelo prefixo, capacity=None via gramática.
            #
            # Rentabilidade sem decode:
            #   assess_profitability() verifica LPDDR3 no `subtype` (combined) antes do
            #   guard de capacidade vazia (FIX 2026-06-26 — engine.py, bloco eMCP,
            #   lpddr_gen_sub check). LPDDR2 → NÃO RENTÁVEL imediato; LPDDR3 depende
            #   de specs de capacidade → INDETERMINADO sem KnownPart enriquecido.
            #
            # Estrutura parcialmente conhecida (Tier 2-3, sem confirmação Tier 1):
            #   pn[0:3]  = "TYD"  → família eMCP LPDDR3/BGA-221 (TYC = LPDDR2/BGA-162)
            #   pn[3:5]  = capacidade NAND: '0F'=4GB · '0G'=8GB (Preduo Tier 3 ✓)
            #   pn[5]    = 'H' → marcador de RAM (hipótese — consistente com TYC)
            #   pn[6:8]  = código de capacidade RAM: '22'=1GB LPDDR3 (âncora Preduo ✓)
            #   pn[8:12] = código de lote/batch (ex.: 1627, 1651)
            #   pn[12:14]= sufixo de variante (ex.: RA)
            #
            # PNs de referência:
            #   TYD0GH221651RA — 8GB eMMC + 1GB LPDDR3 · Preduo Tier 3 ✓ (âncora principal)
            #   TYD0FH221627RA — 4GB eMMC + 1GB LPDDR3 · Inferência estrutural (fix_known_parts)
            #
            # ⚠️ DISCREPÂNCIA TYC/LPDDR3 (Preduo vs. Octopart):
            #   Preduo (Tier 3) classificou TYC0FH121642RA como "LPDDR3, 221ball".
            #   REFUTADO: Octopart (Tier 2) confirma TYC0FH121638RA = "4Gb LPDDR2 + 4GB EMCP".
            #   TYC = BGA-162/LPDDR2; TYD = BGA-221/LPDDR3. Preduo confunde os prefixos.
            #
            dict(
                prefix="TYD",
                chip_type="eMCP",
                subtype="eMCP Toshiba LPDDR3 (BGA-221)",
                interface="",
                pn_length=14,
                decode_cap_pos=None,
                decode_cap_len=1,      # NOT NULL no DB; map="" → engine não decodifica
                decode_cap_map="",
                decode_gen_pos=None,
                decode_gen_map="",
                is_emcp=True,
                active=True,
                priority=50,
                tip=(
                    "eMCP Toshiba: eMMC 4.5 + LPDDR3, package BGA-221 (mais novo que TYC/BGA-162). "
                    "Família sem decode gramatical — capacity/specs dependem de KnownPart manual. "
                    "Rentabilidade: depende da capacidade (LPDDR3 ≥ threshold → RENTÁVEL; sem specs → INDETERMINADO). "
                    "Subprefixos: TYD0F*=4GB NAND · TYD0G*=8GB NAND (Preduo Tier 3 ✓). "
                    "RAM: pn[6:8]='22'→1GB LPDDR3 (âncora TYD0GH221651RA, Preduo Tier 3 ✓). "
                    "Cluster de lote: TYD0FH221[XXXX]RA = mesmas specs, só lote diferente. "
                    "Distinguir de TYC* (LPDDR2, BGA-162) — geração mais antiga e NÃO RENTÁVEL."
                ),
                reasoning=(
                    '["TYD = Toshiba eMCP LPDDR3/BGA-221 (~2015-2020) — geração seguinte ao TYC/LPDDR2/BGA-162", '
                    '"pn[3:5]: capacidade NAND — 0F=4GB · 0G=8GB (Preduo Tier 3 ✓)", '
                    '"pn[5]=H: marcador de RAM (hipótese — consistente com TYC; sem Tier 1)", '
                    '"pn[6:8]: código RAM — 22=1GB LPDDR3 (âncora TYD0GH221651RA, Preduo Tier 3 ✓)", '
                    '"pn[8:12]: código de lote/batch — não encode specs (ex.: 1627, 1651)", '
                    '"Família magra adicionada 2026-06-26: reconhecimento por prefixo sem decode posicional", '
                    '"Fonte: Preduo Tier 3 (TYD0GH221651RA=8+8 eMMC+LPDDR3 221ball) + Octopart Tier 2 (tipo SDRAM+eMMC MCP ✓)"]'
                ),
            ),

            # ═══ UFS: THGJF ═══════════════════════════════════════════════════
            #
            # UFS Kioxia de nova geração: UFS 3.1 / 4.0 / 4.1 (2020–2025).
            # Presente em smartphones flagship e mid-range modernos.
            # Capacidades: 128GB, 256GB, 512GB, 1TB.
            # Fonte: Kioxia UFS Product Brief Rev.3.0 (2025) e Rev.2.0 (2022).
            # Consumer grade. Package BGA (dimensões variam por capacidade).
            # 18 PNs confirmados em fix_known_parts.py (Tier 1 ✓, 2026-06-26).
            #
            # Por que NÃO tem decode map (família magra):
            #   A posição de capacidade no PN THGJF* não foi mapeada posicionalmente
            #   nesta sessão — os KnownParts confirmados com capacity explícita
            #   cobrem os 18 PNs conhecidos. Decode posicional pode ser adicionado
            #   numa sessão futura se necessário para cobertura de cauda longa.
            #
            # Estrutura parcialmente inferida (sem mapeamento formal):
            #   pn[0:5]  = "THGJF" → família UFS Kioxia nova geração
            #   pn[5]    = sub-geração (P=3.1, M=4.0, R=4.1, G=3.1, H=3.1, J=4.0)
            #   pn[6:10] = capacidade/config (não decodificado)
            #   pn_length = 15
            #
            dict(
                prefix="THGJF",
                brand=kioxia,               # Kioxia — nunca Toshiba (prefixo pós-2019)
                chip_type="UFS",
                subtype="UFS Kioxia",
                interface="",               # versão varia (3.1/4.0/4.1) — lida do KnownPart
                pn_length=15,
                decode_cap_pos=None,
                decode_cap_len=1,           # NOT NULL no DB; map="" → engine não decodifica
                decode_cap_map="",
                decode_gen_pos=None,
                decode_gen_map="",
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "UFS Kioxia nova geração: UFS 3.1 / 4.0 / 4.1 (2020–2025). "
                    "Família sem decode gramatical — capacity/specs dependem de KnownPart confirmado. "
                    "Capacidades: 128GB, 256GB, 512GB, 1TB. Todos RENTÁVEIS. "
                    "Fonte Tier 1: Kioxia UFS Product Brief Rev.3.0 (2025) + Rev.2.0 (2022). "
                    "18 PNs consumer grade confirmados em fix_known_parts.py. "
                    "Distinguir de THGAF* (UFS 2.1, geração anterior)."
                ),
                reasoning=(
                    '["THGJF = prefixo UFS Kioxia pós-2019 (confirmado kioxia.com Tier 1)", '
                    '"pn[5]: sub-geração — P=3.1 · M=4.0 · R=4.1 · G/H=3.1 · J=4.0 (inferido, não decodificado)", '
                    '"Família magra adicionada 2026-06-26: reconhecimento por prefixo sem decode posicional", '
                    '"Fonte: Kioxia UFS Product Brief Rev.3.0 (2025) kioxia.com Tier 1 ✓"]'
                ),
            ),

            # ═══ UFS: THGAF ═══════════════════════════════════════════════════
            #
            # UFS Kioxia geração anterior: UFS 2.1 (nasceu era Toshiba ~2017,
            # documentado em briefs Kioxia). Silkscreen físico pode ser "Toshiba"
            # ou "KIOXIA" dependendo da data de fabricação.
            # Capacidades: 16GB → 256GB (consumer + automotive Grade 2 AEC-Q100).
            # Fonte: Kioxia UFS Product Brief Rev.2.0 (2022) + Automotive Product
            #   Brief Rev.2.0 (2020). Tier 1 ✓. 11 PNs em fix_known_parts.py.
            #
            # Por que NÃO tem decode map (família magra):
            #   Mesmo raciocínio do THGJF — posições não mapeadas posicionalmente
            #   nesta sessão. KnownParts confirmados cobrem o universo conhecido.
            #
            dict(
                prefix="THGAF",
                brand=kioxia,               # Kioxia — fonte dos briefs é Kioxia era
                chip_type="UFS",
                subtype="UFS Kioxia",
                interface="UFS 2.1",        # padrão fixo para toda a família
                pn_length=15,
                decode_cap_pos=None,
                decode_cap_len=1,           # NOT NULL no DB; map="" → engine não decodifica
                decode_cap_map="",
                decode_gen_pos=None,
                decode_gen_map="",
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "UFS 2.1 Kioxia (era de transição Toshiba→Kioxia, ~2017-2022). "
                    "Família sem decode gramatical — capacity/specs dependem de KnownPart confirmado. "
                    "Capacidades: 16GB → 256GB (consumer + automotive Grade 2 AEC-Q100). "
                    "Fonte Tier 1: Kioxia UFS Product Brief Rev.2.0 (2022) + Automotive Brief (2020). "
                    "11 PNs confirmados em fix_known_parts.py. "
                    "Distinguir de THGJF* (UFS 3.1/4.0/4.1, geração mais nova)."
                ),
                reasoning=(
                    '["THGAF = UFS 2.1 Toshiba/Kioxia (~2017-2022) — confirmado kioxia.com Tier 1", '
                    '"Silkscreen físico: Toshiba (pré-2019) ou KIOXIA (pós-2019) — mesmo PN", '
                    '"Família magra adicionada 2026-06-26: reconhecimento por prefixo sem decode posicional", '
                    '"Fonte: Kioxia UFS Product Brief Rev.2.0 (2022) + Automotive Brief Rev.2.0 (2020)"]'
                ),
            ),

            # ═══ eMMC: THGAM ══════════════════════════════════════════════════
            #
            # eMMC 5.1 BiCS FLASH Kioxia — prefixo NOVO, distinto de THGBM.
            # NÃO é coberto pela gramática THGBM (pn[0:5]="THGAM" ≠ "THGBM").
            # Consumer grade, BGA-153, capacidades: 16GB, 32GB, 64GB, 128GB.
            # Séries V (VG7/VG8/VG9/VT0) e S (SG9/ST0).
            # Fonte: Kioxia e-MMC Product Brief Rev.2.0 (2023). Tier 1 ✓.
            # 6 PNs confirmados em fix_known_parts.py (2026-06-26).
            #
            # Por que NÃO tem decode map (família magra):
            #   Posições de capacidade no PN THGAM* não foram mapeadas posicionalmente
            #   nesta sessão — os 6 KnownParts confirmados cobrem o universo atual.
            #   Se mais variantes aparecerem na esteira, o decode map pode ser
            #   construído numa sessão futura com os 6 âncoras como ponto de partida.
            #
            # Estrutura parcialmente inferida (sem mapeamento formal):
            #   pn[0:5]  = "THGAM" → família eMMC 5.1 BiCS Kioxia (≠ THGBM)
            #   pn[5]    = série V ou S (VG7/VG8/VG9/VT0 = 16-128GB; SG9/ST0 = 64-128GB)
            #   pn_length = 15
            #
            dict(
                prefix="THGAM",
                brand=kioxia,               # Kioxia — prefixo nunca existiu como Toshiba
                chip_type="eMMC",
                subtype="eMMC Kioxia",
                interface="eMMC 5.1",       # padrão fixo para toda a família
                pn_length=15,
                decode_cap_pos=None,
                decode_cap_len=1,           # NOT NULL no DB; map="" → engine não decodifica
                decode_cap_map="",
                decode_gen_pos=None,
                decode_gen_map="",
                is_emcp=False,
                active=True,
                priority=50,
                tip=(
                    "eMMC 5.1 BiCS FLASH Kioxia — prefixo novo, distinto de THGBM. "
                    "NÃO coberto pela gramática THGBM (prefixo 5-char diferente). "
                    "Família sem decode gramatical — capacity/specs dependem de KnownPart confirmado. "
                    "Capacidades: 16GB, 32GB, 64GB, 128GB. Todos RENTÁVEIS. Package BGA-153. "
                    "Série V: VG7=16GB · VG8=32GB · VG9=64GB · VT0=128GB. "
                    "Série S: SG9=64GB · ST0=128GB. "
                    "Fonte Tier 1: Kioxia e-MMC Product Brief Rev.2.0 (2023). "
                    "6 PNs confirmados em fix_known_parts.py. "
                    "NÃO confundir com THGBM* (eMMC legado Toshiba/Kioxia, decodificado pela gramática)."
                ),
                reasoning=(
                    '["THGAM = prefixo eMMC 5.1 BiCS Kioxia novo (≠ THGBM) — confirmado kioxia.com Tier 1", '
                    '"pn[5]: série — V=consumer standard · S=consumer slim? (inferido, não decodificado)", '
                    '"Família magra adicionada 2026-06-26: reconhecimento por prefixo sem decode posicional", '
                    '"Fonte: Kioxia e-MMC Product Brief Rev.2.0 (2023) americas.kioxia.com Tier 1 ✓"]'
                ),
            ),

            # ═══ FAMÍLIAS BLOQUEADAS — pesquisa pendente ══════════════════════
            #
            # As famílias abaixo são vistas na esteira mas não têm documentação
            # positiva suficiente para o banco. Não remova estes comentários —
            # eles são a memória de trabalho para a próxima sessão de pesquisa.
            #
            # ── KLUE: UFS Kioxia (pós-2019) ───────────────────────────────────
            # Ex: KLUEG4UHDB-B2D1 (Kioxia EXCERIA UFS 3.1, 64GB — avaq.com, JS-rendered).
            # INSTRUÇÃO EXPLÍCITA DO OPERADOR: nunca adicionar KLUE sem verificar kioxia.com.
            # Pendente: buscar datasheet oficial em https://business.kioxia.com/
            #
            # ── TH58: NAND standalone Toshiba ─────────────────────────────────
            # TH58TEG7T23BAJGSB — NAND standalone (não é eMMC nem UFS).
            # Baixa prioridade operacional. Pendente: confirmar estrutura do PN.
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
