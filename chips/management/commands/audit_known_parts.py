"""
audit_known_parts.py
====================
Audita os known_parts AUTORITATIVOS (confidence in confirmed/manual) contra a
GRAMÁTICA CORRIGIDA. **Read-only — só REPORTA divergências, nunca escreve.**

Por quê existe
--------------
Quando corrigimos a gramática de uma família (ex: KM2* de 4GB→6GB, KMG X6 2→3GB),
os known_parts confirmados que já estavam no banco com o valor ANTIGO (assados por
import/gramática velha) continuam VENCENDO a gramática (regra de ouro #2) — então o
fix da gramática fica INVISÍVEL pra esses PNs. Este comando acha esses registros
stale para que o dono os corrija (a correção é comando à parte, com --commit +
backup + revisão).

Como compara
------------
Para cada known_part, roda `_result_from_family(pn, fam)` — o decode PURO da
gramática, IGNORANDO o known_part — e compara com os specs gravados. Só marca
divergência quando a gramática tem valor CONFIANTE (tem capacidade, sem "não
mapeada") e ele DIFERE do banco. Se a gramática não decodifica (não mapeada), NÃO
marca — não queremos "corrigir" um valor confirmado para nada.

Escopo
------
Use `--family` para limitar às famílias JÁ CORRIGIDAS (seguro). `--all-emcp` audita
todas as is_emcp — só use quando TODAS estiverem corrigidas, senão gera ruído das
famílias ainda antigas.

Uso (DATABASE_URL apontando ao banco a inspecionar; roda DEPOIS do load_brands com
o yaml novo):
    python manage.py audit_known_parts --brand samsung --family KMD,KMG,KM4,KM5,KM8,KM2,KM2L,KM2P
    python manage.py audit_known_parts --family KM5 --out audit_km5.csv   # CSV p/ a correção
    python manage.py audit_known_parts --all-emcp                          # tudo (quando pronto)
"""

import csv
import re
from collections import Counter

from django.core.management.base import BaseCommand

from chips.models import KnownPart
from chips.engine import _match_family, _result_from_family

_CAP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([TGMK])B", re.I)
_UNMAPPED = ("não mapeada", "nao mapeada", "não mapeado", "nao mapeado",
             "consultar datasheet", "código não", "codigo nao")


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").strip().upper())


def _cap_only(s):
    """Só a capacidade (ex: '128GB') — compara NAND ignorando a versão da interface."""
    m = _CAP_RE.search(s or "")
    return f"{m.group(1)}{m.group(2).upper()}B" if m else ""


def _confident(s):
    """A gramática produziu valor REAL? (tem capacidade e não é 'não mapeada')."""
    s = s or ""
    if any(u in s.lower() for u in _UNMAPPED):
        return False
    return bool(_CAP_RE.search(s))


class Command(BaseCommand):
    help = "Audita known_parts confirmados vs gramática corrigida. Read-only (só reporta)."

    def add_arguments(self, parser):
        parser.add_argument("--brand", default="", help="Filtra por marca (nome).")
        parser.add_argument("--family", default="",
                            help="Prefixos de família separados por vírgula (ex: KM2,KM5). RECOMENDADO.")
        parser.add_argument("--all-emcp", action="store_true",
                            help="Audita TODAS as famílias is_emcp (só quando todas estiverem corrigidas).")
        parser.add_argument("--confidence", default="confirmed,manual",
                            help="Níveis a auditar (default: confirmed,manual).")
        parser.add_argument("--out", default="", help="Grava CSV das divergências (p/ a etapa de correção).")
        parser.add_argument("--list", type=int, default=0, help="Máximo de linhas a mostrar (0=todas).")

    def handle(self, *args, **o):
        confs = tuple(c.strip() for c in o["confidence"].split(",") if c.strip())
        fam_prefixes = {f.strip().upper() for f in o["family"].split(",") if f.strip()}

        qs = KnownPart.objects.all()
        if confs:
            qs = qs.filter(confidence__in=confs)
        if o["brand"]:
            qs = qs.filter(brand__name__iexact=o["brand"])

        rows = []
        audited = matched = skipped = 0
        by_family = Counter()
        for kp in qs.select_related("family", "brand").iterator():
            pn = kp.part_number
            fam = _match_family(pn) or kp.family
            if not fam:
                continue
            # ── escopo ──
            if o["all_emcp"]:
                if not fam.is_emcp:
                    continue
            elif fam_prefixes:
                if fam.prefix.upper() not in fam_prefixes:
                    continue
            # (sem escopo explícito: audita tudo que casou brand/confidence)

            audited += 1
            try:
                g = _result_from_family(pn, fam)
            except Exception:
                skipped += 1
                continue

            if fam.is_emcp:
                checks = [("emcp_ram", kp.emcp_ram, g.get("emcp_ram"), "full"),
                          ("emcp_nand", kp.emcp_nand, g.get("emcp_nand"), "cap")]
            else:
                checks = [("capacity", kp.capacity, g.get("capacity"), "full")]

            flagged = False
            for field, db_val, gr_val, mode in checks:
                if not _confident(gr_val):          # gramática sem valor confiável → não marca
                    continue
                if not (db_val or "").strip():       # banco vazio → falta de dado, não "stale"
                    continue
                same = (_cap_only(db_val) == _cap_only(gr_val)) if mode == "cap" \
                    else (_norm(db_val) == _norm(gr_val))
                if not same:
                    rows.append((pn, fam.prefix, field, (db_val or "").strip(),
                                 (gr_val or "").strip(), kp.confidence))
                    by_family[fam.prefix] += 1
                    flagged = True
            if not flagged:
                matched += 1

        w = self.stdout.write
        w("")
        w(f"Auditados: {audited} known_part(s)  ·  DIVERGENTES: {len(rows)}  ·  ok: {matched}"
          + (f"  ·  pulados (erro decode): {skipped}" if skipped else ""))
        if by_family:
            w("Por família: " + " · ".join(f"{k}={v}" for k, v in sorted(by_family.items())))
        w("")
        if rows:
            w(f"{'PN':16} {'FAMÍLIA':8} {'CAMPO':10} {'BANCO':24} {'GRAMÁTICA':24} conf")
            w("-" * 96)
            limit = o["list"] or len(rows)
            for r in rows[:limit]:
                w(f"{r[0]:16} {r[1]:8} {r[2]:10} {r[3]:24} {r[4]:24} {r[5]}")
            if len(rows) > limit:
                w(f"... (+{len(rows) - limit} — use --list 0 p/ ver todas)")
        else:
            w("✓ Nenhuma divergência: os known_parts confirmados batem com a gramática corrigida.")
        w("")
        w("READ-ONLY: nada foi gravado. Correção = comando à parte (dry-run + backup + revisão do dono).")

        if o["out"] and rows:
            with open(o["out"], "w", newline="") as fh:
                cw = csv.writer(fh)
                cw.writerow(["part_number", "family", "field", "db_value", "grammar_value", "confidence"])
                cw.writerows(rows)
            w(f"CSV gravado: {o['out']} ({len(rows)} linha(s)) — insumo da correção.")
