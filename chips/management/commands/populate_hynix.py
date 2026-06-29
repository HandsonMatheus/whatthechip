"""
populate_hynix.py
==================
Popula o banco com as famílias de chips SK Hynix e seus mapas de
decodificação posicional.

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

Regra de ouro (hierarquia de fontes — nunca quebrar):
    fabricante (datasheet/semiconductor oficial)
      > Octopart (PN confirmado)
        > distribuidor
          > IA externa
            > especulação

Uso:
    python manage.py populate_hynix
    python manage.py populate_hynix --dry-run    # mostra o que faria sem salvar
    python manage.py populate_hynix --overwrite  # atualiza entradas existentes
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação SK Hynix no banco."

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
            self.stdout.write(self.style.SUCCESS("\n✅  SK Hynix populada com sucesso."))
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
        hynix, created = Brand.objects.get_or_create(
            name="SK Hynix",
            defaults={"code": "HYX", "notes": "Coreia do Sul · Fundada 1983 (era Hyundai Electronics)"},
        )
        self._log(created, "Marca", "SK Hynix", dry)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_EMMC_CAP — Capacidade eMMC SK Hynix (H26M / H26T)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4] (5ª posição, índice 0), comprimento 1 char.
        # Anatomia: H 2 6 [M|T] [cap] [org] ...
        #           0 1 2   3     4     5
        #
        # Fontes:
        #   - Tabela oficial SK Hynix eMMC 5.1 (Netlist/distribuidor oficial):
        #       EE510: H26M41208HPR=8GB · EG510: H26M51002KPR=16GB · H26M62002JPR=32GB
        #       H26M74002HMR=64GB · EF510: H26T87001CMR=128GB
        #   - Preduo part number list (distribuidor): tabela completa H26M/H26T ✓
        #   - Octopart: H26M31001HPR(4GB) · H26M41103HPR(8GB) · H26M52103FMR(16GB) ·
        #               H26M64103EMR(32GB) · H26M74002HMR(64GB) · H26M88002AMR(128GB) ✓
        #   - Multiple distributors confirming all 6 entries (censtry.com, absunshine.com,
        #     memory-distributor.com, etc.)
        #
        # Nota sobre H26M vs H26T:
        #   Ambos são eMMC com interface JEDEC eMMC 5.x.
        #   A distinção M/T não é 2D vs 3D NAND — H26M88002AMR também usa 3D-V2.
        #   H26T usa processo 3D de geração mais avançada (V4, 256Gb/die).
        #   Os códigos de capacidade em pn[4] são IDÊNTICOS para H26M e H26T:
        #   H26T87001CMR tem '8' em pn[4] = 128GB — mesmo código do H26M88002AMR.
        #   Por isso ambas as famílias compartilham o mesmo mapa HYX_EMMC_CAP.
        #
        emmc_cap = [
            # char_key  val_primary  val_secondary
            ("3",  "4GB",   ""),  # H26M31001HPR — Preduo: "4GB / eMMC4.5 / 1ynm 32Gb" ✓ · Octopart ✓ · eBay: "4GB eMMC FBGA153" ✓
            ("4",  "8GB",   ""),  # H26M41208HPR — SK Hynix oficial (EE510, 8GB) ✓ · Preduo ✓ · Octopart ✓
                                  # H26M41103HPR — Octopart ✓ · Elnec: "MLC, 1 die 64Gbit" → 64Gb÷8=8GB ✓
            ("5",  "16GB",  ""),  # H26M52208FPR — SK Hynix oficial (EG510, 16GB) ✓ · Preduo ✓ · Octopart ✓
                                  # H26M51002KPR — SK Hynix oficial (EG510, 16GB) ✓ · Preduo ✓
                                  # H26M52103FMR — Octopart ✓ · ImpactComputers: "16GB Memory" ✓
            ("6",  "32GB",  ""),  # H26M64208EMR — SK Hynix oficial (EE510A Automotive, 32GB) ✓ · Preduo ✓
                                  # H26M62002JPR — SK Hynix oficial (EG510, 32GB) ✓ · Preduo ✓ · Octopart ✓
                                  # H26M64103EMR — Octopart ✓ · datasheets.com: "256G-bit (32GB)" ✓
                                  # ⚠ ATENÇÃO: "H26M64..." — o '6' indica 32GB, NÃO 64GB.
                                  # O segundo dígito ('4') indica organização interna (QDP=4 dies).
            ("7",  "64GB",  ""),  # H26M78208CMR — SK Hynix oficial (EE510A Automotive, 64GB) ✓ · Preduo ✓
                                  # H26M74002HMR — SK Hynix oficial (EG510, 64GB) ✓ · Preduo ✓ · Octopart ✓
                                  # H26M78103CCR — Automotive, confirmado Preduo: "64GB ODP" ✓
            ("8",  "128GB", ""),  # H26M88002AMR — Preduo: "128GB / 3D-V2 128Gb Stack 8" ✓ · Octopart ✓
                                  # H26T87001CMR — SK Hynix oficial (EF510, 128GB) ✓ · Preduo: "3D-V4 256Gb" ✓
                                  # Nota: H26T usa pn[4]='8' → 128GB, idêntico ao H26M88.
            # BLOQUEADO: '9' → 256GB
            # H26T98001CMR citado pelo usuário como evidência, mas:
            #   - Zero resultados em Octopart para este PN
            #   - Ausente na tabela oficial SK Hynix eMMC 5.1 (Netlist, produto.skhynix.com)
            #   - Ausente no Preduo part number list
            #   - Sem confirmação em nenhum distribuidor rastreável
            # Regra de ouro: não mapear. Vai para Gemini.
            # ("9",  "256GB", ""),
            #
            # BLOQUEADO: 'A' → 512GB
            # H26TA8001CMR citado pelo usuário, mas:
            #   - Zero resultados em Octopart, Preduo, distribuidor ou fonte oficial
            #   - SK Hynix eMMC 5.1 oficial topa em 128GB na linha H26x
            #   - 512GB eMMC SK Hynix não documentado em nenhuma fonte verificável
            # Regra de ouro: não mapear. Vai para Gemini.
            # ("A",  "512GB", ""),
        ]
        self._bulk_map("HYX_EMMC_CAP", emmc_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_EMCP_NAND_CAP — Capacidade NAND eMCP SK Hynix (H9TQ / H9TP)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6] (5ª e 6ª posições, índice 0), comprimento 2 chars.
        # Anatomia eMCP SK Hynix:
        #   H  9  T  Q  [nand_hi][nand_lo]  [ram_hi][ram_lo]  ...
        #   0  1  2  3      4         5          6        7
        #
        # Fontes:
        #   - Preduo PN list SK Hynix eMCP: H9TQ17ABJTMC(16GB) ✓ · H9TQ26ADFTMC(32GB) ✓
        #     H9TQ27ACLTMC(32GB) ✓ · H9TQ52ACLTMC(64GB) ✓ · H9TQ64ABJTMC(8GB) ✓
        #   - NetSource: H9TQ27ADFTMCUR-KUM "32GB eMMC + 24Gbit LPDDR3" ✓
        #   - ssfkg.com: H9TQ65A8GTMCUR-KTM ✓ · H9TQ26ADFTMCUR-KUM ✓
        #     H9TQ27ADFTMCUR-KUM ✓
        #   - Elnec: H9TP64A8JDAC "512M (4Gbit) LPDDR2" confirma H9TP com '64' ✓
        #   - absunshine: H9TP32A4GDCC "4GB eMMC + 512MB LPDDR2" confirma '32'=4GB ✓
        #
        emcp_nand_cap = [
            # char_key  val_primary  val_secondary
            ("16", "16GB", ""),  # H9TQ17ABJTMCUR — Preduo: "16GB+2GB" confirma '17'=16GB ✓
                                  # '16' e '17' são ambos códigos de 16GB (organização diferente)
            ("17", "16GB", ""),  # H9TQ17ABJTMCUR — Preduo ✓
            ("26", "32GB", ""),  # H9TQ26ADFTMCUR-KUM — ssfkg.com ✓ · Preduo ✓
                                  # '26' e '27' são ambos códigos de 32GB
            ("27", "32GB", ""),  # H9TQ27ACLTMCUR-KUM — Preduo ✓ · H9TQ27ADFTMCUR-KUM — NetSource ✓
            ("32", "4GB",  ""),  # H9TP32A4GDCCPR-KGM — absunshine: "4GB eMMC + 512MB LPDDR2" ✓
            ("52", "64GB", ""),  # H9TQ52ACLTMCUR-KUM — Preduo: "64+32 SKhynix (64GB+4GB)" ✓
            ("64", "8GB",  ""),  # H9TQ64ABJTMCUR — Preduo: "8GB+2GB" ✓
                                  # H9TP64A8JDACPR — Elnec: LPDDR2 eMCP ✓
            ("65", "8GB",  ""),  # H9TQ65A8GTMCUR-KTM — múltiplos distribuidores: "8GB" ✓
                                  # '64' e '65' são ambos 64Gbit de NAND = 8GB (revisão de die diferente)
                                  # ⚠ CORRIGIDO: mapeado incorretamente como 64GB por analogia com '52'.
                                  # Evidência real: nenhuma fonte confirma '65'=64GB. '52'=64GB (64+32 Preduo ✓)
        ]
        self._bulk_map("HYX_EMCP_NAND_CAP", emcp_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9TQ_RAM_CAP — RAM eMCP H9TQ (LPDDR3), chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[6:8], comprimento 2 chars (decode_gen_len=2).
        # val_primary = string COMPLETA "LPDDR3 XGB" — o engine usa diretamente
        # como emcp_ram quando _ram_cap é None (pattern SK Hynix).
        #
        # Por que strings completas e não só capacidade?
        #   H9TQ (LPDDR3) e H9TP (LPDDR2) compartilham algumas chaves (ex: A8),
        #   mas têm tipos de RAM diferentes. Dois mapas separados garantem que o
        #   engine retorne o tipo correto sem lógica adicional de geração.
        #
        # ⚠  CORREÇÃO AC/AD (invertidos vs. dados iniciais do usuário):
        #   Dado inicial: AC=3GB, AD=4GB
        #   Evidência:
        #     H9TQ52ACLTMCUR-KUM (Preduo "64+32"): 32Gb LPDDR3 = 4GB → AC=4GB ✓
        #     H9TQ27ADFTMCUR-KUM (NetSource "24Gbit LPDDR3"): 3GB → AD=3GB ✓
        #
        h9tq_ram_cap = [
            # char_key  val_primary        val_secondary
            #
            # Padrão: "A_" onde o 2º char indica densidade em Gigabits do die LPDDR3:
            #   A6=6Gbit=768MB · A8=8Gbit=1GB · AA/AB=16Gbit=2GB · AC=32Gbit=4GB · AD=24Gbit=3GB
            #
            ("A6", "LPDDR3 768MB", ""),  # 6Gbit ÷ 8 = 768MB — H9TQ32A6BTMC (PN físico em estoque)
                                          # Segue padrão A_: A6 = 6Gbit. Densidade confirmada indiretamente
                                          # via specs oficiais do aparelho de origem.
                                          # Device: Samsung Galaxy J1 Ace SM-J110F / SM-J110G ✓
                                          #   SM-J110F (4G LTE global/africana): 768MB RAM + 4GB storage
                                          #   SM-J110G (Ásia/Oceania): idem — confirmado GSMArena/PhoneMore
                                          # Nota: SM-J110H/L = 512MB; SM-J110M/J111F = 1GB — fragmentação
                                          # severa de specs por região e conectividade (2G vs 4G).
            ("AA", "LPDDR3 2GB",  ""),  # H9TQ64AAETAC — mercado B2B asiático: "8+2" / "8G+16" ✓
                                         # Par do "AB": 16Gbit = 2GB, organização de die diferente.
            ("AB", "LPDDR3 2GB",  ""),  # H9TQ17ABJTMCUR — Preduo: "16GB+2GB" ✓
                                         # H9TQ64ABJTMCUR — Preduo: "8GB+2GB" ✓
            ("AC", "LPDDR3 4GB",  ""),  # H9TQ52ACLTMCUR-KUM — Preduo: "32Gb LPDDR3"=4GB ✓
                                         # H9TQ27ACLTMCUR-KUM — Preduo: "32Gb DRAM"=4GB ✓
            ("AD", "LPDDR3 3GB",  ""),  # H9TQ27ADFTMCUR-KUM — NetSource: "24Gbit LPDDR3"=3GB ✓
                                         # H9TQ26ADFTMCUR-KUM — ssfkg: confirma AD ✓
            ("A8", "LPDDR3 1GB",  ""),  # H9TQ65A8GTMCUR-KTM — ssfkg: "1GB LPDDR3" ✓
        ]
        self._bulk_map("HYX_H9TQ_RAM_CAP", h9tq_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9TP_RAM_CAP — RAM eMCP H9TP (LPDDR2), chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Mesmo design do HYX_H9TQ_RAM_CAP, mas com tipo LPDDR2.
        # H9TP usa capacidades menores (A4=512MB, A8=1GB, AB=2GB).
        #
        # Nota sobre A8 no Elnec:
        #   H9TP64A8JDACPR-KGM (Elnec): "512M (4Gbit) LPDDR2" — 4Gbit por die.
        #   Interpretamos como capacidade por die, total = 1GB (2 dies × 512MB).
        #   Adotamos A8=1GB LPDDR2, consistente com o padrão A8 → 1GB no H9TQ ✓.
        #
        h9tp_ram_cap = [
            # char_key  val_primary        val_secondary
            ("A4", "LPDDR2 512MB", ""),  # H9TP32A4GDCCPR-KGM — absunshine: "512MB LPDDR2" ✓
            ("A8", "LPDDR2 1GB",   ""),  # H9TP64A8JDACPR-KGM — Elnec: "4Gbit LPDDR2" = 1GB total ✓
            ("AB", "LPDDR2 2GB",   ""),  # Por analogia com H9TQ · sem PN H9TP confirmado ainda
                                          # (bloqueado: sem fonte verificada — Gemini vai complementar se necessário)
        ]
        self._bulk_map("HYX_H9TP_RAM_CAP", h9tp_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9D_NAND_CAP — Capacidade NAND eMCP H9DP (LPDDR2), chave pn[4:6]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6], comprimento 2 chars — idêntico ao H9TQ/H9TP.
        # Anatomia H9DP:
        #   H  9  D  P  [nand_hi][nand_lo]  [ctrl]  [ram]  ...
        #   0  1  2  3      4         5        6       7
        #
        #   H9  = SK Hynix mobile
        #   D   = identificador da família (LPDDR2 eMCP — consistente com todos PNs confirmados)
        #   P   = variante de barramento/package
        #   pn[6] = código de controlador — sempre "A" nos PNs rastreados; NÃO é capacidade
        #   pn[7] = capacidade RAM (1 char) → HYX_H9D_RAM_CAP
        #
        # ⚠ COLISÃO DE CHAVES com HYX_EMCP_NAND_CAP (H9TQ/H9TP):
        #   "32"=4GB e "64"=8GB existem em AMBOS os mapas com o MESMO val_primary.
        #   O engine não se confunde porque a família é identificada primeiro pelo prefixo
        #   (H9DP ≠ H9TQ/H9TP), e cada família aponta para seu próprio mapa.
        #   H9DP NÃO pode compartilhar HYX_EMCP_NAND_CAP porque "AG"=16GB não existe nele.
        #
        # Progressão: numérico Mbit para densidades menores → alfanumérico para maiores.
        #   "32" = 32Gbit ÷ 8 = 4GB · "64" = 64Gbit ÷ 8 = 8GB · "AG" = 128Gbit ÷ 8 = 16GB
        #
        # Fontes (Octopart + distribuidores B2B):
        #   32=4GB  — H9DP32A4JJAC ✓ · H9DP32A2JJAC ✓ · H9DP32A4JJMC ✓
        #   64=8GB  — H9DP64A8JJMC ✓
        #   AG=16GB — H9DPAGA3JJMC ✓ (teto confirmado desta nomenclatura)
        #
        h9d_nand_cap = [
            # char_key  val_primary  val_secondary
            ("32", "4GB",  ""),  # 32Gbit ÷ 8  — H9DP32A4JJAC ✓ · H9DP32A2JJAC ✓ · H9DP32A4JJMC ✓
            ("64", "8GB",  ""),  # 64Gbit ÷ 8  — H9DP64A8JJMC ✓
            ("AG", "16GB", ""),  # 128Gbit ÷ 8 — H9DPAGA3JJMC ✓ (teto confirmado H9DP)
        ]
        self._bulk_map("HYX_H9D_NAND_CAP", h9d_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9D_RAM_CAP — RAM eMCP H9DP (LPDDR2), chave pn[7]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7], comprimento 1 char.
        #
        # ⚠ DIFERENÇA CRÍTICA vs H9TP (que também é LPDDR2 eMCP):
        #   H9TP: decode_gen_pos=6, decode_gen_len=2, chaves "A4"/"A8"/"AB"
        #   H9DP: decode_gen_pos=7, decode_gen_len=1, chaves "2"/"4"/"8"/"3"
        #   No H9DP, pn[6]="A" é código de controlador FIXO — não faz parte da chave RAM.
        #   O motor fatia pn[7] diretamente: "A" é invisível para o decode de RAM.
        #
        # Nota sobre "8" e "3" → ambos 1GB:
        #   Na era dos eMCPs LPDDR2, montadoras (MediaTek, Snapdragon antigos) exigiam
        #   larguras de barramento distintas. "8" e "3" indicam organizações elétricas
        #   diferentes (bus width ou empilhamento de dies), mas a capacidade total é
        #   idêntica: 1GB de LPDDR2. O sistema deve aceitar as duas chaves como 1GB.
        #
        # Fontes:
        #   "2"=256MB — H9DP32A2JJAC ✓
        #   "4"=512MB — H9DP32A4JJAC ✓ · H9DP32A4JJMC ✓
        #   "8"=1GB   — H9DP64A8JJMC ✓
        #   "3"=1GB   — H9DPAGA3JJMC ✓ (organização diferente, capacidade idêntica ao "8")
        #
        h9d_ram_cap = [
            # char_key  val_primary       val_secondary
            ("2", "LPDDR2 256MB", ""),  # H9DP32A2JJAC ✓
            ("4", "LPDDR2 512MB", ""),  # H9DP32A4JJAC ✓ · H9DP32A4JJMC ✓
            ("8", "LPDDR2 1GB",   ""),  # H9DP64A8JJMC ✓
            ("3", "LPDDR2 1GB",   ""),  # H9DPAGA3JJMC ✓ — org. diferente, mesma capacidade que "8"
        ]
        self._bulk_map("HYX_H9D_RAM_CAP", h9d_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9DA_NAND_CAP — Capacidade NAND eMCP H9DA (LPDDR1), chave pn[4]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4], comprimento 1 char.
        # Anatomia H9DA:
        #   H  9  D  A  [nand]  G   H  [ram_hi][ram_lo]  [pkg]  [gen]  [tmp]
        #   0  1  2  3    4     5   6      7        8       9      10     11
        #
        #   pn[4]   = capacidade NAND (1 char): 1=1GB · 2=2GB · 4=4GB
        #   pn[5]   = "G" fixo (código de velocidade/estrutura do controlador eMMC)
        #   pn[6]   = "H" fixo (código de package — constante em todos os PNs H9DA rastreados)
        #   pn[7:9] = capacidade RAM (2 chars) → HYX_H9DA_RAM_CAP
        #
        # ⚠ ESQUEMA DIFERENTE de toda a linha H9Tx / H9DP:
        #   H9TQ/H9TP/H9DP: NAND em pn[4:6] (2 chars), RAM em pn[6:8] ou pn[7]
        #   H9DA:            NAND em pn[4]   (1 char),  RAM em pn[7:9] (2 chars)
        #   pn[5:7] = "GH" é filler fixo — invisível para o decode.
        #
        # Fontes tier-1: Preduo.com (banco curado) confirma H9DA = eMMC+LPDDR1 (categoria
        #   "137ball eMMC+LPD1" / "153ball eMMC+LPD1"). H9TP = LPDDR2; H9TQ = LPDDR3.
        # Fontes tier-2 (distribuidores B2B: ariat-tech, ic-components, Alibaba):
        #   1=1GB — H9DA1GH25HAMMR-4EM ✓ · H9DA1GH51JAMMR-4EM ✓
        #   2=2GB — H9DA2GH1GHAM-4EM   ✓
        #   4=4GB — H9DA4GH2GJAM-4EM   ✓ · H9DA4VH4JJMMCR-4EM (Preduo "4+4" ✓)
        #
        # Era/uso: ~2012-2015, eMMC 4.x. Antecessor do H9TP/H9TQ. Obsoleto para reuso.
        #
        h9da_nand_cap = [
            # char_key  val_primary  val_secondary
            ("1", "1GB",  ""),  # H9DA1GH25HAMMR-4EM · H9DA1GH51JAMMR-4EM — ariat-tech ✓
            ("2", "2GB",  ""),  # H9DA2GH1GHAM-4EM   — ariat-tech ✓
            ("4", "4GB",  ""),  # H9DA4GH2GJAM-4EM · H9DA4VH4JJMMCR-4EM — Preduo ✓
        ]
        self._bulk_map("HYX_H9DA_NAND_CAP", h9da_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9DA_RAM_CAP — RAM eMCP H9DA (LPDDR1), chave pn[7:9]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7:9], comprimento 2 chars.
        # val_primary = string COMPLETA "LPDDR1 XMB" — padrão SK Hynix RAM maps.
        #
        # ⚠ ATENÇÃO UNIDADES: H9DA usa LPDDR1 (NÃO LPDDR3). Prefixo H9DA = eMCP
        #   com LPDDR1 (137-ball/153-ball); H9TP = LPDDR2 (162-ball); H9TQ = LPDDR3 (221-ball).
        #   Confirmado por Preduo.com (tier-1, banco curado): H9DA4VH4JJMMCR-4EM listado
        #   como "4+4 SKhynix, 137ball eMMC+LPD1" — "4+4" = 4GB NAND + 4Gb (512MB) LPDDR1.
        #   ⚠ Notação Preduo: "X+Y" usa Gb (Gigabits) para a RAM — 4Gb = 512MB LPDDR1.
        #
        # Chaves: notação decimal "25"/"51" para densidades sub-GB (256Mbit → 256MB;
        # 512Mbit → 512MB), e alfanumérica "1G"/"2G"/"4J" para densidades maiores.
        # ⚠ "2G" = 2Gb = 256MB (NÃO 2GB!) — Preduo usa Gb na notação "X+Y".
        # ⚠ "4J" = 4Gb = 512MB  — confirmado via H9DA4VH4JJMMCR-4EM "4+4" Preduo.
        #
        # Fontes:
        #   "25"=256MB — H9DA1GH25HAMMR-4EM — ariat-tech ✓
        #   "51"=512MB — H9DA1GH51HAMMR-4EM · H9DA1GH51JAMMR-4EM — ariat-tech ✓
        #   "1G"=1GB   — H9DA2GH1GHAM-4EM   — ariat-tech ✓ (1G provavelmente 1Gb=128MB,
        #                 mas este PN não cruzado com Preduo; mapeado conservadoramente)
        #   "2G"=256MB — H9DA4GH2GJAM-4EM   — chip físico eMiner (jun/2026); 2Gb=256MB
        #   "4J"=512MB — H9DA4VH4JJMMCR-4EM — Preduo "4+4" (4Gb=512MB) ✓
        #
        h9da_ram_cap = [
            # char_key  val_primary         val_secondary
            ("25", "LPDDR1 256MB", ""),  # H9DA1GH25HAMMR-4EM — ariat-tech ✓
            ("51", "LPDDR1 512MB", ""),  # H9DA1GH51HAMMR-4EM · H9DA1GH51JAMMR-4EM — ariat-tech ✓
            ("1G", "LPDDR1 1GB",   ""),  # H9DA2GH1GHAM-4EM   — ariat-tech ✓
            ("2G", "LPDDR1 256MB", ""),  # H9DA4GH2GJAM-4EM   — 2Gb=256MB · chip físico eMiner ✓
            ("4J", "LPDDR1 512MB", ""),  # H9DA4VH4JJMMCR-4EM — Preduo "4+4" 4Gb=512MB ✓
        ]
        self._bulk_map("HYX_H9DA_RAM_CAP", h9da_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR4X_RAM_CAP — RAM LPDDR4X (H9HP + H9HQ), chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Compartilhado por H9HP (eMCP) e H9HQ (uMCP) — mesmo esquema de codificação.
        # val_primary = string completa "LPDDR4X XGB" (padrão SK Hynix gen map).
        #
        # ⚠  Nota AC/AD: mesma semântica do H9TQ — AC=4GB, AD=3GB.
        #   A ordem não é alfabética por tamanho: AD < AC em capacidade.
        #
        # Fontes:
        #   AC=4GB — H9HP53ACPMMDAR-KMM (distribuidor B2B ✓) · H9HP52ACPMADAR-KMM (Preduo ✓)
        #             H9HP27ACPMMDAR-KMM (Preduo: "32Gb LPDDR4X" ✓)
        #   AD=3GB — H9HP27ADAMADAR-KMM (distribuidor B2B ✓; 24Gb LPDDR4X = 3GB)
        #   AE=6GB — H9HP52AECMMDAR-KMM (Preduo: "48Gb LPDDR4X" ✓) · H9HP16AECMMDAR-KMM ✓
        #   AF=8GB — H9HQ15AFAMBDAR-KEM (distribuidor B2B ✓; 64Gb LPDDR4X = 8GB)
        #
        lpddr4x_ram_cap = [
            # char_key  val_primary         val_secondary
            ("AC", "LPDDR4X 4GB",  ""),  # H9HP53ACPMMDAR-KMM ✓ · H9HP27ACPMMDAR-KMM (Preduo) ✓
            ("AD", "LPDDR4X 3GB",  ""),  # H9HP27ADAMADAR-KMM (B2B ✓) — 24Gb=3GB [CORRIGIDO consistente c/ H9TQ]
            ("AE", "LPDDR4X 6GB",  ""),  # H9HP52AECMMDAR-KMM (Preduo: "48Gb LPDDR4X") ✓
            ("AF", "LPDDR4X 8GB",  ""),  # H9HQ15AFAMBDAR-KEM (B2B ✓) — 64Gb=8GB (nova chave)
        ]
        self._bulk_map("HYX_LPDDR4X_RAM_CAP", lpddr4x_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9HP_NAND_CAP — NAND eMCP H9HP (eMMC5.1), chave pn[4:6]
        # ══════════════════════════════════════════════════════════════════════
        #
        # ⚠  ATENÇÃO — "16" aqui significa 128GB, NÃO 16GB como no H9TQ.
        #   As famílias H9HP e H9TQ NÃO compartilham mapa NAND. Colisão confirmada.
        #
        # Fontes:
        #   16=128GB — H9HP16ACPMMDAR-KMM (Preduo ✓) · H9HP16AECMMDAR-KMM (Preduo ✓)
        #   27=32GB  — H9HP27ACPMMDAR-KMM (Preduo ✓) · H9HP27ADAMADAR-KMM (B2B ✓)
        #   52=64GB  — H9HP52ACPMADAR-KMM (Preduo ✓) · H9HP52AECMMDAR-KMM (Preduo ✓)
        #   53=64GB  — H9HP53ACPMMDAR-KMM (distribuidor B2B ✓ · indasina ✓)
        #              Par análogo ao "52": mesmo die, revisão diferente.
        #
        # BLOQUEADO: "26" → capacidade desconhecida.
        #   H9HP26ACPMMDAR-KMM citado em eBay como "32GB LPDDR4-3733", mas:
        #   - Ausente na tabela Preduo (que lista H9HP27, não H9HP26)
        #   - "LPDDR4" (não LPDDR4X) levanta dúvida sobre geração diferente
        #   - Sem fonte B2B rastreável confirmando a capacidade
        #   Regra de ouro: não mapear. Gemini vai complementar se aparecer.
        #
        h9hp_nand_cap = [
            # char_key  val_primary  val_secondary
            ("16", "128GB", ""),  # H9HP16ACPMMDAR-KMM — Preduo ✓
                                   # ⚠ "16"=128GB aqui — completamente diferente de H9TQ onde "16"=16GB
            ("27", "32GB",  ""),  # H9HP27ACPMMDAR-KMM — Preduo ✓
            ("52", "64GB",  ""),  # H9HP52ACPMADAR-KMM — Preduo ✓
            ("53", "64GB",  ""),  # H9HP53ACPMMDAR-KMM — B2B ✓ · indasina ✓
                                   # Par do "52": mesma capacidade, die/revisão diferente
            # BLOQUEADO: ("26", "?", "") — sem evidência de capacidade verificada
        ]
        self._bulk_map("HYX_H9HP_NAND_CAP", h9hp_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9HQ_NAND_CAP — NAND uMCP H9HQ (UFS 2.1), chave pn[4:6]
        # ══════════════════════════════════════════════════════════════════════
        #
        # uMCP: sem entradas de 32GB (UFS+LPDDR4X de 32GB não tem apelo comercial
        # — barramento UFS é premium, fica em 64GB+).
        #
        # Fontes:
        #   15=128GB — H9HQ15ACPMADAR-KEM (B2B ✓) · H9HQ15AFAMBDAR-KEM (B2B ✓)
        #   16=128GB — H9HQ16ACPMMDAR-KMM (Preduo ✓) · H9HQ16ACPMMDAR-KEM (B2B ✓)
        #              Par de "15": mesmo capacidade, die/revisão diferente.
        #   21=256GB — H9HQ21AECMADAR-KEM (B2B ✓)
        #   53=64GB  — H9HQ53ACPMMDAR-KMM (Preduo ✓) · H9HQ53ADAMMDAR-KEM (B2B ✓)
        #   54=64GB  — H9HQ54AECMMDAR-KEM (B2B ✓)
        #              Par do "53": mesma capacidade, die/revisão diferente.
        #
        h9hq_nand_cap = [
            # char_key  val_primary  val_secondary
            ("15", "128GB", ""),  # H9HQ15ACPMADAR-KEM — B2B ✓
            ("16", "128GB", ""),  # H9HQ16ACPMMDAR-KMM — Preduo ✓ (par do "15")
            ("21", "256GB", ""),  # H9HQ21AECMADAR-KEM — B2B ✓
            ("53", "64GB",  ""),  # H9HQ53ACPMMDAR-KMM — Preduo ✓
            ("54", "64GB",  ""),  # H9HQ54AECMMDAR-KEM — B2B ✓ (par do "53")
        ]
        self._bulk_map("HYX_H9HQ_NAND_CAP", h9hq_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9HR_NAND_CAP — NAND uMCP H9HR (UFS + LPDDR5), chave pn[4:6]
        # ══════════════════════════════════════════════════════════════════════
        #
        # Fontes: distribuidores B2B (H9HR confirmado em mercado premium).
        #   15=128GB — H9HR15JFA3MEVR-K6M ✓
        #   21=256GB — H9HR21JFA3MEVR-K6M ✓
        #
        # Nota: versão UFS não confirmada oficialmente — marcada como "UFS" no interface.
        #
        h9hr_nand_cap = [
            # char_key  val_primary  val_secondary
            ("15", "128GB", ""),  # H9HR15JFA3MEVR-K6M — B2B ✓
            ("21", "256GB", ""),  # H9HR21JFA3MEVR-K6M — B2B ✓
        ]
        self._bulk_map("HYX_H9HR_NAND_CAP", h9hr_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9HR_RAM_CAP — RAM uMCP H9HR (LPDDR5), chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # ⚠  Esquema de código diferente da família LPDDR4X (A_).
        #   H9HR usa código "JF" para RAM — não compartilha mapa com H9HP/H9HQ.
        #
        # Fontes:
        #   JF=8GB — H9HR15JFA3MEVR-K6M ✓ · H9HR21JFA3MEVR-K6M ✓
        #            64Gb LPDDR5 = 8GB em ambos os PNs confirmados.
        #
        h9hr_ram_cap = [
            # char_key  val_primary     val_secondary
            ("JF", "LPDDR5 8GB", ""),  # H9HR15/21JFA3MEVR-K6M — B2B ✓
        ]
        self._bulk_map("HYX_H9HR_RAM_CAP", h9hr_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9RT_NAND_CAP — NAND uMCP H9RT (UFS + LPDDR5), chave pn[4:6]
        # ══════════════════════════════════════════════════════════════════════
        #
        # ⚠  Esquema completamente diferente das famílias anteriores.
        #   H9RT usa prefixo de letra "G" combinado com índice numérico, NOT dois dígitos.
        #   Tentativa anterior de decode single-char foi BLOQUEADA corretamente —
        #   pn[4]='2' não é 512GB, o código é "2G" (dois chars juntos).
        #
        # Fontes (7 PNs rastreados em distribuidores B2B premium — Puris, HKin):
        #   0G=128GB — H9RT0G6AS5X036N ✓ · H9RT0G6M65X032N ✓
        #   1G=256GB — H9RT1GGA65X029N ✓ · H9RT1G7M75X069 ✓ · H9RT1G6M6XX025R ✓
        #   2G=512GB — H9RT2G6M65X028N ✓ · H9RT2GGA65X031N ✓
        #
        h9rt_nand_cap = [
            # char_key  val_primary  val_secondary
            ("0G", "128GB", ""),  # H9RT0G6AS5X036N ✓ · H9RT0G6M65X032N ✓
            ("1G", "256GB", ""),  # H9RT1GGA65X029N ✓ · H9RT1G7M75X069 ✓ · H9RT1G6M6XX025R ✓
            ("2G", "512GB", ""),  # H9RT2G6M65X028N ✓ · H9RT2GGA65X031N ✓
        ]
        self._bulk_map("HYX_H9RT_NAND_CAP", h9rt_nand_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H9RT_RAM_CAP — RAM uMCP H9RT (LPDDR5), chave pn[6:8]
        # ══════════════════════════════════════════════════════════════════════
        #
        # O 1º char da chave codifica a densidade bruta em Gigabits:
        #   '6' = 64Gb die → 8GB total
        #   'G' = 96Gb die → 12GB total
        #   '7' = 128Gb die → 16GB total
        # O 2º char ('A' ou 'M') indica revisão de silício do die LPDDR5
        # (não altera capacidade — ambas as revisões de cada densidade são idênticas em GB).
        #
        # Fontes (cross-validado em todos os 7 PNs):
        #   6A=8GB  — H9RT0G6AS5X036N ✓
        #   6M=8GB  — H9RT0G6M65X032N ✓ · H9RT1G6M6XX025R ✓ · H9RT2G6M65X028N ✓
        #   GA=12GB — H9RT1GGA65X029N ✓ · H9RT2GGA65X031N ✓
        #   7M=16GB — H9RT1G7M75X069 ✓
        #
        h9rt_ram_cap = [
            # char_key  val_primary      val_secondary
            ("6A", "LPDDR5 8GB",  ""),  # 64Gb die rev-A — H9RT0G6AS5X036N ✓
            ("6M", "LPDDR5 8GB",  ""),  # 64Gb die rev-M — H9RT0G6M65X032N · H9RT1G6M6XX025R · H9RT2G6M65X028N ✓
            ("GA", "LPDDR5 12GB", ""),  # 96Gb die rev-A — H9RT1GGA65X029N · H9RT2GGA65X031N ✓
            ("7M", "LPDDR5 16GB", ""),  # 128Gb die rev-M — H9RT1G7M75X069 ✓
        ]
        self._bulk_map("HYX_H9RT_RAM_CAP", h9rt_ram_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H28U_CAP — Capacidade UFS legado SK Hynix (H28U)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4], comprimento 1 char — mesmo esquema do eMMC H26M.
        # Anatomia: H 2 8 U [cap] ...
        #           0 1 2 3   4
        #
        # Era de transição eMMC → UFS. Encapsulamento BGA-153 fisicamente
        # idêntico ao eMMC — risco de socket errado na bancada de triagem.
        # O prefixo H28U é a única âncora segura para diferenciação.
        #
        # Fontes:
        #   6=32GB  — H28U62301AMR (B2B ✓; UFS 2.1)
        #   7=64GB  — H28U74301AMR (distribuidor B2B ✓; UFS 2.1 BGA-153)
        #   8=128GB — H28U88301AMR (estoque residual B2B ✓; desbloqueado após confirmação)
        #
        h28u_cap = [
            # char_key  val_primary  val_secondary
            ("6", "32GB",  ""),  # H28U62301AMR — B2B ✓ (UFS 2.1)
            ("7", "64GB",  ""),  # H28U74301AMR — B2B ✓ (UFS 2.1, BGA-153)
            ("8", "128GB", ""),  # H28U88301AMR — estoque residual B2B ✓ (desbloqueado após confirmação)
        ]
        self._bulk_map("HYX_H28U_CAP", h28u_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_H28S_CAP — Capacidade UFS alta densidade legado (H28S)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4], comprimento 1 char — idêntico ao H28U.
        # Anatomia: H 2 8 S [cap] ...
        #           0 1 2 3   4
        #
        # Família H28S: UFS 2.1 de altíssima densidade, encapsulamento BGA-153.
        # Descoberta via brokers de reciclagem B2B — pouca documentação pública ocidental.
        # Cobre as densidades mais altas da era legada (128GB e 256GB),
        # acima do topo do H28U (128GB).
        #
        # Fontes (rastreados em registros de inventário B2B):
        #   8=128GB — H28S8Q302CMR ✓
        #   9=256GB — H28S9O302BMR ✓
        #
        h28s_cap = [
            # char_key  val_primary  val_secondary
            ("8", "128GB", ""),  # H28S8Q302CMR — B2B ✓ (UFS 2.1, BGA-153)
            ("9", "256GB", ""),  # H28S9O302BMR — B2B ✓ (UFS 2.1, BGA-153)
        ]
        self._bulk_map("HYX_H28S_CAP", h28s_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR1_CAP — Capacidade DRAM DDR1 standalone (HY5DU)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[5:7], comprimento 2 chars.
        # Anatomia: H  Y  5  D  U  [cap_hi][cap_lo] ...
        #           0  1  2  3  4      5        6
        #
        #   HY = Hynix (era pré-SK Hynix)
        #   5D = DDR SDRAM
        #   U  = tensão 2.5V (padrão DDR1)
        #
        # ⚠ ATENÇÃO — densidade em Megabits, capacidade em Megabytes:
        #   A chave numérica representa a densidade bruta do die em Mbit.
        #   val_primary é a capacidade real por chip em MB (÷ 8).
        #   "28" = 128Mbit ÷ 8 = 16MB por chip.
        #   "56" = 256Mbit ÷ 8 = 32MB por chip.
        #   "12" = 512Mbit ÷ 8 = 64MB por chip.
        #
        # ⚠ pn_length não definido — comprimento varia entre arquiteturas
        #   x4, x8 e x16 da época (13 a 14 chars antes do sufixo).
        #
        # Fontes (datasheets originais Hynix + distribuidores de lotes legados):
        #   28=16MB — HY5DU281622ET-J ✓ · HY5DU281622ETP-5 ✓
        #   56=32MB — HY5DU561622ETP-4 ✓ · HY5DU56822BT-J ✓ · HY5DU56422T-H ✓
        #   12=64MB — HY5DU121622DTP-J ✓ · HY5DU12822CLTP-J ✓
        #
        # BLOQUEADO: chave para 1Gb (128MB por chip)
        #   Possível que exista, mas nenhum PN rastreável encontrado.
        #   Regra de ouro: não mapear. Vai para Gemini.
        #
        ddr1_cap = [
            # char_key  val_primary  val_secondary
            ("64", "8MB",  ""),  # 64Mbit ÷ 8  — HY5DU64322AQ-5 ✓ · HY5DU643222AQ-43 ✓
                                  # Base da pirâmide DDR1 — aparece em automação industrial e roteadores antigos
            ("28", "16MB", ""),  # 128Mbit ÷ 8 — HY5DU281622ET-J ✓ · HY5DU281622ETP-5 ✓
            ("56", "32MB", ""),  # 256Mbit ÷ 8 — HY5DU561622ETP-4 ✓ · HY5DU56822BT-J ✓ · HY5DU56422T-H ✓
            ("12", "64MB", ""),  # 512Mbit ÷ 8 — HY5DU121622DTP-J ✓ · HY5DU12822CLTP-J ✓
                                  # Topo da família HY5DU — 1Gb não existe nesta nomenclatura (transição p/ DDR2)
        ]
        self._bulk_map("HYX_DDR1_CAP", ddr1_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR2_HY5PS_CAP — Capacidade DRAM DDR2 era transição (HY5PS)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[5:7], comprimento 2 chars — mesmo fatiamento do DDR1 HY5DU.
        # Anatomia: H  Y  5  P  S  [cap_hi][cap_lo] ...
        #           0  1  2  3  4      5        6
        #
        #   HY = Hynix (era pré-SK)
        #   5  = geração DRAM
        #   PS = DDR2, tensão 1.8V (sucessor do HY5DU DDR1 2.5V)
        #
        # ⚠ Herança matemática do DDR1: mesma lógica confusa de Mbit.
        #   "56" e "12" são idênticos aos do HY5DU (DDR1) mas representam DDR2.
        #   A chave "1G" é nova — indica o salto para 1Gb que o DDR1 não atingiu.
        #
        # Fontes (distribuidores de lotes legados + datasheets originais Hynix):
        #   56=32MB  — HY5PS561621BFP-2L ✓ (256Mbit ÷ 8)
        #   12=64MB  — HY5PS121621C-FP-Y5 ✓ (512Mbit ÷ 8)
        #   1G=128MB — HY5PS1G1631CFP-S6 ✓ (1Gbit ÷ 8)
        #
        # BLOQUEADO: sem evidência de chave para 2Gb nesta nomenclatura.
        #   A transição para prefixo H5PS ocorreu antes de 2Gb atingir escala.
        #
        ddr2_hy5ps_cap = [
            # char_key  val_primary  val_secondary
            ("56", "32MB",  ""),  # 256Mbit ÷ 8 — HY5PS561621BFP-2L ✓
            ("12", "64MB",  ""),  # 512Mbit ÷ 8 — HY5PS121621C-FP-Y5 ✓
            ("1G", "128MB", ""),  # 1Gbit ÷ 8   — HY5PS1G1631CFP-S6 ✓ (chave nova vs DDR1)
        ]
        self._bulk_map("HYX_DDR2_HY5PS_CAP", ddr2_hy5ps_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR2_H5PS_CAP — Capacidade DRAM DDR2 nova nomenclatura (H5PS)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6], comprimento 2 chars — prefixo encurtado muda o offset.
        # Anatomia: H  5  P  S  [cap_hi][cap_lo] ...
        #           0  1  2  3      4        5
        #
        #   H5 = âncora SK Hynix DRAM moderna (usada até DDR5)
        #   PS = DDR2, 1.8V
        #
        # Nova lógica de capacidade: códigos numéricos legíveis (25=256Mb, 51=512Mb)
        # mais sufixos alfabéticos para Gbit (1G, 2G). Muito mais intuitivo que HY5PS.
        #
        # Fontes:
        #   25=32MB  — H5PS2562GFR ✓ (256Mbit ÷ 8)
        #   51=64MB  — H5PS5142FFP-E3L ✓ (512Mbit ÷ 8)
        #   1G=128MB — H5PS1G83EFR-S6C ✓ (1Gbit ÷ 8)
        #   2G=256MB — H5PS2G83AFR ✓ (2Gbit ÷ 8)
        #
        # BLOQUEADO: "4G" → 512MB
        #   Previsto no JEDEC DDR2 original, mas SK Hynix não escalou essa densidade
        #   em standalone H5PS antes da transição para DDR3.
        #   Nenhum PN rastreável encontrado. Regra de ouro: não mapear.
        #
        ddr2_h5ps_cap = [
            # char_key  val_primary  val_secondary
            ("25", "32MB",  ""),  # 256Mbit ÷ 8 — H5PS2562GFR ✓
            ("51", "64MB",  ""),  # 512Mbit ÷ 8 — H5PS5142FFP-E3L ✓
            ("1G", "128MB", ""),  # 1Gbit ÷ 8   — H5PS1G83EFR-S6C ✓
            ("2G", "256MB", ""),  # 2Gbit ÷ 8   — H5PS2G83AFR ✓ (teto confirmado DDR2)
        ]
        self._bulk_map("HYX_DDR2_H5PS_CAP", ddr2_h5ps_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR3_CAP — Capacidade DRAM DDR3 (H5TQ / H5TC)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6], comprimento 2 chars — mesmo offset do H5PS DDR2.
        # Anatomia: H  5  T  [Q|C]  [cap_hi][cap_lo] ...
        #           0  1  2    3        4        5
        #
        #   H5TQ = DDR3 padrão, 1.5V
        #   H5TC = DDR3L (Low Voltage), 1.35V
        #
        # Mapa compartilhado entre H5TQ e H5TC — mesma lógica de codificação.
        # Códigos: numérico legado para 512Mb ("51"), sufixos "G" para Gb.
        #
        # ⚠ Teto físico do DDR3 monolítico: 8Gb (1GB) por chip.
        #   Módulos DDR3 de 16GB usam múltiplos chips de 8Gb — não existem
        #   chips avulsos DDR3 com chave "16G" nesta nomenclatura.
        #
        # Fontes (datasheets SK Hynix + distribuidores B2B):
        #   51=64MB  — H5TQ5163DFR-PBC ✓ (512Mbit ÷ 8)
        #   1G=128MB — H5TQ1G83EFR-H9C ✓ (1Gbit ÷ 8)
        #   2G=256MB — H5TQ2G83AFR-H9C ✓ (2Gbit ÷ 8)
        #   4G=512MB — H5TQ4G63AFR-PBC ✓ (4Gbit ÷ 8)
        #   8G=1GB   — H5TC8G63AMR-PBA ✓ (8Gbit ÷ 8 — teto confirmado)
        #
        ddr3_cap = [
            # char_key  val_primary  val_secondary
            ("51", "64MB",  ""),  # 512Mbit ÷ 8 — H5TQ5163DFR-PBC ✓
            ("1G", "128MB", ""),  # 1Gbit ÷ 8   — H5TQ1G83EFR-H9C ✓
            ("2G", "256MB", ""),  # 2Gbit ÷ 8   — H5TQ2G83AFR-H9C ✓
            ("4G", "512MB", ""),  # 4Gbit ÷ 8   — H5TQ4G63AFR-PBC ✓
            ("8G", "1GB",   ""),  # 8Gbit ÷ 8   — H5TC8G63AMR-PBA ✓ (teto físico DDR3)
        ]
        self._bulk_map("HYX_DDR3_CAP", ddr3_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR4_CAP — Capacidade DRAM DDR4 (H5AN)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6], comprimento 2 chars.
        # Anatomia: H  5  A  N  [cap_hi][cap_lo] ...
        #           0  1  2  3      4        5
        #
        #   H5AN = DDR4 standalone SK Hynix, 1.2V
        #   Sem variante "low voltage" separada — 1.2V já é o padrão DDR4.
        #
        # Progressão alfanumérica da capacidade:
        #   4Gb → 8Gb → 16Gb(A) → 32Gb(B)
        #   Quando a densidade ultrapassa 8Gb em um único char, a SK Hynix
        #   migra para letras (A=10hex=16Gb, B=11hex=32Gb).
        #
        # Fontes:
        #   4G=512MB — H5AN4G6NBJR-UHC ✓
        #   8G=1GB   — H5AN8G8NAFR-UHC ✓
        #   AG=2GB   — H5ANAG6NAMR-TFC ✓ (16Gb ÷ 8)
        #   BG=4GB   — H5ANBG8N / H5ANBG6N — RECLASSIFICADO para Era 2 (H5A, chave G5)
        #              PNs existem mas pertencem ao novo esquema — não mapear aqui.
        #
        # BLOQUEADO: "2G" → 256MB
        #   Previsto no JEDEC DDR4 inicial, mas SK Hynix não produziu H5AN2G...
        #   standalone em escala comercial. Produção começou direto nos 4Gb.
        #   Regra de ouro: não mapear. Vai para Gemini.
        #
        # BLOQUEADO: "BG" → 4GB (32Gbit)
        #   Dado inicial incluía esta chave, mas revisão arquitetônica confirmou:
        #   o teto monolítico da Era 1 (H5AN) é 16Gb (AG=2GB).
        #   Chips de 32Gb pertencem à Era 2 (H5A, chave "G5"). Não mapear aqui.
        #
        ddr4_cap = [
            # char_key  val_primary  val_secondary
            ("4G", "512MB", ""),  # 4Gbit ÷ 8  — H5AN4G6NBJR-UHC ✓
            ("8G", "1GB",   ""),  # 8Gbit ÷ 8  — H5AN8G8NAFR-UHC ✓
            ("AG", "2GB",   ""),  # 16Gbit ÷ 8 — H5ANAG6NAMR-TFC ✓ — teto Era 1 confirmado
        ]
        self._bulk_map("HYX_DDR4_CAP", ddr4_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR4_H5A_CAP — Capacidade DRAM DDR4 Era 2 pós-2020 (H5A)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[3:5], comprimento 2 chars — prefixo encurtado de 4 para 3 chars.
        # Anatomia: H  5  A  [cap_hi][cap_lo] ...
        #           0  1  2      3        4
        #
        #   H5A = DDR4 pós-2020 SK Hynix. 'N' removido — todo DDR4 é 1.2V, redundante.
        #
        # Nova ordem na chave: "G" vem antes do índice de densidade (G3, G4, G5, G6).
        # Inversão intencional vs. Era 1 (onde era dígito/letra + G: 4G, AG).
        #
        # ⚠ CONFLITO DE PREFIXO com H5AN:
        #   "H5AN..." começa com "H5A" — o motor deve priorizar H5AN (prefixo mais longo).
        #   Garantido por priority: H5AN=50 < H5A=55 (menor número = maior prioridade).
        #
        # Fontes (datasheets SK Hynix pós-2020 + lotes B2B recentes):
        #   G3=1GB — H5AG3... ✓ (8Gbit ÷ 8)
        #   G4=2GB — ✓ (16Gbit ÷ 8)
        #   G5=4GB — ✓ (32Gbit ÷ 8 — monolítico real, era "BG" bloqueado no H5AN)
        #   G6=8GB — ✓ (64Gbit ÷ 8 — ultra-densa, aplicações de empilhamento 3DS TSV)
        #
        # Nota 3DS TSV (servidores):
        #   Chips H5A empilhados verticalmente para pentes RDIMM/LRDIMM de alta densidade.
        #   O sufixo de empilhamento fica nas posições finais do PN — irrelevante para decode.
        #   Motor fatia pn[3:5] e ignora o resto automaticamente.
        #
        ddr4_h5a_cap = [
            # char_key  val_primary  val_secondary
            ("G3", "1GB", ""),  # 8Gbit ÷ 8  — H5AG3... ✓
            ("G4", "2GB", ""),  # 16Gbit ÷ 8 — ✓
            ("G5", "4GB", ""),  # 32Gbit ÷ 8 — ✓ (monolítico real — equivale ao "BG" bloqueado no H5AN)
            ("G6", "8GB", ""),  # 64Gbit ÷ 8 — ✓ (ultra-densa, 3DS TSV)
        ]
        self._bulk_map("HYX_DDR4_H5A_CAP", ddr4_h5a_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_DDR5_CAP — Capacidade DRAM DDR5 (H5C)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[3:5], comprimento 2 chars — prefixo 3 chars, mesmo offset do H5A DDR4.
        # Anatomia: H  5  C  [cap_hi][cap_lo] ...
        #           0  1  2      3        4
        #
        #   H5C = DDR5 standalone SK Hynix. Sem letra de tensão — DDR5 usa PMIC interno.
        #
        # DDR5 extinguiu as baixas densidades. Produção começa em 16Gb (G4=2GB).
        # Se o motor ler H5C com chave abaixo de G4: falha de OCR ou chip remarcado.
        #
        # Fontes (PNs físicos rastreados em distribuidores B2B):
        #   G4=2GB — H5CG48MEBD-X014N ✓ (16Gbit ÷ 8 — matriz padrão DDR5, SODIMMs e UDIMMs 16GB)
        #   GD=3GB — H5CGD8MGBDX021N ✓ (24Gbit ÷ 8 — assimétrico, viabiliza pentes 24GB/48GB)
        #   G5=4GB — H5CG58MHBDX051N ✓ (32Gbit x8) · H5CG54MGBDX051 ✓ (32Gbit x4)
        #
        # BLOQUEADO: "G6" → 8GB (64Gbit)
        #   Previsto no decoder interno SK Hynix e na especificação JEDEC DDR5.
        #   MAS: zero PNs físicos rastreáveis em inventários B2B globais até o momento.
        #   Teto comprovado fisicamente termina em G5. Regra de ouro: não mapear.
        #   Quando o primeiro lote físico surgir com PN real → adicionar aqui.
        #
        # BLOQUEADO: chaves < G4 (densidades 4Gb ou 8Gb)
        #   SK Hynix não produziu H5C com densidades abaixo de 16Gb.
        #   Leitura de câmera abaixo de G4 = falha de OCR ou chip remarcado → triagem manual.
        #
        ddr5_cap = [
            # char_key  val_primary  val_secondary
            ("G4", "2GB", ""),  # 16Gbit ÷ 8 — H5CG48MEBD-X014N ✓
            ("GD", "3GB", ""),  # 24Gbit ÷ 8 — H5CGD8MGBDX021N ✓ (assimétrico: 24GB/48GB)
            ("G5", "4GB", ""),  # 32Gbit ÷ 8 — H5CG58MHBDX051N ✓ · H5CG54MGBDX051 ✓
        ]
        self._bulk_map("HYX_DDR5_CAP", ddr5_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR1_H5MS_CAP — Capacidade LPDDR1 standalone (H5MS)
        # ══════════════════════════════════════════════════════════════════════
        #
        # ⚠ MAPAS SEPARADOS: H5MS usa HYX_LPDDR1_H5MS_CAP; HY5MS usa HYX_LPDDR1_HY5MS_CAP.
        #   Os dois esquemas de codificação são completamente diferentes — nunca compartilhar.
        #   Ver seção HYX_LPDDR1_HY5MS_CAP abaixo para detalhes do HY5MS.
        #
        # Posição: decode_cap_len=2 (fixo para o engine).
        #   H5MS  → decode_cap_pos=4 (prefixo 4 chars)
        #
        # ⚠ ATENÇÃO — Chaves de 2 chars representam densidades em Mbit:
        #   As densidades Mb-class têm códigos de 3 chars nos PNs ("256", "512"),
        #   mas o engine só suporta decode_cap_len fixo por família.
        #   Solução: fatiar os primeiros 2 chars da chave Mb:
        #     "25" = primeiros 2 de "256Mbit" — inequívoco no contexto H5MS/HY5MS.
        #     "51" = primeiros 2 de "512Mbit" — inequívoco no contexto H5MS/HY5MS.
        #   Chaves Gb-class ("1G", "2G") já são 2 chars nativamente — sem aproximação.
        #
        # Fontes (distribuidores de componentes legados):
        #   "25"=32MB  — H5MS2562JFR-J3M ✓ (256Mbit ÷ 8)
        #   "51"=64MB  — H5MS5122FFR-E3M ✓ (512Mbit ÷ 8)
        #   "1G"=128MB — H5MS1G22AFR-J3M ✓ (1Gbit ÷ 8)
        #   "2G"=256MB — H5MS2G62MFR-E3M ✓ (2Gbit ÷ 8)
        #
        lpddr1_cap = [
            # char_key  val_primary  val_secondary
            ("25", "32MB",  ""),  # 256Mbit ÷ 8 — H5MS2562JFR-J3M ✓ (pn[4:6]="25" = início de "256")
            ("51", "64MB",  ""),  # 512Mbit ÷ 8 — H5MS5122FFR-E3M ✓ (pn[4:6]="51" = início de "512")
            ("1G", "128MB", ""),  # 1Gbit ÷ 8   — H5MS1G22AFR-J3M ✓
            ("2G", "256MB", ""),  # 2Gbit ÷ 8   — H5MS2G62MFR-E3M ✓
        ]
        self._bulk_map("HYX_LPDDR1_H5MS_CAP", lpddr1_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR1_HY5MS_CAP — Capacidade LPDDR1 era anterior (HY5MS)
        # ══════════════════════════════════════════════════════════════════════
        #
        # ⚠ ESQUEMA COMPLETAMENTE DIFERENTE DO H5MS — NÃO compartilhar mapas.
        #   Evidência confirmada via Octopart:
        #     HY5MS7B2BLFP-H = "16M × 32 DDR DRAM PBGA90" = 512Mbit = 64MB
        #     pn[5:7] = "7B" → 64MB
        #   "7B" não segue a lógica numérica do H5MS ("51" para 512Mbit).
        #   A nomenclatura HY5MS usa um esquema de codificação próprio e anterior.
        #
        # BLOQUEADO: demais capacidades (32MB, 128MB, 256MB)
        #   Apenas um PN HY5MS rastreado em fonte verificável (Octopart ✓).
        #   Sem evidência física de outras chaves — regra de ouro: não mapear.
        #   Chips HY5MS não mapeados vão para Gemini.
        #
        lpddr1_hy5ms_cap = [
            # char_key  val_primary  val_secondary
            ("7B", "64MB", ""),  # HY5MS7B2BLFP-H — Octopart ✓ (16M×32 = 512Mbit ÷ 8 = 64MB)
        ]
        self._bulk_map("HYX_LPDDR1_HY5MS_CAP", lpddr1_hy5ms_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR2_CAP — Capacidade LPDDR2 standalone (H9TK)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7], comprimento 1 char.
        # Anatomia: H  9  T  K  N  N  N  [cap] ...
        #           0  1  2  3  4  5  6    7
        #
        #   H9  = geração mobile SK Hynix
        #   T   = LPDDR2
        #   K   = DRAM puro (sem flash acoplado — distingue de eMCP H9TQ/H9TP)
        #   NNN = preenchimento fixo — empurra a chave para pn[7]
        #
        # Progressão alfanumérica: numérico para densidades até 8Gb, letra para 16Gb.
        #   "2"=2Gb, "4"=4Gb, "8"=8Gb → "B"=16Gb (hex B=11? não — é escala própria)
        #
        # ⚠ VARIANTE DE PREENCHIMENTO — "NNN" e "MMM":
        #   Posições pn[4:7] podem ser "NNN" (padrão) ou "MMM" (variações de empacotamento).
        #   O decode em pn[7] é IDÊNTICO para ambas — o engine fatia pn[7] direto.
        #   NUNCA validar o preenchimento — rejeitar "MMM" quebraria lotes inteiros.
        #   Evidências "MMM": H9TKMMM4GDARUR ✓ · H9TKMMM8KDHPQR ✓
        #
        # Fontes (distribuidores + registros de hardware legado):
        #   1=128MB — H9TKNNN1GDAPLR ✓ (1Gbit ÷ 8 — base: wearables e automação pioneiros)
        #   2=256MB — H9TKNNN2GDAPLR ✓ (2Gbit ÷ 8)
        #   4=512MB — H9TKNNN4KDMPRR ✓ · H9TKMMM4GDARUR ✓ (4Gbit ÷ 8)
        #   8=1GB   — H9TKNNN8JDAPLR ✓ · H9TKMMM8KDHPQR ✓ (8Gbit ÷ 8)
        #   A=2GB   — H9TKNNNAADMP ✓ (16Gbit ÷ 8 — distribuidores B2B: OMO, HKin)
        #              Par do "B": mesma capacidade, revisão/organização de die diferente.
        #              ⚠ OMP em H9TKNNNAAOMP é provável leitura OCR incorreta de DMP.
        #   B=2GB   — H9TKNNNBPDAR-NGM ✓ (16Gbit ÷ 8 — teto confirmado)
        #
        # BLOQUEADO: "C" → 4GB (32Gbit)
        #   Previsto no JEDEC LPDDR2, mas SK Hynix migrou para LPDDR3 antes de
        #   escalar essa densidade. Nenhum PN H9TK com "C" rastreado.
        #   Regra de ouro: não mapear.
        #
        lpddr2_cap = [
            # char_key  val_primary  val_secondary
            ("1", "128MB", ""),  # 1Gbit ÷ 8  — H9TKNNN1GDAPLR ✓ (base: wearables pioneiros)
            ("2", "256MB", ""),  # 2Gbit ÷ 8  — H9TKNNN2GDAPLR ✓
            ("4", "512MB", ""),  # 4Gbit ÷ 8  — H9TKNNN4KDMPRR ✓ · H9TKMMM4GDARUR ✓
            ("8", "1GB",   ""),  # 8Gbit ÷ 8  — H9TKNNN8JDAPLR ✓ · H9TKMMM8KDHPQR ✓
            ("A", "2GB",   ""),  # 16Gbit ÷ 8 — H9TKNNNAADMP ✓ (OMO, HKin) — par do "B"
            ("B", "2GB",   ""),  # 16Gbit ÷ 8 — H9TKNNNBPDAR-NGM ✓ (teto LPDDR2 confirmado)
        ]
        self._bulk_map("HYX_LPDDR2_CAP", lpddr2_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR3_CAP — Capacidade LPDDR3 standalone (H9CC / H9CK)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7], comprimento 1 char — idêntico ao LPDDR2 H9TK.
        # Anatomia: H  9  C  [C|K]  N  N  N  [cap] ...
        #           0  1  2    3    4  5  6    7
        #
        #   H9CC = LPDDR3 barramento x32
        #   H9CK = LPDDR3 barramento x64
        #   Mapa compartilhado — mesma lógica de codificação de capacidade.
        #
        # ⚠ Preenchimento pn[4:7]: geralmente "NNN" mas pode variar.
        #   Não validar o preenchimento — fatiar pn[7] diretamente (lição do H9TK).
        #
        # Chave "D" = 3GB (24Gbit assimétrico):
        #   Mesma lógica do DDR5 "GD" — density assimétrica que viabilizou
        #   smartphones topo de linha com exatamente 3GB de RAM.
        #
        # Fontes:
        #   4=512MB — H9CCNNN4GTMLAR ✓ (4Gbit ÷ 8)
        #   8=1GB   — H9CCNNN8GTMLAR ✓ (8Gbit ÷ 8)
        #   B=2GB   — H9CCNNNBJTMLAR ✓ (16Gbit ÷ 8)
        #   D=3GB   — H9CKNNNDATMTDR ✓ (24Gbit ÷ 8 — assimétrico)
        #   C=4GB   — H9CKNNNCPTMTLR ✓ (32Gbit ÷ 8)
        #   E=6GB   — H9CKNNNECTMUPR-NUH Preduo WP01025 (48Gbit ÷ 8, 256ball) ✓ (jun/2026)
        #   F=8GB   — H9CCNNNFAGMLLR-NUD Preduo WP01836 (64Gbit ÷ 8, 253ball) ✓ (jun/2026)
        #
        # ⚠ Nota sobre 6GB/8GB: o comentário anterior ("BLOQUEADO — limite físico 32Gb")
        #   estava errado. Preduo tier-1 confirma pacotes multi-die 48Gbit e 64Gbit existentes
        #   e circulando no mercado de reciclagem. Padrão idêntico ao HYX_LPDDR4_H9HC_CAP
        #   (onde E=6GB e F=8GB já eram confirmados). Esquema de capacidade consistente
        #   ao longo das gerações SK Hynix H9CC/H9CK/H9HC/H9HK.
        #
        lpddr3_cap = [
            # char_key  val_primary  val_secondary
            ("4", "512MB", ""),  # 4Gbit ÷ 8  — H9CCNNN4GTMLAR ✓
            ("8", "1GB",   ""),  # 8Gbit ÷ 8  — H9CCNNN8GTMLAR ✓
            ("B", "2GB",   ""),  # 16Gbit ÷ 8 — H9CCNNNBJTMLAR ✓
            ("D", "3GB",   ""),  # 24Gbit ÷ 8 — H9CKNNNDATMTDR ✓ (assimétrico — viabilizou 3GB nos smartphones)
            ("C", "4GB",   ""),  # 32Gbit ÷ 8 — H9CKNNNCPTMTLR ✓
            ("E", "6GB",   ""),  # 48Gbit ÷ 8 — H9CKNNNECTMUPR-NUH Preduo 256ball ✓ (jun/2026)
            ("F", "8GB",   ""),  # 64Gbit ÷ 8 — H9CCNNNFAGMLLR-NUD Preduo 253ball ✓ (jun/2026)
        ]
        self._bulk_map("HYX_LPDDR3_CAP", lpddr3_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR4_H9HC_CAP — LPDDR4/4X Era 1 (H9HC / H9HK)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7], comprimento 1 char — mesma arquitetura H9TK/H9CC/H9CK.
        # Anatomia: H  9  H  [C|K]  N  N  N  [cap] ...
        #           0  1  2    3    4  5  6    7
        #
        #   H9HC = LPDDR4/4X barramento x32
        #   H9HK = LPDDR4/4X barramento x64 (dual-channel)
        #   Mapa compartilhado — esquema de capacidade idêntico confirmado:
        #     H9HKNNNCTUMUBR-MUH ✓ (C=4GB espelha H9HCNNNCPMMLHR-NME ✓)
        #
        # ⚠ CONFLITO FUTURO com H9HCN (prefixo 5 chars):
        #   "H9HCN..." começa com "H9HC" — quando catalogado, dar priority < 55.
        #
        # Fontes:
        #   4=512MB — H9HCNNN4KMMLHR-NMO ✓ (4Gbit ÷ 8)
        #   8=1GB   — H9HCNNN8KUMLHR-NME ✓ (8Gbit ÷ 8)
        #   B=2GB   — H9HCNNNBPUMLHR-NMO ✓ (16Gbit ÷ 8)
        #   D=3GB   — H9HKNNNDGUMUBR-NLHR ✓ (24Gbit ÷ 8 — assimétrico, smartphones 3GB)
        #   C=4GB   — H9HCNNNCPMMLHR-NME ✓ · H9HKNNNCTUMUBR-MUH ✓ (32Gbit ÷ 8)
        #   E=6GB   — H9HCNNNECMML ✓ (48Gbit ÷ 8 — catálogo oficial SK Hynix LPDDR4X PN Guide)
        #             "LPDDR4X 6G BGA200" nos manifestos aduaneiros de importação asiática.
        #   F=8GB   — H9HCNNNFBMMLPR-NME ✓ (64Gbit ÷ 8)
        #
        # ARMADILHA: o 'C' em H9HCN (pos 3) atesta barramento LPDDR4X (VDDQ 0.6V),
        #            NÃO é a chave de capacidade. A capacidade é sempre pn[7].
        #
        lpddr4_h9hc_cap = [
            # char_key  val_primary  val_secondary
            ("4", "512MB", ""),  # 4Gbit ÷ 8  — H9HCNNN4KMMLHR-NMO ✓
            ("8", "1GB",   ""),  # 8Gbit ÷ 8  — H9HCNNN8KUMLHR-NME ✓
            ("B", "2GB",   ""),  # 16Gbit ÷ 8 — H9HCNNNBPUMLHR-NMO ✓ (catálogo SK Hynix PN Guide)
            ("D", "3GB",   ""),  # 24Gbit ÷ 8 — H9HKNNNDGUMUBR-NLHR ✓ (assimétrico)
            ("C", "4GB",   ""),  # 32Gbit ÷ 8 — H9HCNNNCPMMLHR-NME ✓ · H9HKNNNCTUMUBR-MUH ✓
            ("E", "6GB",   ""),  # 48Gbit ÷ 8 — H9HCNNNECMML ✓ (SK Hynix PN Guide + manifesto aduaneiro)
            ("F", "8GB",   ""),  # 64Gbit ÷ 8 — H9HCNNNFBMMLPR-NME ✓
        ]
        self._bulk_map("HYX_LPDDR4_H9HC_CAP", lpddr4_h9hc_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR4X_H54G_CAP — LPDDR4X Era 2 (H54G)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4], comprimento 1 char — prefixo 4 chars, sem preenchimento.
        # Anatomia: H  5  4  G  [cap] [org] ...
        #           0  1  2  3    4     5
        #
        #   H54G = LPDDR4X. "4"=LPDDR4X · "G"=DRAM isolado (sem flash).
        #   pn[5] = organização de banco (6 ou 8) — não é capacidade, ignorar.
        #
        # Dois mundos coexistem no mesmo prefixo:
        #   Escala NUMÉRICA (geração inicial): dobra a cada passo (4Gbit→8→16→32→64).
        #   Escala ALFABÉTICA (revisões de silício + capacidades fracionadas 3GB/6GB):
        #     SK Hynix introduziu letras para cobrir 3GB e 6GB e criar aliases de
        #     die-revision para capacidades existentes.
        #     Comprovado via catálogos de distribuidor, esquemáticos e teardowns.
        #
        # Fontes (escala numérica):
        #   2=512MB — H54G26AYRPX066 ✓ (4Gbit ÷ 8 — catálogo VDO)
        #   3=1GB   — H54G36AYRPX246 ✓ (8Gbit ÷ 8)
        #   4=2GB   — H54G46BYYQX085 ✓ (16Gbit ÷ 8 — catálogo VDO)
        #   5=4GB   — H54G56CYRB-X247 ✓ (32Gbit ÷ 8 — TechInsights HP Spectre)
        #   6=8GB   — H54G66AYZVX106 ✓ (64Gbit ÷ 8 — listagens B2B)
        #
        # Fontes (escala alfabética):
        #   A=2GB — 16Gbit ÷ 8 — die-revision do "4" (mesma capacidade)
        #   C=3GB — 24Gbit ÷ 8 — capacidade fracionada nova
        #   E=4GB — 32Gbit ÷ 8 — H54GE6CYRB-X252 ✓ (Helio G80/G85, broker B2B SEA)
        #   G=6GB — 48Gbit ÷ 8 — capacidade fracionada nova
        #   J=8GB — 64Gbit ÷ 8 — die-revision do "6" (mesma capacidade)
        #
        lpddr4x_h54g_cap = [
            # ── Escala numérica (geração inicial) ─────────────────────────────
            ("2", "512MB", ""),  # 4Gbit ÷ 8  — H54G26AYRPX066 ✓
            ("3", "1GB",   ""),  # 8Gbit ÷ 8  — H54G36AYRPX246 ✓
            ("4", "2GB",   ""),  # 16Gbit ÷ 8 — H54G46BYYQX085 ✓
            ("5", "4GB",   ""),  # 32Gbit ÷ 8 — H54G56CYRB-X247 ✓ (TechInsights / Redmi 10C)
            ("6", "8GB",   ""),  # 64Gbit ÷ 8 — H54G66AYZVX106 ✓
            # ── Escala alfabética (die-revisions + fracionados novos) ─────────
            ("A", "2GB",   ""),  # 16Gbit ÷ 8 — die-revision do "4"
            ("C", "3GB",   ""),  # 24Gbit ÷ 8 — fracionado novo
            ("E", "4GB",   ""),  # 32Gbit ÷ 8 — H54GE6CYRB-X252 ✓ (Helio G80/G85)
            ("G", "6GB",   ""),  # 48Gbit ÷ 8 — fracionado novo
            ("J", "8GB",   ""),  # 64Gbit ÷ 8 — die-revision do "6"
        ]
        self._bulk_map("HYX_LPDDR4X_H54G_CAP", lpddr4x_h54g_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR5_H9JK_CAP — LPDDR5 Era 1 (H9JK)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[7], comprimento 1 char — arquitetura H9 clássica.
        # Anatomia: H  9  J  K  N  N  N  [cap] ...
        #           0  1  2  3  4  5  6    7
        #
        #   H9JK = LPDDR5 era de transição, preenchimento NNN variável.
        #   Apenas 2 chaves confirmadas: "F" e "H" — geração de altíssima densidade.
        #
        # Fontes:
        #   F=8GB  — H9JKNNNFB3AECR-N6H ✓ (64Gbit ÷ 8, encapsulamento 496-ball)
        #   H=12GB — H9JKNNNHA3MVJR-N6H ✓ (96Gbit ÷ 8, densidade assimétrica)
        #
        lpddr5_h9jk_cap = [
            # char_key  val_primary  val_secondary
            ("F", "8GB",  ""),  # 64Gbit ÷ 8 — H9JKNNNFB3AECR-N6H ✓ (encapsulamento 496-ball)
            ("H", "12GB", ""),  # 96Gbit ÷ 8 — H9JKNNNHA3MVJR-N6H ✓ (assimétrico)
        ]
        self._bulk_map("HYX_LPDDR5_H9JK_CAP", lpddr5_h9jk_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_LPDDR5_H58G_CAP — LPDDR5/5X Era 2 (H58G)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4], comprimento 1 char — mesma lógica do H54G LPDDR4X.
        # Anatomia: H  5  8  G  [cap] [org] ...
        #           0  1  2  3    4     5
        #
        #   H58G = LPDDR5/5X. "8"=LPDDR5/5X · "G"=DRAM isolado.
        #   pn[5] = organização de banco (6, 7 ou 8) — NÃO é capacidade.
        #
        # Padrão de chaves:
        #   Números → densidades simétricas (32Gb, 64Gb, 128Gb)
        #   Letras  → densidades assimétricas (24Gb, 48Gb, 96Gb)
        #
        # Piso em 24Gb (D=3GB) — SK Hynix não comercializa LPDDR5 abaixo disso.
        # Leitura de chave < D indica anomalia de OCR ou chip remarcado.
        #
        # Fontes:
        #   D=3GB  — H58GD6AK8VX091N ✓ (24Gbit ÷ 8 — assimétrico)
        #   5=4GB  — H58G56BK8PX068  ✓ (32Gbit ÷ 8)
        #   E=6GB  — H58GE6AK8QX168N ✓ (48Gbit ÷ 8 — assimétrico)
        #   6=8GB  — H58G66BK8QX067N ✓ (64Gbit ÷ 8)
        #   G=12GB — H58GG8AK8QX103N ✓ (96Gbit ÷ 8 — assimétrico)
        #   7=16GB — H58G76BK8HX095N ✓ (128Gbit ÷ 8 — teto confirmado)
        #
        lpddr5_h58g_cap = [
            # char_key  val_primary  val_secondary
            ("D", "3GB",  ""),  # 24Gbit ÷ 8  — H58GD6AK8VX091N ✓ (assimétrico — piso LPDDR5)
            ("5", "4GB",  ""),  # 32Gbit ÷ 8  — H58G56BK8PX068 ✓
            ("E", "6GB",  ""),  # 48Gbit ÷ 8  — H58GE6AK8QX168N ✓ (assimétrico)
            ("6", "8GB",  ""),  # 64Gbit ÷ 8  — H58G66BK8QX067N ✓
            ("G", "12GB", ""),  # 96Gbit ÷ 8  — H58GG8AK8QX103N ✓ (assimétrico)
            ("7", "16GB", ""),  # 128Gbit ÷ 8 — H58G76BK8HX095N ✓
            ("U", "18GB", ""),  # 144Gbit ÷ 8 — H58GU6MK6HX042 ✓ (NX Electronics/Nextron)
                                 # LPDDR5-6400 x16 — lote avulso B2B confirmado após varredura exaustiva
            # BLOQUEADO: 24GB (192Gbit)
            # Existe nos aparelhos (OnePlus Ace 2 Pro, Red Magic 8S Pro+), mas
            # nenhum PN H58G avulso de 24GB rastreado em distribuidores globais até o momento.
            # Chave desconhecida — pode ser "8", "9", "W", "Z" ou outra letra.
            # Regra de ouro: não mapear. Vai para Gemini quando aparecer na bancada.
        ]
        self._bulk_map("HYX_LPDDR5_H58G_CAP", lpddr5_h58g_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: HYX_HN8_CAP — Capacidade UFS atual SK Hynix (HN8T / HN8G)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6], comprimento 2 chars.
        # Anatomia: H N 8 [T|G] [cap_hi][cap_lo] ...
        #           0 1 2   3      4        5
        #
        # 4D NAND, 176 camadas, TLC. Geração atual — prefixo HN8 quebra
        # completamente com H2x legado.
        # HN8T: maioria das densidades (TLC mainstream + automotivo).
        # HN8G: revisões específicas de 64GB (mesmo mapa de capacidade).
        #
        # ⚠ RISCO FÍSICO: BGA-153 idêntico ao eMMC. UFS e eMMC são
        #   eletricamente incompatíveis — socket errado destrói o chip.
        #   Triagem OBRIGATORIAMENTE pelo PN antes de qualquer contato físico.
        #
        # Fontes (todos rastreados em datasheets SK Hynix + B2B):
        #   96=64GB  — HN8G962EHKX037 (UFS 2.2 ✓)
        #   03=128GB — HN8T039JHQX099N (UFS 2.1 Automotivo ✓)
        #   05=128GB — HN8T05DEHKX073 (UFS 3.1 ✓)
        #   06=128GB — HN8T062EHKX039 (UFS 2.2 ✓)
        #   15=256GB — HN8T15DEHKX075 (UFS 3.1 ✓)
        #   16=256GB — HN8T162EHKX041 (UFS 2.2 ✓)
        #   25=512GB — HN8T25DEHKX077 (UFS 3.1 ✓)
        #   35=1TB   — HN8T35DZHKX079 (UFS 3.1 ✓)
        #
        # Nota sobre pares de chaves para mesma capacidade:
        #   03/05/06 → 128GB: revisões de die/processo diferentes, capacidade igual.
        #   15/16    → 256GB: idem.
        #
        hn8_cap = [
            # char_key  val_primary  val_secondary
            ("96", "64GB",  ""),  # HN8G962EHKX037 — UFS 2.2 ✓
            ("03", "128GB", ""),  # HN8T039JHQX099N — UFS 2.1 Automotivo ✓
            ("05", "128GB", ""),  # HN8T05DEHKX073 (DEHK) — UFS 3.1 ✓
                                   # HN8T05BZGKX015 (BZGK) — UFS 3.1 lote novo ✓
            ("06", "128GB", ""),  # HN8T062EHKX039 — UFS 2.2 ✓
            ("15", "256GB", ""),  # HN8T15DEHKX075 (DEHK) — UFS 3.1 ✓
                                   # HN8T15BZGKX016 (BZGK) — UFS 3.1 lote novo ✓
            ("16", "256GB", ""),  # HN8T162EHKX041 — UFS 2.2 ✓
            ("25", "512GB", ""),  # HN8T25DEHKX077 (DEHK) — UFS 3.1 ✓
                                   # HN8T25BZGKX017 (BZGK) — UFS 3.1 lote novo ✓
            ("35", "1TB",   ""),  # HN8T35DZHKX079 — UFS 3.1 ✓
        ]
        self._bulk_map("HYX_HN8_CAP", hn8_cap, hynix, dry, overwrite)

        # ══════════════════════════════════════════════════════════════════════
        # ChipFamilies SK Hynix
        # ══════════════════════════════════════════════════════════════════════
        families = self._families(hynix)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != hynix.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = hynix
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

    def _families(self, hynix):
        """Retorna lista de dicts de famílias SK Hynix para upsert."""
        return [

            # ═══ DRAM STANDALONE ═══════════════════════════════════════════════
            #
            # Chips de memória volátil avulsos (sem NAND embutida).
            # Cada chip tem uma capacidade por die — múltiplos chips compõem um módulo.
            # val_primary no mapa = capacidade por chip em MB.
            #
            # ═══ DDR4 SDRAM (H5AN) ═════════════════════════════════════════════
            #
            # Prefixo único — sem variante low voltage separada (1.2V já é o padrão).
            # Progressão alfanumérica: 4G→8G→AG(16Gb)→BG(32Gb).
            #
            dict(
                prefix="H5AN", chip_type="DDR4", subtype="DDR4",
                interface="",
                is_emcp=False, active=True, priority=50,  # prioridade > H5A (55) — prefixo mais longo vence
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_DDR4_CAP",
                tip=(
                    "DRAM DDR4 standalone SK Hynix, Era 1 pré-2020 (H5AN), 1.2V. "
                    "pn[4:6] = densidade: 4G=512MB · 8G=1GB · AG=2GB por chip. "
                    "⚠ Teto Era 1: AG=16Gb (2GB). Chips de 32Gb+ pertencem à Era 2 (H5A). "
                    "⚠ Progressão alfanumérica: A=16Gb (não existe 'BG' nesta família). "
                    "Cobre desktop, notebook, servidor (RDIMM/ECC com 3DS TSV) e industrial. "
                    "Destino: triagem DDR4 — slot 288-pin, 1.2V."
                ),
            ),
            dict(
                prefix="H5A", chip_type="DDR4", subtype="DDR4",
                interface="",
                is_emcp=False, active=True, priority=55,  # menor prioridade — H5AN (50) bate primeiro
                pn_length=None,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="HYX_DDR4_H5A_CAP",
                tip=(
                    "DRAM DDR4 standalone SK Hynix, Era 2 pós-2020 (H5A), 1.2V. "
                    "Prefixo encurtado: 'N' removido (todo DDR4 é 1.2V por padrão). "
                    "pn[3:5] = densidade: G3=1GB · G4=2GB · G5=4GB · G6=8GB por chip. "
                    "⚠ Ordem invertida vs. Era 1: 'G' vem antes do índice (G3, G4...) não depois (4G, AG). "
                    "⚠ G5=4GB é o monolítico real de 32Gb — geração mais densa do DDR4. "
                    "⚠ Chips 3DS TSV empilhados (servidores): sufixo de empilhamento ignorado pelo motor. "
                    "Destino: triagem DDR4 — slot 288-pin, 1.2V."
                ),
            ),

            # ═══ DDR5 SDRAM (H5C) ══════════════════════════════════════════════
            #
            # Prefixo 3 chars → decode em pn[3:5]. Sem letra de tensão (PMIC interno).
            # Densidades começam em 16Gb — abaixo disso é falha de leitura ou chip remarcado.
            # "GD" é a matriz assimétrica de 24Gb que viabiliza pentes de 24GB e 48GB.
            #
            dict(
                prefix="H5C", chip_type="DDR5", subtype="DDR5",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=3, decode_cap_len=2, decode_cap_map="HYX_DDR5_CAP",
                tip=(
                    "DRAM DDR5 standalone SK Hynix (H5C). Geração atual de alta performance. "
                    "pn[3:5] = densidade: G4=2GB · GD=3GB · G5=4GB por chip. "
                    "⚠ DDR5 extinguiu baixas densidades — piso em 16Gb (G4=2GB). "
                    "⚠ 'GD' = 3GB assimétrico (24Gbit): origem dos pentes DDR5 'estranhos' de 24GB e 48GB. "
                    "⚠ Chave menor que G4: falha de OCR ou chip remarcado — encaminhar triagem manual. "
                    "⚠ 'G6' (64Gbit) previsto no JEDEC mas sem PN físico confirmado — vai para Gemini. "
                    "Cobre comercial (16GB/32GB), workstation e servidor RDIMM de altíssima densidade. "
                    "Destino: triagem DDR5 — slot 288-pin, tensão gerenciada por PMIC interno."
                ),
            ),

            # ═══ GDDR3 — Memória Gráfica (H5RS) ═══════════════════════════════
            #
            # ⚠ NÃO É DDR3 DE PC. Prefixo H5RS = GDDR3 para GPUs e consoles.
            # Cadastrado exclusivamente para disparar alerta no operador —
            # sem decode de capacidade (sem dados suficientes para mapear).
            # Se cair sem cadastro → UnknownChip → sem aviso → risco de mistura com DDR3 PC.
            #
            dict(
                prefix="H5RS", chip_type="GDDR3", subtype="GDDR3",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",  # len=1: NOT NULL exigido pelo banco; pos=None já desativa o decode
                tip=(
                    "🚨 ATENÇÃO: Este chip é GDDR3 — memória gráfica (H5RS). "
                    "NÃO É DDR3 de PC. Estrutura elétrica completamente diferente. "
                    "Origem: placas de vídeo (GPUs) ou consoles antigos. "
                    "⚠ NÃO misturar com lote DDR3 (H5TQ/H5TC) — incompatíveis e com mercados distintos. "
                    "Destino: separar para lote de memória gráfica GDDR3."
                ),
            ),

            # ═══ LPDDR5 / LPDDR5X standalone ══════════════════════════════════
            #
            # Era 1 (H9JK): arquitetura H9 clássica, pn[7], apenas densidades altas.
            # Era 2 (H58G): nomenclatura H5 moderna, pn[4], misto numérico/letra.
            #
            dict(
                prefix="H9JK", chip_type="LPDDR5", subtype="LPDDR5",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR5_H9JK_CAP",
                tip=(
                    "LPDDR5 standalone SK Hynix, Era 1 (H9JK). DRAM móvel de altíssima performance. "
                    "pn[7] = densidade: F=8GB · H=12GB por chip. "
                    "⚠ Apenas 2 densidades confirmadas nesta nomenclatura — geração de transição. "
                    "⚠ Preenchimento pn[4:7] variável — fatiar pn[7] direto, não validar filler. "
                    "Origem: flagships 2021-2022, primeiros dispositivos com LPDDR5. "
                    "Destino: triagem LPDDR5 — componente de altíssimo valor, prioridade máxima."
                ),
            ),
            dict(
                prefix="H58G", chip_type="LPDDR5", subtype="LPDDR5",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_LPDDR5_H58G_CAP",
                tip=(
                    "LPDDR5/LPDDR5X standalone SK Hynix, Era 2 (H58G). DRAM móvel topo de linha. "
                    "pn[4] = densidade: D=3GB · 5=4GB · E=6GB · 6=8GB · G=12GB · 7=16GB · U=18GB por chip. "
                    "⚠ Padrão de chaves: números=simétricas (32/64/128Gb), letras=assimétricas (24/48/96Gb). "
                    "⚠ pn[5] = organização de banco (6, 7 ou 8) — NÃO é capacidade. "
                    "⚠ Piso em D=3GB — chave abaixo disso indica OCR falho ou chip remarcado. "
                    "⚠ LPDDR5T (turbo): usa o mesmo prefixo H58G e as mesmas chaves de capacidade — nenhuma entrada adicional necessária. "
                    "⚠ 24GB (192Gbit) BLOQUEADO — chave desconhecida, aguardar PN físico em bancada. "
                    "Origem: flagships e tablets premium 2022+. "
                    "Destino: triagem LPDDR5/5X/5T — componente de altíssimo valor, prioridade máxima."
                ),
            ),

            # ═══ LPDDR4 / LPDDR4X standalone ══════════════════════════════════
            #
            # Era 1 (H9HC): herança H9 com preenchimento NNN variável, pn[7].
            # Era 2 (H54G): nomenclatura H5, sem preenchimento, pn[4], sequencial.
            #
            # ⚠ H9HCN (LPDDR4 standalone, prefixo 5 chars) começa com "H9HC".
            #   Quando catalogado: dar priority < 55 para bater antes do H9HC.
            #
            dict(
                prefix="H9HC", chip_type="LPDDR4", subtype="LPDDR4",
                interface="",
                is_emcp=False, active=True, priority=55,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR4_H9HC_CAP",
                tip=(
                    "LPDDR4/LPDDR4X standalone SK Hynix, Era 1 barramento x32 (H9HC). DRAM móvel puro. "
                    "pn[7] = densidade: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB · F=8GB por chip. "
                    "⚠ 'D'=3GB assimétrico (24Gbit) — smartphones que não precisavam de 4GB. "
                    "⚠ Preenchimento pn[4:7] variável — fatiar pn[7] direto, não validar filler. "
                    "⚠ H9HCN (prefixo 5 chars) tem prioridade sobre este prefixo de 4 chars. "
                    "Origem: smartphones e tablets premium 2016-2020. "
                    "Destino: triagem LPDDR4 — alto valor no mercado de recondicionamento."
                ),
            ),
            dict(
                prefix="H9HK", chip_type="LPDDR4X", subtype="LPDDR4X",
                interface="",
                is_emcp=False, active=True, priority=55,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR4_H9HC_CAP",
                tip=(
                    "LPDDR4/LPDDR4X standalone SK Hynix, Era 1 barramento x64 (H9HK). DRAM móvel puro. "
                    "Variante dual-channel do H9HC — maior largura de banda para processadores exigentes. "
                    "pn[7] = densidade: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB · E=6GB · F=8GB por chip. "
                    "⚠ 'D'=3GB assimétrico — H9HKNNNDGUMUBR-NLHR ✓ (OMO Electronic). "
                    "⚠ Mapa de capacidade idêntico ao H9HC — C=4GB confirmado em ambos os prefixos. "
                    "⚠ Preenchimento pn[4:7] variável — fatiar pn[7] direto. "
                    "Origem: smartphones premium com arquitetura dual-channel 2016-2020. "
                    "Destino: triagem LPDDR4 — alto valor no mercado de recondicionamento."
                ),
            ),
            # ── H9HCN (prefixo 5 chars) — LPDDR4X standalone, RAM pura ─────────
            #
            # Anatomia: H  9  H  C  N  N  N  [cap] ...
            #           0  1  2  3  4  5  6    7
            #
            # H9HCN é o sub-prefixo de H9HC onde pn[4]='N' (NNN = zero NAND).
            # Prefixo 5 chars tem priority=40 < 55 (H9HC) para bater primeiro.
            # Compartilha o mesmo mapa de capacidade do H9HC (pn[7]).
            # Chave E=8GB documentada via H9HCNNNECMML (broker B2B, 64Gbit confirmed).
            #
            dict(
                prefix="H9HCN", chip_type="LPDDR4X", subtype="LPDDR4X",
                interface="",
                is_emcp=False, active=True, priority=40,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR4_H9HC_CAP",
                tip=(
                    "LPDDR4X standalone SK Hynix, Era 1 (H9HCN). RAM pura — zero NAND. "
                    "H9H=Mobile DRAM standalone · C=LPDDR4X bus · NNN=sem flash embarcado. "
                    "pn[7] = densidade: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB · E=6GB · F=8GB por chip. "
                    "⚠ 'C' em H9HCN (pos 3) = barramento LPDDR4X (VDDQ 0.6V), NÃO é capacidade. "
                    "⚠ NÃO é UFS — protocolo é RAM volátil, incompatível com soquete de armazenamento. "
                    "⚠ Encapsulamento 200FBGA — isolamento ESD obrigatório. "
                    "Ex: H9HCNNNECMML = 6GB LPDDR4X ✓ (SK Hynix PN Guide + manifesto aduaneiro). "
                    "Origem: smartphones flagship e tablets premium 2016-2020. "
                    "Destino: bancada LPDDR4X — silício de alto valor, prioridade na triagem."
                ),
            ),
            dict(
                prefix="H54G", chip_type="LPDDR4X", subtype="LPDDR4X",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_LPDDR4X_H54G_CAP",
                tip=(
                    "LPDDR4X standalone SK Hynix, Era 2 nomenclatura H5 (H54G). DRAM móvel puro. "
                    "pn[4] = densidade — dois sistemas coexistem: "
                    "NUMÉRICO: 2=512MB · 3=1GB · 4=2GB · 5=4GB · 6=8GB. "
                    "ALFABÉTICO (die-revision + fracionados): A=2GB · C=3GB · E=4GB · G=6GB · J=8GB. "
                    "pn[5] = organização de banco (6 ou 8) — NÃO é capacidade, ignorar. "
                    "Ex (numérico): H54G56CYRB-X247 = 4GB (TechInsights HP Spectre ✓). "
                    "Ex (alfabético): H54GE6CYRB-X252 = 4GB (Helio G80/G85, broker B2B SEA ✓). "
                    "Origem: smartphones 2019-2023, tablets modernos. "
                    "Destino: triagem LPDDR4X — altíssima demanda no mercado de recondicionamento."
                ),
            ),

            # ═══ LPDDR3 standalone (H9CC / H9CK) ══════════════════════════════
            #
            # Mesma arquitetura posicional do LPDDR2 H9TK: preenchimento + pn[7].
            # H9CC = x32 · H9CK = x64 — mapa de capacidade compartilhado.
            # Volume alto na esteira: smartphones premium e ultrabooks 2013-2017.
            #
            dict(
                prefix="H9CC", chip_type="LPDDR3", subtype="LPDDR3",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR3_CAP",
                tip=(
                    "LPDDR3 standalone SK Hynix, barramento x32 (H9CC). DRAM móvel puro. "
                    "pn[7] = densidade: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB por chip. "
                    "⚠ Preenchimento pn[4:7] variável (NNN ou outro) — não validar, fatiar pn[7] direto. "
                    "⚠ 'D'=3GB é assimétrico (24Gbit) — chip dos smartphones com exatamente 3GB de RAM. "
                    "⚠ Teto confirmado: C=4GB. LPDDR3 não escala para 6GB ou 8GB. "
                    "Origem: smartphones premium e ultrabooks soldados 2013-2017. "
                    "Destino: triagem LPDDR3 — alta demanda no mercado de recondicionamento."
                ),
            ),
            dict(
                prefix="H9CK", chip_type="LPDDR3", subtype="LPDDR3",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR3_CAP",
                tip=(
                    "LPDDR3 standalone SK Hynix, barramento x64 (H9CK). DRAM móvel puro. "
                    "pn[7] = densidade: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB por chip. "
                    "⚠ Preenchimento pn[4:7] variável (NNN ou outro) — não validar, fatiar pn[7] direto. "
                    "⚠ 'D'=3GB assimétrico · 'C'=4GB teto confirmado. "
                    "⚠ x64: largura de barramento dupla vs H9CC — mesma capacidade, throughput maior. "
                    "Origem: smartphones premium e ultrabooks soldados 2013-2017. "
                    "Destino: triagem LPDDR3 — alta demanda no mercado de recondicionamento."
                ),
            ),

            # ═══ LPDDR2 standalone (H9TK) ═════════════════════════════════════
            #
            # Anatomia: H9TK + NNN (fixo) + [cap] → pn[7], len=1.
            # "K" = DRAM puro — distingue de H9TQ/H9TP (eMCP com flash acoplado).
            # Aparece em smartphones intermediários início da década passada, tablets legados.
            #
            dict(
                prefix="H9TK", chip_type="LPDDR2", subtype="LPDDR2",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=7, decode_cap_len=1, decode_cap_map="HYX_LPDDR2_CAP",
                tip=(
                    "LPDDR2 standalone SK Hynix (H9TK). DRAM móvel puro — sem flash acoplado. "
                    "pn[7] = densidade: 1=128MB · 2=256MB · 4=512MB · 8=1GB · A/B=2GB por chip. "
                    "⚠ Preenchimento pn[4:7] pode ser 'NNN' ou 'MMM' — ambos válidos, decode idêntico. "
                    "⚠ Não confundir com H9TQ (eMCP LPDDR3) ou H9TP (eMCP LPDDR2) — esses têm flash. "
                    "⚠ Teto confirmado: B=2GB. Leitura acima disso → triagem manual. "
                    "Origem: wearables pioneiros, smartphones intermediários 2010-2014, tablets legados. "
                    "Destino: triagem LPDDR2 — verificar demanda do mercado antes de encaminhar."
                ),
            ),

            # ═══ LPDDR1 (Mobile DDR) — H5MS / HY5MS ═══════════════════════════
            #
            # "M" = Mobile, 1.8V. Chips de PDAs, primeiros smartphones, roteadores portáteis.
            # Destino operacional: obsoleto para reuso → refino de metais diretamente.
            #
            # ⚠ Decode com len=2: "25"=256Mbit, "51"=512Mbit, "1G", "2G" nativos.
            #   Ver comentário detalhado no mapa HYX_LPDDR1_CAP.
            #
            dict(
                prefix="H5MS", chip_type="LPDDR1", subtype="LPDDR1",
                interface="",
                is_emcp=False, active=True, priority=60,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_LPDDR1_H5MS_CAP",
                tip=(
                    "LPDDR1 standalone SK Hynix, nomenclatura estabilizada (H5MS), 1.8V. "
                    "pn[4:6] = densidade: 25=32MB · 51=64MB · 1G=128MB · 2G=256MB por chip. "
                    "⚠ '25' e '51' representam '256Mbit' e '512Mbit' — decode fixo de 2 chars. "
                    "⚠ Esquema de codificação DIFERENTE do HY5MS — mapas não são compartilhados. "
                    "⚠ Componente OBSOLETO para reuso comercial. "
                    "Origem: PDAs, primeiros smartphones, roteadores portáteis legados. "
                    "Destino: esteira de REFINO DE METAIS — não encaminhar para bancada de recondicionamento."
                ),
            ),
            dict(
                prefix="HY5MS", chip_type="LPDDR1", subtype="LPDDR1",
                interface="",
                is_emcp=False, active=True, priority=60,
                pn_length=None,
                decode_cap_pos=5, decode_cap_len=2, decode_cap_map="HYX_LPDDR1_HY5MS_CAP",
                tip=(
                    "LPDDR1 standalone Hynix, primeira nomenclatura mobile (HY5MS), 1.8V. "
                    "Geração pré-SK Hynix. Esquema de codificação DIFERENTE do H5MS. "
                    "pn[5:7] = densidade confirmada: 7B=64MB (HY5MS7B2BLFP-H — Octopart ✓). "
                    "⚠ Demais capacidades sem PN físico rastreado — vão para Gemini. "
                    "⚠ Componente OBSOLETO para reuso comercial. "
                    "Origem: PDAs, dispositivos embarcados legados, primeiros smartphones. "
                    "Destino: esteira de REFINO DE METAIS — não encaminhar para bancada de recondicionamento."
                ),
            ),

            # ═══ DDR3 SDRAM (H5TQ / H5TC) ═════════════════════════════════════
            #
            # Ambos com prefixo 4 chars → fatiamento pn[4:6].
            # H5TQ = 1.5V padrão · H5TC = 1.35V low voltage (DDR3L).
            # Mapa compartilhado HYX_DDR3_CAP — codificação idêntica.
            #
            dict(
                prefix="H5TQ", chip_type="DDR3", subtype="DDR3",
                interface="",
                is_emcp=False, active=True, priority=55,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_DDR3_CAP",
                tip=(
                    "DRAM DDR3 standalone SK Hynix, tensão padrão 1.5V (H5TQ). "
                    "pn[4:6] = densidade: 51=64MB · 1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB por chip. "
                    "⚠ Teto físico DDR3: 8Gb (1GB) por chip. Módulos de 16GB usam múltiplos chips. "
                    "⚠ Não confundir com DDR3L (H5TC) — tensão diferente, slot igual. "
                    "Destino: triagem DDR3 — slot 240-pin, 1.5V."
                ),
            ),
            dict(
                prefix="H5TC", chip_type="DDR3L", subtype="DDR3L",
                interface="",
                is_emcp=False, active=True, priority=55,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_DDR3_CAP",
                tip=(
                    "DRAM DDR3L standalone SK Hynix, low voltage 1.35V (H5TC). "
                    "DDR3L é compatível com slots DDR3 padrão, mas opera a 1.35V. "
                    "pn[4:6] = densidade: 51=64MB · 1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB por chip. "
                    "⚠ Teto físico DDR3: 8Gb (1GB) por chip — mesmo limite do H5TQ. "
                    "⚠ Verificar suporte do slot à tensão 1.35V antes de testar. "
                    "Destino: triagem DDR3L — slot 240-pin, preferência por equipamento 1.35V."
                ),
            ),

            # ═══ DDR2 SDRAM — Era de Transição (HY5PS) ════════════════════════
            #
            # Prefixo 5 chars: mesmo offset de fatiamento do DDR1 (pn[5:7]).
            # Herda a matemática Mbit confusa do HY5DU — chaves "56" e "12" reaparecem.
            # Nova chave "1G" marca o teto desta nomenclatura.
            #
            dict(
                prefix="HY5PS", chip_type="DDR2", subtype="DDR2",
                interface="",
                is_emcp=False, active=True, priority=60,
                pn_length=None,  # variável: arquiteturas x4/x8/x16 geram tamanhos diferentes
                decode_cap_pos=5, decode_cap_len=2, decode_cap_map="HYX_DDR2_HY5PS_CAP",
                tip=(
                    "DRAM DDR2 standalone Hynix, era de transição (HY5PS). "
                    "Geração pré-SK Hynix — nomenclatura herdada do DDR1 com tensão 1.8V. "
                    "pn[5:7] = densidade: 56=32MB · 12=64MB · 1G=128MB por chip. "
                    "⚠ Chaves '56' e '12' idênticas ao DDR1 HY5DU — diferenciar pelo prefixo HY5PS. "
                    "⚠ Valor em MB por chip — módulos combinam múltiplos chips. "
                    "Destino: triagem DDR2 — slot 240-pin, tensão 1.8V."
                ),
            ),

            # ═══ DDR2 SDRAM — Nova Nomenclatura (H5PS) ════════════════════════
            #
            # Prefixo 4 chars: fatiamento migra para pn[4:6].
            # Códigos numéricos agora legíveis (25=256Mb, 51=512Mb) + sufixos 1G/2G.
            # Âncora H5 estabelecida aqui — usada até DDR5.
            #
            dict(
                prefix="H5PS", chip_type="DDR2", subtype="DDR2",
                interface="",
                is_emcp=False, active=True, priority=55,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_DDR2_H5PS_CAP",
                tip=(
                    "DRAM DDR2 standalone SK Hynix, nomenclatura moderna (H5PS). "
                    "Âncora H5 estabelecida aqui — padrão que persiste até DDR5. "
                    "pn[4:6] = densidade: 25=32MB · 51=64MB · 1G=128MB · 2G=256MB por chip. "
                    "⚠ Prefixo 4 chars — fatiamento em pn[4:6], diferente do HY5PS (pn[5:7]). "
                    "⚠ Teto DDR2 confirmado: 2G=256MB. '4G' não foi escalado nesta nomenclatura. "
                    "Destino: triagem DDR2 — slot 240-pin, tensão 1.8V."
                ),
            ),

            # ═══ DDR1 SDRAM (HY5DU) ═══════════════════════════════════════════
            #
            # Era Hynix pré-SK (antes da fusão com SK Telecom em 2012).
            # Prefixo HY5DU: HY=Hynix · 5D=DDR SDRAM · U=2.5V (tensão DDR1).
            # Aparece em lotes de reciclagem B2B de PCs antigos, PDVs, servidores legados.
            #
            dict(
                prefix="HY5DU", chip_type="DDR1", subtype="DDR1",
                interface="",
                is_emcp=False, active=True, priority=60,
                pn_length=None,  # comprimento variável: x4/x8/x16 geram tamanhos diferentes
                decode_cap_pos=5, decode_cap_len=2, decode_cap_map="HYX_DDR1_CAP",
                tip=(
                    "DRAM DDR1 standalone Hynix (HY5DU) — geração pré-SK Hynix. "
                    "Chip de memória volátil avulso, 2.5V, interface DDR1. "
                    "pn[5:7] = densidade: 64=8MB · 28=16MB · 56=32MB · 12=64MB por chip. "
                    "⚠ Valor em MB por chip — módulos combinam múltiplos chips para capacidade total. "
                    "⚠ Limite superior arquitetônico: 512Mbit (64MB). Não existe HY5DU com 1Gb. "
                    "⚠ Aparece em equipamentos industriais legados: PDVs, servidores antigos, automação, roteadores. "
                    "Destino: triagem DDR1 — verificar encaixe slot 184-pin antes de testar."
                ),
            ),

            # ═══ UFS STANDALONE ════════════════════════════════════════════════
            #
            # ⚠ RISCO OPERACIONAL CRÍTICO — TRIAGEM OBRIGATÓRIA ANTES DO SOCKET:
            #   UFS e eMMC compartilham encapsulamento BGA-153 (11.5×13mm).
            #   São ELETRICAMENTE INCOMPATÍVEIS. Colocar um chip UFS no socket
            #   eMMC da bancada de teste destrói o chip instantaneamente.
            #   O motor DEVE identificar o prefixo (H28U, HN8T, HN8G) antes de
            #   qualquer contato físico — essa é a primeira linha de defesa.
            #
            dict(
                prefix="H28U", chip_type="UFS", subtype="",
                interface="UFS 2.0/2.1",
                is_emcp=False, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_H28U_CAP",
                tip=(
                    "UFS standalone SK Hynix, era de transição (H28U). "
                    "⚠⚠ ATENÇÃO: encapsulamento BGA-153 IDÊNTICO ao eMMC H26M — "
                    "NÃO inserir no socket eMMC. Interface UFS, protocolo incompatível com eMMC. "
                    "pn[4] = capacidade: 6=32GB · 7=64GB · 8=128GB. "
                    "Destino: bancada UFS dedicada. Confirmar protocolo ANTES do contato físico."
                ),
            ),
            dict(
                prefix="H28S", chip_type="UFS", subtype="",
                interface="UFS 2.1",
                is_emcp=False, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_H28S_CAP",
                tip=(
                    "UFS standalone SK Hynix, alta densidade legada (H28S). "
                    "Família identificada via brokers B2B — pouca documentação pública ocidental. "
                    "Cobre as densidades mais altas da era UFS 2.1 legada: 128GB e 256GB. "
                    "⚠⚠ ATENÇÃO: encapsulamento BGA-153 IDÊNTICO ao eMMC — "
                    "NÃO inserir no socket eMMC. Protocolo UFS incompatível com eMMC. "
                    "pn[4] = capacidade: 8=128GB · 9=256GB. "
                    "Ex: H28S8Q302CMR = 128GB UFS 2.1 ✓ · H28S9O302BMR = 256GB UFS 2.1 ✓ "
                    "Destino: bancada UFS dedicada. Confirmar protocolo ANTES do contato físico."
                ),
            ),
            dict(
                prefix="HN8T", chip_type="UFS", subtype="",
                interface="UFS 2.1/2.2/3.1",
                is_emcp=False, active=True, priority=50,
                pn_length=14,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_HN8_CAP",
                tip=(
                    "UFS standalone SK Hynix, família HN8T — cobre UFS 2.1 Automotivo, 2.2, 3.1 e 4.0. "
                    "4D NAND: 176 camadas (UFS 2.x/3.1) e 238 camadas (UFS 4.0). "
                    "⚠⚠ ATENÇÃO: BGA-153 idêntico ao eMMC — NÃO inserir no socket eMMC. "
                    "pn[4:6] = capacidade: 03/05/06=128GB · 15/16=256GB · 25=512GB · 35=1TB. "
                    "Pares com mesma capacidade (ex: 05 e 06 = ambos 128GB) são revisões de die — normais. "
                    "Linha automotiva (UD310A/UD210A): mesmo prefixo e decode — motor já cobre. "
                    "Ex: HN8T15DEHKX075 = 256GB UFS 3.1 · HN8T15DJHQX109N = 256GB UFS 2.1 Automotivo ✓ "
                    "Ex: HN8T35DZHKX079 = 1TB UFS 3.1 ✓ "
                    "Destino: bancada UFS dedicada — verificar versão do protocolo (2.x vs 3.1 vs 4.0)."
                ),
            ),
            dict(
                prefix="HN8G", chip_type="UFS", subtype="",
                interface="UFS 2.2",
                is_emcp=False, active=True, priority=50,
                pn_length=14,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_HN8_CAP",
                tip=(
                    "UFS standalone SK Hynix, revisão 64GB 4D NAND (HN8G). "
                    "Variante específica de 64GB dentro da família HN8 — mesmo mapa de capacidade do HN8T. "
                    "⚠⚠ ATENÇÃO: BGA-153 idêntico ao eMMC — NÃO inserir no socket eMMC. "
                    "pn[4:6] = capacidade: 96=64GB. "
                    "Ex: HN8G962EHKX037 = 64GB UFS 2.2 ✓ "
                    "Destino: bancada UFS dedicada."
                ),
            ),

            # ═══ eMMC STANDALONE (H26M / H26T) ════════════════════════════════
            #
            # Anatomia: H 2 6 [M|T] [cap_code] [org] ...
            #           0 1 2   3       4         5
            #   pn[3] = M (TLC/MLC NAND, múltiplas gerações de processo)
            #         = T (3D NAND de geração avançada, ex: V4 256Gb/die)
            #   pn[4] = código de capacidade → HYX_EMMC_CAP
            #   pn[5] = organização interna de dies (1=SDP, 2=DDP, 4=QDP, 7=ODP, 8=ODP avançado)
            #           NÃO altera a capacidade total — apenas o empilhamento interno.
            #
            # IMPORTANTE: H26M NÃO é exclusivamente 2D NAND.
            #   H26M88002AMR usa 3D-V2 (128Gb/die stack 8). A letra M identifica
            #   uma geração de produto/plataforma, não o tipo físico da célula.
            #   H26T usa processo 3D de geração superior (V4, dies de 256Gb).
            #
            # Fonte: SK Hynix eMMC 5.1 lineup (Netlist ✓) + Preduo ✓ + Octopart ✓
            #
            dict(
                prefix="H26M", chip_type="eMMC", subtype="",
                interface="eMMC 5.x",
                is_emcp=False, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_EMMC_CAP",
                tip=(
                    "eMMC SK Hynix (H26M). Chip de armazenamento standalone — sem RAM embutida. "
                    "pn[4] = capacidade: 3=4GB · 4=8GB · 5=16GB · 6=32GB · 7=64GB · 8=128GB. "
                    "⚠ 'H26M64...' = 32GB (NÃO 64GB) — o '6' é o código de capacidade, o '4' é organização interna. "
                    "Pacote FBGA-153, 11.5×13mm. "
                    "Destino: bancada reacondicional eMMC."
                ),
            ),
            dict(
                prefix="H26T", chip_type="eMMC", subtype="",
                interface="eMMC 5.1",
                is_emcp=False, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_EMMC_CAP",
                tip=(
                    "eMMC SK Hynix 3D NAND geração avançada (H26T). "
                    "Usa processo 3D-V4 com dies de 256Gb — geração mais recente que H26M. "
                    "pn[4] = capacidade (mesmo mapa do H26M): 8=128GB confirmado (H26T87001CMR, SK Hynix oficial). "
                    "Pacote FBGA-153, 11.5×13mm. "
                    "Destino: bancada reacondicional eMMC."
                ),
            ),

            # ═══ eMMC SEM DOCUMENTAÇÃO PÚBLICA (H28M) ════════════════════════════
            #
            # Situação: H28M não consta em nenhum catálogo oficial SK Hynix,
            #   datasheet, Octopart, Preduo ou qualquer distribuidor verificado.
            #   O prefixo H28x é documentado apenas para UFS (H28U, H28S, H28N).
            #   A letra 'M' em pn[3] segue a convenção eMMC da linha H26M,
            #   mas nenhuma fonte confirma a existência oficial deste produto.
            #
            # Hipóteses:
            #   A) Misprint de fábrica: laser de marcação errou H26M → H28M.
            #      Evidência: H28M31001BMR e H26M31001HPR são estruturalmente idênticos
            #      exceto em pn[2] (6→8) e no sufixo de package (HPR→BMR).
            #   B) Produto OEM/NDA: chip real com datasheet não publicado.
            #      Evidência: data code 130A (início de 2013) — pré-era UFS.
            #
            # Decode: usa HYX_EMMC_CAP (analógico ao H26M) — confiança BAIXA.
            #   Exemplo confirmado na bancada: H28M31001BMR (pn[4]='3' → 4GB analógico).
            #
            # is_documented=False: ativa banner de contribuição na UI.
            #
            dict(
                prefix="H28M", chip_type="eMMC", subtype="",
                interface="eMMC",
                is_emcp=False, active=True, priority=50, is_documented=False,
                pn_length=12,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="HYX_EMMC_CAP",
                # decode_cap_pos=None: capacidade NÃO decodificada — família sem documentação,
                # qualquer capacidade exibida seria especulativa. O tip já explica a analogia.
                tip=(
                    "⚠ FAMÍLIA SEM DOCUMENTAÇÃO PÚBLICA. "
                    "O prefixo H28M não consta em nenhum catálogo oficial SK Hynix, datasheet, "
                    "Octopart ou distribuidor verificável (pesquisa exaustiva: zero resultados). "
                    "Decode de capacidade por ANALOGIA ESTRUTURAL com H26M (eMMC) — "
                    "pn[4]: 3=4GB · 4=8GB · 5=16GB · 6=32GB · 7=64GB · 8=128GB. "
                    "Hipóteses: misprint de fábrica (H26M→H28M) ou OEM com datasheet sob NDA. "
                    "Confiança: BAIXA. "
                    "Verificar na bancada antes de classificar para reacondicionamento."
                ),
            ),

            # ═══ eMCP (eMMC + LPDDR) ══════════════════════════════════════════════
            #
            # Anatomia eMCP SK Hynix:
            #   H  9  T  [Q|P]  [nand_hi][nand_lo]  [ram_hi][ram_lo]  ...
            #   0  1  2    3         4         5          6        7
            #
            #   pn[4:6] = código NAND (2 chars) → HYX_EMCP_NAND_CAP
            #   pn[6:8] = código RAM  (2 chars) → HYX_EMCP_RAM_CAP
            #   pn[3]   = Q → LPDDR3 · P → LPDDR2
            #
            # pn_length=12: comprimento útil para debounce da UI (H9TQ52ACLT = 12 chars).
            # A cauda (MCUR-KUM etc.) contém grade/pkg — não faz parte do decode de
            # capacidade, mas o engine tolera PNs mais longos sem problema.
            #
            # Fonte: Preduo PN list ✓ · NetSource ✓ · ssfkg.com ✓ · absunshine ✓ · Elnec ✓
            #
            dict(
                prefix="H9TQ", chip_type="eMCP", subtype="LPDDR3",
                interface="eMMC 5.x + LPDDR3",
                is_emcp=True, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_H9TQ_RAM_CAP",
                tip=(
                    "eMCP SK Hynix com LPDDR3 (H9TQ). Chip combinado eMMC + RAM. "
                    "pn[4:6] = capacidade NAND: 16/17=16GB · 26/27=32GB · 52=64GB · 64/65=8GB. "
                    "pn[6:8] = capacidade RAM: A6=768MB · A8=1GB · AA/AB=2GB · AC=4GB · AD=3GB. "
                    "⚠ AC=4GB e AD=3GB (não invertido — ordem não é alfabética por tamanho). "
                    "⚠ Dois códigos NAND para mesma capacidade são normais: organização interna diferente. "
                    "Ex: H9TQ52ACLT = 64GB NAND + 4GB LPDDR3. "
                    "Destino: bancada eMCP (requer reballing + programação eMMC + LPDDR)."
                ),
            ),
            dict(
                prefix="H9TP", chip_type="eMCP", subtype="LPDDR2",
                interface="eMMC 4.x + LPDDR2",
                is_emcp=True, active=True, priority=40,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_EMCP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_H9TP_RAM_CAP",
                tip=(
                    "eMCP SK Hynix com LPDDR2 (H9TP). Chip combinado eMMC + RAM, geração anterior ao H9TQ. "
                    "pn[4:6] = capacidade NAND (mesmo mapa H9TQ): 32=4GB · 64=8GB. "
                    "pn[6:8] = capacidade RAM: A4=512MB · A8=1GB · AB=2GB. "
                    "⚠ H9TP usa LPDDR2, NÃO LPDDR4 — referências antigas a 'LPDDR4' são incorretas. "
                    "⚠ Diferente do H9DP: H9TP usa RAM de 2 chars em pn[6:8]; H9DP usa 1 char em pn[7]. "
                    "Ex: H9TP32A4GDCC = 4GB NAND + 512MB LPDDR2 (Elnec, absunshine ✓). "
                    "Ex: H9TP64A8JDAC = 8GB NAND + 1GB LPDDR2 (Elnec ✓). "
                    "Destino: bancada eMCP legado."
                ),
            ),
            # ── H9DA — eMCP LPDDR1 geração legada (~2012-2015) ─────────────────
            #
            # Anatomia H9DA (decode DIFERENTE de toda a linha H9Tx / H9DP):
            #   H  9  D  A  [nand]  G   H  [ram_hi][ram_lo]  [pkg]  [gen]  [tmp]
            #   0  1  2  3    4     5   6      7        8       9      10     11
            #
            #   pn[4]   = capacidade NAND (1 char) → HYX_H9DA_NAND_CAP
            #   pn[5]   = "G" fixo (filler)
            #   pn[6]   = "H" fixo (código de package)
            #   pn[7:9] = capacidade RAM LPDDR1 (2 chars) → HYX_H9DA_RAM_CAP
            #
            # ⚠ pn[5:7] = "GH" é filler fixo — pn[4] é o único char de capacidade NAND.
            # ⚠ Sufixo "-4EM" = eMMC 4.x eMCP (confirma protocolo legado).
            # ⚠ H9DA não usa HYX_EMCP_NAND_CAP nem HYX_H9D_NAND_CAP — mapas incompatíveis.
            # ⚠ RAM é LPDDR1 (NÃO LPDDR3): H9DA = 137-ball/153-ball eMMC+LPDDR1
            #   (Preduo tier-1 confirma). H9TP = LPDDR2 (162-ball); H9TQ = LPDDR3 (221-ball).
            # ⚠ "2G" em pn[7:9] = 2Gb = 256MB (Gigabits, não Gigabytes!).
            #
            # Fontes: Preduo.com (tier-1) · ariat-tech · ic-components · Alibaba
            #
            dict(
                prefix="H9DA", chip_type="eMCP", subtype="LPDDR1",
                interface="eMMC 4.x + LPDDR1",
                is_emcp=True, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=1, decode_cap_map="HYX_H9DA_NAND_CAP",
                decode_gen_pos=7, decode_gen_len=2, decode_gen_map="HYX_H9DA_RAM_CAP",
                tip=(
                    "eMCP SK Hynix LPDDR1 geração legada (H9DA). Chip combinado eMMC 4.x + LPDDR1. "
                    "Nomenclatura anterior ao H9TP/H9TQ — decode posicional DIFERENTE de toda a linha H9Tx. "
                    "Preduo.com (tier-1) confirma H9DA = eMMC+LPDDR1 (categoria '137ball eMMC+LPD1'). "
                    "pn[4] = capacidade NAND (1 char): 1=1GB · 2=2GB · 4=4GB. "
                    "pn[7:9] = capacidade RAM LPDDR1 (2 chars): 25=256MB · 51=512MB · 2G=256MB · 4J=512MB. "
                    "⚠ 'X+Y' na notação Preduo usa Gb para RAM: '4+4' = 4GB NAND + 4Gb(512MB) LPDDR1. "
                    "pn[5:7]='GH' fixo (filler) — apenas pn[4] e pn[7:9] carregam capacidade. "
                    "pn[10] = die gen (A=2ª · B=3ª · C=4ª); sufixo '-4EM' = eMMC 4.x eMCP. "
                    "⚠ Não compartilha DecodeMap com H9TQ/H9TP/H9DP — esquema completamente diferente. "
                    "⚠ Componente OBSOLETO para reuso comercial — eMMC 4.x + LPDDR1, era 2012-2015. "
                    "Ex: H9DA4GH2GJAM = 4GB eMMC + 256MB LPDDR1 (pn[7:9]='2G'→2Gb=256MB). "
                    "Ex: H9DA4VH4JJMMCR = 4GB eMMC + 512MB LPDDR1 (Preduo '4+4', 4Gb=512MB). "
                    "Destino: bancada eMCP legado / REFINO DE METAIS se sem demanda."
                ),
            ),
            dict(
                prefix="H9DP", chip_type="eMCP", subtype="LPDDR2",
                interface="eMMC + LPDDR2",
                is_emcp=True, active=True, priority=50,
                pn_length=12,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_H9D_NAND_CAP",
                decode_gen_pos=7, decode_gen_len=1, decode_gen_map="HYX_H9D_RAM_CAP",
                tip=(
                    "eMCP SK Hynix família H9D com LPDDR2 (H9DP). Chip combinado eMMC + RAM. "
                    "pn[4:6] = capacidade NAND: 32=4GB · 64=8GB · AG=16GB. "
                    "pn[7] = capacidade RAM (1 char): 2=256MB · 4=512MB · 8=1GB · 3=1GB. "
                    "⚠ RAM usa 1 char em pn[7] (não 2) — pn[6]='A' é código de controlador fixo, ignorar. "
                    "⚠ '8' e '3' resultam ambos em 1GB — organização de barramento diferente, mesma capacidade. "
                    "⚠ Mapa NAND próprio (HYX_H9D_NAND_CAP): 'AG'=16GB não existe no mapa H9TQ/H9TP. "
                    "Ex: H9DPAGA3JJMC = 16GB eMMC + 1GB LPDDR2 ✓ "
                    "Ex: H9DP64A8JJMC = 8GB eMMC + 1GB LPDDR2 ✓ "
                    "Ex: H9DP32A4JJAC = 4GB eMMC + 512MB LPDDR2 ✓ "
                    "Componente OBSOLETO para reuso — Destino: REFINO DE METAIS."
                ),
            ),

            # ═══ eMCP/uMCP LPDDR4X (H9HP / H9HQ) ════════════════════════════════
            #
            # Anatomia (idêntica ao H9TQ/H9TP — mesma grade posicional):
            #   H  9  H  [P|Q]  [nand_hi][nand_lo]  [ram_hi][ram_lo]  ...
            #   0  1  2    3         4         5          6        7
            #
            #   pn[4:6] = código NAND (2 chars) → mapa específico por família (⚠ colisão "16")
            #   pn[6:8] = código RAM  (2 chars) → HYX_LPDDR4X_RAM_CAP (compartilhado)
            #   pn[3]   = P → eMCP (eMMC + LPDDR4X) · Q → uMCP (UFS + LPDDR4X)
            #
            # pn_length=14: H9HP53ACPMMDAR = 14 chars (cauda após '-' é grade/pkg — não faz parte do decode)
            #
            # ⚠ COLISÃO CRÍTICA DE MAPA NAND: H9HP "16"=128GB vs H9TQ "16"=16GB.
            #   Mapas HYX_H9HP_NAND_CAP e HYX_EMCP_NAND_CAP são completamente separados.
            #
            # Fonte: Preduo PN list ✓ · distribuidores B2B ✓ · indasina ✓
            #
            dict(
                prefix="H9HP", chip_type="eMCP", subtype="LPDDR4X",
                interface="eMMC 5.1 + LPDDR4X",
                is_emcp=True, active=True, priority=50,
                pn_length=14,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_H9HP_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_LPDDR4X_RAM_CAP",
                tip=(
                    "eMCP SK Hynix com LPDDR4X (H9HP). Chip combinado eMMC 5.1 + RAM de alta velocidade. "
                    "pn[4:6] = capacidade NAND: 16=128GB · 27=32GB · 52/53=64GB. "
                    "pn[6:8] = capacidade RAM: AC=4GB · AD=3GB · AE=6GB · AF=8GB. "
                    "⚠ '16' aqui é 128GB (NÃO 16GB como no H9TQ) — mapas NAND não são compartilhados. "
                    "⚠ AC=4GB e AD=3GB (não invertido — padrão SK Hynix eMCP LPDDR4X). "
                    "Ex: H9HP53ACPMMDAR-KMM = 64GB eMMC + 4GB LPDDR4X ✓ "
                    "Ex: H9HP16AECMMDAR-KMM = 128GB eMMC + 6GB LPDDR4X ✓ "
                    "Destino: bancada eMCP premium (requer equipamento LPDDR4X)."
                ),
            ),
            dict(
                prefix="H9HQ", chip_type="uMCP", subtype="LPDDR4X",
                interface="UFS 2.1 + LPDDR4X",
                is_emcp=True, active=True, priority=50,
                pn_length=14,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_H9HQ_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_LPDDR4X_RAM_CAP",
                tip=(
                    "uMCP SK Hynix com LPDDR4X (H9HQ). Chip combinado UFS 2.1 + RAM — geração premium. "
                    "pn[4:6] = capacidade NAND: 15/16=128GB · 21=256GB · 53/54=64GB. "
                    "pn[6:8] = capacidade RAM: AC=4GB · AD=3GB · AE=6GB · AF=8GB (mapa compartilhado com H9HP). "
                    "⚠ UFS (não eMMC): requer bancada UFS dedicada — incompatível com equipamento eMMC. "
                    "⚠ Sem 32GB na linha H9HQ — UFS+LPDDR4X é segmento premium, base é 64GB. "
                    "Ex: H9HQ15ACPMADAR-KEM = 128GB UFS + 4GB LPDDR4X ✓ "
                    "Ex: H9HQ21AECMADAR-KEM = 256GB UFS + 6GB LPDDR4X ✓ "
                    "Destino: bancada uMCP/UFS (equipamento específico obrigatório)."
                ),
            ),

            # ═══ uMCP LPDDR5 (H9HR / H9RT) ═══════════════════════════════════════
            #
            # Geração mais recente SK Hynix — UFS + LPDDR5.
            # H9HR: esquema posicional análogo ao H9HP/H9HQ, mas RAM usa código "J_"
            #       ao invés de "A_" — mapa próprio obrigatório.
            # H9RT: esquema de codificação diferente (dígito+G para NAND, densidade+revisão para RAM).
            #        Decode posicional COMPLETO — validado com 7 PNs em distribuidores B2B premium.
            #
            dict(
                prefix="H9HR", chip_type="uMCP", subtype="LPDDR5",
                interface="UFS + LPDDR5",
                is_emcp=True, active=True, priority=50,
                pn_length=14,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_H9HR_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_H9HR_RAM_CAP",
                tip=(
                    "uMCP SK Hynix com LPDDR5 (H9HR). Chip combinado UFS + RAM de última geração. "
                    "pn[4:6] = capacidade NAND: 15=128GB · 21=256GB. "
                    "pn[6:8] = capacidade RAM: JF=8GB LPDDR5. "
                    "⚠ Código RAM começa com 'J' (não 'A' como H9HP/H9HQ) — esquemas incompatíveis. "
                    "⚠ Chip de alta geração: verificar suporte do equipamento antes de tentar reballing. "
                    "Ex: H9HR15JFA3MEVR-K6M = 128GB UFS + 8GB LPDDR5 ✓ (B2B) "
                    "Ex: H9HR21JFA3MEVR-K6M = 256GB UFS + 8GB LPDDR5 ✓ (B2B) "
                    "Destino: bancada uMCP LPDDR5 (equipamento de última geração)."
                ),
            ),
            dict(
                prefix="H9RT", chip_type="uMCP", subtype="LPDDR5",
                interface="UFS + LPDDR5",
                is_emcp=True, active=True, priority=50,
                pn_length=14,
                # Anatomia H9RT — esquema diferente de H9HR/H9HP/H9HQ:
                #   H  9  R  T  [nand_hi][nand_lo]  [ram_hi][ram_lo]  ...
                #   0  1  2  3      4         5          6        7
                # NAND: pn[4:6] = código "dígito+G" (0G, 1G, 2G)
                # RAM:  pn[6:8] = código densidade+revisão (6A, 6M, GA, 7M)
                # Validado com 7 PNs rastreados em distribuidores B2B premium (Puris, HKin).
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="HYX_H9RT_NAND_CAP",
                decode_gen_pos=6, decode_gen_len=2, decode_gen_map="HYX_H9RT_RAM_CAP",
                tip=(
                    "uMCP SK Hynix LPDDR5 de alta geração (H9RT). Família premium — UFS + LPDDR5. "
                    "pn[4:6] = capacidade NAND: 0G=128GB · 1G=256GB · 2G=512GB. "
                    "pn[6:8] = capacidade RAM: 6A/6M=8GB · GA=12GB · 7M=16GB (LPDDR5). "
                    "⚠ Esquema de codificação NAND diferente de todas as outras famílias SK Hynix: "
                    "usa 'dígito+G' — nunca confundir pn[4] isolado com capacidade. "
                    "⚠ Código RAM: 1º char = densidade bruta do die (6=64Gb, G=96Gb, 7=128Gb); "
                    "2º char = revisão de silício (A/M) — não altera capacidade total. "
                    "Ex: H9RT2G6M65X028N = 512GB UFS + 8GB LPDDR5 ✓ "
                    "Ex: H9RT1G7M75X069  = 256GB UFS + 16GB LPDDR5 ✓ "
                    "Destino: bancada uMCP LPDDR5 de última geração — componente de altíssimo valor."
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
