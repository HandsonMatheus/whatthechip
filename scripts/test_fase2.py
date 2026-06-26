#!/usr/bin/env python
"""
Fase 2 — Testes do scrape_preduo management command
=====================================================
Cobre as garantias que o script de testes de terminal deve verificar:

  1. Lógica de extração de PNs (sem Django, sem rede)
  2. Inferência de marca a partir do prefixo do PN
  3. Validação de PNs (falsos positivos, comprimento, formato)
  4. Mapeamento chip_type → slug Preduo
  5. Dry-run não persiste nada no banco (Django + DB)
  6. Campos obrigatórios presentes em KnownPart criado
  7. Deduplicação: PN já existente com confidence=confirmed não é sobrescrito
  8. --overwrite atualiza campos vazios em KnownPart existente com confiança ≤ distributor
  9. Source "Preduo" é criado/recuperado corretamente

Por que isso importa:
  O scrape_preduo.py salva dados no banco com status=raw. Se a lógica de
  deduplicação falhar, podemos sobrescrever KnownParts confirmados com lixo.
  Estes testes garantem que a hierarquia de confiança é respeitada.

Uso:
    cd /caminho/para/chipdocs
    python scripts/test_fase2.py

Pré-requisito: migrate + fix_known_parts já aplicados (Fase 0 + Fase 1 OK).
"""

import os
import sys
import django
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

django.setup()

from chips.management.commands.scrape_preduo import (
    PREDUO_CHIP_TYPES,
    BRAND_PREFIX_MAP,
    _infer_brand,
    _extract_pns,
    _is_valid_pn,
)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"
WARN = "⚠️  WARN"

errors: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f"\n         └─ {detail}" if detail else ""))
        errors.append(label)


print()
print("=" * 65)
print("  FASE 2 — Testes scrape_preduo.py")
print("=" * 65)


# ── 1. Extração de PNs ───────────────────────────────────────────────────────
print("\n[1] Extração e validação de PNs")

# PNs que DEVEM ser extraídos
VALID_PNS = [
    "KLM8G1GETF",        # Samsung eMMC
    "H9TQ64ABMM",        # SK Hynix eMCP
    "MT53B512M64D4TX",   # Micron LPDDR4X
    "MTFC8GAKAJCN",      # Micron eMMC (tem dígitos — válido)
    "KMR310002M",        # Samsung eMCP
    "THGBMHG8C4LBAIR",   # KIOXIA eMMC
    # KLMCGUCTA removido: sem dígito → corretamente rejeitado por _is_valid_pn
]

# Tokens que NÃO devem ser extraídos (falsos positivos)
FALSE_POSITIVES = [
    "SAMSUNG",       # nome de marca
    "PREDUO",        # nome do site
    "EMMC",          # muito curto (4 chars)
    "MEMORY",        # palavra genérica
    "DOWNLOAD",      # palavra de UI
    "LPDDR4",        # tipo de chip com sufixo numérico — deve estar em _FALSE_POSITIVES
    "12345678",      # número puro
]

# Texto simulando uma página Preduo com mistura de PNs e lixo
SAMPLE_TEXT = " ".join(VALID_PNS + FALSE_POSITIVES + [
    "B041",          # sufixo de revisão (muito curto: 4 chars)
    "Page 1 of 15",  # navegação
    "View Details",  # UI
])

extracted = _extract_pns(SAMPLE_TEXT)
extracted_set = set(extracted)

for pn in VALID_PNS:
    check(
        f"_extract_pns: '{pn}' extraído",
        pn in extracted_set,
        f"Extraídos: {extracted}"
    )

for fp in FALSE_POSITIVES:
    # EMMC tem 4 chars → rejeitado por comprimento < 6; skip se muito curto
    if len(fp) < 6:
        continue
    if not any(c.isdigit() for c in fp):
        # Palavra pura → rejeitada por falta de dígito
        check(
            f"_extract_pns: '{fp}' NÃO extraído (sem dígito)",
            fp not in extracted_set,
        )
    else:
        check(
            f"_extract_pns: '{fp}' NÃO extraído (false positive)",
            fp not in extracted_set,
        )


# ── 2. Inferência de marca ──────────────────────────────────────────────────
print("\n[2] Inferência de marca (_infer_brand)")

BRAND_TESTS = [
    # (pn, expected_brand)
    ("KLM8G1GETF",    "Samsung"),
    ("KMR310002M",    "Samsung"),
    ("K4F8E3S4HB",    "Samsung"),
    ("KVR26N19S8",    "Kingston"),   # KVR antes de K
    ("KHX3200C16D4",  "Kingston"),
    ("H9TQ64ABMM",    "SK Hynix"),
    ("H9HP32A8JYNMC", "SK Hynix"),
    ("HMCG88MEBSA",   "SK Hynix"),
    ("MT53B512M64D4TX", "Micron"),
    ("MTFC4GACAJCN",  "Micron"),
    ("MT6765",        "MediaTek"),   # MT6x antes de MT
    ("MT8183",        "MediaTek"),
    ("THGBMHG8C4LBAIR", "KIOXIA"),
    ("SDINB4G1244E",  "SanDisk"),
    ("GD25Q64CSIG",   "GigaDevice"),
    ("IS42S16160J",   "ISSI"),
    ("XYZABC123",     None),         # desconhecida
    ("123456789",     None),         # número puro (infer também retorna None)
]

for pn, expected in BRAND_TESTS:
    got = _infer_brand(pn)
    check(
        f"_infer_brand('{pn}') → {expected!r}",
        got == expected,
        f"obtido: {got!r}"
    )


# ── 3. Validação de PNs individuais ─────────────────────────────────────────
print("\n[3] Validação de PNs (_is_valid_pn)")

VALID_INDIVIDUAL = [
    "KLM8G1GETF",
    "H9TQ64ABMM",
    "MT53B512M",
    "THGBMHG8C",
    "GD25Q64CS",
    "IS42S1616",
]
INVALID_INDIVIDUAL = [
    "SAMSUNG",           # false positive (nome de marca)
    "LPDDR4",            # false positive (tipo de chip com sufixo numérico)
    "LPDDR5",            # idem
    "EMMC",              # muito curto (4 chars)
    "12345678",          # número puro
    "ABCDEFGH",          # palavra pura (sem dígito)
    "KLMCGUCTA",         # sem dígito — PN incompleto / mal lido
    "PARTDETAILSABC123", # substring proibida
    "A" * 25,            # muito longo
]

for pn in VALID_INDIVIDUAL:
    check(
        f"_is_valid_pn('{pn}') = True",
        _is_valid_pn(pn),
    )

for pn in INVALID_INDIVIDUAL:
    check(
        f"_is_valid_pn('{pn}') = False",
        not _is_valid_pn(pn),
        f"PN aceito indevidamente"
    )


# ── 4. Configuração dos tipos de chip ────────────────────────────────────────
print("\n[4] Configuração de tipos (PREDUO_CHIP_TYPES)")

# Todos os tipos esperados devem estar presentes
EXPECTED_TYPES = {
    "eMCP", "eMMC", "uMCP", "UFS",
    "LPDDR5", "LPDDR4", "LPDDR3", "LPDDR2",
    "DDR5", "DDR4", "DDR3", "DDR2",
    "GDDR6", "GDDR5",
    "HBM3", "HBM2",
    "NORFLASH",
}

configured_slugs = {key for key, _, _, _ in PREDUO_CHIP_TYPES}

for expected in sorted(EXPECTED_TYPES):
    check(
        f"Tipo '{expected}' configurado",
        expected in configured_slugs,
    )

# Verifica que chip_type e subtype fazem sentido
for slug, _url_path, chip_type, subtype in PREDUO_CHIP_TYPES:
    check(
        f"Slug '{slug}' tem chip_type não-vazio",
        bool(chip_type),
        f"chip_type vazio para slug '{slug}'"
    )
    if "LPDDR" in slug or "DDR" in slug or "GDDR" in slug or "HBM" in slug:
        check(
            f"Slug '{slug}' tem subtype preenchido (é RAM)",
            bool(subtype),
            f"subtype vazio para tipo RAM '{slug}'"
        )


# ── 5. Dry-run não persiste ──────────────────────────────────────────────────
print("\n[5] Dry-run: não cria KnownParts no banco")

from django.core.management import call_command
from io import StringIO
from chips.models import KnownPart

# PNs de teste — prefixo MT (Micron) para que _infer_brand retorne "Micron"
# Padrão similar a PNs reais mas com sufixo TSTEXX para não colidir com nada real
TEST_PN_DRY = "MTTSTE0DRY01A"

# Garante que não existe antes
try:
    KnownPart.objects.filter(part_number=TEST_PN_DRY).delete()
except Exception:
    pass

# Executa o command em dry-run com um mock de PNs coletados
# Como não temos rede, testamos o método _save_to_db diretamente com dry=True
from chips.management.commands.scrape_preduo import Command as ScrapeCommand

cmd = ScrapeCommand()
cmd.stdout = StringIO()
cmd.stderr = StringIO()
cmd.style = type("Style", (), {
    "SUCCESS": lambda s, x: x,
    "WARNING": lambda s, x: x,
    "ERROR":   lambda s, x: x,
})()

try:
    counts = cmd._save_to_db(
        seen_pns={TEST_PN_DRY: ("eMMC", "", "https://www.preduo.com/eMMC-List")},
        dry=True,
        overwrite=False,
        limit=0,
    )
    still_absent = not KnownPart.objects.filter(part_number=TEST_PN_DRY).exists()
    check(
        "Dry-run não criou KnownPart no banco",
        still_absent,
    )
    check(
        "Dry-run contabilizou 'created' corretamente",
        counts["created"] == 1,
        f"counts={counts}"
    )
except Exception as exc:
    check("_save_to_db(dry=True) sem exceção", False, f"{exc}\n{traceback.format_exc()[-400:]}")


# ── 6. Campos obrigatórios em KnownPart criado ──────────────────────────────
print("\n[6] Criação real: campos obrigatórios presentes")

TEST_PN_REAL = "MTTSTE0REAL01B"

try:
    KnownPart.objects.filter(part_number=TEST_PN_REAL).delete()
except Exception:
    pass

from chips.models import Brand, Source

try:
    # Garante que a marca Micron existe
    Brand.objects.get_or_create(name="Micron", defaults={"code": "MIC"})

    from django.db import transaction
    with transaction.atomic():
        counts = cmd._save_to_db(
            seen_pns={
                TEST_PN_REAL: ("eMMC", "", "https://www.preduo.com/eMMC-List?page=1")
            },
            dry=False,
            overwrite=False,
            limit=0,
        )

    created_part = KnownPart.objects.filter(part_number=TEST_PN_REAL).first()
    check(
        "KnownPart criado no banco",
        created_part is not None,
        f"counts={counts}"
    )
    if created_part:
        check("confidence = 'distributor'", created_part.confidence == "distributor",
              f"confidence={created_part.confidence}")
        check("chip_type = 'eMMC'",      created_part.chip_type == "eMMC",
              f"chip_type={created_part.chip_type}")
        check("source_url preenchido",   bool(created_part.source_url),
              f"source_url={created_part.source_url!r}")
        check("source (Preduo) definido", created_part.source is not None,
              "source é None")
        if created_part.source:
            check("source.name = 'Preduo'",
                  created_part.source.name == "Preduo",
                  f"source.name={created_part.source.name!r}")
            check("source.src_type = 'scraper'",
                  created_part.source.src_type == "scraper",
                  f"src_type={created_part.source.src_type!r}")

except Exception as exc:
    check("_save_to_db(dry=False) sem exceção", False,
          f"{exc}\n{traceback.format_exc()[-600:]}")


# ── 7. Deduplicação: confirmed não é sobrescrito ─────────────────────────────
print("\n[7] Deduplicação: KnownPart confirmed não é sobrescrito")

TEST_PN_DEDUP = "MTTSTE0DUP002C"

try:
    KnownPart.objects.filter(part_number=TEST_PN_DEDUP).delete()
    brand_mic, _ = Brand.objects.get_or_create(name="Micron", defaults={"code": "MIC"})

    # Cria um KnownPart com confidence=confirmed
    KnownPart.objects.create(
        brand=brand_mic,
        part_number=TEST_PN_DEDUP,
        chip_type="eMMC",
        confidence="confirmed",
        notes="Dado confirmado — NÃO sobrescrever",
    )

    # Tenta sobrescrever com --overwrite
    counts_dedup = cmd._save_to_db(
        seen_pns={TEST_PN_DEDUP: ("eMMC", "", "https://www.preduo.com/eMMC-List")},
        dry=False,
        overwrite=True,
        limit=0,
    )

    reloaded = KnownPart.objects.get(part_number=TEST_PN_DEDUP)
    check(
        "confidence=confirmed preservado após --overwrite",
        reloaded.confidence == "confirmed",
        f"confidence foi alterado para: {reloaded.confidence}"
    )
    check(
        "notes preservada após --overwrite",
        "NÃO sobrescrever" in reloaded.notes,
        f"notes={reloaded.notes!r}"
    )
    check(
        "PN contabilizado como 'skipped' (não updated)",
        counts_dedup["skipped"] == 1 and counts_dedup["updated"] == 0,
        f"counts={counts_dedup}"
    )

except Exception as exc:
    check("Deduplicação sem exceção", False,
          f"{exc}\n{traceback.format_exc()[-400:]}")


# ── 8. --overwrite atualiza campos vazios ────────────────────────────────────
print("\n[8] --overwrite atualiza campos vazios (confidence <= distributor)")

TEST_PN_OVW = "MTTSTE0OVW003D"

try:
    KnownPart.objects.filter(part_number=TEST_PN_OVW).delete()
    brand_mic, _ = Brand.objects.get_or_create(name="Micron", defaults={"code": "MIC"})

    # KnownPart existente com confidence=estimated e chip_type vazio
    KnownPart.objects.create(
        brand=brand_mic,
        part_number=TEST_PN_OVW,
        chip_type="",       # vazio — deve ser preenchido
        confidence="estimated",
    )

    counts_ovw = cmd._save_to_db(
        seen_pns={TEST_PN_OVW: ("eMMC", "", "https://www.preduo.com/eMMC-List")},
        dry=False,
        overwrite=True,
        limit=0,
    )

    reloaded = KnownPart.objects.get(part_number=TEST_PN_OVW)
    check(
        "--overwrite preencheu chip_type vazio",
        reloaded.chip_type == "eMMC",
        f"chip_type={reloaded.chip_type!r}"
    )
    check(
        "--overwrite atualizou confidence para 'distributor'",
        reloaded.confidence == "distributor",
        f"confidence={reloaded.confidence!r}"
    )
    check(
        "PN contabilizado como 'updated'",
        counts_ovw["updated"] == 1,
        f"counts={counts_ovw}"
    )

except Exception as exc:
    check("--overwrite sem exceção", False,
          f"{exc}\n{traceback.format_exc()[-400:]}")


# ── 9. Source Preduo ─────────────────────────────────────────────────────────
print("\n[9] Source 'Preduo' no banco")

try:
    from chips.models import Source
    sources = Source.objects.filter(name="Preduo")
    check(
        "Source 'Preduo' existe no banco",
        sources.exists(),
        "Nenhum Source com name='Preduo' encontrado"
    )
    if sources.exists():
        src = sources.first()
        check(
            "Source.src_type = 'scraper'",
            src.src_type == "scraper",
            f"src_type={src.src_type!r}"
        )
except Exception as exc:
    check("Source Preduo sem exceção", False, str(exc))


# ── Limpeza ──────────────────────────────────────────────────────────────────
for pn in [TEST_PN_DRY, TEST_PN_REAL, TEST_PN_DEDUP, TEST_PN_OVW]:
    try:
        KnownPart.objects.filter(part_number=pn).delete()
    except Exception:
        pass


# ── Resultado ────────────────────────────────────────────────────────────────
print()
print("=" * 65)
if errors:
    print(f"  RESULTADO: {len(errors)} FALHA(S)")
    print()
    for e in errors:
        print(f"    - {e}")
    print()
    print("  Consulte a saída acima para detalhes de cada falha.")
else:
    print("  RESULTADO: TODOS OS TESTES PASSARAM ✅")
    print()
    print("  Fase 2 validada. Próximos passos:")
    print()
    print("  1. Executar scraping real (sem --dry-run):")
    print("       python manage.py scrape_preduo --type eMCP --type eMMC --limit 100")
    print()
    print("  2. Verificar PNs coletados no admin:")
    print("       python manage.py shell -c")
    print("       \"from chips.models import KnownPart; print(KnownPart.objects.filter(source__name='Preduo').count())\"")
    print()
    print("  3. Se Cloudflare bloquear, instale Playwright:")
    print("       pip install playwright && playwright install chromium")
    print("       python manage.py scrape_preduo --type eMCP")

print("=" * 65)
print()
