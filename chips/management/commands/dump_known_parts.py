"""
dump_known_parts.py — exporta os KnownParts CURADOS do fix_known_parts para o YAML
declarativo de cada marca (bloco `known_parts`), fechando a migração da AUTORIDADE.

Filosofia (a mesma da gramática): NÃO porta as 600 entradas CORRECTIONS (o histórico
de como o banco chegou aqui) — dumpa o **estado atual** do KnownPart de cada PN (o
resultado). Assim não precisa replicar a lógica do motor (fields×create_defaults,
promoção de confidence, fallbacks): tudo já está "assado" no registro final.

Escopo: só os PNs listados em `fix_known_parts.CORRECTIONS` (a autoridade hand-crafted).
Os KnownParts vindos dos imports (PSG/Micron) ficam como estão.

Proveniência: a `reason` de cada entrada (com fontes Tier-1) é preservada no campo
`notes` do known_part (mesclada com o notes existente) — o conhecimento não se perde
quando o fix_known_parts.py for removido.

**characterize IDÊNTICO:** o dump é fiel (campos do banco como estão) — a FONTE migra de
Python p/ YAML, o dado não muda. (A normalização da convenção nos known_parts é fase
separada e revisada, igual foi na gramática.)

Uso:
    python manage.py dump_known_parts                 # DRY-RUN (só conta, não escreve)
    python manage.py dump_known_parts --write         # grava nos yamls das marcas
    python manage.py dump_known_parts --write --out-dir /tmp/kp   # grava noutro dir (teste)
"""
import os
import re as _re

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand

_KNOWLEDGE_DIR = os.path.join(settings.BASE_DIR, "chips", "knowledge")

# Campos do KnownPart exportados (espelham _KNOWNPART_FIELDS do load_brands + part_number).
_DUMP_FIELDS = [
    "chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
    "emcp_nand", "interface", "fbga_code", "device", "notes", "source_url", "confidence",
]


class _FlowList(list):
    """Marca listas p/ dump em flow-style (as entradas de mapa; não usado aqui, mas
    mantém o dumper consistente com os yamls existentes)."""


def _represent_flowlist(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


yaml.add_representer(_FlowList, _represent_flowlist, Dumper=yaml.SafeDumper)


class Command(BaseCommand):
    help = "Exporta os KnownParts curados (fix_known_parts) → known_parts nos yamls das marcas."

    def add_arguments(self, parser):
        parser.add_argument("--write", action="store_true",
                            help="Grava nos yamls (senão só conta — dry-run).")
        parser.add_argument("--out-dir", default=_KNOWLEDGE_DIR,
                            help="Diretório de saída (default: chips/knowledge).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart
        from chips.management.commands.fix_known_parts import CORRECTIONS

        # 1. PN normalizado → reason (proveniência curada)
        def _norm(pn):
            return _re.sub(r"[^A-Z0-9]", "", pn.upper())
        pn2reason = {}
        for entry in CORRECTIONS:
            pn2reason[_norm(entry["pn"])] = entry.get("reason", "")
        alvo_pns = set(pn2reason)
        self.stdout.write(f"PNs curados no fix_known_parts: {len(alvo_pns)}")

        # 2. mapa brand.name → slug do yaml (robusto: lê o brand.name de cada arquivo)
        name2slug = {}
        for fn in os.listdir(_KNOWLEDGE_DIR):
            if not fn.endswith(".yaml"):
                continue
            with open(os.path.join(_KNOWLEDGE_DIR, fn), encoding="utf-8") as fh:
                y = yaml.safe_load(fh) or {}
            nome = (y.get("brand") or {}).get("name")
            if nome:
                name2slug[nome] = fn[:-5]

        # 3. dumpa o estado ATUAL do KnownPart de cada PN alvo, agrupado por marca
        por_marca = {}          # slug → list[dict]
        achados = ausentes = sem_marca = 0
        for kp in (KnownPart.objects.filter(part_number__in=alvo_pns)
                   .select_related("brand")):
            achados += 1
            slug = name2slug.get(kp.brand.name if kp.brand else None)
            if not slug:
                sem_marca += 1
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ {kp.part_number}: marca {kp.brand.name if kp.brand else None!r} "
                    f"sem yaml — pulado."))
                continue
            rec = {"part_number": kp.part_number}
            for f in _DUMP_FIELDS:
                rec[f] = getattr(kp, f)
            # proveniência: mescla a reason curada no notes (sem perder o notes do banco)
            reason = pn2reason.get(kp.part_number, "")
            db_notes = (rec.get("notes") or "").strip()
            if reason and reason not in db_notes:
                rec["notes"] = (f"{db_notes} | {reason}" if db_notes else reason)
            por_marca.setdefault(slug, []).append(rec)
        ausentes = len(alvo_pns) - achados

        self.stdout.write(
            f"KnownParts achados no banco: {achados} · ausentes: {ausentes} · "
            f"sem yaml de marca: {sem_marca}")
        for slug in sorted(por_marca):
            self.stdout.write(f"  {slug}: {len(por_marca[slug])} known_parts")

        if not opts["write"]:
            self.stdout.write(self.style.WARNING("\n⚠  DRY-RUN — nada gravado. Use --write."))
            return

        # 4. grava: lê o yaml da marca, substitui o bloco known_parts, reescreve
        os.makedirs(opts["out_dir"], exist_ok=True)
        for slug, recs in sorted(por_marca.items()):
            src = os.path.join(_KNOWLEDGE_DIR, f"{slug}.yaml")
            with open(src, encoding="utf-8") as fh:
                head = "".join(l for l in fh if l.lstrip().startswith("#"))
            with open(src, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            recs_sorted = sorted(recs, key=lambda r: r["part_number"])
            data["known_parts"] = [
                {k: v for k, v in r.items() if v not in ("", None)} for r in recs_sorted]
            out = os.path.join(opts["out_dir"], f"{slug}.yaml")
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(head)
                yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True,
                               default_flow_style=False, width=100000)
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ {out}: {len(recs_sorted)} known_parts gravados"))
        self.stdout.write(self.style.SUCCESS("\n✅ Dump concluído."))
