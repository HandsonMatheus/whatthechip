# -*- coding: utf-8 -*-
"""
audit_type_vs_family.py  —  Fase 0 / sonda 5 (PLANO_MICRON_IDENTITY_ONLY_FASE2.md)
=================================================================================
READ-ONLY. Dimensiona o risco da Fase B (ligar o override de ``chip_type`` do
known_part confirmado/manual sobre a família): conta, por família, os registros
``confirmed``/``manual`` em que ``known.chip_type`` DIFERE do tipo que o engine
mostra HOJE (o da família, já considerando o override BUG-3 por ``source_url``).

Esses são EXATAMENTE os PNs cujo tipo na tela vai MUDAR quando a Fase B entrar —
ou seja, a **allowlist** a que o ``characterize_baseline --diff`` deve ficar
restrito no commit da Fase B (qualquer PN fora desta lista mudando = investigar).

NÃO escreve nada. Não é o ``fix_micron_type_from_api`` (aquele corrige o dado);
este só MEDE, pra decidir D5 com número na mão. Rode com o DATABASE_URL do
banco-alvo, DEPOIS do ``load_brands --commit`` (a gramática precisa estar carregada).

Uso:
    python manage.py audit_type_vs_family                 # todas as marcas
    python manage.py audit_type_vs_family --brand Micron  # só Micron
    python manage.py audit_type_vs_family --csv var/audit_type_vs_family.csv
"""
import csv
import os
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from chips.models import KnownPart
from chips.engine import _match_family, classify, is_dead_by_generation

try:
    from chips.chip_types import canonical_chip_type as _canon
except Exception:  # fallback: comparação crua
    def _canon(ct, sub=""):
        return (ct or "").strip()


def _effective_current_type(kp, fam) -> str:
    """O chip_type que o engine EXIBE hoje p/ este PN (família + override BUG-3).

    Espelha chips/engine.py::_result_from_known: quando a família é MCP e o
    known.source_url aponta ufs/emmc-based-mcp, o engine JÁ sobrescreve o tipo.
    Fora disso, vale o tipo da família."""
    if fam and getattr(fam, "is_emcp", False) and kp.source_url:
        src = kp.source_url
        if "ufs-based-mcp" in src:
            return "uMCP"
        if "emmc-based-mcp" in src:
            return "eMCP"
    return (fam.chip_type if fam else "") or ""


class Command(BaseCommand):
    help = ("READ-ONLY: mede, por família, os confirmed/manual cujo known.chip_type "
            "difere do tipo exibido hoje (allowlist da Fase B). Não grava nada.")

    def add_arguments(self, parser):
        parser.add_argument("--brand", default="", help="Filtra por marca (nome).")
        parser.add_argument("--confidence", default="confirmed,manual",
                            help="Confidences a auditar (default: confirmed,manual).")
        parser.add_argument("--csv", default="", help="Grava a lista completa de divergências.")

    def handle(self, *args, **o):
        w = self.stdout.write
        confs = tuple(c.strip() for c in o["confidence"].split(",") if c.strip())

        qs = KnownPart.objects.filter(confidence__in=confs)
        if o["brand"]:
            qs = qs.filter(brand__name__iexact=o["brand"])
        qs = qs.select_related("family", "brand")

        per_fam_total = Counter()          # confirmed/manual COM família, por família
        per_fam_mism = Counter()           # divergências, por família
        rows = []                          # divergências detalhadas
        no_family = 0
        no_known_type = 0

        for kp in qs.iterator():
            fam = _match_family(kp.part_number) or kp.family
            if not fam:
                no_family += 1
                continue
            per_fam_total[fam.prefix] += 1
            known_ct = (kp.chip_type or "").strip()
            if not known_ct:
                no_known_type += 1
                continue
            current = _effective_current_type(kp, fam)
            if _canon(known_ct) == _canon(current):
                continue
            # DIVERGE → vai mudar na Fase B. Tagueia liveness pra priorizar.
            try:
                dead = is_dead_by_generation(classify(kp.part_number))
            except Exception:
                dead = None
            per_fam_mism[fam.prefix] += 1
            rows.append({
                "part_number": kp.part_number,
                "brand": kp.brand.name if kp.brand else "",
                "family": fam.prefix,
                "known_chip_type": known_ct,
                "current_shown_type": current,
                "confidence": kp.confidence,
                "fbga_code": kp.fbga_code or "",
                "dead_by_generation": "" if dead is None else ("SIM" if dead else "NAO"),
                "source_url": kp.source_url or "",
            })

        rows.sort(key=lambda r: (r["dead_by_generation"] == "SIM", r["brand"], r["family"], r["part_number"]))

        # ── Relatório ──
        w("")
        w(f"Auditados ({'/'.join(confs)}): {qs.count()}  ·  sem família: {no_family}  ·  "
          f"sem chip_type próprio: {no_known_type}")
        w(f"DIVERGÊNCIAS (tipo vai mudar na Fase B): {len(rows)}")
        vivos = sum(1 for r in rows if r["dead_by_generation"] == "NAO")
        w(f"  vivos (mudança RELEVANTE): {vivos}  ·  dead-by-gen (mudança inócua): {len(rows) - vivos}")
        if per_fam_mism:
            w("\nPor família (divergências / total confirmed-manual com família):")
            for fam, n in per_fam_mism.most_common():
                w(f"  {fam:12s} {n:4d} / {per_fam_total[fam]}")
        # transições de tipo mais comuns
        trans = Counter(f"{r['current_shown_type'] or '∅'} → {r['known_chip_type']}" for r in rows)
        if trans:
            w("\nTransições (tipo_hoje → tipo_known):")
            for t, n in trans.most_common():
                w(f"  {t:26s} {n}")

        if o["csv"] and rows:
            os.makedirs(os.path.dirname(o["csv"]) or ".", exist_ok=True)
            with open(o["csv"], "w", newline="", encoding="utf-8") as fh:
                wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                wr.writeheader()
                wr.writerows(rows)
            w(f"\nLista completa → {o['csv']}  (é a ALLOWLIST do characterize --diff da Fase B)")
        w("\nREAD-ONLY: nada foi gravado no banco.")
