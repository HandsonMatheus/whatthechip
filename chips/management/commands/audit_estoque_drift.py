"""
audit_estoque_drift.py
======================
Varre o estoque (InventoryEntry) e, para cada PN, responde de forma objetiva por
que ele é (ou não) reconhecido como registro do banco AGORA. Read-only.

Três baldes:
  RECONHECIDO     → classify() devolve known_exact=True (engine vê como banco). OK.
  KP-NÃO-RECON ⚠  → EXISTE KnownPart para o PN, mas o engine NÃO o reconhece.
                    Isso é problema de GATE (bug a corrigir). Lista confidence+specs.
  SEM-KP          → não existe KnownPart para o PN (apagado pelo purge ou nunca
                    teve registro — questão de DADO, não de gate).

A coluna 'antes (estoque)' mostra o classification_source gravado no InventoryEntry
no momento do lançamento — se era 'banco de dados' e agora não reconhece, é deriva.

Uso (DATABASE_URL apontando ao banco que quer inspecionar):
    python manage.py audit_estoque_drift
    python manage.py audit_estoque_drift --lot 39
    python manage.py audit_estoque_drift --list 60        # lista mais exemplos
"""

import re

from django.core.management.base import BaseCommand


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").strip().upper())


def _has_specs(kp):
    return bool(kp.capacity or kp.emcp_ram or kp.emcp_nand or kp.density_gbit)


class Command(BaseCommand):
    help = "Audita o estoque: quantos PNs o engine ainda reconhece como banco vs gramática. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=0, help="Só um lote (default: todos).")
        parser.add_argument("--list", type=int, default=40, help="Quantos exemplos KP-NÃO-RECON listar.")

    def handle(self, *args, **opts):
        from estoque.models import InventoryEntry
        from chips.models import KnownPart
        from chips.engine import classify

        qs = InventoryEntry.objects.all()
        if opts["lot"]:
            qs = qs.filter(lot__number=opts["lot"])

        # PN único → classification_source gravado (pega o primeiro que aparecer)
        stored = {}
        for e in qs.values("part_number", "classification_source"):
            stored.setdefault(e["part_number"], e["classification_source"] or "")

        recon = kp_nao_recon = sem_kp = 0
        era_banco_virou_gram = 0
        gate_bugs = []   # (pn, confidence, has_specs, stored_src)
        sem_kp_list = []

        for pn, src_antes in stored.items():
            norm = _norm(pn)
            kp = KnownPart.objects.filter(part_number=norm).first()
            if not kp and norm != pn:
                kp = KnownPart.objects.filter(part_number=pn).first()
            r = classify(pn) or {}
            is_recon = bool(r.get("known_exact"))

            if is_recon:
                recon += 1
            elif kp:
                kp_nao_recon += 1
                gate_bugs.append((pn, kp.confidence, _has_specs(kp), src_antes))
            else:
                sem_kp += 1
                if src_antes == "banco de dados":
                    era_banco_virou_gram += 1
                if len(sem_kp_list) < 12:
                    sem_kp_list.append((pn, src_antes))

        total = len(stored)
        self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.stdout.write(f"  PNs únicos no estoque        : {total}")
        self.stdout.write(f"  RECONHECIDO (known_exact)    : {recon}")
        self.stdout.write(self.style.WARNING(
            f"  KP-NÃO-RECON (bug de gate ⚠)  : {kp_nao_recon}"))
        self.stdout.write(f"  SEM-KP (questão de dado)     : {sem_kp}")
        self.stdout.write(f"     dos quais 'antes=banco de dados' (deriva): {era_banco_virou_gram}")
        self.stdout.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if gate_bugs:
            self.stdout.write(self.style.WARNING(
                "⚠ EXISTE KnownPart mas o engine NÃO reconhece (corrigir o gate):"))
            self.stdout.write(f"  {'PN':24s} {'confidence':12s} {'tem_specs':9s} antes(estoque)")
            # prioriza mostrar a variedade de confidence
            for pn, conf, spec, src in gate_bugs[: opts["list"]]:
                self.stdout.write(f"  {pn:24s} {conf:12s} {str(spec):9s} {src}")
            if len(gate_bugs) > opts["list"]:
                self.stdout.write(f"  ... (+{len(gate_bugs) - opts['list']})")
            # resumo por confidence dos bugados
            from collections import Counter
            byc = Counter((c, s) for _, c, s, _ in gate_bugs)
            self.stdout.write("  resumo (confidence, tem_specs → n): "
                              + ", ".join(f"{k}→{v}" for k, v in byc.items()))

        if sem_kp_list:
            self.stdout.write("\nSEM-KP (sem registro no banco — exemplos):")
            for pn, src in sem_kp_list:
                self.stdout.write(f"  {pn:24s} antes(estoque)={src!r}")

        self.stdout.write(self.style.SUCCESS(
            "\nLeitura: se KP-NÃO-RECON > 0 → é bug de gate, me manda o resumo que eu "
            "ajusto o engine. Se o grosso é SEM-KP → os registros foram apagados/nunca "
            "existiram (recuperação por restore_purge / criação por fix_known_parts)."))
