"""
characterize_baseline.py
========================
Rede de regressão do refactor de escalabilidade — **PASSO 0** do
`docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`. É o trilho de segurança de TODO
passo que toca o engine.

O QUE FAZ (READ-ONLY): roda o banco inteiro (todos os `KnownPart`) pelo pipeline
real — `classify()` → `assess_profitability()` → `_compute_destination()` (label
da caixa) → `is_dead_by_generation()` — e captura, por PN, os campos de saída.
**Não persiste nada**: como `classify()` grava em `SearchLog`/`UnknownChip`, toda
a execução roda dentro de uma transação que é **revertida** no fim (padrão
dry-run). Seguro rodar contra produção.

DOIS MODOS:
  --out  ARQUIVO   (snapshot)  grava o baseline "antes" (1 entrada por PN)
  --diff ARQUIVO   (regressão) roda de novo e compara: lista cada PN cujo
                               qualquer campo de saída mudou (+ adicionados/removidos)

USO:
    # ANTES de um refactor (gera o baseline)
    python manage.py characterize_baseline --out baseline_antes.json
    # DEPOIS do refactor (exige saída idêntica, salvo o esperado)
    python manage.py characterize_baseline --diff baseline_antes.json

RODAR LOCAL sem o Postgres de produção (ver §Passo 0 do plano): carregue o
`prod_data.json` (fixture dumpdata) num SQLite descartável e rode contra ele:
    export DATABASE_URL="sqlite:////tmp/wtc_baseline.sqlite3"
    python manage.py migrate --noinput
    python manage.py loaddata prod_data.json        # ou um subconjunto chips.*
    python manage.py characterize_baseline --out baseline_antes.json
"""

import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class _Rollback(Exception):
    """Sentinela para reverter a transação (desfaz as escritas de log do classify)."""


# Campos de saída capturados por PN — estáveis e suficientes: o que todo refactor
# que preserva comportamento NÃO pode alterar (classificação + rentabilidade + label).
def _characterize_one(pn: str) -> dict:
    from chips.engine import classify, assess_profitability, is_dead_by_generation

    r = classify(pn) or {}
    out = {
        "chip_type":             r.get("chip_type") or "",
        "subtype":               r.get("subtype") or "",
        "capacity":              r.get("capacity") or "",
        "emcp_ram":              r.get("emcp_ram") or "",
        "emcp_nand":             r.get("emcp_nand") or "",
        "density_gbit":          r.get("density_gbit") or "",
        "dram_density":          r.get("dram_density") or "",
        "interface":             r.get("interface") or "",
        "is_emcp":               bool(r.get("is_emcp")),
        "classification_source": r.get("classification_source") or "",
        "confidence":            r.get("confidence") or "",
        "remarked_flag":         bool(r.get("remarked_flag")),
        "profitable":            assess_profitability(r),
        "is_dead":               bool(is_dead_by_generation(r)),
    }
    # Label da caixa física (estoque) — import lazy para não acoplar o engine ao estoque.
    try:
        from estoque.views import _compute_destination
        label, category = _compute_destination(r)
        out["dest_label"] = label or ""
        out["dest_category"] = category or ""
    except Exception:
        out["dest_label"] = ""
        out["dest_category"] = ""
    return out


class Command(BaseCommand):
    help = ("Rede de regressão (READ-ONLY): caracteriza classify() para todos os "
            "KnownPart. Use --out (snapshot) ou --diff (compara com um baseline).")

    def add_arguments(self, parser):
        parser.add_argument("--out", help="Grava o baseline (snapshot) neste arquivo JSON.")
        parser.add_argument("--diff", help="Compara o estado atual com este baseline JSON.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Caracteriza só os N primeiros PNs (para teste rápido).")

    def handle(self, *args, **opts):
        if not opts["out"] and not opts["diff"]:
            raise CommandError("Use --out ARQUIVO (snapshot) OU --diff ARQUIVO (regressão).")

        # Falha RÁPIDA: se o baseline do --diff não existe, avisa antes de caracterizar
        # os milhares de PNs (50s) — não depois (era o erro do usuário em 2026-06-30).
        if opts["diff"] and not os.path.exists(opts["diff"]):
            raise CommandError(
                f"Baseline não encontrado: {opts['diff']}\n"
                f"   Gere o baseline ANTES da mudança que quer validar:\n"
                f"       python manage.py characterize_baseline --out {opts['diff']}\n"
                f"   e depois rode de novo com --diff {opts['diff']} para comparar.")

        from chips.models import KnownPart

        pns = list(
            KnownPart.objects.all().order_by("part_number")
            .values_list("part_number", flat=True)
        )
        if opts["limit"]:
            pns = pns[: opts["limit"]]

        try:
            from tqdm import tqdm
            it = tqdm(pns, desc="caracterizando", unit="pn")
        except Exception:
            it = pns

        # Tudo dentro de uma transação revertida → nada persiste (nem os logs do classify).
        current: dict = {}
        try:
            with transaction.atomic():
                for pn in it:
                    current[pn] = _characterize_one(pn)
                raise _Rollback()
        except _Rollback:
            pass

        if opts["out"]:
            with open(opts["out"], "w", encoding="utf-8") as fh:
                json.dump(current, fh, ensure_ascii=False, sort_keys=True, indent=1)
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Baseline gravado: {opts['out']}  ({len(current)} PNs)"))
            return

        # ── modo --diff ────────────────────────────────────────────────────────
        with open(opts["diff"], encoding="utf-8") as fh:
            base = json.load(fh)

        added   = sorted(p for p in current if p not in base)
        removed = sorted(p for p in base if p not in current)
        changed = []
        for pn in sorted(current):
            if pn in base and current[pn] != base[pn]:
                deltas = {
                    k: (base[pn].get(k), current[pn].get(k))
                    for k in set(base[pn]) | set(current[pn])
                    if base[pn].get(k) != current[pn].get(k)
                }
                changed.append((pn, deltas))

        self.stdout.write("")
        self.stdout.write(f"PNs no baseline: {len(base)}  ·  agora: {len(current)}")
        self.stdout.write(
            f"  alterados: {self.style.WARNING(str(len(changed)))}  ·  "
            f"adicionados: {self.style.SUCCESS(str(len(added)))}  ·  "
            f"removidos: {self.style.ERROR(str(len(removed)))}")

        for pn, deltas in changed[:200]:
            campos = "; ".join(f"{k}: {a!r}→{b!r}" for k, (a, b) in sorted(deltas.items()))
            self.stdout.write(f"   ~ {pn}: {campos}")
        if len(changed) > 200:
            self.stdout.write(f"   ... (+{len(changed) - 200} alterados)")
        for pn in added[:50]:
            self.stdout.write(self.style.SUCCESS(f"   + {pn}  {current[pn].get('chip_type','')}"))
        for pn in removed[:50]:
            self.stdout.write(self.style.ERROR(f"   - {pn}"))

        if not changed and not added and not removed:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ IDÊNTICO — nenhuma mudança. Refactor seguro."))
        else:
            self.stdout.write(self.style.WARNING(
                "\n⚠ Há mudanças — confirme que TODAS são as esperadas para este passo."))
