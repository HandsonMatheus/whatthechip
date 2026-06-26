"""
audit_targets
=============
Lê um CSV de correções (errado,certo) e, para cada PN destino (`certo`), consulta
o banco AO VIVO: existe KnownPart? qual confidence? o que o engine devolve?
Classifica cada um em CONFIRMADO / GRAMÁTICA / NÃO-VISÍVEL / AUSENTE e reescreve o
CSV com colunas de status. Somente LEITURA do banco (não grava nada no DB).

Buckets:
  CONFIRMADO    → KnownPart confidence ∈ confirmed|manual (vence a gramática)
  NÃO-VISÍVEL   → KnownPart existe mas não é confirmed|manual (engine o ignora como autoridade)
  GRAMÁTICA     → sem KnownPart confirmado; engine reconhece pela gramática da família
  AUSENTE       → engine não reconhece o PN (nem banco nem gramática)

Uso (DATABASE_URL apontando ao Render para checar produção):
    python manage.py audit_targets --file correcoes_samsung_fuzzy.csv
    python manage.py audit_targets --file correcoes_samsung_fuzzy.csv --out status.csv
"""

import csv
import os
import re

from django.core.management.base import BaseCommand, CommandError

from chips.engine import classify
from chips.models import KnownPart

CONFIRMED_CONF = {"confirmed", "manual"}


def _norm(raw):
    return re.sub(r"[^A-Z0-9]", "", (raw or "").strip().upper())


def _bucket(certo):
    pn = _norm(certo)
    kp = KnownPart.objects.filter(part_number=pn).first()
    r = classify(certo) or {}
    src = r.get("classification_source") or ""
    conf = kp.confidence if kp else ""
    # Visibilidade do KnownPart para o engine: autoridade (vence a gramática),
    # ignorado (existe mas não confirmado) ou ausente. Substitui o antigo kp.status.
    kp_visib = "ausente" if not kp else ("autoridade" if kp.confidence in CONFIRMED_CONF else "ignorado")
    cap = r.get("capacity") or (f"{r.get('emcp_nand','')} / {r.get('emcp_ram','')}".strip(" /")) or ""

    if kp and kp.confidence in CONFIRMED_CONF:
        bucket = "CONFIRMADO"
    elif kp:
        bucket = "NAO-VISIVEL"
    elif src == "banco de dados":
        bucket = "CONFIRMADO"
    elif "gramática" in src or "gramatica" in src:
        bucket = "GRAMATICA"
    else:
        bucket = "AUSENTE"
    return bucket, conf, kp_visib, src or "—", cap


class Command(BaseCommand):
    help = "Checa no banco (ao vivo) o status de cada PN destino de um CSV de correções. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="CSV errado,certo[,...].")
        parser.add_argument("--out", type=str, default="", help="CSV de saída (default: sobrescreve o de entrada).")

    def handle(self, *args, **opts):
        path = opts["file"]
        if not os.path.exists(path):
            raise CommandError(f"CSV não encontrado: {path}")

        rows = []
        with open(path, encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if not row or not row[0].strip():
                    continue
                if row[0].strip().lower() in ("errado", "wrong", "pn"):
                    continue
                wrong = row[0].strip()
                correct = row[1].strip() if len(row) > 1 and row[1].strip() else wrong
                rows.append((wrong, correct))

        out_rows = [("errado", "certo", "status_alvo", "confidence", "visib_kp", "fonte_engine", "capacidade")]
        counts = {}
        self.stdout.write("")
        self.stdout.write(f"{'CERTO (alvo)':<16}{'STATUS':<13}{'conf':<11}{'visib_kp':<12}{'fonte_engine'}")
        self.stdout.write("-" * 74)
        for wrong, correct in rows:
            bucket, conf, kp_visib, src, cap = _bucket(correct)
            counts[bucket] = counts.get(bucket, 0) + 1
            tag = {"CONFIRMADO": self.style.SUCCESS, "GRAMATICA": self.style.WARNING}.get(bucket, self.style.ERROR)
            self.stdout.write(f"{correct:<16}{tag(f'{bucket:<12}')} {(conf or '—'):<11}{kp_visib:<12}{src}")
            out_rows.append((wrong, correct, bucket, conf or "", kp_visib, src, cap))

        out = opts["out"] or path
        with open(out, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerows(out_rows)

        self.stdout.write("-" * 74)
        resumo = "  ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        self.stdout.write(self.style.SUCCESS(f"Resumo → {resumo}"))
        self.stdout.write(f"CSV atualizado: {out}")
