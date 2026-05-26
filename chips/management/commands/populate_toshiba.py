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
                    "pós-2019 gravados 'KIOXIA' mas mantêm os mesmos prefixos THGBM/THGAF."
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
        #           '5' = 32 Gbit/die (4 GB/die)   eMMC 5.0 era (BiCS1/2)
        #           '6' = 64 Gbit/die (8 GB/die)   eMMC 5.1 era (BiCS2/3)
        #           '7' = 128 Gbit/die (16 GB/die)  eMMC 5.1 alta densidade
        #           '8' = 64 Gbit/die (8 GB/die)   eMMC 5.1 BiCS3/4 (Toshiba Memory/Kioxia)
        #           '9' = 64 Gbit/die (8 GB/die)   eMMC 5.1 multi-die alta densidade
        #   pn[8] = tipo de stack (C / D / A / J…)  — sem significado de capacidade
        #   pn[9] = número de dies empilhados (1 / 2 / 4 / 8…)
        #
        #   Capacidade total = densidade(pn[7]) × dies(pn[9])
        #   A chave de 3 chars serve como índice único sem necessidade de cálculo no engine.
        #
        # Chaves confirmadas (Tier 2-3):
        #
        #   "4D1" = 2GB   → THGBM4G4D1HBAIR         censtry.com Tier 3 ✓
        #   "5D1" = 4GB   → THGBMNG5D1LBAIL          neven7.eu Tier 3 ✓
        #                 → THGBMTG5D1LBAIL          AIChipLink ✓ (worked example eMMC 5.0)
        #                 → THGBM4G5D1HBAIR          datasheet4u / Octopart ✓ (4-GByte e-MMC datasheet)
        #   "5D2" = 8GB   → THGBMDG5D2HBAIL          AIChipLink ✓ (worked example)
        #   "6C1" = 8GB   → THGBMJG6C1LBAU7          utmel.com Tier 3 ✓ (Memory Size: 64Gb 8G×8)
        #                 → THGBMJG6C1LBAIL          neven7.eu Tier 3 ✓ (v5.1 8GB)
        #   "7C1" = 16GB  → THGBMJG7C1LBAIL          search results Tier 3 ✓
        #   "8C4" = 32GB  → THGBMHG8C4LBAIR          Lisleapex search Tier 3 ✓
        #   "8D4" = 32GB  → THGBMBG8D4KBAIR          iiic.cc Tier 3 ✓ (256G-bit = 32GB, 4 dies)
        #   "9C8" = 64GB  → THGBMJG9C8LBAU8          Mouser Tier 2 ✓
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
            ("4D1",  "2GB",  ""),  # THGBM4G4D1HBAIR — censtry.com ✓
            ("5D1",  "4GB",  ""),  # THGBMNG5D1LBAIL — neven7.eu ✓; THGBMTG5D1LBAIL — AIChipLink ✓
            ("5D2",  "8GB",  ""),  # THGBMDG5D2HBAIL — AIChipLink ✓
            ("6C1",  "8GB",  ""),  # THGBMJG6C1LBAU7 — utmel ✓; THGBMJG6C1LBAIL — neven7.eu ✓
            ("7C1",  "16GB", ""),  # THGBMFG7C1LBAIL — Octopart 11 distrib. Tier 2 ✓ + Mouser/Kioxia America Tier 1 ✓ (128G-bit=16GB)
            ("7C2",  "16GB", ""),  # THGBMJG7C2LBAU8 — TrustedParts/Avnet/DigiKey Tier 2 ✓ (128Gbit=16GB); THGBMFG7C2LBAIL — Puris ✓
            ("7D2",  "16GB", ""),  # THGBMBG7D2KBAIL — Puris A19nm eMMC 5.0 ✓
            ("6D1",   "8GB", ""),  # THGBMBG6D1KBAIL — Puris A19nm eMMC 5.0 ✓ (cross-valida 6C1)
            ("8C4",  "32GB", ""),  # THGBMHG8C4LBAIR — Octopart Tier 2 ✓ (32G-byte=32GB) + Lisleapex Tier 3 ✓
            ("8D4",  "32GB", ""),  # THGBMBG8D4KBAIR — iiic.cc ✓ (256Gbit = 32GB)
            ("9C8",  "64GB", ""),  # THGBMJG9C8LBAU8 — Mouser ✓
        ]
        self._bulk_map("THGBM_CAP", thgbm_cap, toshiba, dry, overwrite)

        # ── DecodeMap: THGBM geração eMMC (pn[5], len=1) ──────────────────────
        #
        # pn[5] codifica a geração do processo NAND / versão eMMC:
        #   Letra = variante de processo NAND e velocidade eMMC.
        #   O engine usa val_primary para exibir a versão eMMC ao operador.
        #
        # Chaves confirmadas (Tier 2-3):
        #
        #   "N" = eMMC 5.0 → THGBMNG5D1LBAIL — neven7.eu "v5.0" ✓ + AIChipLink ✓
        #   "T" = eMMC 5.0 → THGBMTG5D1LBAIL — AIChipLink ✓ (mesmo tier que N)
        #   "H" = eMMC 5.1 → THGBMHG8C4LBAIR — Lisleapex ✓ (eMMC 5.1)
        #   "J" = eMMC 5.1 → THGBMJG6C1LBAIL — neven7.eu "v5.1" ✓
        #
        # Chaves BLOQUEADAS (sem fonte explícita para versão eMMC):
        #   "D" → provável eMMC 5.0 (THGBMDG5D2HBAIL — AIChipLink menciona mas sem versão)
        #   "4" → eMMC 4.41 (THGBM4G... — lógico pelo prefixo mas sem fonte primária)
        #   "G","M" → identificados em PNs de campo, versão não verificada
        #
        # Chaves DESBLOQUEADAS nesta sessão (2026-05-25):
        #   "F" → eMMC 5.0 CONFIRMADO: THGBMFG7C2LBAIL — Puris (/emmc-5-0/) + Alibaba "EMMC5.0" ✓
        #   "B" → eMMC 5.0 CONFIRMADO: THGBMBG8D4KBAIR — Puris + Preduo (/emmc-5-0/) + made-in-china "V5.0" ✓
        #         (IA externa havia estimado "eMMC 5.1" — ERRADO, refutado pela pesquisa)
        #
        # NÃO adicionar chaves BLOQUEADAS sem fonte Tier 2+ com versão eMMC explícita.
        thgbm_gen = [
            # (char_key,  val_primary,    val_secondary)
            ("N",  "eMMC 5.0",  ""),  # THGBMNG5D1LBAIL — neven7.eu ✓
            ("T",  "eMMC 5.0",  ""),  # THGBMTG5D1LBAIL — AIChipLink ✓
            ("F",  "eMMC 5.0",  ""),  # THGBMFG7C2LBAIL — Puris (/emmc-5-0/) + Alibaba "EMMC5.0" ✓
            ("B",  "eMMC 5.0",  ""),  # THGBMBG8D4KBAIR — Puris + Preduo (/emmc-5-0/) + made-in-china "V5.0" ✓
            ("H",  "eMMC 5.1",  ""),  # THGBMHG8C4LBAIR — Lisleapex ✓
            ("J",  "eMMC 5.1",  ""),  # THGBMJG6C1LBAIL — neven7.eu ✓
        ]
        self._bulk_map("THGBM_GEN", thgbm_gen, toshiba, dry, overwrite)

        # ── ChipFamilies ──────────────────────────────────────────────────────
        families = self._families(toshiba)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != toshiba.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = toshiba
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

    def _families(self, toshiba):
        """
        Retorna a lista de dicts de famílias Toshiba / Kioxia.

        Famílias implementadas:
          THGBM  — eMMC MLC/TLC (família principal, alta frequência na esteira)

        Famílias BLOQUEADAS (pesquisa pendente):
          THGAF  — UFS 2.x Toshiba (prefixo visto na esteira, sem spec verificada)
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
            #              N/T = eMMC 5.0 · H/J = eMMC 5.1 · (D/B/4 = BLOQUEADOS)
            #   pn[6]    = 'G' constante (processo de gravação — sem decode)
            #   pn[7:10] = chave composta de capacidade → THGBM_CAP
            #              pn[7] = densid./die · pn[8] = stack type · pn[9] = die count
            #   pn[10]   = tier de qualidade/organização (L/K/E/J…)
            #   pn[11:13]= "BA" constante (package type BGA153)
            #   pn[13]   = voltagem de I/O (I=1.8V, U=1.8V/3.3V)
            #   pn[14]   = variante de sufixo (R/L/7/8 = temperatura/bin)
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
            #   THGBMNG5D1LBAIL — 4GB eMMC 5.0 · neven7.eu ✓
            #   THGBMTG5D1LBAIL — 4GB eMMC 5.0 · AIChipLink ✓
            #   THGBMDG5D2HBAIL — 8GB eMMC 5.x · AIChipLink ✓
            #   THGBMJG6C1LBAU7 — 8GB eMMC 5.1 · utmel ✓
            #   THGBMJG6C1LBAIL — 8GB eMMC 5.1 · neven7.eu ✓
            #   THGBMFG7C1LBAIL — 16GB eMMC 5.0 · Octopart Tier 2 ✓ + Mouser/Kioxia Tier 1 ✓
            #   THGBMHG8C4LBAIR — 32GB eMMC 5.1 · Lisleapex ✓
            #   THGBMBG8D4KBAIR — 32GB (256Gbit) · iiic.cc ✓
            #   THGBMJG9C8LBAU8 — 64GB · Mouser ✓
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
                    "Geração automática: pn[5] → N/T/F/B=eMMC 5.0 | H/J=eMMC 5.1. "
                    "⚠ Separe por geração: 5.1 (H/J) vale ~15-25% a mais que 5.0 (N/T/F/B). "
                    "Capacidade: pn[7:10] → chave 3-chars → THGBM_CAP: "
                    "5D1=4GB · 5D2=8GB · 6C1=8GB · 6D1=8GB · 7C1=16GB · 7C2=16GB · 7D2=16GB · 8C4=32GB · 8D4=32GB · 9C8=64GB. "
                    "⚠ Chaves não mapeadas (ex: 4D4, 6A2, 8D2) ficam com capacity=null — "
                    "confirmar via Octopart/distribuidor e adicionar ao THGBM_CAP. "
                    "Pacote: BGA153 (11.5×13mm). "
                    "Interface paralela eMMC — NUNCA confundir com socket UFS (THGAF/KLUE). "
                    "Destino: bancada reacondicional Flash eMMC (separar por geração)."
                ),
                reasoning=(
                    '["T=Toshiba · H=NAND tipo H · G=geração G · B=bus 8-bit · M=mobile", '
                    '"pn[5]: código de geração NAND — N/T/F/B=eMMC 5.0 · H/J=eMMC 5.1", '
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

            # ═══ FAMÍLIAS BLOQUEADAS — pesquisa pendente ══════════════════════
            #
            # As famílias abaixo são vistas na esteira mas não têm documentação
            # positiva suficiente para o banco. Não remova estes comentários —
            # eles são a memória de trabalho para a próxima sessão de pesquisa.
            #
            # ── THGAF: UFS Toshiba (pré-2019) ─────────────────────────────────
            # Prefixo visto em campo: THGAF8G8T23BAIR (UFS 2.1, 256GB? — não confirmado).
            # BLOQUEAR até: verificar spec de capacity decode no toshiba.semicon-storage.com
            #   ou Mouser/DigiKey com datasheet completo.
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
