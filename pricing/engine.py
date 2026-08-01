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

Moeda (F10, RMB CANÔNICO — PRECIFICACAO §12.18): o ``Price`` guarda **¥ (RMB)**
— o número que o comprador digitou, que NUNCA muda. O **USD é DERIVADO na
leitura**: ¥ × ``Buyer.fx_usd_rate`` (taxa CONTRATUAL, gerida pelo dono),
calculado na construção do ``PriceQuote`` — por isso ``price_min/max``/
``value()``/``mid`` continuam devolvendo USD e NENHUM consumidor do estoque
(valoração, export, congelamento F8) muda. O ¥ armazenado sai em
``rmb_min/rmb_max``/``rmb``/``mid_rmb`` (card dual "¥ 90 · US$ 12.60").
``Decimal`` sempre (PRECIFICACAO §1.3). Cenário de faixa:
low = mínimo · mid = ponto médio (ROUND_HALF_UP, centavos) · high = máximo.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from chips.chip_types import canonical_chip_type, is_generic, label_kind

from .models import (KIND_UNIT, KINDS, ORIGIN_PCB, ORIGIN_PHONE, Price,
                     PriceList, PricingConfig,
                     STATUS_NO_BUY, STATUS_NOT_MADE, STATUS_QUOTED,
                     STATUS_UNQUOTED, fold_gen, valid_gen)

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
    # O valor (só em PRICED) — F10 (RMB canônico): price_min/max carregam o
    # USD **DERIVADO** (¥ × Buyer.fx_usd_rate, calculado no price()) para que
    # NENHUM consumidor mude (estoque/export/F8 seguem lendo USD daqui);
    # rmb_min/max carregam o ¥ **ARMAZENADO** (o que o comprador digitou).
    price_min: Decimal | None = None      # USD derivado
    price_max: Decimal | None = None      # USD derivado
    rmb_min: Decimal | None = None        # ¥ armazenado (Price.price_min)
    rmb_max: Decimal | None = None        # ¥ armazenado (Price.price_max)
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
        """USD do cenário (low/mid/high; default = PricingConfig). None se
        não-PRICED. F10: é o USD **derivado** (¥ × taxa contratual do buyer,
        já calculado em price_min/max) — a moeda de valoração/export."""
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
        """Ponto médio da faixa em USD — atalho SEM argumentos p/ template."""
        return self.value(PricingConfig.SCENARIO_MID)

    # ── ¥ armazenado (F10 — RMB canônico, PRECIFICACAO §12.18) ──────────────
    def value_rmb(self, scenario: str | None = None) -> Decimal | None:
        """¥ do cenário — espelho de value() na moeda ARMAZENADA. Preço é
        FIXO (min == max desde 2026-07-07), então os cenários coincidem."""
        if self.status != PRICED:
            return None
        scenario = scenario or PricingConfig.get_config().default_scenario
        if scenario == PricingConfig.SCENARIO_LOW:
            return self.rmb_min
        if scenario == PricingConfig.SCENARIO_HIGH:
            return self.rmb_max
        return ((self.rmb_min + self.rmb_max) / 2).quantize(_CENT, ROUND_HALF_UP)

    @property
    def mid_rmb(self) -> Decimal | None:
        """Ponto médio da faixa em ¥ — atalho SEM argumentos p/ template."""
        return self.value_rmb(PricingConfig.SCENARIO_MID)

    @property
    def rmb(self) -> Decimal | None:
        """O ¥ de exibição (preço fixo: rmb_min == rmb_max)."""
        return self.rmb_min

    @property
    def rmb_display(self) -> str | None:
        """¥ SEM zeros à direita p/ o card dual ('90', '117.86') — o comprador
        pensa em ¥ redondo. ⚠ ``normalize()`` sozinho imprime notação
        científica (90.00 → 9E+1); o ``:f`` força decimal (PRECIFICACAO §12)."""
        if self.rmb is None:
            return None
        return f'{self.rmb.normalize():f}'


def _no_key(kind: str, reason: str) -> PriceQuote:
    return PriceQuote(status=NO_KEY, reason=reason, kind=kind)


# ── Fallback de densidade DDR (bug lote 40, 2026-07-11) ────────────────────────
# `density_gbit_num` (F0) só nasce de `dram_density` — que Samsung (decode
# próprio) e Micron (FBGA) preenchem, mas as famílias DDR de SK Hynix/Nanya
# NÃO: a gramática delas põe os BYTES POR DIE no `capacity` ('256MB'), e os
# confirmados via bless_base carregam a convenção da caixa ('2G' = 2 Gbit,
# density_gbit vazio). Nos dois casos a densidade está no `capacity` — só que
# em outra roupa. Este fallback a despe, SÓ para kind ddr:
#   '2Gb'   → 2.0   (Gbit explícito — raro, mas _extract_gbit-style)
#   '2G'    → 2.0   (Gbit da convenção da caixa; 'G' sem B, case-sensitive)
#   '256MB' → 2.0   (bytes por die × 8 ÷ 1024)
#   '1GB'   → 8.0   (bytes por die × 8 — caso H5AN, lote 042: dies ≥ 1GB)
# ⚠ o caso 'GB' SÓ é seguro aqui porque este fallback roda DENTRO do branch
# kind == 'ddr' do derive_price_key (lá capacity é per-die por convenção §6);
# fora de kind-DDR, 'GB' segue sendo pacote e nunca vira densidade.
# O padrão bare-Gbit é COMPARTILHADO com o portão de ESCRITA (convention.py,
# regra 4): leitor e escritor nunca podem divergir sobre o que é densidade.
from chips.knowledge.convention import RX_DENSITY_BARE, RX_DIE_GB  # noqa: E402

_RX_MB_DIE = re.compile(r'^(\d+(?:\.\d+)?)\s*MB$')


def _gbit_from_capacity(result: dict):
    cap = str(result.get('capacity') or '').strip()
    m = RX_DENSITY_BARE.match(cap)
    if m:
        return float(m.group(1))
    m = _RX_MB_DIE.match(cap)
    if m:
        return float(m.group(1)) * 8 / 1024
    m = RX_DIE_GB.match(cap)
    if m:
        return float(m.group(1)) * 8
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

    # geração da chave — sempre DOBRADA na geração-base da categoria
    # (fold_gen, fonte única em pricing/models.py): DDR3L/DDR3U→DDR3 (dono
    # 2026-07-11), LPDDR4X→LPDDR4 avulso (dono 2026-07-21 — "uma só caixa").
    # eMCP/uMCP mantêm a geração da RAM intacta.
    if kind in ('emmc', 'ufs', 'emcp', 'umcp', 'ssd'):
        # v3.1 (dono 2026-07-24, planilha v9 "unified by cap"): eMCP/uMCP
        # keiam SÓ pelo NAND — a geração da RAM fica nas specs/rótulo, fora
        # da chave (igual eMMC/UFS).
        gen = ''
    elif kind == 'lpddr':
        # LPDDR avulso: o chip_type canônico carrega a geração — ram_gen da
        # F0 espelha; X dobra na base.
        gen = (result.get('ram_gen') or '').strip()
        if not gen and not is_generic(canon):
            gen = canon
        gen = fold_gen(kind, gen)
        if not valid_gen(kind, gen):
            return _no_key(kind, 'geração LPDDR indeterminada — não keia preço'), None
    else:  # ddr
        if is_generic(canon):
            return _no_key(kind, f'geração {canon} genérica — não keia preço'), None
        gen = fold_gen(kind, canon)
        if not valid_gen(kind, gen):
            return _no_key(kind, f'geração {gen!r} inválida para {kind}'), None

    # tier (capacidade da faixa) — SEMPRE dos campos numéricos da F0
    if kind in ('emcp', 'umcp'):
        tier, faltou = result.get('nand_gb'), 'NAND (GB) indisponível'
    elif kind == 'ddr':
        tier = result.get('density_gbit_num') or _gbit_from_capacity(result)
        faltou = 'densidade (Gb) indisponível'
    else:
        tier, faltou = result.get('cap_gb'), 'capacidade (GB) indisponível'
    if not tier or tier <= 0:
        return _no_key(kind, f'{faltou} — não keia preço'), None

    return None, (kind, gen, Decimal(str(tier)), KIND_UNIT[kind])


def _ssd_quote(buyer, tier_value, tier_unit):
    """SSD é LINEAR (dono 2026-07-24: '512GB×0.1=51rmb'): ¥ = GB ×
    Buyer.ssd_rmb_per_gb, arredondado ao ¥ INTEIRO (128×0.1=12.8→13, meio
    pra cima); US$ derivado do ¥ como sempre. SEM linhas de grid; taxa
    ausente → sem preço COM MOTIVO (nunca chute). Taxa é contratual →
    nunca 'velha' (is_stale=False)."""
    rate = buyer.ssd_rmb_per_gb
    if rate is None:
        return PriceQuote(status=UNQUOTED,
                          reason='SSD sem taxa ¥/GB — defina no comprador (admin)',
                          kind='ssd', gen='', tier_value=tier_value,
                          tier_unit=tier_unit)
    rmb = (Decimal(tier_value) * rate).quantize(Decimal('1'), ROUND_HALF_UP)
    usd = (rmb * buyer.fx_usd_rate).quantize(_CENT, ROUND_HALF_UP)
    return PriceQuote(status=PRICED, kind='ssd', gen='',
                      tier_value=tier_value, tier_unit=tier_unit,
                      price_min=usd, price_max=usd, rmb_min=rmb, rmb_max=rmb,
                      quote_date=None, is_stale=False, via='por GB')


def _chain_from_lists(lists, brand_name: str):
    """[(PriceList, rótulo)] na ordem de resolução do §4 (sem duplicatas) —
    PURO, a partir das listas ativas já carregadas. Fonte única da ordem:
    consumido por _resolution_chain (1 chip) e BuyerPricingContext (lote)."""
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


def _active_lists(buyer):
    return list(PriceList.all_companies
                .filter(buyer=buyer, active=True)
                .select_related('inherits_from', 'brand'))


def _resolution_chain(buyer, brand_name: str):
    """[(PriceList, rótulo)] na ordem de resolução do §4 (sem duplicatas)."""
    return _chain_from_lists(_active_lists(buyer), brand_name)


def _quote_no_list(buyer, kind, gen, tier_value, tier_unit) -> PriceQuote:
    return PriceQuote(status=NO_LIST, kind=kind, gen=gen,
                      tier_value=tier_value, tier_unit=tier_unit,
                      reason=f'comprador {buyer} sem lista de preços ativa')


def _quote_from_candidates(rows, chain, buyer, cfg,
                           kind, gen, tier_value, tier_unit) -> PriceQuote:
    """Cauda compartilhada de price() e do caminho de LOTE: escolhe a linha
    (1ª da cadeia vence) e monta o PriceQuote — status, staleness e a
    derivação ¥→US$ vivem SÓ aqui (fonte única)."""
    if not rows:
        return PriceQuote(status=NO_ROW, kind=kind, gen=gen,
                          tier_value=tier_value, tier_unit=tier_unit,
                          reason=f'faixa {kind}/{gen or "—"} '
                                 f'{tier_value.normalize():f}{tier_unit} fora da '
                                 'grade — adicionar linha na tabela')

    order = {pl.pk: i for i, (pl, _) in enumerate(chain)}
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

    stale = (row.quote_date is None or
             (date.today() - row.quote_date).days > cfg.staleness_days)
    # F10 (RMB canônico): o banco guarda ¥; o USD é DERIVADO AQUI — ¥ × taxa
    # CONTRATUAL do comprador (Buyer.fx_usd_rate; mudar a taxa nunca toca os
    # ¥). Derivar na construção mantém TODOS os consumidores de USD intactos
    # (value()/mid, valoração, export, congelamento F8).
    rate = buyer.fx_usd_rate
    return PriceQuote(
        status=PRICED,
        rmb_min=row.price_min, rmb_max=row.price_max,
        price_min=(row.price_min * rate).quantize(_CENT, ROUND_HALF_UP),
        price_max=(row.price_max * rate).quantize(_CENT, ROUND_HALF_UP),
        is_stale=stale, **base)


def _row_origin(kind, origin):
    """Origem efetiva da LINHA (2026-08-01): só o eMMC carrega origem na
    chave — celular (unificado) × PCB (por marca). ``origin`` vem do LOTE;
    fora de lote (busca avulsa) o default é 'phone' (o preço CONSERVADOR —
    o mesmo que o comprador assume para material sem origem declarada)."""
    if kind != 'emmc':
        return ''
    return origin if origin in (ORIGIN_PHONE, ORIGIN_PCB) else ORIGIN_PHONE


def price(result: dict, buyer, origin='') -> PriceQuote:
    """Quanto o ``buyer`` paga pelo chip do ``result``. Fonte única (§5).
    Caminho de 1 CHIP (card/busca): consulta estreita por chave. Para LOTES,
    use ``BuyerPricingContext`` — mesmo resultado, I/O constante.
    ``origin`` (2026-08-01) = origem do LOTE ('phone'|'pcb') — só muda o
    eMMC; vazio = 'phone' (conservador)."""
    err, key = derive_price_key(result or {})
    if err is not None:
        return err
    kind, gen, tier_value, tier_unit = key
    if kind == 'ssd':                       # LINEAR ¥/GB — sem grid (2026-07-24)
        return _ssd_quote(buyer, tier_value, tier_unit)

    chain = _resolution_chain(buyer, result.get('brand') or '')
    if not chain:
        return _quote_no_list(buyer, kind, gen, tier_value, tier_unit)

    rows = list(Price.all_companies.filter(
        price_list_id__in=[pl.pk for pl, _via in chain], kind=kind, gen=gen,
        tier_value=tier_value, tier_unit=tier_unit,
        origin=_row_origin(kind, origin),
    ).select_related('price_list'))
    return _quote_from_candidates(rows, chain, buyer, PricingConfig.get_config(),
                                  kind, gen, tier_value, tier_unit)


class BuyerPricingContext:
    """Contexto pré-carregado para precificar MUITAS linhas do MESMO buyer.

    Incidente 2026-07-16 (lote 42): ``price_lot`` fazia ~3 queries POR PN
    (cadeia de listas + linha de preço + PricingConfig.get_or_create) — num
    lote de centenas de linhas contra o Postgres remoto isso passava dos 30s
    do gunicorn, o worker morria em loop e o site inteiro parecia fora.
    Este contexto fixa o I/O do lote em **3 queries totais** (listas + TODAS
    as linhas do buyer + config), independente do tamanho do lote; sobra por
    linha só o ``classify()`` (CPU + cache do catálogo). O resultado é
    idêntico ao de ``price()`` — a cauda (_quote_from_candidates) é a mesma.
    """

    def __init__(self, buyer):
        self.buyer = buyer
        self.cfg = PricingConfig.get_config()
        self._lists = _active_lists(buyer)
        #: (price_list_id, kind, gen, tier_value, tier_unit, origin) → Price
        #  (Decimal hasheia por VALOR: 64 == 64.0 → a chave derivada casa a
        #  armazenada mesmo diferindo em casas decimais, como no filtro SQL.)
        #  origin (2026-08-01): '' exceto eMMC (phone|pcb).
        self._rows = {
            (r.price_list_id, r.kind, r.gen, r.tier_value, r.tier_unit,
             r.origin): r
            for r in Price.all_companies.filter(
                price_list_id__in=[pl.pk for pl in self._lists])
        }
        self._chains = {}

    def _chain(self, brand_name: str):
        if brand_name not in self._chains:
            self._chains[brand_name] = _chain_from_lists(self._lists, brand_name)
        return self._chains[brand_name]

    def price(self, result: dict, origin='') -> PriceQuote:
        """Equivalente a ``price(result, self.buyer, origin)`` — sem banco."""
        err, key = derive_price_key(result or {})
        if err is not None:
            return err
        kind, gen, tier_value, tier_unit = key

        chain = self._chain(result.get('brand') or '')
        if not chain:
            return _quote_no_list(self.buyer, kind, gen, tier_value, tier_unit)

        _og = _row_origin(kind, origin)
        rows = [r for r in (self._rows.get((pl.pk, kind, gen, tier_value,
                                            tier_unit, _og))
                            for pl, _via in chain)
                if r is not None]
        return _quote_from_candidates(rows, chain, self.buyer, self.cfg,
                                      kind, gen, tier_value, tier_unit)

    def price_from_key(self, kind, gen, tier_value, tier_unit,
                       brand_name='', no_key_reason='', origin=''):
        """Quote a partir da CHAVE MATERIALIZADA na entrada do estoque
        (F11.1) — ZERO classify, zero query: a chave foi derivada no
        lançamento (a bancada já classifica) e aqui só resolve contra a
        tabela viva. Chave ausente com motivo = NO_KEY gravado.
        ``origin`` (2026-08-01) = origem do LOTE — só muda o eMMC."""
        if not kind or tier_value is None:
            return _no_key(kind or '',
                           no_key_reason or 'chave de preço ausente')
        # Fold na LEITURA (dono 2026-07-21): chave materializada antes do
        # fold (price_gen='LPDDR4X'/'DDR3L' gravado) resolve na linha-base
        # do grid sem exigir resnapshot — leitor acompanha o escritor.
        gen = fold_gen(kind, gen or '')
        if kind == 'ssd':                   # LINEAR ¥/GB — sem grid (2026-07-24)
            return _ssd_quote(self.buyer, tier_value, tier_unit)
        chain = self._chain(brand_name or '')
        if not chain:
            return _quote_no_list(self.buyer, kind, gen, tier_value, tier_unit)
        _og = _row_origin(kind, origin)
        rows = [r for r in (self._rows.get((pl.pk, kind, gen, tier_value,
                                            tier_unit, _og))
                            for pl, _via in chain)
                if r is not None]
        return _quote_from_candidates(rows, chain, self.buyer, self.cfg,
                                      kind, gen, tier_value, tier_unit)


def quotes_for_admin(request, result, origin=''):
    """[(Buyer, PriceQuote)] para o card — papel ADMIN da empresa OU admin do
    SISTEMA (superuser — dono, 2026-07-17: a plataforma vê o preço no card
    mesmo sem Membership; é a única exceção ao "plataforma navega com
    Membership real": preço é dado DELA). O gate roda ANTES de qualquer
    query: operador, gerente e anônimo recebem lista vazia sem nem disparar
    a resolução. Fonte única do gate — consumida por chips/views (busca:
    JSON do search_api que alimenta a home) e estoque/views (bancada, F8)."""
    user = getattr(request, 'user', None)
    is_platform = bool(user is not None and user.is_authenticated
                       and user.is_superuser)
    is_company_admin = getattr(request, 'company_role', None) == 'admin'
    if not (is_company_admin or is_platform):
        return []
    from .models import Buyer
    # Admin de empresa: manager ESCOPADO (só os compradores da empresa dele).
    # Plataforma SEM membership: sem escopo de request → o manager escopado
    # explodiria (fail-closed); usa o cru — plataforma enxerga todas.
    manager = Buyer.objects if is_company_admin else Buyer.all_companies
    # origin (2026-08-01): origem do LOTE quando o card está na bancada;
    # na busca avulsa (sem lote) fica '' → eMMC assume 'phone' (conservador).
    return [(b, price(result, b, origin=origin))
            for b in manager.filter(active=True)]


def serialize_quote(buyer, q) -> dict:
    """PriceQuote → dict JSON-safe (Decimal vira string — nunca float) para o
    card client-side da home (search_api). F10: as DUAS moedas — min/max/mid
    seguem USD (derivado); 'rmb' é o ¥ de exibição ('90', sem zeros) e
    'mid_rmb' o ponto médio ¥ cru ('90.00')."""
    return {
        # F11.3 (sigilo): para a empresa a contraparte é o WhatTheChip —
        # nenhuma identidade de comprador sai da plataforma.
        'buyer': 'WhatTheChip', 'status': q.status, 'reason': q.reason,
        'min': str(q.price_min) if q.price_min is not None else None,
        'max': str(q.price_max) if q.price_max is not None else None,
        'mid': str(q.mid) if q.mid is not None else None,
        'rmb': q.rmb_display,
        'mid_rmb': str(q.mid_rmb) if q.mid_rmb is not None else None,
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

    I/O constante (incidente 2026-07-16): usa ``BuyerPricingContext`` — 3
    queries fixas para o lote inteiro em vez de ~3 por PN (que estourava o
    timeout do gunicorn em lote grande e derrubava o worker). Para VÁRIOS
    compradores use ``price_lot_multi`` (classify 1× por PN — F11.0).
    """
    (_b, report), = price_lot_multi(lot, [buyer])
    return report


def price_lot_multi(lot, buyers) -> list:
    """[(Buyer, LotPricingReport)] — o lote inteiro para VÁRIOS compradores,
    classificando cada PN **UMA vez** (F11.0, 2026-07-16): o painel de
    valoração roda um price_lot POR buyer e o classify dominava o tempo
    (lote 42: ~300 PNs × 3 buyers = ~900 classificações ≈ 28s). Aqui o
    classify roda 1× por PN DISTINTO e cada buyer só re-precifica o result
    (BuyerPricingContext, em memória). Mesmo resultado, N× menos CPU/I/O.
    """
    from chips.engine import classify   # lazy: evita acoplamento na importação

    entries = list(lot.entries.all())
    # F11.1: entrada com CHAVE materializada (ou NO_KEY com motivo) precifica
    # SEM classify — a chave nasceu no lançamento. O classify só roda para
    # entradas LEGADAS (tudo vazio: pré-F11.1, aprovação de pendência,
    # restores) — 1× por PN distinto; a cura definitiva é o resnapshot_lote.
    def _legacy(e):
        return (not e.price_kind and not e.price_key_reason
                and e.price_tier_value is None)

    results = {}                        # pn → result (1 classify por PN legado)
    for e in entries:
        if _legacy(e) and e.part_number not in results:
            results[e.part_number] = classify(e.part_number)

    # Origem do LOTE (2026-08-01): decide a tabela do eMMC (celular
    # unificado × PCB por marca) — os demais kinds ignoram.
    lot_origin = lot.origin

    out = []
    for buyer in buyers:
        ctx = BuyerPricingContext(buyer)
        report = LotPricingReport(totals={
            PricingConfig.SCENARIO_LOW: Decimal('0.00'),
            PricingConfig.SCENARIO_MID: Decimal('0.00'),
            PricingConfig.SCENARIO_HIGH: Decimal('0.00'),
        })
        for entry in entries:
            if entry.part_number in results:
                q = ctx.price(results[entry.part_number], origin=lot_origin)
            else:
                q = ctx.price_from_key(
                    entry.price_kind, entry.price_gen,
                    entry.price_tier_value, entry.price_tier_unit,
                    brand_name=entry.brand,
                    no_key_reason=entry.price_key_reason,
                    origin=lot_origin)
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
                report.unpriced.append((entry.part_number, qty,
                                        q.status, q.reason))
        out.append((buyer, report))
    return out
