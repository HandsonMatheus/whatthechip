"""
correct_known_parts.py — o PAR DE ESCRITA do audit_known_parts.
=================================================================
Corrige os known_parts confirmados STALE (spec gravado diverge da gramática JÁ
CORRIGIDA e Tier-1-verificada), gravando o valor da gramática no banco.

⚠ Use SEMPRE depois de revisar o `audit_known_parts` — a auditoria é mão dupla:
já aconteceu de a GRAMÁTICA estar errada e o BANCO certo (KMG P6). Este comando
assume que você JÁ conferiu que, para as famílias em escopo, a gramática é a
correta. Use --exclude para pular qualquer PN sobre o qual ainda tenha dúvida.

Travas (regra de ouro #1 / operações destrutivas):
  • Dry-run por PADRÃO (só mostra o que faria); --commit grava.
  • Escopo por --family — nunca toca no que não foi validado.
  • Só corrige campo cuja gramática é CONFIANTE (com capacidade, sem "não mapeada")
    e que DIFERE do banco (mesma lógica do audit).
  • Escreve pelo PORTÃO (KnownPart.save() → full_clean + normaliza + bump catalog_version).
  • BACKUP JSON reversível antes de gravar → --revert <json> desfaz.

Uso (localhost ou DATABASE_URL do alvo):
    python manage.py correct_known_parts --brand samsung --family KMD,KMG,KM4,KM5,KM8   # DRY-RUN
    python manage.py correct_known_parts --brand samsung --family KMD,KMG,KM4,KM5,KM8 --commit
    python manage.py correct_known_parts --exclude KMGP6001BM --family KMG --commit     # pula 1 PN
    python manage.py correct_known_parts --revert correct_kp_revert_20260706_2312.json  # desfaz
"""

import json
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from chips.models import KnownPart
from chips.engine import _match_family, _result_from_family
from chips.management.commands.audit_known_parts import _norm, _cap_only, _confident

# campo do KnownPart → chave no dict da gramática, + modo de comparação
_EMCP_FIELDS = [("emcp_ram", "emcp_ram", "full"), ("emcp_nand", "emcp_nand", "cap")]
_DISCRETE_FIELDS = [("capacity", "capacity", "full")]


class Command(BaseCommand):
    help = ("Corrige known_parts stale (spec diverge da gramática corrigida). "
            "Dry-run por padrão; --commit grava; --revert desfaz.")

    def add_arguments(self, parser):
        parser.add_argument("--brand", default="")
        parser.add_argument("--family", default="", help="Prefixos separados por vírgula. RECOMENDADO.")
        parser.add_argument("--all-emcp", action="store_true",
                            help="Todas as is_emcp (só quando TODAS estiverem corrigidas).")
        parser.add_argument("--confidence", default="confirmed,manual")
        parser.add_argument("--exclude", default="",
                            help="PNs a PULAR (vírgula) — ex: um que você ainda não confirmou.")
        parser.add_argument("--sync-subtype", action="store_true",
                            help="Também sincroniza o subtype ao da gramática (default: não).")
        parser.add_argument("--commit", action="store_true", help="Grava (senão, dry-run).")
        parser.add_argument("--revert", default="", help="JSON de reversão a desfazer.")
        parser.add_argument("--backup", default="", help="Caminho do JSON de backup (default: BASE_DIR/timestamp).")

    # ────────────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        w = self.stdout.write
        if o["revert"]:
            return self._revert(o["revert"], w)

        confs = tuple(c.strip() for c in o["confidence"].split(",") if c.strip())
        fam_prefixes = {f.strip().upper() for f in o["family"].split(",") if f.strip()}
        exclude = {p.strip().upper() for p in o["exclude"].split(",") if p.strip()}

        qs = KnownPart.objects.all()
        if confs:
            qs = qs.filter(confidence__in=confs)
        if o["brand"]:
            qs = qs.filter(brand__name__iexact=o["brand"])

        plan = []  # [(kp, [(field, old, new), ...])]
        for kp in qs.select_related("family", "brand").iterator():
            pn = kp.part_number
            if pn.upper() in exclude:
                continue
            fam = _match_family(pn) or kp.family
            if not fam:
                continue
            if o["all_emcp"]:
                if not fam.is_emcp:
                    continue
            elif fam_prefixes:
                if fam.prefix.upper() not in fam_prefixes:
                    continue
            try:
                g = _result_from_family(pn, fam)
            except Exception:
                continue

            fields = _EMCP_FIELDS if fam.is_emcp else _DISCRETE_FIELDS
            changes = []
            for db_field, gkey, mode in fields:
                db_val = (getattr(kp, db_field) or "").strip()
                gr_val = (g.get(gkey) or "").strip()
                if not _confident(gr_val) or not db_val:
                    continue
                same = (_cap_only(db_val) == _cap_only(gr_val)) if mode == "cap" \
                    else (_norm(db_val) == _norm(gr_val))
                if not same:
                    changes.append((db_field, db_val, gr_val))
            # opcional: subtype (só quando já vamos corrigir o registro)
            if changes and o["sync_subtype"]:
                gsub = (g.get("subtype") or "").strip()
                if gsub and _norm(gsub) != _norm(kp.subtype or ""):
                    changes.append(("subtype", (kp.subtype or "").strip(), gsub))
            if changes:
                plan.append((kp, changes))

        w("")
        if not plan:
            w("✓ Nenhum registro stale nas famílias em escopo. Nada a corrigir.")
            return
        w(f"{'PN':16} {'CAMPO':10} {'DE':24}    {'PARA':24}")
        w("-" * 80)
        for kp, changes in plan:
            for field, old, new in changes:
                w(f"{kp.part_number:16} {field:10} {old:24} → {new:24}")
        total = sum(len(c) for _, c in plan)
        w("")
        w(f"{len(plan)} registro(s) · {total} campo(s) a corrigir.")

        if not o["commit"]:
            w("\n[DRY-RUN] nada gravado. REVISE a lista acima (a gramática é a fonte). "
              "Rode com --commit para aplicar.")
            return

        db = settings.DATABASES["default"]
        w(f"\n⚠  BANCO-ALVO → name={db.get('NAME')}  host={db.get('HOST')}  — GRAVANDO")
        revert_log = []
        for kp, changes in plan:
            before = {}
            for field, old, new in changes:
                before[field] = getattr(kp, field) or ""
                setattr(kp, field, new)
            kp.save()  # PORTÃO: full_clean + normaliza + bump catalog_version (signal)
            revert_log.append({"part_number": kp.part_number, "before": before})

        path = o["backup"] or os.path.join(
            settings.BASE_DIR, f"correct_kp_revert_{datetime.now():%Y%m%d_%H%M%S}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(revert_log, fh, ensure_ascii=False, indent=0)
        w(f"\n✅ {len(plan)} registro(s) corrigido(s). Backup reversível: {path}")
        w(f"   Desfazer: python manage.py correct_known_parts --revert {path}")

    # ────────────────────────────────────────────────────────────────────
    def _revert(self, path, w):
        log = json.load(open(path, encoding="utf-8"))
        n = 0
        for row in log:
            try:
                kp = KnownPart.objects.get(part_number=row["part_number"])
            except KnownPart.DoesNotExist:
                continue
            for field, old in row["before"].items():
                setattr(kp, field, old)
            kp.save()
            n += 1
        w(f"↩  Revertido: {n} de {len(log)} registro(s) restaurado(s) de {path}.")
