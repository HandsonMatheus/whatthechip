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
        subtype       = "LPDDR4X standalone",
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
        subtype       = "LPDDR4X standalone",
        capacity      = "6GB",
        interface     = "LPDDR4X",
        confidence    = "confirmed",
        notes         = (
            "Confirmado manualmente pelo operador. "
            "pn[7]='E' → 48Gbit ÷ 8 = 6GB (SK Hynix LPDDR4X PN Guide + manifesto aduaneiro). "
            "Descrição aduaneira: 'LPDDR4X 6G BGA200 Memory Chip Original'. "
            "RAM pura (zero NAND). 200FBGA. Smartphones premium / edge computing."
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
        subtype       = "LPDDR4X standalone",
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
        subtype       = "LPDDR2 standalone",
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
