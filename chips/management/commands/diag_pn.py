"""
diag_pn.py
==========
Diagnóstico (SOMENTE LEITURA): para cada PN, mostra o que existe no banco e o que
o engine devolve. Serve para entender por que um PN é (ou não) reconhecido como
registro do banco — útil ao investigar "esse PN deixou de ser confirmado".

Para cada PN imprime:
  • KnownPart no banco (match exato e normalizado): confidence, chip_type, specs;
  • se o gate de visibilidade (_USABLE: tem specs OU é confirmed/manual) casa;
  • o resultado do classify(): known_exact, confidence, classification_source.

Uso (DATABASE_URL apontando ao banco que quer inspecionar):
    python manage.py diag_pn KMFN10012M SDIN7DU2-8G H9CKNNNDJTMP
    python manage.py diag_pn --file pns.txt
"""

import re

from django.core.management.base import BaseCommand
from django.db.models import Q


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").strip().upper())


def _has_specs(kp):
    return bool(kp.capacity or kp.emcp_ram or kp.emcp_nand or kp.density_gbit)


class Command(BaseCommand):
    help = "Diagnóstico read-only de um ou mais PNs: KnownPart no banco + saída do engine."

    def add_arguments(self, parser):
        parser.add_argument("pns", nargs="*", help="PNs a inspecionar.")
        parser.add_argument("--file", default="", help="Arquivo com um PN por linha.")

    def handle(self, *args, **opts):
        from chips.models import KnownPart
        from chips.engine import classify, _CONFIRMED_CONFIDENCE

        pns = list(opts["pns"])
        if opts["file"]:
            with open(opts["file"], encoding="utf-8") as fh:
                pns += [ln.strip() for ln in fh if ln.strip()]
        if not pns:
            self.stdout.write(self.style.ERROR("Informe ao menos um PN (ou --file)."))
            return

        for raw in pns:
            pn = _norm(raw)
            self.stdout.write("\n" + "═" * 64)
            self.stdout.write(f"PN digitado: {raw!r}  →  normalizado: {pn}")

            # Match exato + match por part_number normalizado (hífen/espaço no banco)
            kp = KnownPart.objects.filter(part_number=pn).first()
            if not kp:
                cand = (KnownPart.objects
                        .filter(Q(part_number__startswith=pn[:6]))
                        .exclude(part_number=pn))
                norm_match = next((k for k in cand if _norm(k.part_number) == pn), None)
                if norm_match:
                    kp = norm_match
                    self.stdout.write(f"  (match por normalização: banco tem '{kp.part_number}')")

            if kp:
                usable = _has_specs(kp) or kp.confidence in _CONFIRMED_CONFIDENCE
                self.stdout.write(f"  KnownPart no banco:  SIM (id={kp.id})")
                self.stdout.write(f"    confidence : {kp.confidence}")
                self.stdout.write(f"    chip_type  : {kp.chip_type!r}")
                self.stdout.write(f"    capacity   : {kp.capacity!r}")
                self.stdout.write(f"    emcp_ram   : {kp.emcp_ram!r}   emcp_nand: {kp.emcp_nand!r}")
                self.stdout.write(f"    density_gbit: {kp.density_gbit!r}")
                self.stdout.write(f"    tem specs? {_has_specs(kp)}   →  gate _USABLE casa? "
                                  + ("SIM ✓" if usable else "NÃO ✗ (some na camada 1)"))
                if not usable:
                    self.stdout.write(self.style.WARNING(
                        "    ⚠ Registro existe mas é placeholder vazio (sem specs e não confirmed/manual)."))
            else:
                self.stdout.write("  KnownPart no banco:  NÃO (nenhum registro p/ este PN)")

            r = classify(raw) or {}
            tag = self.style.SUCCESS if r.get("known_exact") else self.style.WARNING
            self.stdout.write("  classify():")
            self.stdout.write("    known_exact          : " + tag(str(r.get("known_exact"))))
            self.stdout.write(f"    confidence           : {r.get('confidence')}")
            self.stdout.write(f"    classification_source: {r.get('classification_source')}")
            self.stdout.write(f"    pn_not_in_db         : {r.get('pn_not_in_db')}")

        self.stdout.write("\n" + "═" * 64)
        self.stdout.write(
            "Leitura: se 'KnownPart no banco: SIM' mas 'gate _USABLE casa? NÃO', o "
            "registro é um placeholder vazio. Se confidence é distributor/estimated "
            "COM specs, agora ele é reconhecido (known_exact=True), mas a gramática "
            "completa ainda vence o valor — só confirmed/manual sobrepõem.")
