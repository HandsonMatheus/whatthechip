"""
merge_toshiba_kioxia.py — consolida os brands **Toshiba + Kioxia + KIOXIA** numa
marca única **'Toshiba-Kioxia'** (code TXK). One-shot, REVERSÍVEL.

Contexto (CLAUDE.md §8): Toshiba Memory foi renomeada **Kioxia** em out/2019 —
mesma empresa, mesmas fábricas, mesmo esquema de PN (THGBM coexiste nas duas eras).
O banco tinha 3 brands (Toshiba/Kioxia + um 'KIOXIA' maiúsculo duplicado do antigo
add_chip_families), gerando ambiguidade de prefixo e duplicação. Esta migração
reatribui as famílias/KnownParts pro brand único e apaga os antigos.

**NÃO muda `classify`** — a marca não entra na saída do engine (nem no `_ident`,
nem no `_characterize_one`) → `characterize --diff` deve dar **IDÊNTICO**.

PRÉ-REQUISITO: rodar **`load_brands --brand toshiba-kioxia --commit`** ANTES (cria o
brand alvo + as 11 famílias canônicas + os mapas THGBM_CAP/GEN). Esta migração só
MOVE os KnownParts pro alvo e limpa os brands/famílias antigos.

Uso:
    python manage.py merge_toshiba_kioxia            # DRY-RUN (mostra o plano)
    python manage.py merge_toshiba_kioxia --commit   # grava (backup JSON antes)
    python manage.py merge_toshiba_kioxia --revert backup_merge_tk.json
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

TARGET_NAME = "Toshiba-Kioxia"
SOURCE_NAMES = ["Toshiba", "Kioxia", "KIOXIA"]

# Campos do ChipFamily capturados no backup (p/ recriar no --revert).
_FAM_FIELDS = [
    "prefix", "chip_type", "subtype", "interface", "is_emcp", "active", "priority",
    "pn_length", "decode_cap_pos", "decode_cap_len", "decode_cap_map", "decode_gen_pos",
    "decode_gen_map", "decode_gen_len", "decode_density_type", "suffix_rules", "tip", "reasoning",
]


class Command(BaseCommand):
    help = "Consolida Toshiba + Kioxia + KIOXIA → Toshiba-Kioxia (reversível)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true",
                            help="Grava (senão dry-run). Salva backup JSON antes.")
        parser.add_argument("--revert", metavar="BACKUP.json",
                            help="Desfaz uma consolidação a partir do backup JSON.")
        parser.add_argument("--backup", default="backup_merge_tk.json",
                            help="Arquivo de backup a gravar no --commit (default: backup_merge_tk.json).")

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["revert"])
        self._merge(opts["commit"], opts["backup"])

    # ── consolidação ─────────────────────────────────────────────────────────
    def _merge(self, commit, backup_path="backup_merge_tk.json"):
        from chips.models import Brand, ChipFamily, KnownPart, CatalogVersion

        try:
            target = Brand.objects.get(name=TARGET_NAME)
        except Brand.DoesNotExist:
            raise CommandError(
                f"Brand '{TARGET_NAME}' não existe. Rode PRIMEIRO:\n"
                f"    python manage.py load_brands --brand toshiba-kioxia --commit")

        tgt_fams = {f.prefix: f for f in ChipFamily.objects.filter(brand=target)}
        sources = list(Brand.objects.filter(name__in=SOURCE_NAMES).exclude(pk=target.pk))
        if not sources:
            self.stdout.write(self.style.SUCCESS("✅ Nada a consolidar (nenhum brand antigo)."))
            return

        tag = "" if commit else "[DRY] "
        # backup chaveado por NOME/prefixo (estável na ida e volta — pks mudam ao recriar)
        backup = {"target_name": TARGET_NAME, "knownparts": [], "families": [], "brands": []}
        moved_kp = deleted_fam = 0

        for src in sources:
            self.stdout.write(self.style.WARNING(f"\n── {src.name} (code={src.code}) ──"))
            # 1. reatribui KnownParts (brand + re-aponta family pelo prefixo)
            for kp in KnownPart.objects.filter(brand=src).select_related("family"):
                old_prefix = kp.family.prefix if kp.family_id else None
                new_fam = tgt_fams.get(old_prefix) if old_prefix else None
                backup["knownparts"].append(
                    {"pk": kp.pk, "old_brand_name": src.name, "old_family_prefix": old_prefix})
                self.stdout.write(
                    f"  {tag}KnownPart {kp.part_number}: brand→{TARGET_NAME}"
                    + (f", family {old_prefix}→alvo" if new_fam else
                       (f", family {old_prefix} SEM alvo (mantém)" if old_prefix else "")))
                if commit:
                    kp.brand = target
                    if new_fam:
                        kp.family = new_fam
                    kp.save(update_fields=["brand", "family"])
                moved_kp += 1
            # 2. apaga famílias (o alvo já tem a versão canônica); backup full-field
            for fam in ChipFamily.objects.filter(brand=src):
                if fam.prefix not in tgt_fams:
                    raise CommandError(
                        f"família {fam.prefix} ({src.name}) NÃO existe no alvo — rode "
                        f"load_brands toshiba-kioxia primeiro. ABORTADO p/ não perder dado.")
                backup["families"].append(
                    {**{k: getattr(fam, k) for k in _FAM_FIELDS}, "brand_name": src.name})
                self.stdout.write(f"  {tag}deleta família duplicada {fam.prefix}")
                if commit:
                    fam.delete()
                deleted_fam += 1
            # 3. apaga o brand (só se ficou vazio)
            backup["brands"].append({"name": src.name, "code": src.code, "notes": src.notes})
            if commit:
                if KnownPart.objects.filter(brand=src).exists() or ChipFamily.objects.filter(brand=src).exists():
                    self.stdout.write(self.style.ERROR(f"  ✗ {src.name} não ficou vazio — NÃO deletado"))
                else:
                    src.delete()
                    self.stdout.write(f"  🗑  brand {src.name} deletado")
            else:
                self.stdout.write(f"  {tag}deleta brand {src.name}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"KnownParts movidos: {moved_kp} · famílias dup deletadas: {deleted_fam} · brands: {len(sources)}"))
        if commit:
            path = backup_path
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(backup, fh, ensure_ascii=False, indent=1)
            nova = CatalogVersion.bump()
            self.stdout.write(self.style.SUCCESS(
                f"✅ Consolidado em '{TARGET_NAME}'. Backup: {path} (--revert desfaz). "
                f"catalog_version → {nova}."))
        else:
            self.stdout.write(self.style.WARNING("⚠  DRY-RUN — nada gravado. Use --commit."))

    # ── revert ───────────────────────────────────────────────────────────────
    def _revert(self, path):
        from chips.models import Brand, ChipFamily, KnownPart, CatalogVersion
        with open(path, encoding="utf-8") as fh:
            bk = json.load(fh)
        with transaction.atomic():
            # 1. recria os brands antigos (por nome)
            name2brand = {}
            for b in bk["brands"]:
                obj, _ = Brand.objects.get_or_create(
                    name=b["name"], defaults={"code": b["code"], "notes": b["notes"]})
                name2brand[b["name"]] = obj
            # 2. recria as famílias deletadas sob seus brands antigos
            pf2fam = {}
            for f in bk["families"]:
                brand = name2brand[f["brand_name"]]
                fields = {k: f[k] for k in _FAM_FIELDS}
                obj, _ = ChipFamily.objects.get_or_create(
                    prefix=fields["prefix"], brand=brand, defaults=fields)
                pf2fam[(f["brand_name"], fields["prefix"])] = obj
            # 3. re-aponta os KnownParts pro brand/family antigos (chaveado por nome/prefixo)
            n = 0
            for kp_bk in bk["knownparts"]:
                kp = KnownPart.objects.filter(pk=kp_bk["pk"]).first()
                if not kp:
                    continue
                kp.brand = name2brand[kp_bk["old_brand_name"]]
                if kp_bk["old_family_prefix"]:
                    kp.family = pf2fam.get((kp_bk["old_brand_name"], kp_bk["old_family_prefix"]))
                kp.save(update_fields=["brand", "family"])
                n += 1
            CatalogVersion.bump()
        self.stdout.write(self.style.SUCCESS(
            f"✅ Revertido: {len(name2brand)} brand(s), {len(pf2fam)} família(s), {n} KnownPart(s)."))
