"""
characterize_baseline.py
========================
Rede de regressão do refactor de escalabilidade — **PASSO 0** do
`docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`. É o trilho de segurança de TODO
passo que toca o engine.

O QUE FAZ (READ-ONLY): roda o banco inteiro (todos os `KnownPart`) pelo pipeline
real — `classify()` → `assess_profitability()` → `_compute_destination()` (label
da caixa) → `is_dead_by_generation()` → `pricing.derive_price_key()` — e captura,
por PN, os campos de saída.

AS TRÊS COLUNAS QUE O NEGÓCIO ENXERGA (dono, 2026-08-28): **DESTINO**
(`dest_label`/`dest_category`), **RENTABILIDADE** (`profitable`/`is_dead`) e
**PREÇO**. Nenhuma pode mudar num refactor. O preço entra em DUAS camadas, e a
distinção é o que separa alarme falso de regressão de verdade:
  · `price_key` = (kind, gen, tier, unidade) — FUNÇÃO PURA do classify(), sem
    comprador, sem lista, sem câmbio. **Se ela mudar, a culpa é nossa.**
  · `price_<comprador>` = a cotação. Muda legitimamente quando o comprador edita
    a lista ou o câmbio anda. Diferença aqui COM `price_key` idêntica é
    MERCADO, não regressão.
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
def _characterize_one(pn: str, contextos=()) -> dict:
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
    out.update(_price_fields(r, contextos or ()))
    return out


def _price_fields(r: dict, contextos) -> dict:
    """A 3ª coluna: PREÇO. Ver o cabeçalho do módulo para as duas camadas.

    Tolerante a falha de propósito: um ambiente sem pricing montado (SQLite de
    teste, banco recém-criado) tem que continuar produzindo baseline das outras
    duas colunas — o silêncio aqui vira string, nunca exceção que aborta 8 mil PNs.
    """
    out = {}
    try:
        from pricing.engine import derive_price_key
        err, key = derive_price_key(r or {})
        if key is not None:
            kind, gen, tier, unidade = key
            out["price_key"] = f"{kind}|{gen}|{tier}|{unidade}"
            out["price_no_key_reason"] = ""
        else:
            out["price_key"] = ""
            out["price_no_key_reason"] = f"{err.kind}: {err.reason}"
    except Exception as exc:                       # noqa: BLE001
        out["price_key"] = ""
        out["price_no_key_reason"] = f"ERRO {type(exc).__name__}: {exc}"
    for slug, ctx in contextos:
        try:
            q = ctx.price(r)
            out[f"price_{slug}"] = f"{q.status}|{q.rmb_min}|{q.rmb_max}"
        except Exception as exc:                   # noqa: BLE001
            out[f"price_{slug}"] = f"ERRO {type(exc).__name__}"
    return out


def _contextos_de_preco(stdout):
    """Um BuyerPricingContext por comprador ATIVO (I/O constante — o contexto
    pré-carrega as linhas; sem ele seriam ~3 queries POR PN, incidente do lote 42).

    ⚠ `platform_scope()` NÃO é opcional: comprador/lista/preço são linhas de
    PLATAFORMA (company_id IS NULL) sob RLS, e comando roda FORA de request —
    sem o GUC o banco devolve ZERO linhas EM SILÊNCIO (CLAUDE.md §7,
    `audit_category_codes`). Baseline com preço vazio por RLS seria pior que não
    ter preço: 'não mudou nada' medido sobre nada."""
    try:
        from pricing.engine import BuyerPricingContext
        from pricing.models import Buyer
        from tenancy.scope import platform_scope
    except Exception:                              # noqa: BLE001
        return [], None
    ctxs = []
    try:
        with platform_scope():
            mgr = getattr(Buyer, "all_companies", None) or Buyer.objects
            compradores = list(mgr.filter(active=True).order_by("pk"))
            for b in compradores:
                slug = (getattr(b, "slug", "") or getattr(b, "name", "")
                        or f"buyer{b.pk}").strip().lower().replace(" ", "_")
                ctxs.append((slug, BuyerPricingContext(b)))
    except Exception as exc:                       # noqa: BLE001
        stdout.write(f"⚠ preço por comprador indisponível ({type(exc).__name__}: {exc}) "
                     "— o baseline segue com `price_key`, que é o invariante.")
        return [], None
    if not ctxs:
        stdout.write("⚠ NENHUM comprador ativo — baseline sem cotação. "
                     "`price_key` (o invariante) segue capturado.")
    return ctxs, platform_scope


class Command(BaseCommand):
    help = ("Rede de regressão (READ-ONLY): caracteriza classify() para todos os "
            "KnownPart. Use --out (snapshot) ou --diff (compara com um baseline).")

    def add_arguments(self, parser):
        parser.add_argument("--out", help="Grava o baseline (snapshot) neste arquivo JSON.")
        parser.add_argument("--diff", help="Compara o estado atual com este baseline JSON.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Caracteriza só os N primeiros PNs (para teste rápido).")
        parser.add_argument("--summary", action="store_true",
                            help="Com --diff: agrega TODAS as mudanças por campo e por "
                                 "transição distinta (old→new), sem truncar. Prova compacta "
                                 "de que só os campos esperados mudaram.")

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

        contextos, escopo = _contextos_de_preco(self.stdout)
        if contextos:
            self.stdout.write(f"   preço: {len(contextos)} comprador(es) ativo(s) — "
                              + ", ".join(slug for slug, _ in contextos))

        # Tudo dentro de uma transação revertida → nada persiste (nem os logs do classify).
        # O `platform_scope` fica DENTRO dela e emite o GUC que a RLS exige para
        # ler as linhas de plataforma do pricing (sem ele: zero linhas, em silêncio).
        current: dict = {}
        try:
            with transaction.atomic():
                if escopo is not None:
                    with escopo():
                        for pn in it:
                            current[pn] = _characterize_one(pn, contextos)
                else:
                    for pn in it:
                        current[pn] = _characterize_one(pn, contextos)
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
        # Campo que o baseline ANTIGO não tinha (ex.: as colunas de preço, 2026-08-28)
        # não é "mudança": é coluna nova. Comparar cria milhares de falsos positivos
        # e o diff perde o valor de alarme — o mesmo custo do alarme que nunca apaga.
        campos_base = set()
        for v in base.values():
            campos_base |= set(v)
        campos_agora = set()
        for v in current.values():
            campos_agora |= set(v)
        campos_novos = campos_agora - campos_base
        if campos_novos:
            self.stdout.write(self.style.WARNING(
                "⚠ colunas AUSENTES no baseline (ignoradas na comparação): "
                + ", ".join(sorted(campos_novos))
                + "\n   Regrave o baseline para passar a cobri-las."))

        changed = []
        for pn in sorted(current):
            if pn in base and current[pn] != base[pn]:
                deltas = {
                    k: (base[pn].get(k), current[pn].get(k))
                    for k in (set(base[pn]) | set(current[pn])) - campos_novos
                    if base[pn].get(k) != current[pn].get(k)
                }
                if deltas:
                    changed.append((pn, deltas))

        self.stdout.write("")
        self.stdout.write(f"PNs no baseline: {len(base)}  ·  agora: {len(current)}")
        self.stdout.write(
            f"  alterados: {self.style.WARNING(str(len(changed)))}  ·  "
            f"adicionados: {self.style.SUCCESS(str(len(added)))}  ·  "
            f"removidos: {self.style.ERROR(str(len(removed)))}")

        # ── modo --summary: agrega TODAS as mudanças (prova completa, sem truncar) ──
        if opts["summary"]:
            from collections import Counter
            by_field = Counter()
            transitions: dict[str, Counter] = {}
            for _pn, deltas in changed:
                for k, (a, b) in deltas.items():
                    by_field[k] += 1
                    transitions.setdefault(k, Counter())[f"{a!r} → {b!r}"] += 1
            self.stdout.write("\n── mudanças por CAMPO (todas as %d) ──" % len(changed))
            for field, n in by_field.most_common():
                self.stdout.write(f"  {n:6d}  {field}")
            self.stdout.write("\n── transições DISTINTAS por campo (old → new) ──")
            for field, _ in by_field.most_common():
                self.stdout.write(f"  [{field}]")
                trs = transitions[field].most_common()
                for t, n in trs[:50]:
                    self.stdout.write(f"     {n:6d} ×  {t}")
                if len(trs) > 50:
                    self.stdout.write(f"     ... (+{len(trs) - 50} transições distintas)")
            return

        for pn, deltas in changed[:200]:
            campos = "; ".join(f"{k}: {a!r}→{b!r}" for k, (a, b) in sorted(deltas.items()))
            self.stdout.write(f"   ~ {pn}: {campos}")
        if len(changed) > 200:
            self.stdout.write(f"   ... (+{len(changed) - 200} alterados)")
        for pn in added[:50]:
            self.stdout.write(self.style.SUCCESS(f"   + {pn}  {current[pn].get('chip_type','')}"))
        for pn in removed[:50]:
            self.stdout.write(self.style.ERROR(f"   - {pn}"))

        # ── VEREDITO das TRÊS COLUNAS (dono, 2026-08-28) ────────────────────
        # Separa o que é CULPA NOSSA do que é o mercado andando. Um diff que
        # mistura os dois vira alarme que ninguém lê.
        NOSSAS = {"dest_label", "dest_category", "profitable", "is_dead",
                  "price_key", "price_no_key_reason"}
        n_nossas = sum(1 for _pn, d in changed if NOSSAS & set(d))
        n_mercado = len(changed) - n_nossas
        self.stdout.write("\n── AS TRÊS COLUNAS ──")
        self.stdout.write(f"   DESTINO · RENTABILIDADE · CHAVE DE PREÇO alterados em: "
                          f"{n_nossas} PN(s)")
        self.stdout.write(f"   só a COTAÇÃO mudou (câmbio/lista — não somos nós): "
                          f"{n_mercado} PN(s)")

        if not changed and not added and not removed:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ IDÊNTICO — nenhuma mudança. Refactor seguro."))
        elif n_nossas == 0 and not added and not removed:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ AS TRÊS COLUNAS INTACTAS — nenhum chip mudou de destino, de "
                "rentabilidade nem de chave de preço. As diferenças são de cotação."))
        else:
            self.stdout.write(self.style.WARNING(
                "\n⚠ Há mudanças — confirme que TODAS são as esperadas para este passo."))
