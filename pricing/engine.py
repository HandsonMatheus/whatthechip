"""
pricing/engine.py — a FONTE ÚNICA do preço (F3 do PRECIFICACAO.md).

Ponto de entrada: ``price(result, buyer)`` — recebe o dict do
``chips.engine.classify()`` (com as specs numéricas da F0) e um ``Buyer``, e
devolve um ``PriceQuote``. NUNCA inventa: qualquer furo vira status + motivo.
``price_lot(lot, buyer)`` agrega um lote inteiro (unitário × qtd, cobertura,
sem-preço com motivo, totais por cenário).

Como o preço é achado (PRECIFICACAO §2 e §4):

  1. **Chave** derivada da saída normalizada do classify — brand-agnostic:
       kind = label_kind(canonical_chip_type(...))   (chips/chip_types.py)
       gen  = geração canônica (chip_type p/ DRAM; ram_gen da F0 p/ eMCP/uMCP)
       tier = capacidade da faixa (cap_gb / nand_gb / density_gbit_num da F0)
     ⚠ eMCP/uMCP: a RAM exata fica FORA da chave (regra do comprador — cota
     por faixa de NAND + geração LPDDR). Tipo genérico (DDR/LPDDR sem número)
     NÃO keia preço → NO_KEY, nunca chute.
  2. **Resolução** com herança como DADO (1 salto por lista):
       lista da marca → inherits_from dela → lista GENÉRICA → inherits_from dela
     Primeira linha que casa vence; linha própria sobrepõe herdada.

Segurança/escopo: as queries internas usam ``all_companies`` FILTRADAS pelo
``buyer`` recebido — o *buyer* é o parâmetro de autorização, e quem o obtém é o
chamador, por caminho escopado (request com Membership, ``company_scope`` em
comando, ou o vínculo ``Buyer.users`` no /partner/ da F6). ⚠ Sob Postgres+RLS a
conexão ainda precisa do GUC (`app.company_id`): requests de membro já o têm
(middleware); **o dashboard do parceiro (F6) precisará emitir o GUC da empresa
do Buyer** — anotado no PRECIFICACAO §12.

Moeda: USD, ``Decimal`` sempre (PRECIFICACAO §1.3). Cenário de faixa:
low = mínimo · mid = ponto médio (ROUND_HALF_UP, centavos) · high = máximo.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from chips.chip_types import canonical_chip_type, is_generic, label_kind

from .models import (KIND_UNIT, KINDS, Price, PriceList, PricingConfig,
                     STATUS_NO_BUY, STATUS_NOT_MADE, STATUS_QUOTED,
                     STATUS_UNQUOTED, valid_gen)

# ── Status do PriceQuote (§5 do PRECIFICACAO) ──────────────────────────────────
PRICED   = 'PRICED'     # linha cotada encontrada
NO_BUY   = 'NO_BUY'     # linha encontrada: comprador NÃO compra (o "NO")
UNQUOTED = 'UNQUOTED'   # linha encontrada: não cotado ainda (célula amarela)
NOT_MADE = 'NOT_MADE'   # linha encontrada: a marca NÃO FABRICA este combo —
                        # negativa AUTORITATIVA (bloqueia fallback de propósito)
NO_KEY   = 'NO_KEY'     # o chip não gera chave (geração/capacidade indeterminada)
NO_ROW   = 'NO_ROW'     # chave ok, mas nenhuma lista tem a linha (fora da grade)
NO_LIST  = 'NO_LIST'    # o comprador não tem nenhuma lista ativa

_CENT = Decimal('0.01')


@dataclass
class PriceQuote:
    """Resultado de price(): status + valor + proveniência + frescor."""

    status: str
    reason: str = ''
    # A chave derivada (útil no card/relatório mesmo quando NO_ROW):
    kind: str = ''
    gen: str = ''
    tier_value: Decimal | None = None
    tier_unit: str = ''
    # O valor (só em PRICED):
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    quote_date: date | None = None
    is_stale: bool = False          # cotação velha/sem data → exibir "≈"
    # Proveniência (auditável):
    source_list: 'PriceList | None' = None
    via: str = ''                   # marca | herança da marca | genérica | herança da genérica

    @property
    def is_range(self) -> bool:
        return (self.price_min is not None and self.price_max is not None
                and self.price_min != self.price_max)

    def value(self, scenario: str | None = None) -> Decimal | None:
        """USD do cenário (low/mid/high; default = PricingConfig). None se não-PRICED."""
        if self.status != PRICED:
            return None
        scenario = scenario or PricingConfig.get_config().default_scenario
        if scenario == PricingConfig.SCENARIO_LOW:
            return self.price_min
        if scenario == PricingConfig.SCENARIO_HIGH:
            return self.price_max
        return ((self.price_min + self.price_max) / 2).quantize(_CENT, ROUND_HALF_UP)

    @property
    def mid(self) -> Decimal | None:
        """Ponto médio da faixa — atalho SEM argumentos para uso em template."""
        return self.value(PricingConfig.SCENARIO_MID)


def _no_key(kind: str, reason: str) -> PriceQuote:
    return PriceQuote(status=NO_KEY, reason=reason, kind=kind)


# ── Fallback de densidade DDR/GDDR (bug lote 40, 2026-07-11) ───────────────────
# `density_gbit_num` (F0) só nasce de `dram_density` — que Samsung (decode
# próprio) e Micron (FBGA) preenchem, mas as famílias DDR de SK Hynix/Nanya
# NÃO: a gramática delas põe os BYTES POR DIE no `capacity` ('256MB'), e os
# confirmados via bless_base carregam a convenção da caixa ('2G' = 2 Gbit,
# density_gbit vazio). Nos dois casos a densidade está no `capacity` — só que
# em outra roupa. Este fallback a despe, SÓ para kind ddr/gddr:
#   '2Gb'   → 2.0   (Gbit explícito — raro, mas _extract_gbit-style)
#   '2G'    → 2.0   (Gbit da convenção da caixa; 'G' sem B, case-sensitive)
#   '256MB' → 2.0   (bytes por die × 8 ÷ 1024)
# '2GB' NÃO entra (GB = byte de pacote, nunca densidade — Gb≠GB, regra da casa).
# O padrão bare-Gbit é COMPARTILHADO com o portão de ESCRITA (convention.py,
# regra 4): leitor e escritor nunca podem divergir sobre o que é densidade.
from chips.knowledge.convention import RX_DENSITY_BARE  # noqa: E402

_RX_MB_DIE = re.compile(r'^(\d+(?:\.\d+)?)\s*MB$')


def _gbit_from_capacity(result: dict):
    cap = str(result.get('capacity') or '').strip()
    m = RX_DENSITY_BARE.match(cap)
    if m:
        return float(m.group(1))
    m = _RX_MB_DIE.match(cap)
    if m:
        return float(m.group(1)) * 8 / 1024
    return None


def derive_price_key(result: dict):
    """Deriva (kind, gen, tier_value, tier_unit) da saída do classify().

    Retorna (PriceQuote de erro, None) quando não há chave — com o MOTIVO
    (nunca chuta) — ou (None, tupla-chave) quando há.
    """
    chip_type = (result.get('chip_type') or '').strip()
    subtype   = (result.get('subtype') or '').strip()
    canon = canonical_chip_type(chip_type, subtype)
    kind  = label_kind(canon)

    if kind not in KINDS:
        return _no_key(kind, f'tipo {canon or chip_type or "desconhecido"!r} '
                             'fora do mercado de preço (triagem descarta)'), None

    # geração da chave
    if kind in ('emmc', 'ufs'):
        gen = ''
    elif kind in ('emcp', 'umcp', 'lpddr'):
        # eMCP/uMCP: geração da RAM (F0: ram_gen). LPDDR avulso: o próprio
        # chip_type canônico carrega a geração — ram_gen da F0 espelha os dois.
        gen = (result.get('ram_gen') or '').strip()
        if kind == 'lpddr' and not gen and not is_generic(canon):
            gen = canon
        if not valid_gen(kind, gen):
            return _no_key(kind, 'geração LPDDR indeterminada — não keia preço'), None
    else:  # ddr / gddr
        if is_generic(canon):
            return _no_key(kind, f'geração {canon} genérica — não keia preço'), None
        gen = canon
        if kind == 'ddr':
            # Variantes de TENSÃO precificam como a geração-base (dono,
            # 2026-07-11: "DDR3L e DDR3 são a mesma coisa em termos de
            # preço"). Cobre DDR3L/DDR3U/DDR4L… — só sufixo L/U; GDDR5X
            # etc. NÃO entram (são chips de outro mercado, não tensão).
            m = re.match(r'^(DDR\d+)[LU]$', gen)
            if m:
                gen = m.group(1)
        if not valid_gen(kind, gen):
            return _no_key(kind, f'geração {gen!r} inválida para {kind}'), None

    # tier (capacidade da faixa) — SEMPRE dos campos numéricos da F0
    if kind in ('emcp', 'umcp'):
        tier, faltou = result.get('nand_gb'), 'NAND (GB) indisponível'
    elif kind in ('ddr', 'gddr'):
        tier = result.get('density_gbit_num') or _gbit_from_capacity(result)
        faltou = 'densidade (Gb) indisponível'
    else:
        tier, faltou = result.get('cap_gb'), 'capacidade (GB) indisponível'
    if not tier or tier <= 0:
        return _no_key(kind, f'{faltou} — não keia preço'), None

    return None, (kind, gen, Decimal(str(tier)), KIND_UNIT[kind])


def _resolution_chain(buyer, brand_name: str):
    """[(PriceList, rótulo)] na ordem de resolução do §4 (sem duplicatas)."""
    lists = list(PriceList.all_companies
                 .filter(buyer=buyer, active=True)
                 .select_related('inherits_from', 'brand'))
    by_brand = {pl.brand.name: pl for pl in lists if pl.brand_id}
    generic  = next((pl for pl in lists if pl.brand_id is None), None)

    chain, seen = [], set()

    def _add(pl, rotulo):
        if pl is not None and pl.active and pl.pk not in seen:
            seen.add(pl.pk)
            chain.append((pl, rotulo))

    brand_list = by_brand.get(brand_name or '')
    _add(brand_list, 'marca')
    if brand_list is not None:
        _add(brand_list.inherits_from, 'herança da marca')
    _add(generic, 'genérica')
    if generic is not None:
        _add(generic.inherits_from, 'herança da genérica')
    return chain


def price(result: dict, buyer) -> PriceQuote:
    """Quanto o ``buyer`` paga pelo chip do ``result``. Fonte única (§5)."""
    err, key = derive_price_key(result or {})
    if err is not None:
        return err
    kind, gen, tier_value, tier_unit = key

    chain = _resolution_chain(buyer, result.get('brand') or '')
    if not chain:
        return PriceQuote(status=NO_LIST, kind=kind, gen=gen,
                          tier_value=tier_value, tier_unit=tier_unit,
                          reason=f'comprador {buyer} sem lista de preços ativa')

    order = {pl.pk: i for i, (pl, _) in enumerate(chain)}
    rows = list(Price.all_companies.filter(
        price_list_id__in=list(order), kind=kind, gen=gen,
        tier_value=tier_value, tier_unit=tier_unit,
    ).select_related('price_list'))
    if not rows:
        return PriceQuote(status=NO_ROW, kind=kind, gen=gen,
                          tier_value=tier_value, tier_unit=tier_unit,
                          reason=f'faixa {kind}/{gen or "—"} '
                                 f'{tier_value.normalize():f}{tier_unit} fora da '
                                 'grade — adicionar linha na tabela')

    row = min(rows, key=lambda r: order[r.price_list_id])   # 1ª da cadeia vence
    pl, via = chain[order[row.price_list_id]]

    base = dict(kind=kind, gen=gen, tier_value=tier_value, tier_unit=tier_unit,
                source_list=pl, via=via, quote_date=row.quote_date)
    if row.status == STATUS_NO_BUY:
        return PriceQuote(status=NO_BUY, reason='comprador não compra este item',
                          **base)
    if row.status == STATUS_NOT_MADE:
        return PriceQuote(status=NOT_MADE,
                          reason='combo não fabricado pela marca', **base)
    if row.status == STATUS_UNQUOTED:
        return PriceQuote(status=UNQUOTED,
                          reason='aguardando cotação do comprador', **base)

    cfg = PricingConfig.get_config()
    stale = (row.quote_date is None or
             (date.today() - row.quote_date).days > cfg.staleness_days)
    return PriceQuote(status=PRICED, price_min=row.price_min,
                      price_max=row.price_max, is_stale=stale, **base)


def quotes_for_admin(request, result):
    """[(Buyer, PriceQuote)] para o card — SÓ papel ADMIN da empresa
    (PRECIFICACAO §7). O gate roda ANTES de qualquer query: operador, gerente e
    anônimo recebem lista vazia sem nem disparar a resolução de preço.
    Fonte única do gate — consumida por chips/views (busca) e estoque/views
    (bancada do lote, F8)."""
    if getattr(request, 'company_role', None) != 'admin':
        return []
    from .models import Buyer
    return [(b, price(result, b)) for b in Buyer.objects.filter(active=True)]


def serialize_quote(buyer, q) -> dict:
    """PriceQuote → dict JSON-safe (Decimal vira string — nunca float) para o
    card client-side da home (search_api)."""
    return {
        'buyer': buyer.name, 'status': q.status, 'reason': q.reason,
        'min': str(q.price_min) if q.price_min is not None else None,
        'max': str(q.price_max) if q.price_max is not None else None,
        'mid': str(q.mid) if q.mid is not None else None,
        'is_range': q.is_range, 'is_stale': q.is_stale,
        'quote_date': q.quote_date.strftime('%d/%m/%Y') if q.quote_date else None,
        'via': q.via,
    }


# ── Lote inteiro (§5: regra 6 do comprador) ────────────────────────────────────

@dataclass
class LotQuoteLine:
    part_number: str
    quantity: int
    quote: PriceQuote


@dataclass
class LotPricingReport:
    lines: list = field(default_factory=list)         # [LotQuoteLine]
    totals: dict = field(default_factory=dict)        # {low|mid|high: Decimal}
    total_lines: int = 0
    priced_lines: int = 0
    total_units: int = 0
    priced_units: int = 0
    unpriced: list = field(default_factory=list)      # [(pn, qty, status, reason)]

    @property
    def coverage_lines(self) -> float:
        return (100.0 * self.priced_lines / self.total_lines) if self.total_lines else 0.0

    @property
    def coverage_units(self) -> float:
        return (100.0 * self.priced_units / self.total_units) if self.total_units else 0.0


def price_lot(lot, buyer) -> LotPricingReport:
    """Precifica um lote ON-READ (classifica cada PN de novo — catálogo VIVO,
    nunca o snapshot; PRECIFICACAO §1.7) e agrega: total por cenário, cobertura
    (% de linhas e de unidades) e o sem-preço com motivo. Não persiste nada —
    o congelamento no fechamento do lote é a F8 (``LotPricing``).

    ⚠ Requer escopo de empresa ativo (request de membro ou ``company_scope``):
    ``lot.entries`` usa o manager escopado fail-closed.
    """
    from chips.engine import classify   # lazy: evita acoplamento na importação

    report = LotPricingReport(totals={
        PricingConfig.SCENARIO_LOW: Decimal('0.00'),
        PricingConfig.SCENARIO_MID: Decimal('0.00'),
        PricingConfig.SCENARIO_HIGH: Decimal('0.00'),
    })
    for entry in lot.entries.all():
        q = price(classify(entry.part_number), buyer)
        qty = entry.quantity or 0
        report.lines.append(LotQuoteLine(entry.part_number, qty, q))
        report.total_lines += 1
        report.total_units += qty
        if q.status == PRICED:
            report.priced_lines += 1
            report.priced_units += qty
            for scenario in report.totals:
                report.totals[scenario] += q.value(scenario) * qty
        else:
            report.unpriced.append((entry.part_number, qty, q.status, q.reason))
    return report
