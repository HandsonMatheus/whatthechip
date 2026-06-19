"""
Adiciona/atualiza um Part Number confirmado no banco de dados.
Uso (na pasta do projeto, com o venv ativado):

    python add_confirmed_part.py

Pode ser rodado quantas vezes quiser — usa update_or_create (idempotente).
"""
import os, sys, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from chips.models import Brand, ChipFamily, KnownPart

PARTS = [
    dict(
        part_number = "HN8T05BZGR",
        brand_name  = "SK Hynix",
        family_prefix = "HN8T",
        chip_type   = "UFS",
        subtype     = "UFS standalone 4D NAND",
        capacity    = "128GB",
        interface   = "UFS 2.1/2.2/3.1",
        confidence  = "confirmed",
        notes       = "Confirmado manualmente pelo operador. pn[4:6]=05 → 128GB.",
    ),
    dict(
        part_number   = "H54GE6CYRB",
        brand_name    = "SK Hynix",
        family_prefix = "H54G",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "4GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='E' → escala alfabética SK Hynix = 32Gbit ÷ 8 = 4GB. "
            "Sufixo -X252. Plataforma MediaTek Helio G80/G85 (Unisoc T606 também reportado). "
            "Fonte: broker B2B sudeste asiático, equivalência de lote com H54G56CYRB."
        ),
    ),
    dict(
        part_number   = "H28U88301AMR",
        brand_name    = "SK Hynix",
        family_prefix = "H28U",
        chip_type     = "UFS",
        subtype       = "UFS standalone legado",
        capacity      = "128GB",
        interface     = "UFS 2.0/2.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='8' → 128GB. Era de transição H28U (UFS 2.0/2.1). "
            "BGA-153 idêntico ao eMMC H26M — verificar protocolo antes do contato físico."
        ),
    ),
    dict(
        part_number   = "K3UH6M6",
        brand_name    = "Samsung",
        family_prefix = "K3U",
        chip_type     = "LPDDR4X",
        subtype       = "LPDDR4X Multi-Channel",
        capacity      = "4GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[3]='H' → 32Gb por die = 4GB. Samsung LPDDR4X Multi-Channel. "
            "Tensão I/O 0.6V — não confundir com K4F (LPDDR4, 1.1V)."
        ),
    ),
    dict(
        part_number   = "H9HCNNNECMML",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "6GB",
        interface     = "LPDDR4X",
        confidence    = "manual",
        notes         = (
            "Confirmado pelo operador via manifesto aduaneiro ('LPDDR4X 6G BGA200'). "
            "⚠ DIVERGÊNCIA: pesquisa tier-1 (Glochip página oficial SK Hynix, 2021) indica que "
            "a família H9HCNNN 200-ball NÃO possui código de densidade 'E' (6GB). "
            "6GB (48Gbit) existe apenas na família H9HKNNN (376/556-ball, pacote maior). "
            "Possível confusão de família no manifesto. Pendente verificação física / datasheet. "
            "Mantido como manual até confirmação. RAM pura (zero NAND). FBGA-200."
        ),
    ),
    dict(
        part_number   = "H26M74002HMR",
        brand_name    = "SK Hynix",
        family_prefix = "H26M",
        chip_type     = "eMMC",
        subtype       = "eMMC standalone",
        capacity      = "64GB",
        interface     = "eMMC 5.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart: '64GB EMMC5.1 EG510'. "
            "pn[4]='7' → 64GB. FBGA-153. "
            "Fonte: octopart.com/part/hynix/H26M74002HMR."
        ),
    ),
    dict(
        part_number   = "H9HCNNNCPMML",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "4GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[7]='C' → 32Gbit ÷ 8 = 4GB. "
            "Fonte interna: H9HCNNNCPMMLHR-NME ✓ (duas referências independentes no mapa H9HC). "
            "Octopart lista variante -XR-NEE com '4GBIT Par 78FBGA' — dados incorretos: "
            "confusão Gbit/GB (4GB ≠ 4Gbit) e encapsulamento errado (200FBGA, não 78FBGA). "
            "RAM pura, zero NAND. 200FBGA."
        ),
    ),
    dict(
        part_number   = "H28U64222MMR",
        brand_name    = "SK Hynix",
        family_prefix = "H28U",
        chip_type     = "UFS",
        subtype       = "UFS standalone legado",
        capacity      = "32GB",
        interface     = "UFS 2.0/2.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='6' → 256Gbit ÷ 8 = 32GB. Era de transição H28U. "
            "BGA-153 idêntico ao eMMC H26M — verificar protocolo antes do contato físico. "
            "Fonte do mapa: H28U62301AMR B2B ✓ (mesma chave '6'=32GB)."
        ),
    ),
    dict(
        part_number   = "H9TQ32A6BTMC",
        brand_name    = "SK Hynix",
        family_prefix = "H9TQ",
        chip_type     = "eMCP",
        subtype       = "eMCP LPDDR3",
        capacity      = "4GB + 768MB",
        interface     = "eMMC 5.x + LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4:6]='32' → 4GB eMMC (HYX_EMCP_NAND_CAP ✓ — '32'=4GB). "
            "pn[6:8]='A6' → LPDDR3 768MB (HYX_H9TQ_RAM_CAP ✓ — A6=6Gbit÷8=768MB). "
            "PN físico em estoque, referência documentada em populate_hynix.py. "
            "Dispositivo de origem: Samsung Galaxy J1 Ace SM-J110F / SM-J110G "
            "(4G LTE global/africana — 768MB RAM + 4GB storage — GSMArena ✓). "
            "⚠ Fragmentação severa: SM-J110H/L=512MB; SM-J110M/J111F=1GB por região e conectividade."
        ),
    ),
    dict(
        part_number   = "H26M31001HPR",
        brand_name    = "SK Hynix",
        family_prefix = "H26M",
        chip_type     = "eMMC",
        subtype       = "eMMC standalone",
        capacity      = "4GB",
        interface     = "eMMC 4.5",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='3' → 4GB (HYX_EMMC_CAP ✓ — 32Gbit÷8=4GB). "
            "Preduo: '4GB / eMMC4.5 / 1ynm 32Gb' ✓ · Octopart ✓ · eBay: '4GB eMMC FBGA153' ✓. "
            "FBGA-153. Processo planar 1ynm."
        ),
    ),
    dict(
        part_number   = "H9TKNNN8JDAP",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "1GB",
        interface     = "LPDDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[7]='8' → 1GB (HYX_LPDDR2_CAP ✓ — 8Gbit÷8=1GB). "
            "Variante sem sufixo -LR do PN de referência H9TKNNN8JDAPLR ✓. "
            "DRAM puro — zero NAND. pn[4:7]='NNN' (preenchimento fixo padrão)."
        ),
    ),
    dict(
        part_number   = "H9DP32A4JJBC",
        brand_name    = "SK Hynix",
        family_prefix = "H9DP",
        chip_type     = "eMCP",
        subtype       = "eMCP LPDDR2",
        capacity      = "4GB + 512MB",
        interface     = "eMMC + LPDDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4:6]='32' → 4GB eMMC (HYX_H9D_NAND_CAP ✓ — 32Gbit÷8=4GB). "
            "pn[6]='A' → código de controlador fixo (não é capacidade). "
            "pn[7]='4' → LPDDR2 512MB (HYX_H9D_RAM_CAP ✓ — 4Gbit÷8=512MB). "
            "Variante de revisão (pos[10]='B') dos PNs de referência H9DP32A4JJAC ✓ / H9DP32A4JJMC ✓."
        ),
    ),
    dict(
        part_number   = "H26M78103CCR",
        brand_name    = "SK Hynix",
        family_prefix = "H26M",
        chip_type     = "eMMC",
        subtype       = "eMMC standalone Automotive",
        capacity      = "64GB",
        interface     = "eMMC 5.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='7' → 64GB (HYX_EMMC_CAP ✓ — referência direta na tabela). "
            "Preduo: '64GB ODP' ✓ (ODP = Octal Die Package). Variante Automotive. "
            "FBGA-153."
        ),
    ),
    dict(
        part_number   = "H26T87001CMR",
        brand_name    = "SK Hynix",
        family_prefix = "H26T",
        chip_type     = "eMMC",
        subtype       = "eMMC standalone 3D NAND",
        capacity      = "128GB",
        interface     = "eMMC 5.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart: '128GB EMMC5.1 EF510 3D-V4 FBGA153'. "
            "pn[4]='8' → 128GB. Processo 3D-V4, dies 256Gb. FBGA-153 11.5×13mm. "
            "⚠ Entrada digitada no estoque como H26T87001CMB (typo B→R) — PN correto: H26T87001CMR. "
            "Fonte: octopart.com/part/hynix/H26T87001CMR."
        ),
    ),
    dict(
        part_number   = "H9HP16AECMMD",
        brand_name    = "SK Hynix",
        family_prefix = "H9HP",
        chip_type     = "eMCP",
        subtype       = "eMCP LPDDR4X",
        capacity      = "128GB + 6GB",
        interface     = "eMMC 5.1 + LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4:6]='16' → 128GB eMMC (HYX_H9HP_NAND_CAP ✓ — ⚠ '16'=128GB nesta família, NÃO 16GB). "
            "pn[6:8]='AE' → LPDDR4X 6GB (HYX_LPDDR4X_RAM_CAP ✓ — AE=48Gbit÷8=6GB). "
            "BUG-7 corrigido no engine: emcp_nand exibia 'eMMC 5.1 + LPDDR4X 128GB' (LPDDR vazava); "
            "emcp_ram exibia 'LPDDR4X 6GB ⚠ cap. não mapeada' (falso aviso). "
            "Chip de alto valor: eMCP premium LPDDR4X — bancada equipamento dedicado."
        ),
    ),
    dict(
        part_number   = "H26M64103EMR",
        brand_name    = "SK Hynix",
        family_prefix = "H26M",
        chip_type     = "eMMC",
        subtype       = "eMMC standalone",
        capacity      = "32GB",
        interface     = "eMMC 5.1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4]='6' → 32GB (HYX_EMMC_CAP ✓ — referência direta na tabela). "
            "Octopart ✓ · datasheets.com: '256G-bit (32GB)' ✓ (256Gbit÷8=32GB). "
            "⚠ H26M64 = 32GB, NÃO 64GB — '6' é capacidade, '4' é organização interna (QDP). "
            "FBGA-153."
        ),
    ),
    dict(
        part_number   = "H9TQ17ABJTCC",
        brand_name    = "SK Hynix",
        family_prefix = "H9TQ",
        chip_type     = "eMCP",
        subtype       = "eMCP LPDDR3",
        capacity      = "16GB + 2GB",
        interface     = "eMMC 5.x + LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[4:6]='17' → 16GB eMMC (HYX_EMCP_NAND_CAP ✓). "
            "pn[6:8]='AB' → LPDDR3 2GB (HYX_H9TQ_RAM_CAP ✓). "
            "Variante de sufixo (BTCC) do PN de referência H9TQ17ABJTMCUR — Preduo: '16GB+2GB' ✓. "
            "Decode em pn[0:8] idêntico."
        ),
    ),
    # ──────────────────────────────────────────────────────────────────────────
    # DDR3 SDRAM — H5TQ (1.5V)
    # Decode: pn[4:6] → HYX_DDR3_CAP  |  1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5TQ2G63GFR-RDC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via LCSC C390897 ✓ e PS4 Developer Wiki (usado na PS4 fat). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). G-die (7ª geração). "
            "DDR3-1866 (1866 MT/s, CL13), x16, FBGA-96. "
            "Chip standalone — slot DDR3 240-pin, tensão 1.5V."
        ),
    ),
    dict(
        part_number   = "H5TQ4G63EFR-RDC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via LCSC C2803259 ✓ (datasheet SK Hynix H5TQ4G63EFR Rev1.2 Set/2016). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). E-die (5ª geração). "
            "DDR3-1866 (1866 MT/s, CL13), x16, FBGA-96. "
            "Chip standalone — slot DDR3 240-pin, tensão 1.5V."
        ),
    ),
    dict(
        part_number   = "H5TQ4G63EFR-TEC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via LCSC C2927628 ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). E-die (5ª geração). "
            "DDR3-2133 (2133 MT/s, CL14), x16, FBGA-96. Teto de velocidade do E-die. "
            "Chip standalone — slot DDR3 240-pin, tensão 1.5V."
        ),
    ),
    dict(
        part_number   = "H5TQ4G83EFR-RDC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via LCSC C2841156 ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). E-die, organização x8. "
            "DDR3-1866 (1866 MT/s, CL13), x8, FBGA-78. "
            "⚠ x8 = FBGA-78 (78 bolas) — diferente do x16 FBGA-96."
        ),
    ),
    dict(
        part_number   = "H5TQ4G63AFR-PBC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via datasheet PDF SK Hynix H5TQ4G63AFR (via NXP community) ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). A-die (1ª geração 4Gb). "
            "DDR3-1600 (1600 MT/s, CL11), x16, FBGA-96. "
            "Chip standalone — slot DDR3 240-pin, tensão 1.5V."
        ),
    ),
    dict(
        part_number   = "H5TQ2G83BFR-H9C",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart ✓. "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). B-die, organização x8. "
            "DDR3-1333 (1333 MT/s, CL9), x8, FBGA-78. "
            "⚠ x8 = FBGA-78 — chip de 256MB por die individual."
        ),
    ),
    dict(
        part_number   = "H5TQ4G83MFR-H9C",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). M-die (1ª geração 4Gb). "
            "DDR3-1333 (1333 MT/s, CL9), x8, FBGA-78. "
            "Chip standalone — slot DDR3 240-pin, tensão 1.5V."
        ),
    ),
    dict(
        part_number   = "H5TQ8G63AMR-H9C",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "1GB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). DDP (Dual Die Package — dois dies 4Gb empilhados). "
            "Sufixo AMR (não FR) indica encapsulamento DDP. DDR3-1333, x8, FBGA-96. "
            "⚠ DDP: 1GB por encapsulamento, equivale a dois chips de 512MB."
        ),
    ),
    dict(
        part_number   = "H5TQ1G83EFR-PBC",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "128MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Datasheets360 ✓. "
            "pn[4:6]='1G' → 128MB (1Gbit÷8). E-die, organização x8. "
            "DDR3-1600 (1600 MT/s, CL11), x8, FBGA-78. "
            "Chip de baixa densidade — comum em equipamentos embarcados e tablets simples."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR3L SDRAM — H5TC (1.35V low voltage)
    # Decode: pn[4:6] → HYX_DDR3_CAP  |  mesmo mapa do H5TQ
    # ⚠ Tensão diferente (1.35V vs 1.5V) — slot DDR3 igual (240-pin), compatível
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5TC4G83CFR-PBA",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via datasheet oficial SK Hynix H5TC4G8(6)3CFR Rev0.2 Jul/2014 "
            "(mirror NXP community) ✓ · Octopart ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). C-die, organização x8. "
            "DDR3L 1.35V (DDR3-1600, CL11), x8, FBGA-78. "
            "⚠ Slot DDR3 compatível, mas tensão 1.35V — verificar suporte da placa."
        ),
    ),
    dict(
        part_number   = "H5TC4G63CFR-PBA",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart ✓ · datasheet SK Hynix H5TC4G8(6)3CFR Rev0.2 ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). C-die, organização x16. "
            "DDR3L 1.35V (DDR3-1600, CL11), x16, FBGA-96. "
            "⚠ x16 = FBGA-96 (96 bolas) — diferente do x8 FBGA-78."
        ),
    ),
    dict(
        part_number   = "H5TC4G63CFR-RDA",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). C-die, organização x16. "
            "DDR3L 1.35V (DDR3-1866, CL13), x16, FBGA-96. Sufixo -RDA = 1866 MT/s comercial."
        ),
    ),
    dict(
        part_number   = "H5TC4G83BFR-PBA",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). B-die, organização x8. "
            "DDR3L 1.35V (DDR3-1600, CL11), x8, FBGA-78."
        ),
    ),
    dict(
        part_number   = "H5TC8G83AMR-PBA",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "1GB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Win Source · Alldatasheet ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). DDP, AMR suffix. DDR3L 1.35V, x8, FBGA-78. "
            "⚠ DDP: 1GB por encapsulamento. "
            "⚠ Tensão 1.35V — verificar suporte da placa antes de testar."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR4 SDRAM — H5AN (1.2V)
    # Decode: pn[4:6] → HYX_DDR4_CAP  |  4G=512MB · 8G=1GB · AG=2GB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5AN8G8NAFR-VKC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet (datasheet PDF SK Hynix) ✓ · Avaq ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die (Era 1, 20nm), organização x8. "
            "DDR4-2666 (2666 MT/s, CL19), x8, FBGA-78. Slot DDR4, tensão 1.2V."
        ),
    ),
    dict(
        part_number   = "H5AN8G8NAFR-UHC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die (Era 1), organização x8. "
            "DDR4-2400 (2400 MT/s, CL17), x8, FBGA-78. Tensão 1.2V."
        ),
    ),
    dict(
        part_number   = "H5AN8G6NAFR-UHC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via LCSC ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die (Era 1), organização x16. "
            "DDR4-2400, x16, FBGA-96. Tensão 1.2V. "
            "⚠ x16 = FBGA-96 — diferente do x8 FBGA-78."
        ),
    ),
    dict(
        part_number   = "H5AN4G8NBJR-VKC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "512MB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via catálogo oficial SK Hynix DDR4 (DigiKey PDF Fev/2021) ✓ · Avaq ✓. "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). B-die (Era 1, 2ª geração), organização x8. "
            "DDR4-2666, x8, FBGA-78. Tensão 1.2V."
        ),
    ),
    dict(
        part_number   = "H5AN8G8NCJR-VKC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via JLCPCB/LCSC C2803261 ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). C-die (Era 1, 3ª geração 10nm), organização x8. "
            "DDR4-2666, x8, FBGA-78. Tensão 1.2V."
        ),
    ),
    dict(
        part_number   = "H5AN8G8NDJR-VKC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via catálogo oficial SK Hynix DDR4 (DigiKey PDF Fev/2021) ✓. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). D-die (Era 1, 4ª geração), organização x8. "
            "DDR4-2666, x8, FBGA-78. Tensão 1.2V."
        ),
    ),
    dict(
        part_number   = "H5ANAG6NCJR-VKC",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "2GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via catálogo oficial SK Hynix DDR4 (DigiKey PDF Fev/2021) ✓. "
            "pn[4:6]='AG' → 2GB (16Gbit÷8). C-die, organização x16. "
            "DDR4-2666, x16, FBGA-96. Tensão 1.2V. "
            "⚠ 'AG' = 16Gbit — não confundir com 16GB (são 2GB por chip)."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR2 SDRAM — HY5PS (nomenclatura pré-SK Hynix, 1.8V)
    # Decode: pn[5:7] → HYX_DDR2_HY5PS_CAP  |  56=32MB · 12=64MB · 1G=128MB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "HY5PS121621CFP-25",
        brand_name    = "SK Hynix",
        family_prefix = "HY5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "64MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Octopart ✓ 'DRAM Chip DDR2 512M-Bit 32Mx16 1.8V 84-Pin FBGA'. "
            "pn[5:7]='12' → 64MB (512Mbit÷8). Organização x16 (32M×16), FBGA-84. "
            "DDR2-400 (400 MT/s), tensão 1.8V. "
            "⚠ Nomenclatura HY5 = era pré-SK Hynix (anterior à fusão com SK Telecom em 2012)."
        ),
    ),
    dict(
        part_number   = "HY5PS1G831CFP-Y5",
        brand_name    = "SK Hynix",
        family_prefix = "HY5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "128MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓ · Octopart ✓. "
            "pn[5:7]='1G' → 128MB (1Gbit÷8). Organização x8, FBGA-60. "
            "DDR2-667 (667 MT/s), tensão 1.8V. "
            "⚠ Teto de densidade desta nomenclatura — 2Gbit não chegou ao HY5PS."
        ),
    ),
    dict(
        part_number   = "HY5PS1G831CFP-S5",
        brand_name    = "SK Hynix",
        family_prefix = "HY5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "128MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. "
            "pn[5:7]='1G' → 128MB (1Gbit÷8). Organização x8, FBGA-60. "
            "DDR2-800 (800 MT/s), tensão 1.8V. Sufixo -S5 = DDR2-800 bin."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR2 SDRAM — H5PS (nova nomenclatura SK Hynix, 1.8V)
    # Decode: pn[4:6] → HYX_DDR2_H5PS_CAP  |  25=32MB · 51=64MB · 1G=128MB · 2G=256MB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5PS1G83EFR-S6C",
        brand_name    = "SK Hynix",
        family_prefix = "H5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "128MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Farnell UK ✓ 'DRAM DDR2 1Gbit 128Mx8 400MHz FBGA 60 Pins'. "
            "pn[4:6]='1G' → 128MB (1Gbit÷8). E-die, organização x8, FBGA-60. "
            "DDR2-800 (800 MT/s, 400 MHz clock), tensão 1.8V. "
            "Âncora H5 — nomenclatura moderna iniciada nesta série."
        ),
    ),
    dict(
        part_number   = "H5PS1G63EFR-S6C",
        brand_name    = "SK Hynix",
        family_prefix = "H5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "128MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Farnell UK ✓ 'DRAM DDR2 1Gbit 64Mx16 400MHz FBGA 84 Pins'. "
            "pn[4:6]='1G' → 128MB (1Gbit÷8). E-die, organização x16, FBGA-84. "
            "DDR2-800 (800 MT/s), tensão 1.8V. "
            "⚠ x16 = FBGA-84 — diferente do x8 FBGA-60."
        ),
    ),
    dict(
        part_number   = "H5PS5182KFR-S5C",
        brand_name    = "SK Hynix",
        family_prefix = "H5PS",
        chip_type     = "RAM",
        subtype       = "DDR2 SDRAM",
        capacity      = "64MB",
        interface     = "DDR2",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via site oficial SK Hynix EOL ✓ e validação Intel ✓ "
            "(SK Hynix recebeu validação Intel para DDR2-533/400, conforme press release). "
            "pn[4:6]='51' → 64MB (512Mbit÷8). K-die, organização x8, FBGA-60. "
            "DDR2-800 (sufixo -S5C), tensão 1.8V."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR1 SDRAM — HY5DU (era Hynix pré-SK, 2.5V)
    # Decode: pn[5:7] → HYX_DDR1_CAP  |  64=8MB · 28=16MB · 56=32MB · 12=64MB
    # Chave usa os 2 últimos dígitos do valor em Mbit (128→"28", 256→"56", 512→"12")
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "HY5DU281622ET-25",
        brand_name    = "SK Hynix",
        family_prefix = "HY5DU",
        chip_type     = "RAM",
        subtype       = "DDR1 SDRAM",
        capacity      = "16MB",
        interface     = "DDR1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet (datasheet Hynix HY5DU281622ET Rev0.3 Abr/2006) ✓. "
            "pn[5:7]='28' → 16MB (128Mbit÷8). Organização x16, TSOP. "
            "DDR-400 (2.5 ns), tensão 2.5V. Slot DDR1 184-pin. "
            "⚠ Codificação: chave = últimos 2 dígitos de Mbit (128 → '28')."
        ),
    ),
    dict(
        part_number   = "HY5DU561622CTP-28",
        brand_name    = "SK Hynix",
        family_prefix = "HY5DU",
        chip_type     = "RAM",
        subtype       = "DDR1 SDRAM",
        capacity      = "32MB",
        interface     = "DDR1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. Variante gDDR (Graphics DDR) — DDR1 usado em GPUs. "
            "pn[5:7]='56' → 32MB (256Mbit÷8). C-die, x16, TSOP-P (encapsulamento Pb-free). "
            "DDR-350 (2.8 ns), tensão 2.5V. "
            "⚠ 'gDDR' = DDR1 era, não GDDR2+ — classificar como DDR1."
        ),
    ),
    dict(
        part_number   = "HY5DU121622CTP-J",
        brand_name    = "SK Hynix",
        family_prefix = "HY5DU",
        chip_type     = "RAM",
        subtype       = "DDR1 SDRAM",
        capacity      = "64MB",
        interface     = "DDR1",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Alldatasheet ✓. "
            "pn[5:7]='12' → 64MB (512Mbit÷8). C-die, x16, TSOP-P. "
            "DDR-143 (sufixo -J = 7.0 ns), tensão 2.5V. "
            "Topo de densidade da família HY5DU — 1Gbit não foi produzido nesta nomenclatura."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR5 SDRAM — H5C (PMIC interno, sem tensão explícita no PN)
    # Decode: pn[3:5] → HYX_DDR5_CAP  |  G4=2GB · GD=3GB · G5=4GB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5CG48MEBDX014N",
        brand_name    = "SK Hynix",
        family_prefix = "H5C",
        chip_type     = "RAM",
        subtype       = "DDR5 SDRAM",
        capacity      = "2GB",
        interface     = "DDR5",
        confidence    = "confirmed",
        notes         = (
            "Confirmado via Fusion Worldwide ✓ · TechPowerUp ✓. "
            "pn[3:5]='G4' → 2GB (16Gbit÷8). M-die (1ª geração EUV D1a), organização x8. "
            "DDR5-4800 (4800 MT/s). FCBGA-82. "
            "Chip vendido a fabricantes de módulos — raro em estoque de reciclagem avulso. "
            "⚠ DDR5: PMIC interno — tensão via slot DDR5 288-pin (incompatível com DDR4)."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR3 H5TQ — PNs BASE (sem sufixo de velocidade)
    # Chips físicos frequentemente exibem apenas o PN base na marcação a laser
    # (ex: "H5TQ2G63GFR" sem "-RDC"). Entradas com sufixo já existem acima.
    # Capacidade independe do sufixo de velocidade — decode pn[4:6] é o mesmo.
    # ──────────────────────────────────────────────────────────────────────────

    # ── 1G = 128MB por chip ────────────────────────────────────────────────
    dict(
        part_number   = "H5TQ1G83EFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "128MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='1G' → 128MB (1Gbit÷8). E-die, x8, FBGA-78. "
            "Velocidades: -H9C (DDR3-1333) · -PBC (DDR3-1600). "
            "Confirmado via Datasheets360 ✓ (variante -PBC). Tablets / embarcados."
        ),
    ),

    # ── 2G = 256MB por chip ────────────────────────────────────────────────
    dict(
        part_number   = "H5TQ2G63GFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). G-die, x16, FBGA-96. "
            "Velocidades: -RDC (DDR3-1866) · -TEC (DDR3-2133). "
            "Confirmado via LCSC C390897 ✓ · PS4 Developer Wiki ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G63FFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). F-die, x16, FBGA-96. "
            "Velocidades: -H9C (DDR3-1333) · -PBC (DDR3-1600) · -RDC (DDR3-1866). "
            "Confirmado via distribuidores B2B ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G63DFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). D-die, x16, FBGA-96. "
            "Velocidades: -H9C (DDR3-1333) · -RDC (DDR3-1866). "
            "Confirmado via Alldatasheet ✓. Geração de notebooks 2012–2014."
        ),
    ),
    dict(
        part_number   = "H5TQ2G83BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). B-die, x8, FBGA-78. "
            "Velocidade: -H9C (DDR3-1333). Confirmado via Octopart ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G83CFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='2G' → 256MB (2Gbit÷8). C-die, x8, FBGA-78. "
            "Velocidades: -G7C (DDR3-1066) · -H9C (DDR3-1333). "
            "Confirmado via Alldatasheet ✓. Die intermediário entre B e D."
        ),
    ),

    # ── 4G = 512MB por chip ────────────────────────────────────────────────
    dict(
        part_number   = "H5TQ4G63AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). A-die, x16, FBGA-96. "
            "Velocidades: -G7C · -H9C · -PBC · -RDC · -TEC. "
            "Confirmado via datasheet PDF SK Hynix (via NXP community) ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G63EFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). E-die, x16, FBGA-96. "
            "Velocidades: -H9C · -PBC · -RDC · -TEC. "
            "Confirmado via LCSC C2803259 ✓ (datasheet SK Hynix Rev1.2 Set/2016)."
        ),
    ),
    dict(
        part_number   = "H5TQ4G63MFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). M-die (1ª geração), x16, FBGA-96. "
            "Velocidades: -H9C · -PBC · -RDC. Confirmado via distribuidores B2B ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G83AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). A-die, x8, FBGA-78. "
            "Velocidades: -G7C · -H9C · -RDC. Confirmado via distribuidores B2B ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G83EFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). E-die, x8, FBGA-78. "
            "Velocidades: -H9C · -PBC · -RDC · -TEC. "
            "Confirmado via LCSC C2841156 ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G83MFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). M-die (1ª geração), x8, FBGA-78. "
            "Velocidades: -G7C · -H9C · -PBC · -RDC. Confirmado via Octopart ✓."
        ),
    ),

    # ── 8G = 1GB por chip (DDP — dois dies 4Gb empilhados) ────────────────
    dict(
        part_number   = "H5TQ8G63AMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "1GB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). DDP. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die, DDP x8, FBGA-96. "
            "Sufixo AMR (não FR) = Dual Die Package. "
            "Velocidades: -G7C · -H9C · -PBC · -RDC. Confirmado via Alldatasheet ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR3L H5TC — PNs BASE (sem sufixo de velocidade)
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5TC4G83CFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). C-die, x8, FBGA-78. DDR3L 1.35V. "
            "Velocidades: -H9A · -H9I · -PBA · -PBI · -RDA · -RDI. "
            "Confirmado via datasheet oficial SK Hynix H5TC4G8(6)3CFR Rev0.2 ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G63CFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). C-die, x16, FBGA-96. DDR3L 1.35V. "
            "Velocidades: -PBA · -RDA · -RDI. Confirmado via Octopart ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G83BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). B-die, x8, FBGA-78. DDR3L 1.35V. "
            "Velocidades: -PBA · -RDA. Confirmado via Alldatasheet ✓."
        ),
    ),
    dict(
        part_number   = "H5TC8G83AMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "1GB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). DDP. "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). DDP, x8, FBGA-78. DDR3L 1.35V. "
            "Velocidades: -H9A · -PBA. Confirmado via Win Source / Alldatasheet ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR4 H5AN — PNs BASE (sem sufixo de velocidade)
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5AN8G8NAFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die (Era 1), x8, FBGA-78. DDR4 1.2V. "
            "Velocidades: -UHC (DDR4-2400) · -VKC (DDR4-2666). "
            "Confirmado via Alldatasheet ✓."
        ),
    ),
    dict(
        part_number   = "H5AN8G6NAFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). A-die (Era 1), x16, FBGA-96. DDR4 1.2V. "
            "Velocidade: -UHC (DDR4-2400). Confirmado via LCSC ✓."
        ),
    ),
    dict(
        part_number   = "H5AN4G8NBJR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "512MB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='4G' → 512MB (4Gbit÷8). B-die (Era 1, 2ª ger.), x8, FBGA-78. DDR4 1.2V. "
            "Velocidades: -UHC · -VKC · -VKI. Confirmado via catálogo oficial SK Hynix ✓."
        ),
    ),
    dict(
        part_number   = "H5AN8G8NCJR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "PN base sem sufixo de velocidade (chip físico). "
            "pn[4:6]='8G' → 1GB (8Gbit÷8). C-die (Era 1, 3ª ger. 10nm), x8, FBGA-78. DDR4 1.2V. "
            "Velocidades: -VKC · -WMC · -XNC. Confirmado via JLCPCB/LCSC C2803261 ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR3 1.5V — H5TQ x4 (bus x4, organização 4 bits por chip)
    # Decode pn[4:6]: 1G=128MB · 2G=256MB · 4G=512MB (igual ao x8)
    # pn[6]='4' distingue x4; pn[7]='3' = 8 banks (fixo DDR3)
    # Uso: RDIMMs de servidor (x4 permite ECC com 18 chips por módulo)
    # ⚠ H5TQ8G43 NÃO existe (SK Hynix não produziu 8Gb x4 em 1.5V)
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5TQ1G43AFP",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "128MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='1G' → 128MB (1Gbit ÷ 8). x4, FBGA-78, 1.5V. A-gen. "
            "⚠ Sufixo 'AFP' (P = package diferente) — não 'AFR'. "
            "Fonte: Alldatasheet H5TQ1G43AFP datasheet ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ1G43BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "128MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='1G' → 128MB. x4, FBGA-78, 1.5V. B-gen. "
            "Fonte: Alldatasheet H5TQ1G43BFR ✓ · Datasheets360 -H9C ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ1G43TFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "128MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='1G' → 128MB. x4, FBGA-78, 1.5V. T-gen (variante de die). "
            "Fonte: Alldatasheet H5TQ1G43TFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G43AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB (2Gbit ÷ 8). x4, FBGA-78, 1.5V. A-gen. "
            "Chip físico confirmado em bancada eMiner ✓. RDIMM servidor. "
            "Fonte: Alldatasheet H5TQ2G43AFR datasheet ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G43BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.5V. B-gen. "
            "Fonte: Alldatasheet H5TQ2G43BFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G43CFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.5V. C-gen. "
            "Velocidades: -G7C · -H9C · -PBC · -RDC · -TEC · -XXC. "
            "Fonte: Alldatasheet H5TQ2G43CFR ✓ · Octopart -PBC em estoque ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ2G43EFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "256MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.5V. E-gen (EOL). "
            "Fonte: SK Hynix EOL page H5TQ2G43EFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G43AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB (4Gbit ÷ 8). x4, FBGA-78, 1.5V. A-gen. "
            "Velocidades: -G7C · -H9C · -PBC · -RDC · -TEC (RDIMM). "
            "Fonte: Alldatasheet H5TQ4G43AFR ✓ · Datasheets360 -RDC ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G43MFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB. x4, FBGA-78, 1.5V. M-gen (EOL). "
            "Fonte: Alldatasheet H5TQ4G43MFR ✓ · SK Hynix EOL ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G43AMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB total. x4, FBGA-78 DDP, 1.5V. A-gen. "
            "⚠ DDP = Dual Die Package (dois dies de 2Gb empilhados = 4Gb total). "
            "Sufixo 'MR' (M = multi-die). Capacidade por pacote = 512MB. "
            "Fonte: Alldatasheet H5TQ4G43AMR ✓."
        ),
    ),
    dict(
        part_number   = "H5TQ4G43MMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TQ",
        chip_type     = "RAM",
        subtype       = "DDR3 SDRAM",
        capacity      = "512MB",
        interface     = "DDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB total. x4, FBGA-78 DDP, 1.5V. M-gen. "
            "⚠ DDP (M no sufixo). Velocidades: -G7C · -S6C. "
            "Fonte: Alldatasheet H5TQ4G43MMR ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR3L 1.35V — H5TC x4 (bus x4)
    # Decode pn[4:6]: 1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB (DDP)
    # ⚠ Sufixos terminam em 'A' (ex: -PBA), não 'C' — qualif. temp DDR3L
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5TC1G43BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "128MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='1G' → 128MB. x4, FBGA-78, 1.35V. B-gen. "
            "Fonte: Alldatasheet H5TC1G43BFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC1G43TFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "128MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='1G' → 128MB. x4, FBGA-78, 1.35V. T-gen. "
            "Fonte: Alldatasheet H5TC1G43TFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC2G43AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "256MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB (2Gbit ÷ 8). x4, FBGA-78, 1.35V. A-gen. "
            "Velocidades: -G7A · -H9A · -PBA · -RDA. "
            "Fonte: Alldatasheet H5TC2G43AFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC2G43BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "256MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.35V. B-gen. "
            "Fonte: Alldatasheet H5TC2G43BFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC2G43CFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "256MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.35V. C-gen. "
            "Fonte: Alldatasheet H5TC2G43CFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC2G43EFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "256MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='2G' → 256MB. x4, FBGA-78, 1.35V. E-gen. "
            "Fonte: Alldatasheet H5TC2G43EFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G43AFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB (4Gbit ÷ 8). x4, FBGA-78, 1.35V. A-gen. "
            "Velocidades: -G7A · -H9A · -PBA · -RDA · -XXA (RDIMM DDR3L). "
            "Fonte: Alldatasheet H5TC4G43AFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G43BFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB. x4, FBGA-78, 1.35V. B-gen. "
            "Organização 1Gx4 confirmada no datasheet -PBA. "
            "Fonte: Alldatasheet H5TC4G43BFR-PBA ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G43DFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB. x4, FBGA-78, 1.35V. D-gen. "
            "Fonte: Datasheets.com H5TC4G43DFR-RDA ✓."
        ),
    ),
    dict(
        part_number   = "H5TC4G43MFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "512MB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB. x4, FBGA-78, 1.35V. M-gen. "
            "Velocidades: -G7A · -H9A · -PBA. "
            "Fonte: Alldatasheet H5TC4G43MFR ✓."
        ),
    ),
    dict(
        part_number   = "H5TC8G43AMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "1GB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='8G' → 1GB (8Gbit ÷ 8). x4, FBGA-78 DDP, 1.35V. A-gen. "
            "⚠ DDP = dois dies de 4Gb empilhados (2G×4 por die × 2 dies). "
            "Sufixo 'MR' = multi-die package. "
            "Fonte: datasheet oficial SK Hynix via NXP 99H02-11185D ✓ · Alldatasheet ✓."
        ),
    ),
    dict(
        part_number   = "H5TC8G43MMR",
        brand_name    = "SK Hynix",
        family_prefix = "H5TC",
        chip_type     = "RAM",
        subtype       = "DDR3L SDRAM",
        capacity      = "1GB",
        interface     = "DDR3L",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='8G' → 1GB. x4, FBGA-78 DDP, 1.35V. M-gen. "
            "⚠ DDP (sufixo MR). Velocidades: -G7A · -H9A · -PBA. "
            "Fonte: Alldatasheet H5TC8G43MMR ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # DDR4 1.2V — H5AN x4 (barramento x4, organização 4 bits por chip)
    # Em DDR4 não há dígito '3' — pn[6]='4' sozinho indica x4
    # Decode pn[4:6]: 4G=512MB · 8G=1GB (mapa HYX_DDR4_CAP, igual x8)
    # Familia H5AN: A-die=NAFR, B-die=NBJR, C-die=NCJR
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H5AN4G4NAFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "512MB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB (4Gbit ÷ 8). x4, FBGA-78, 1.2V. A-die (Era 1). "
            "Velocidades: -TFC (DDR4-2133) · -UHC (DDR4-2400). RDIMM/LRDIMM servidor. "
            "Fonte: Alldatasheet H5AN4G4NAFR-UHC ✓."
        ),
    ),
    dict(
        part_number   = "H5AN4G4NBJR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "512MB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='4G' → 512MB. x4, FBGA-78, 1.2V. B-die (Era 1, 2ª ger.). "
            "Velocidades: -PBC · -RDC · -TFC · -UHC · -VKC · -XNC. "
            "Fonte: datasheet Netlist/DigiKey H5AN4GxNBJR ✓."
        ),
    ),
    dict(
        part_number   = "H5AN8G4NAFR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='8G' → 1GB (8Gbit ÷ 8). x4, FBGA-78, 1.2V. A-die (Era 1). "
            "Velocidades: -PBC · -RDC · -TFC · -UHC · -VKC. "
            "Fonte: Alldatasheet H5AN8G4NAFR ✓."
        ),
    ),
    dict(
        part_number   = "H5AN8G4NCJR",
        brand_name    = "SK Hynix",
        family_prefix = "H5AN",
        chip_type     = "RAM",
        subtype       = "DDR4 SDRAM",
        capacity      = "1GB",
        interface     = "DDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[4:6]='8G' → 1GB. x4, FBGA-78, 1.2V. C-die (Era 1, 3ª ger. 10nm). "
            "Rev. 1.5 (Mar 2019). "
            "Fonte: Alldatasheet H5AN8G4NCJR ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR3 standalone — H9CC (SK Hynix, x32, móvel)
    # Decode: pn[7] → HYX_LPDDR3_H9CC_CAP  |  8=1GB · B=2GB · D=3GB · C=4GB
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9CCNNNCLTML",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "4GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador (chip físico em bancada). "
            "pn[7]='C' → 4GB (32Gbit÷8). Família H9CC = LPDDR3 standalone SK Hynix x32. "
            "pn[4:7]='NNN' = preenchimento fixo padrão. Sufixo LTML. "
            "4GB LPDDR3 — alto valor no recondicionamento de smartphones premium 2016–2017."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR3 standalone — H9CC 1GB (pn[7]='8')
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9CCNNN8JTALAR-NTM",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "1GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='8' → 1GB (8Gbit ÷ 8). '8J' = 8Gb DDP 1Ch 2CS. FBGA-178, 1.2V. "
            "LPDDR3-1600 (-NTM = grade mobile padrão). "
            "Fonte: datasheet oficial SK Hynix via Pine64 H9CCNNN8JTALAR Rev1.0 ✓. "
            "Tablets Windows / laptops compactos 2014–2019 (Surface, MacBook Air)."
        ),
    ),
    dict(
        part_number   = "H9CCNNN8JTML",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "1GB",
        interface     = "LPDDR3",
        confidence    = "manual",
        notes         = (
            "PN base 12 chars (sem sufixo AR-Nxx) — formato provável de marcação física. "
            "pn[7]='8' → 1GB. Config JTML. FBGA-178 LPDDR3 standalone. "
            "PN completo: H9CCNNN8JTMLAR-NTM (AB Sunshine ✓). "
            "Confidence=manual: inferência de padrão; aguarda scan de chip físico."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR3 standalone — H9CC 2GB (pn[7]='B')
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9CCNNNBLTMLAR-NTM",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "2GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). 'BL' = 16Gb QDP 1Ch 2CS. FBGA-178, 1.2V. "
            "LPDDR3-1600 (-NTM). "
            "Fonte: Preduo WP00904 com foto do chip ✓."
        ),
    ),
    dict(
        part_number   = "H9CCNNNBLTML",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "2GB",
        interface     = "LPDDR3",
        confidence    = "manual",
        notes         = (
            "PN base 12 chars — formato provável de marcação física (padrão H9CCNNNCLTML). "
            "pn[7]='B' → 2GB. Config BL = QDP 1Ch 2CS. "
            "PN completo: H9CCNNNBLTMLAR-NTM (Preduo foto ✓). "
            "Confidence=manual: inferência de padrão."
        ),
    ),
    dict(
        part_number   = "H9CCNNNBJTALAR-NVD",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "2GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). 'BJ' = 16Gb DDP 1Ch 2CS. FBGA-178, 1.2V. "
            "LPDDR3-2133 (-NVD = grade mais rápido). "
            "Fonte: linux-hardware.org 'Row of Chips LPDDR3 2133MT/s' ✓ + Preduo WP00895 ✓."
        ),
    ),
    dict(
        part_number   = "H9CCNNNBJTML",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "2GB",
        interface     = "LPDDR3",
        confidence    = "manual",
        notes         = (
            "PN base 12 chars — marcação física provável para config BJ (DDP). "
            "pn[7]='B' → 2GB. "
            "PN completo: H9CCNNNBJTMLAR-NTD (Preduo WP00901 ✓). "
            "Confidence=manual: inferência de padrão."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR3 standalone — H9CC 4GB (sufixados; base H9CCNNNCLTML já no banco)
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9CCNNNCLTMLAR-NTD",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "4GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='C' → 4GB (32Gbit ÷ 8). Config CL = 32Gb QDP. FBGA-178, 1.2V. "
            "Fonte: datasheet oficial SK Hynix H9CCNNNCLTMLAR Rev1.2 via Pine64 ✓. "
            "Grade -NTD. Marcação física sem sufixo: H9CCNNNCLTML."
        ),
    ),
    dict(
        part_number   = "H9CCNNNCLTMLAR-NUD",
        brand_name    = "SK Hynix",
        family_prefix = "H9CC",
        chip_type     = "RAM",
        subtype       = "LPDDR3",
        capacity      = "4GB",
        interface     = "LPDDR3",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='C' → 4GB (32Gbit ÷ 8). Config CL = 32Gb QDP. FBGA-178, 1.2V. "
            "Fonte: datasheet oficial SK Hynix H9CCNNNCLTMLAR Rev1.2 via Pine64 ✓. "
            "Grade -NUD. Marcação física sem sufixo: H9CCNNNCLTML."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR4X standalone — H9HCNNN 200-ball (SK Hynix)
    # Decode pn[7]: 4=0.5GB · 8=1GB · B=2GB · C=4GB · F=8GB
    # Sufixo MMLXR = 4266 Mbps (LPDDR4X alta velocidade)
    # Sufixo MMLHR = 3733 Mbps (LPDDR4X velocidade padrão)
    # ⚠ Não existe 'E'=6GB nesta família 200-ball. 6GB → H9HKNNN (376/556-ball).
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9HCNNNCPMMLXR-NEE",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "4GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='C' → 4GB (32Gbit ÷ 8). CP = 32Gb LPDDR4X x32. FBGA-200. "
            "4266 Mbps (XR = pacote alta velocidade). VDD2=1.8V, VDDQ=0.6V. "
            "Fonte: LCSC C19192462 em estoque ✓ · Glochip página oficial SK Hynix (MP) ✓ · Preduo ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNCPMMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "4GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='C' → 4GB (32Gbit ÷ 8). CP = 32Gb LPDDR4X x32. FBGA-200. "
            "3733 Mbps (HR). "
            "Fonte: iFixit Amazon Astro placa de tela Step 1 ✓ · Glochip (MP) ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNBKMMLXR-NEE",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "2GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). BK = 16Gb LPDDR4X x32. FBGA-200. "
            "4266 Mbps. "
            "Fonte: iFixit DJI Mavic 3 Pro Steps 1+4 ✓ · Octopart ✓ · Glochip (MP) ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNBKMMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "2GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). BK = 16Gb LPDDR4X x32. FBGA-200. "
            "3733 Mbps. "
            "Fonte: iFixit Amazon Astro placa de sensores Step 9 ✓ · Glochip (MP) ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNFAMMLXR-NEE",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4X",
        capacity      = "8GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='F' → 8GB (64Gbit ÷ 8). FA = 64Gb LPDDR4X. FBGA-200. "
            "4266 Mbps. "
            "Fonte: Glochip página oficial SK Hynix (MP) ✓ · Preduo ✓ · Fusion Worldwide ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR4 standalone — H9HCNNN 200-ball (SK Hynix)
    # Mesmo corpo H9HCNNN, sufixo KU/BU/PU/RU = LPDDR4 (VDDQ 1.1V vs 0.6V LPDDR4X)
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9HCNNN8KUMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4",
        capacity      = "1GB",
        interface     = "LPDDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='8' → 1GB (8Gbit ÷ 8). 8K = 8Gb LPDDR4 x32. FBGA-200. "
            "KU = LPDDR4 (VDDQ 1.1V — diferente de KM=LPDDR4X 0.6V). "
            "Fonte: LCSC C2912103 datasheet ✓ · HardDiskDirect ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNBPUMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4",
        capacity      = "2GB",
        interface     = "LPDDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). BP = 16Gb LPDDR4 x32. FBGA-200. "
            "512Mx32. LPDDR4 3733 Mbps. "
            "Fonte: electronicsdatasheets.com H9HCNNNBPUMLHR-NMI specs ✓ · Preduo ✓ · Fusion Worldwide ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNBKUMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4",
        capacity      = "2GB",
        interface     = "LPDDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='B' → 2GB (16Gbit ÷ 8). BK = 16Gb LPDDR4 x32. FBGA-200. "
            "Fonte: Octopart ✓ · Preduo ✓."
        ),
    ),
    dict(
        part_number   = "H9HCNNNCPUMLHR-NME",
        brand_name    = "SK Hynix",
        family_prefix = "H9HCN",
        chip_type     = "RAM",
        subtype       = "LPDDR4",
        capacity      = "4GB",
        interface     = "LPDDR4",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='C' → 4GB (32Gbit ÷ 8). CP = 32Gb LPDDR4 x32. FBGA-200. "
            "Fonte: Preduo ✓ · HardDiskDirect ✓."
        ),
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # LPDDR2 standalone — H9TK (SK Hynix, FBGA-168, 26nm)
    # Decode pn[7]: 1=128MB · 2=256MB · 4=512MB · 8=1GB
    # pn[8] = nó de processo/geração: G=planar, J=2ª geração, K=3ª geração
    # ──────────────────────────────────────────────────────────────────────────
    dict(
        part_number   = "H9TKNNN8JDAPLR-NGH",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "1GB",
        interface     = "LPDDR2",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='8' → 1GB (8Gbit ÷ 8). LPDDR2-1066. FBGA-168, 26nm. "
            "Fonte de maior confiança desta família: iFixit teardown LG Optimus L90 Dual (2014) "
            "— texto explícito: '1GB LPDDR2-1066 RAM' ✓. "
            "Sufixo -NGH = lead-free, grade G (1066 Mbps), temp H."
        ),
    ),
    dict(
        part_number   = "H9TKNNN8JDMPLR-NDM",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "1GB",
        interface     = "LPDDR2",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='8' → 1GB (8Gbit ÷ 8). LPDDR2-800 (-NDM = grade D, temp M). "
            "256Mx32 — config confirmada como 8Gb (256Mx32 = 8Gbit). FBGA-168. "
            "Fonte: HardDiskDirect '256Mx32 (8GB)' ✓."
        ),
    ),
    dict(
        part_number   = "H9TKNNN4GDMPLR-NDM",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "512MB",
        interface     = "LPDDR2",
        confidence    = "confirmed",
        notes         = (
            "pn[7]='4' → 512MB (4Gbit ÷ 8). LPDDR2-800. 128Mx32. FBGA-168. "
            "Fonte: Worldway Electronics '4Gb x32 LPDDR2-800' ✓ · OMO Electric ✓."
        ),
    ),
    dict(
        part_number   = "H9TKNNN4GDAP",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "512MB",
        interface     = "LPDDR2",
        confidence    = "manual",
        notes         = (
            "PN base sem sufixo de velocidade — marcação física provável. "
            "pn[7]='4' → 512MB. pn[8]='G' = 1ª geração. "
            "Fonte: catálogo OMO Electric (144+ PNs H9TK) ✓. "
            "Confidence=manual: broker sem datasheet oficial."
        ),
    ),
    dict(
        part_number   = "H9TKNNN2GDAP",
        brand_name    = "SK Hynix",
        family_prefix = "H9TK",
        chip_type     = "RAM",
        subtype       = "LPDDR2",
        capacity      = "256MB",
        interface     = "LPDDR2",
        confidence    = "manual",
        notes         = (
            "PN base sem sufixo de velocidade. "
            "pn[7]='2' → 256MB (2Gbit ÷ 8). pn[8]='G' = 1ª geração. "
            "Fonte: catálogo OMO Electric ✓. "
            "Confidence=manual: broker sem datasheet oficial."
        ),
    ),

    # Adicione mais chips aqui no mesmo formato se necessário
]

for p in PARTS:
    brand  = Brand.objects.get(name=p["brand_name"])
    family = ChipFamily.objects.filter(prefix=p["family_prefix"]).first()

    obj, created = KnownPart.objects.update_or_create(
        part_number=p["part_number"],
        defaults=dict(
            brand      = brand,
            family     = family,
            status     = "enriched",
            chip_type  = p["chip_type"],
            subtype    = p.get("subtype", ""),
            capacity   = p.get("capacity", ""),
            interface  = p.get("interface", ""),
            confidence = p.get("confidence", "manual"),
            notes      = p.get("notes", ""),
        )
    )
    action = "✅ CRIADO" if created else "🔄 ATUALIZADO"
    print(f"{action}  {obj.part_number}  |  {obj.confidence}  |  {obj.capacity}")

print("\nPronto.")
