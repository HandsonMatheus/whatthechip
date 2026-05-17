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
