"""
restore_known_parts.py — recuperação EMERGENCIAL dos known_parts a partir de um
JSON extraído do backup (Export) do prod.

Preenche as LACUNAS de known_parts no banco: cria os que ainda NÃO existem (chave =
part_number normalizado), mapeando a marca (Toshiba/Kioxia/KIOXIA → Toshiba-Kioxia) e
religando a família por prefixo. NÃO sobrescreve o que já existe — o dado curado do
yaml/PSG VENCE. Dedupa pela chave normalizada, mantendo a MAIOR confiança.

Uso (rodar LOCALMENTE apontando DATABASE_URL ao prod):
    python manage.py restore_known_parts _restore_kp.json            # dry-run
    python manage.py restore_known_parts _restore_kp.json --commit   # grava + sobe catalog_version
"""
import json

from django.core.management.base import BaseCommand
from django.db import transaction

_CONF_RANK = {"confirmed": 3, "manual": 2, "distributor": 1, "estimated": 0}
_BRAND_ALIAS = {"Toshiba": "Toshiba-Kioxia", "Kioxia": "Toshiba-Kioxia", "KIOXIA": "Toshiba-Kioxia"}
_FIELDS = ("chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
           "emcp_nand", "interface", "device", "notes", "source_url", "fbga_code")


class Command(BaseCommand):
    help = "Recupera known_parts de um JSON de backup, preenchendo as lacunas do banco."

    def add_arguments(self, parser):
        parser.add_argument("json_file")
        parser.add_argument("--commit", action="store_true",
                            help="Grava de verdade (sem isto é dry-run).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart, ChipFamily, Brand, CatalogVersion
        from chips.normalize import normalize_pn
        from chips.knowledge.convention import apply_kp_convention

        commit = opts["commit"]
        rows = json.load(open(opts["json_file"], encoding="utf-8"))
        # maior confiança primeiro → o dedup mantém a melhor
        rows.sort(key=lambda r: _CONF_RANK.get(r.get("confidence"), 0), reverse=True)

        brands = {b.name: b for b in Brand.objects.all()}
        fams = sorted(ChipFamily.objects.all(), key=lambda f: -len(f.prefix))

        def match_family(pnn):
            for f in fams:
                if f.prefix and pnn.startswith(f.prefix.upper()):
                    return f
            return None

        ja_no_banco = set(KnownPart.objects.values_list("part_number_norm", flat=True))
        seen, novos = set(), []
        criados = mantidos = dup_backup = sem_marca = 0
        marcas_faltando = set()

        for r in rows:
            pn = (r.get("part_number") or "").strip()
            if not pn:
                continue
            pnn = normalize_pn(pn)
            if pnn in ja_no_banco:
                mantidos += 1
                continue
            if pnn in seen:
                dup_backup += 1
                continue
            nome = _BRAND_ALIAS.get(r.get("brand"), r.get("brand"))
            brand = brands.get(nome)
            if brand is None:
                sem_marca += 1
                marcas_faltando.add(r.get("brand"))
                continue
            seen.add(pnn)
            kp = KnownPart(part_number=pn, part_number_norm=pnn, brand=brand,
                           family=match_family(pnn),
                           confidence=r.get("confidence") or "confirmed",
                           **{f: (r.get(f) or "") for f in _FIELDS})
            apply_kp_convention(kp)   # bulk_create pula o clean() → normaliza aqui (subtype/interface/'None')
            novos.append(kp)
            criados += 1

        self.stdout.write(
            f"A criar: {criados}  ·  já existiam (mantidos): {mantidos}  ·  "
            f"dups no backup: {dup_backup}  ·  sem marca: {sem_marca}")
        if marcas_faltando:
            self.stdout.write(self.style.WARNING(f"  marcas não encontradas no banco: {sorted(marcas_faltando)}"))

        if not commit:
            self.stdout.write(self.style.WARNING("DRY-RUN — nada gravado. Use --commit para aplicar."))
            return

        with transaction.atomic():
            KnownPart.objects.bulk_create(novos, batch_size=500)
        v = CatalogVersion.bump()
        self.stdout.write(self.style.SUCCESS(
            f"✓ {criados} known_parts restaurados. catalog_version → {v}. O engine recarrega sozinho."))
