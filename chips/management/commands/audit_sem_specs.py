# -*- coding: utf-8 -*-
"""
audit_sem_specs.py — READ-ONLY: por que este PN aparece SEM tipo/capacidade?
=============================================================================
O `audit_known_parts --empty` lista os *identity-only* (registro confirmado sem
spec própria). Este vai um passo além e responde a pergunta que decide a AÇÃO:

    esse PN aparece vazio na bancada/no lote — e agora, o que resolve?

Porque "sem spec no registro" NÃO quer dizer "aparece vazio": quando a gramática
da família decodifica o PN, o engine completa na leitura (o registro humano só
vence quando ele próprio tem o dado — ver `_result_from_known`). Então o mesmo
sintoma tem três causas bem diferentes, e cada uma tem um conserto diferente:

  ✅ GRAMÁTICA RESOLVE   o engine JÁ devolve tipo+capacidade hoje. Se o lote
                         mostra vazio, o que está velho é o SNAPSHOT do
                         lançamento → `resnapshot_lote`. Não precisa pesquisar.
  ⚠ SÓ TIPO              alguém dá o tipo, ninguém dá a capacidade.
  ⛔ PRECISA PESQUISA     nem o registro nem a gramática têm o dado → só fonte
                         Tier-1 resolve (chat de marca).

READ-ONLY: não escreve nada. Roda com o DATABASE_URL do banco a inspecionar.

Uso:
    python manage.py audit_sem_specs --brand Micron
    python manage.py audit_sem_specs --brand Micron --estoque     # + exposição
    python manage.py audit_sem_specs --brand Micron --csv sem_specs.csv
"""
import csv
from collections import Counter

from django.core.management.base import BaseCommand

from chips.engine import _match_family, _result_from_family, classify
from chips.models import KnownPart

_CAP_FIELDS = ("capacity", "emcp_ram", "emcp_nand", "density_gbit", "density_gb")


def _vazio(v) -> bool:
    return not str(v or "").strip()


def _tem_capacidade(txt) -> bool:
    """Qualquer dígito seguido de unidade — o mesmo critério prático do engine."""
    import re
    return bool(re.search(r"\d+\s*(GB|MB|Gb|Mb|TB)", str(txt or "")))


class Command(BaseCommand):
    help = ("READ-ONLY: para cada PN sem spec própria, diz o que resolve — "
            "resnapshot (a gramática já cobre) ou pesquisa Tier-1.")

    def add_arguments(self, parser):
        parser.add_argument("--brand", default="", help="Marca (nome). Vazio = todas.")
        parser.add_argument("--confidence", default="confirmed,manual",
                            help="Default: confirmed,manual (o identity-only clássico).")
        parser.add_argument("--estoque", action="store_true",
                            help="Cruza com o estoque (quantidade e lotes por PN).")
        parser.add_argument("--limit", type=int, default=40, help="Linhas na tela.")
        parser.add_argument("--por-tipo", action="store_true",
                            help="Resume por TIPO de chip + peças em estoque — separa o "
                                 "que vale dinheiro (LPDDR/eMMC) do legado morto (MCP/DDR2).")
        parser.add_argument("--csv", default="", help="Grava a lista completa em CSV.")

    def handle(self, *args, **o):
        w = self.stdout.write
        confs = tuple(c.strip() for c in o["confidence"].split(",") if c.strip())
        qs = KnownPart.objects.filter(review_status="approved")
        if confs:
            qs = qs.filter(confidence__in=confs)
        if o["brand"]:
            qs = qs.filter(brand__name__iexact=o["brand"])

        # identity-only = nenhum campo de capacidade preenchido no REGISTRO
        vazios = [kp for kp in qs.select_related("brand", "family").iterator()
                  if all(_vazio(getattr(kp, c, "")) for c in _CAP_FIELDS)]
        if not vazios:
            w(f"✓ Nenhum registro sem capacidade própria em {o['brand'] or 'nenhuma marca'}.")
            return

        estoque = self._estoque() if o["estoque"] else {}
        linhas, resumo = [], Counter()
        for kp in vazios:
            fam = _match_family(kp.part_number) or kp.family
            gram_tipo = gram_cap = ""
            if fam is not None:
                try:
                    g = _result_from_family(kp.part_number, fam)
                    gram_tipo = g.get("chip_type") or ""
                    gram_cap = (g.get("capacity") or g.get("emcp_ram")
                                or g.get("emcp_nand") or g.get("dram_density") or "")
                except Exception:
                    pass
            try:
                r = classify(kp.part_number) or {}
            except Exception:
                r = {}
            vive_tipo = r.get("chip_type") or kp.chip_type or gram_tipo
            vive_cap = (r.get("capacity") or r.get("emcp_ram") or r.get("emcp_nand")
                        or r.get("dram_density") or gram_cap)

            if _tem_capacidade(vive_cap):
                veredito = "✅ GRAMÁTICA RESOLVE"
            elif vive_tipo:
                veredito = "⚠ SÓ TIPO"
            else:
                veredito = "⛔ PRECISA PESQUISA"
            resumo[veredito] += 1
            qtd, lotes = estoque.get(kp.part_number_norm, (0, set()))
            # O código FBGA é o que a API oficial da Micron aceita como chave —
            # ter ou não ter decide se dá pra resolver por máquina ou só por
            # pesquisa. Às vezes ele veio COLADO no texto do PN (último token,
            # ex.: "MT62F1DAD4DH-DC Y62P") em vez de no campo próprio.
            fbga = (kp.fbga_code or "").strip()
            solto = ""
            if not fbga:
                ult = kp.part_number.strip().split()[-1]
                if 3 <= len(ult) <= 6 and ult.isalnum() and any(c.isdigit() for c in ult) \
                        and any(c.isalpha() for c in ult):
                    solto = ult
            linhas.append({
                "part_number": kp.part_number, "marca": kp.brand.name if kp.brand else "",
                "familia": fam.prefix if fam is not None else "—",
                "tipo_hoje": vive_tipo or "—", "capacidade_hoje": vive_cap or "—",
                "confidence": kp.confidence, "veredito": veredito,
                "fbga_code": fbga, "fbga_no_pn": solto,
                "qtd_estoque": qtd, "lotes": ",".join(str(x) for x in sorted(lotes)),
            })

        alvo = o["brand"] or "TODAS as marcas"
        w(f"\n{len(vazios)} registro(s) SEM capacidade própria em {alvo}\n")
        for v, n in resumo.most_common():
            w(f"  {v:<24} {n:>5}")
        w("")
        w("  ✅ = o engine já devolve o dado (a gramática cobre) — se o LOTE mostra")
        w("       vazio, o que está velho é o snapshot: resnapshot_lote --all --commit")
        w("  ⛔ = ninguém tem o dado; só fonte Tier-1 (chat de marca) resolve")

        # prioriza o que dói: primeiro o que está em estoque, depois o que precisa pesquisa
        linhas.sort(key=lambda x: (-x["qtd_estoque"], x["veredito"], x["part_number"]))
        w(f"\n{'PART NUMBER':<32}{'FAM':<10}{'TIPO HOJE':<12}{'CAPACIDADE HOJE':<20}"
          f"{'QTD':>5}  VEREDITO")
        w("-" * 104)
        for ln in linhas[:o["limit"]]:
            w(f"{ln['part_number'][:31]:<32}{ln['familia'][:9]:<10}{ln['tipo_hoje'][:11]:<12}"
              f"{str(ln['capacidade_hoje'])[:19]:<20}{ln['qtd_estoque']:>5}  {ln['veredito']}")
        if len(linhas) > o["limit"]:
            w(f"… +{len(linhas) - o['limit']} (use --limit ou --csv)")

        if o["por_tipo"]:
            self._por_tipo(linhas)

        if o["csv"]:
            with open(o["csv"], "w", newline="", encoding="utf-8") as fh:
                esc = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
                esc.writeheader()
                esc.writerows(linhas)
            w(f"\n📄 lista completa: {o['csv']} ({len(linhas)} linhas)")

    def _por_tipo(self, linhas):
        """807 linhas viram ~10. O que decide a fila é TIPO × peças em estoque:
        capacidade de chip morto (MCP/DDR2 legado) não muda veredito nem preço;
        capacidade de LPDDR4X/LPDDR5 em estoque é dinheiro parado sem chave."""
        w = self.stdout.write
        por = {}
        for ln in linhas:
            t = ln["tipo_hoje"] or "—"
            n, q, fb = por.get(t, (0, 0, 0))
            por[t] = (n + 1, q + ln["qtd_estoque"],
                      fb + (1 if (ln["fbga_code"] or ln["fbga_no_pn"]) else 0))
        w(self.style.WARNING("\n\nPOR TIPO DE CHIP — a fila de prioridade:"))
        w(f"\n{'TIPO':<16}{'PNs':>6}{'COM FBGA':>10}{'PEÇAS EM ESTOQUE':>19}")
        w("-" * 52)
        for t, (n, q, fb) in sorted(por.items(), key=lambda kv: -kv[1][1]):
            w(f"{t[:15]:<16}{n:>6}{fb:>10}{q:>19}")
        w("-" * 52)
        tot_n = sum(v[0] for v in por.values())
        tot_q = sum(v[1] for v in por.values())
        w(f"{'TOTAL':<16}{tot_n:>6}{'':>10}{tot_q:>19}")
        com_fbga = sum(v[2] for v in por.values())
        w("\n  A fila é de cima pra baixo: mais peças paradas sem capacidade = mais")
        w("  dinheiro sem chave de preço. Tipo morto (MCP/DDR2/NAND raw) pode ficar")
        w("  no fim — o veredito NÃO RENTÁVEL não depende da capacidade exata.")
        w(f"\n  COM FBGA = {com_fbga} de {tot_n}: o código FBGA é a chave que a API")
        w("  oficial da Micron aceita (fill_capacity_from_micron_api / enrich_micron_fbga).")
        w("  Sem ele, só pesquisa Tier-1 no chat da marca resolve.")

    def _estoque(self):
        """{part_number_norm: (quantidade, {lotes})} — all_companies (plataforma).
        Em prod com RLS sem GUC isso pode vir vazio: o aviso é explícito."""
        from chips.normalize import normalize_pn
        try:
            from estoque.models import InventoryEntry
            mapa = {}
            for e in InventoryEntry.all_companies.select_related("lot").iterator():
                k = normalize_pn(e.part_number)
                qtd, lotes = mapa.get(k, (0, set()))
                mapa[k] = (qtd + (e.quantity or 0), lotes | {e.lot.number})
            if not mapa:
                self.stdout.write(self.style.WARNING(
                    "⚠ estoque veio VAZIO — se o banco tem lotes, é RLS sem o GUC de "
                    "plataforma (rode local ou com o escopo certo)."))
            return mapa
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠ estoque não cruzado: {e}"))
            return {}
