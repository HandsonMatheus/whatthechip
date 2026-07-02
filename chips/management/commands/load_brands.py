"""
load_brands.py
==============
**PASSO 4** do `docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`: o loader genérico do
conhecimento por marca. Substitui os `populate_<marca>` (gramática em código Python)
por **dados** em `chips/knowledge/<marca>.yaml`, validados pelo **portão Pydantic**
(`chips/knowledge/schema.py`) — onde as regras de ouro são validadores executáveis.

Fluxo: lê o YAML → `BrandFile(**yaml)` valida (erro claro em vez de bug no engine) →
upsert idempotente em `Brand` / `DecodeMap` / `ChipFamily` / `KnownPart` → **sobe o
`catalog_version`** (o engine recarrega o cache sozinho — não precisa reiniciar).

O upsert espelha o dos `populate_*` (get_or_create por chave natural; famílias por
`prefix`), então o catálogo gerado é **idêntico** — provado pela rede de regressão
(`characterize_baseline --diff`) e pelo teste de equivalência `LoadBrandsPiecemakersTests`.

Dry-run por padrão. `--commit` grava e, num terminal real, pede confirmação do banco
(SafeWriteCommand, passo 1C).

    python manage.py load_brands --brand piecemakers              # valida + mostra (não grava)
    python manage.py load_brands --brand piecemakers --commit     # grava + sobe catalog_version

PoC = PieceMakers (3 registros, limpo). NÃO aposente o `populate_<marca>` até a marca
passar 100% na regressão (existentes idênticos + amostra de PNs inéditos conferida).
"""

import os

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand

_KNOWLEDGE_DIR = os.path.join(settings.BASE_DIR, "chips", "knowledge")

# Mapas de densidade UNIVERSAIS (brand=None): o engine os lê por `map_name` sem filtrar
# marca (chips/engine.py::_decode_map_for_version), e são consumidos por `decode_density_type`
# — hoje SÓ a Samsung usa, mas a semântica é global. Criá-los com brand=<marca> geraria linha
# duplicada (o populate_samsung os criava com brand=None) e violaria o drop-in fiel. Mantidos
# globais aqui: get_or_create(brand=None) reusa a linha existente no prod. (Os dois nomes são os
# mesmos hard-coded no engine, então esta lista é o par fiel — não uma heurística frágil.)
_GLOBAL_MAPS = frozenset({"DRAM_PC", "DRAM_MOBILE"})

# Campos do YAML → ChipFamily (a brand é FK, vem do contexto; doc_page/is_documented
# ficam no default, igual aos populate_*).
_FAMILY_FIELDS = [
    "chip_type", "subtype", "interface", "is_emcp", "active", "priority", "pn_length",
    "decode_cap_pos", "decode_cap_len", "decode_cap_map", "decode_gen_pos",
    "decode_gen_map", "decode_gen_len", "decode_density_type", "suffix_rules",
    "tip", "reasoning",
]
# Campos do YAML → KnownPart (brand/family/source FK + part_number_norm derivado ficam fora).
_KNOWNPART_FIELDS = [
    "chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
    "emcp_nand", "interface", "fbga_code", "device", "notes", "source_url", "confidence",
]


class Command(SafeWriteCommand):
    help = ("Carrega o conhecimento de uma marca de chips/knowledge/<marca>.yaml "
            "(validado por Pydantic). Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument("--brand", required=True,
                            help="Nome do arquivo sem .yaml (ex.: piecemakers).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Só valida e mostra — não grava (é o padrão sem --commit).")
        parser.add_argument("--commit", action="store_true", help="Grava de verdade.")
        parser.add_argument("--skip-known-parts", action="store_true",
                            help="Carrega só a GRAMÁTICA (famílias+mapas), pula os known_parts. Usado "
                                 "nos testes de gramática (a autoridade/known_parts tem teste próprio).")

    def handle(self, *args, **opts):
        import yaml
        from pydantic import ValidationError

        from chips.knowledge.schema import BrandFile

        commit = bool(opts.get("commit")) and not opts.get("dry_run")
        path = os.path.join(_KNOWLEDGE_DIR, f"{opts['brand']}.yaml")
        if not os.path.exists(path):
            raise CommandError(f"Arquivo não encontrado: {path}")

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        # ── PORTÃO: validação Pydantic (regras de ouro como validadores) ──────
        try:
            spec = BrandFile(**raw)
        except ValidationError as e:
            linhas = "\n".join(
                f"   - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in e.errors())
            raise CommandError(f"{path} reprovou na validação:\n{linhas}")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{spec.brand.name}: {sum(len(v) for v in spec.maps.values())} entrada(s) de mapa, "
            f"{len(spec.families)} família(s), {len(spec.known_parts)} known_part(s)  ·  "
            f"{'COMMIT (gravando)' if commit else 'DRY-RUN (nada gravado)'}"))

        if not commit:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: validou OK. Nada foi gravado — use --commit para aplicar."))
            return

        with transaction.atomic():
            brand = self._upsert_brand(spec.brand)
            n_maps = self._upsert_maps(brand, spec.maps)
            n_fams = self._upsert_families(brand, spec.families)
            n_kp = 0 if opts.get("skip_known_parts") else self._upsert_known_parts(brand, spec.known_parts)

        from chips.models import CatalogVersion
        nova = CatalogVersion.bump()
        self.stdout.write(self.style.SUCCESS(
            f"✅ {brand.name}: {n_maps} entrada(s) de mapa, {n_fams} família(s), "
            f"{n_kp} known_part(s). catalog_version → {nova} (cache recarrega sozinho)."))

    # ── upserts (espelham os populate_*) ──────────────────────────────────────

    def _upsert_brand(self, b):
        from chips.models import Brand
        obj, created = Brand.objects.get_or_create(
            name=b.name, defaults={"code": b.code, "notes": b.notes})
        if not created and (obj.code != b.code or obj.notes != b.notes):
            obj.code, obj.notes = b.code, b.notes
            obj.save()
        return obj

    def _upsert_maps(self, brand, maps):
        from chips.models import DecodeMap
        n = 0
        for map_name, entries in maps.items():
            # mapas universais de densidade ficam com brand=None (drop-in fiel; ver _GLOBAL_MAPS)
            map_brand = None if map_name in _GLOBAL_MAPS else brand
            for e in entries:
                obj, created = DecodeMap.objects.get_or_create(
                    map_name=map_name, char_key=e.char_key, brand=map_brand,
                    defaults={"val_primary": e.val_primary, "val_secondary": e.val_secondary})
                if not created and (obj.val_primary != e.val_primary
                                    or obj.val_secondary != e.val_secondary):
                    obj.val_primary, obj.val_secondary = e.val_primary, e.val_secondary
                    obj.save()
                n += 1
        return n

    def _upsert_families(self, brand, families):
        from chips.models import ChipFamily
        n = 0
        for f in families:
            fam = ChipFamily.objects.filter(prefix=f.prefix).first() or ChipFamily(prefix=f.prefix)
            # Guard cross-brand: um prefixo é único GLOBAL e pertence a UMA marca. Se já
            # existe sob outra, é erro — não reatribui em silêncio (evita o clobber entre marcas).
            if fam.pk and fam.brand_id and fam.brand_id != brand.id:
                raise CommandError(
                    f"prefixo '{f.prefix}' já pertence à marca '{fam.brand.name}' — não pode "
                    f"ser declarado por '{brand.name}'. Prefixos são únicos globais.")
            fam.brand = brand
            for k in _FAMILY_FIELDS:
                setattr(fam, k, getattr(f, k))
            fam.save()
            n += 1
        return n

    def _upsert_known_parts(self, brand, kps):
        from chips.models import KnownPart
        n = 0
        for kp in kps:
            obj = (KnownPart.objects.filter(part_number=kp.part_number).first()
                   or KnownPart(part_number=kp.part_number))
            obj.brand = brand
            for k in _KNOWNPART_FIELDS:
                setattr(obj, k, getattr(kp, k))
            obj.save()
            n += 1
        return n
