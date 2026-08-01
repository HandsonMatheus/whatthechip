"""
WhatTheChip — Pricing (sistema de preços do comprador)
=======================================================
F2 do `PRECIFICACAO.md`: dado um chip classificado, quanto o COMPRADOR paga.

Modelos:
    Buyer         → o comprador (ex.: Wuquan). PERTENCE a uma empresa
                    (`Buyer.company`); ``company=NULL`` é RESERVADO para
                    comprador de plataforma (marketplace futuro) — hoje
                    invisível ao manager escopado, de propósito (fail-closed).
    PriceList     → lista de preços por (comprador × marca). ``brand=NULL`` =
                    lista GENÉRICA do comprador (a "UMA PÁGINA" para marcas
                    sem lista própria). Herança como DADO: ``inherits_from``
                    (1 nível, mesmo comprador) — "SK espelha Samsung" e
                    "genérica cai na Nanya" são regras DO COMPRADOR, não código.
    Price         → a linha de preço: chave (kind, gen, tier) + min/max em ¥
                    (RMB) + status (quoted / no_buy / unquoted) + auditoria.
    PricingConfig → singleton global (staleness, cenário default) — padrão
                    ProfitabilityConfig.

Decisões estruturais (PRECIFICACAO.md §1, §3, §12 e §12.18):
  - **RMB (¥) canônico em Decimal — F10 (2026-07-16).** O comprador pensa em
    ¥: o que ele digita é o que o banco guarda (``price_min``/``price_max``,
    SEM rename — a semântica dos campos virou ¥). O **USD é DERIVADO na
    leitura** (¥ × ``Buyer.fx_usd_rate``, taxa CONTRATUAL do dono) — mudar a
    taxa nunca toca os ¥. Faixa = min/max (exato ⇔ min == max). "Sem preço"
    NUNCA é 0: é ``status`` ≠ quoted com campos NULL. (⚠ exceção histórica:
    ``LotPricing`` congelados pré-F10 ficam em USD — snapshots.)
  - **Três estados de sem-preço** (achado na planilha real): ``no_buy`` =
    comprador não compra (o "NO"); ``unquoted`` = combo existe, aguardando
    cotação (as "células amarelas"); linha inexistente = fora da grade.
  - **company DENORMALIZADA** em PriceList e Price (herdada no ``save()``,
    mismatch rejeita) — o RLS exige a coluna LOCAL (padrão estoque T3/T4).
  - **Portão no MODELO** (``save()`` → ``full_clean()`` + CheckConstraints),
    como no KnownPart: cobre TODO write (admin, dashboard, import, shell).
  - **pghistory** em Buyer/PriceList/Price: preço é dado comercial sensível —
    quem mudou o quê é evento. ``updated_by``/``last_updated`` aparecem SÓ no
    admin (PRECIFICACAO §7); o dashboard do comprador não os mostra.
  - **RAM do eMCP fica FORA da chave** (regra do comprador: cota pela FAIXA de
    NAND + geração LPDDR; 64+3 e 64+4 custam igual) — por isso a chave é
    (kind, gen, tier) e não carrega a RAM.
"""

import re
from decimal import Decimal

import pghistory

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
# i18n (I18N.md): SÓ os rótulos de choices exibidos ao COMPRADOR no /partner/
# passam por gettext_lazy. Os VALORES ('quoted', 'no_buy'…) são chaves — nunca.
from django.utils.translation import gettext_lazy as _lazy

from tenancy.scope import CompanyScopedManager


# ── Vocabulário da CHAVE DE PREÇO (consumido também pelo engine na F3) ─────────
# kind = label_kind do chips/chip_types.py (fonte única de tipos). A unidade do
# tier segue a convenção inviolável do produto: pacote em GB, die em Gb.
# (GDDR saiu do mercado em 2026-07-23 — dono: "não rentável, remover do
#  backend". O kind não existe mais: derive_price_key devolve NO_KEY "tipo
#  fora do mercado" e a triagem descarta por tipo no assess_profitability.
#  Linhas gddr remanescentes do grid são apagadas pelo runbook.)
KIND_EMMC, KIND_UFS, KIND_EMCP, KIND_UMCP = 'emmc', 'ufs', 'emcp', 'umcp'
KIND_LPDDR, KIND_DDR, KIND_SSD = 'lpddr', 'ddr', 'ssd'

KIND_CHOICES = [
    (KIND_EMMC,  'eMMC'), (KIND_UFS, 'UFS'),
    (KIND_EMCP,  'eMCP'), (KIND_UMCP, 'uMCP'),
    (KIND_LPDDR, 'LPDDR'), (KIND_DDR, 'DDR'),
    # SSD (BGA/NVMe — dono 2026-07-24): preço LINEAR ¥/GB (Buyer.ssd_rmb_per_gb),
    # SEM linhas de grid — o kind existe p/ chave/caixa; o engine calcula.
    (KIND_SSD, 'SSD'),
]
KINDS = frozenset(k for k, _ in KIND_CHOICES)

UNIT_GB, UNIT_GBIT = 'GB', 'Gb'          # ⚠ case-sensitive: GB=byte, Gb=bit
UNIT_CHOICES = [(UNIT_GB, 'GB (pacote)'), (UNIT_GBIT, 'Gb (die)')]
KIND_UNIT = {                            # unidade OBRIGATÓRIA do tier por kind
    KIND_EMMC: UNIT_GB, KIND_UFS: UNIT_GB, KIND_EMCP: UNIT_GB,
    KIND_UMCP: UNIT_GB, KIND_LPDDR: UNIT_GB,
    KIND_DDR: UNIT_GBIT, KIND_SSD: UNIT_GB,
}
_GEN_RULE = {                            # forma OBRIGATÓRIA do gen por kind
    KIND_EMMC:  re.compile(r'^$'),           # eMMC/UFS não têm geração na chave
    KIND_UFS:   re.compile(r'^$'),
    # v3.1 (dono 2026-07-24, planilha v9 "unified by cap"): eMCP/uMCP também
    # SEM geração — a chave é SÓ o NAND (fold_gen esvazia qualquer LPDDRx).
    KIND_EMCP:  re.compile(r'^$'),
    KIND_UMCP:  re.compile(r'^$'),
    KIND_LPDDR: re.compile(r'^LPDDR\d'),
    KIND_DDR:   re.compile(r'^DDR\d'),       # DDR3/DDR3L/DDR4/DDR5…
    KIND_SSD:   re.compile(r'^$'),           # SSD: sem geração na chave
}

# Repactuação 2026-07-27 (ESTRUTURAL): eMCP/uMCP/LPDDR têm preço ÚNICO,
# brand-agnostic — a linha vive SÓ na lista GENÉRICA (a resolução de qualquer
# marca cai nela). Marca segue dimensão de preço APENAS em eMMC/UFS/DDR.
#: Origem do eMMC (acordo com o comprador, 2026-08-01): o MESMO PN vale
#: diferente conforme a placa de onde saiu — celular (desgastado, preço
#: unificado) × PCB (set-top/TV/notebook…, preço POR MARCA). A origem é
#: atributo do LOTE (declarada na abertura); aqui ela vira a dimensão extra
#: da chave de preço DO eMMC (os demais kinds têm origin='').
ORIGIN_PHONE, ORIGIN_PCB = 'phone', 'pcb'
ORIGIN_CHOICES = [(ORIGIN_PHONE, _lazy('Celular')), (ORIGIN_PCB, 'PCB')]

# eMMC SAIU do clube em 2026-08-01: ele é DUAL — subset phone unificado
# (genérica) + subset pcb por marca. UFS segue unificado ("PCB motherboards
# don't have UFS" — comprador, 2026-08-01).
UNIFIED_KINDS = frozenset({KIND_EMCP, KIND_UMCP, KIND_LPDDR, KIND_UFS})

STATUS_QUOTED, STATUS_NO_BUY, STATUS_UNQUOTED = 'quoted', 'no_buy', 'unquoted'
STATUS_NOT_MADE = 'not_made'
STATUS_CHOICES = [
    (STATUS_QUOTED,   _lazy('Cotado')),
    (STATUS_UNQUOTED, _lazy('Não cotado')),  # a "célula amarela" (aguardando)
    (STATUS_NOT_MADE, _lazy('Não fabricado')),  # a marca não produz este combo
                                             # (grid unificado, dono 2026-07-07)
    (STATUS_NO_BUY,   _lazy('Não compro')),  # o "NO" da planilha: FABRICA, mas
                                             # o comprador não quer (≠ not_made)
]


def valid_gen(kind: str, gen: str) -> bool:
    """A geração casa a forma canônica exigida pelo kind? (fonte única — o
    portão do modelo e o pricing/engine leem a MESMA regra)."""
    rule = _GEN_RULE.get(kind)
    return bool(rule and rule.match(gen or ''))


# ── Fold de geração na CATEGORIA COMERCIAL (dono, 2026-07-11/21/23/24) ────────
# "DDR3L e DDR3 são a mesma coisa" · "LPDDR4X e LPDDR4 são a mesma coisa,
# uma só caixa" — variantes de tensão (L/U) e o sufixo X precificam e
# ENCAIXOTAM como a geração-base. v3.1 (2026-07-24, planilha v9 "unified by
# cap"): nos combos eMCP/uMCP a chave é SÓ o NAND — QUALQUER geração de RAM
# dobra pra VAZIO (a geração segue nas specs/rótulo real; sai só da chave).
# FONTE ÚNICA: derive (escrita da chave), price_from_key (leitura de chave
# legada gravada), CategoryCode (caixa) e o grid (Price.save) dobram AQUI —
# leitor e escritor nunca divergem. (GDDR: kind extinto em 2026-07-23.)
_FOLD_DDR   = re.compile(r'^(DDR\d+)[LU]$')
_FOLD_LPDDR = re.compile(r'^(LPDDR\d+)X$')


def fold_gen(kind: str, gen: str) -> str:
    """Geração-base da CATEGORIA comercial (caixa/preço) para este kind."""
    g = (gen or '').strip()
    if kind == KIND_DDR:
        m = _FOLD_DDR.match(g)
        if m:
            return m.group(1)
    elif kind == KIND_LPDDR:
        m = _FOLD_LPDDR.match(g)
        if m:
            return m.group(1)
    elif kind in (KIND_EMCP, KIND_UMCP):
        return ''                    # v3.1: combo keia SÓ pelo NAND
    return g


def gen_spellings(kind: str, gen: str) -> list[str]:
    """Todas as grafias que DOBRAM nesta geração-base (p/ consultas em dado
    ainda não canonizado — grid antigo, chave materializada pré-fold).
    ⚠ eMCP/uMCP: a base é '' e as grafias legadas são QUALQUER LPDDRx —
    não-enumerável; consultas nesses kinds devem ignorar o gen."""
    out = [gen]
    if kind == KIND_DDR:
        out += [f'{gen}L', f'{gen}U']
    elif kind == KIND_LPDDR:
        out += [f'{gen}X']
    return out


@pghistory.track()  # auditoria: criar/desativar comprador é evento comercial
class Buyer(models.Model):
    """O comprador de chips (ex.: Wuquan). Dono das listas de preço."""

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.PROTECT, null=True, blank=True,
        related_name='buyers', verbose_name='Empresa',
        help_text='De quem é este comprador. VAZIO = comprador de plataforma '
                  '(marketplace futuro) — invisível às empresas até lá.')
    name   = models.CharField(max_length=120, verbose_name='Nome')
    slug   = models.SlugField(max_length=60, unique=True, verbose_name='Slug')
    active = models.BooleanField(default=True, verbose_name='Ativo')
    # As contas que logam no dashboard /partner/ deste comprador (F6). O vínculo
    # é ESTE M2M — comprador é externo, não tem Membership (PLANO_MULTITENANT §8).
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='buyers',
        verbose_name='Contas do comprador',
        help_text='Usuários que acessam o dashboard /partner/ deste comprador.')
    notes      = models.TextField(blank=True, default='', verbose_name='Notas')
    # F11.3 (sigilo, dono 2026-07-16 — revisado): para a EMPRESA-CLIENTE a
    # contraparte é o WhatTheChip — o comprador nem EXISTE nas telas dela
    # (rótulo fixo 'WhatTheChip' em card/JSON/export/valoração). Nome real
    # só no Django admin (plataforma) e no /partner/ do próprio comprador.
    # F10 (RMB canônico, plano §12.18): taxa CONTRATUAL ¥→US$ deste comprador
    # (dono gere; pghistory audita a mudança). Os Price guardam ¥ — o USD é
    # DERIVADO na leitura (¥ × taxa); mudar a taxa NUNCA toca os ¥ gravados.
    fx_usd_rate = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('0.14'),
        verbose_name='Taxa ¥→US$ (contratual)',
        help_text='US$ por 1 ¥ (ex.: 0.14). Muda só quando o contrato mudar; '
                  'os preços em ¥ não são afetados.')
    # TRAVA anti-dupla-migração (incidente local 2026-07-16: o
    # migrate_prices_to_rmb rodou 2× e os ¥ viraram 6,7× maiores — ¥90→¥600).
    # True = os Price deste comprador JÁ estão em ¥; o comando RECUSA re-rodar.
    prices_in_rmb = models.BooleanField(
        default=False, verbose_name='Preços já em ¥ (RMB)',
        help_text='Trava do migrate_prices_to_rmb: marcado = a migração F10 '
                  'já rodou neste banco — re-rodar multiplicaria os valores.')
    # SSD (dono 2026-07-24): o comprador compra SSD LINEAR por GB
    # ("512GB×0.1=51rmb") — taxa contratual, igual à fx_usd_rate. NULL =
    # ainda sem taxa → SSD fica "sem preço" com motivo (nunca chute).
    ssd_rmb_per_gb = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        verbose_name='SSD — ¥ por GB',
        help_text='Preço linear do SSD: ¥ por GB (ex.: 0.10 → 512GB = ¥51). '
                  'Arredonda ao ¥ inteiro. Vazio = SSD sem preço.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Comprador'
        verbose_name_plural = 'Compradores'
        ordering = ['name']
        base_manager_name = 'all_companies'
        # default = CRU (ver estoque/models.py: a validação de UniqueConstraint
        # do Django 5 usa _default_manager — fail-closed ali quebrava o admin
        # de plataforma com CompanyScopeMissing, bug 2026-07-09). O caminho
        # escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'],
                                    name='unique_buyer_company_name'),
        ]

    def __str__(self):
        return self.name

    @property
    def fx_usd_rate_display(self) -> str:
        """Taxa sem zeros à direita p/ o header do /partner/ ('0.14').
        ⚠ Property (não filtro): floatformat SEMPRE localiza (ignora
        {% localize off %}) e viraria '0,1400' em pt-br; dinheiro/taxa é
        com PONTO. O :f evita o 9E+1 do normalize() (PRECIFICACAO §12)."""
        return f'{self.fx_usd_rate.normalize():f}'


@pghistory.track()  # auditoria: criar lista / trocar herança muda preços em massa
class PriceList(models.Model):
    """Lista de preços de um comprador para UMA marca (ou a GENÉRICA).

    Resolução de preço (F3, PRECIFICACAO §4): lista da marca → inherits_from
    (1 salto) → lista genérica do comprador → inherits_from da genérica → nada.
    Linha própria SEMPRE vence linha herdada (override).
    """

    buyer = models.ForeignKey(Buyer, on_delete=models.PROTECT,
                              related_name='price_lists', verbose_name='Comprador')
    brand = models.ForeignKey(
        'chips.Brand', on_delete=models.PROTECT, null=True, blank=True,
        related_name='+', verbose_name='Marca',
        help_text='VAZIO = lista GENÉRICA do comprador (marcas sem lista própria).')
    # Denormalizada do buyer (RLS exige coluna local — padrão estoque T3/T4).
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    inherits_from = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='inherited_by', verbose_name='Herda de',
        help_text='Fallback como DADO (regra do comprador): linha ausente aqui '
                  'é buscada na lista-alvo. 1 nível; mesmo comprador.')
    active     = models.BooleanField(default=True, verbose_name='Ativa')
    notes      = models.TextField(blank=True, default='', verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criada em')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Lista de preços'
        verbose_name_plural = 'Listas de preços'
        ordering = ['buyer__name', 'brand__name']
        base_manager_name = 'all_companies'
        # default = CRU (ver estoque/models.py: a validação de UniqueConstraint
        # do Django 5 usa _default_manager — fail-closed ali quebrava o admin
        # de plataforma com CompanyScopeMissing, bug 2026-07-09). O caminho
        # escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['buyer', 'brand'],
                                    name='unique_pricelist_buyer_brand'),
            # Postgres trata NULL como distinto no unique acima — esta trava
            # garante UMA lista genérica por comprador.
            models.UniqueConstraint(fields=['buyer'],
                                    condition=Q(brand__isnull=True),
                                    name='unique_generic_list_per_buyer'),
        ]

    def __str__(self):
        alvo = self.brand.name if self.brand_id else 'Genérica'
        return f'{self.buyer} · {alvo}'

    def clean(self):
        super().clean()
        if self.inherits_from_id:
            if self.pk and self.inherits_from_id == self.pk:
                raise ValidationError(
                    {'inherits_from': 'Uma lista não pode herdar de si mesma.'})
            alvo = self.inherits_from
            if alvo.buyer_id != self.buyer_id:
                raise ValidationError(
                    {'inherits_from': 'Herança é interna ao comprador — a '
                                      'lista-alvo pertence a outro comprador.'})
            # 1 NÍVEL (PRECIFICACAO §4): a lista-alvo não pode herdar também —
            # mantém a resolução previsível e mata qualquer ciclo pela raiz.
            if alvo.inherits_from_id:
                raise ValidationError(
                    {'inherits_from': 'Herança é limitada a 1 nível: a lista-'
                                      'alvo já herda de outra.'})

    def save(self, *args, **kwargs):
        # company denormalizada: herda do buyer; mismatch é bug de chamador.
        if self.buyer_id:
            buyer_company_id = Buyer.all_companies.values_list(
                'company_id', flat=True).get(pk=self.buyer_id)
            if self.company_id and buyer_company_id != self.company_id:
                raise ValidationError(
                    {'company': 'A lista pertence a uma empresa diferente do comprador.'})
            self.company_id = buyer_company_id
        # Portão no MODELO (padrão KnownPart) — SEM validate_unique/constraints:
        # essas validações CONSULTAM o _default_manager, que aqui é o escopado
        # fail-closed (explodiria fora de request). A unicidade continua
        # garantida pelas UniqueConstraints do BANCO (IntegrityError).
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


@pghistory.track()  # auditoria: TODA mudança de preço é evento (quem/quando/valor)
class Price(models.Model):
    """Uma linha de preço: chave (kind, gen, tier) → ¥ (RMB) min/max + status.

    A leitura para humanos: "eMCP LPDDR4X 64GB → ¥90 (cotado 2026-06-29)".
    F10 (RMB canônico): o ¥ digitado NUNCA muda; o USD (ex.: US$ 12.60 a taxa
    0.14) é derivado na leitura pelo pricing/engine — nunca gravado aqui.
    ``updated_by``/``last_updated`` são auditoria interna — NUNCA aparecem no
    dashboard do comprador (PRECIFICACAO §7).
    """

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE,
                                   related_name='prices', verbose_name='Lista')
    # Denormalizada da lista (RLS exige coluna local — padrão estoque T3/T4).
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)

    # ── A CHAVE (kind, gen, tier) ────────────────────────────────────────────
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, verbose_name='Tipo')
    gen  = models.CharField(
        max_length=12, blank=True, default='', verbose_name='Geração',
        help_text='Token canônico: LPDDR4 / DDR3… Vazio para eMMC/UFS/eMCP/'
                  'uMCP (v3.1: combo keia SÓ pelo NAND — planilha v9).')
    tier_value = models.DecimalField(
        max_digits=6, decimal_places=1, verbose_name='Faixa de capacidade',
        help_text='eMCP/uMCP: GB do NAND (RAM — tamanho E geração — fora da '
                  'chave; v3.1). DDR: densidade do die em Gb.')
    tier_unit = models.CharField(max_length=2, choices=UNIT_CHOICES,
                                 verbose_name='Unidade')
    origin = models.CharField(
        max_length=5, blank=True, default='',
        choices=[('', '—')] + ORIGIN_CHOICES, verbose_name='Origem',
        help_text='SÓ para eMMC (2026-08-01): celular = preço unificado '
                  '(genérica); PCB = por marca. Demais tipos: vazio.')

    # ── O VALOR (¥ RMB, Decimal — nunca float; §1.3/§1.4 + §12.18) ──────────
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default=STATUS_UNQUOTED, verbose_name='Status')
    price_min = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='¥ mín. (RMB)',
        help_text='Em yuan (¥). O USD é derivado na leitura: ¥ × taxa '
                  'contratual do comprador (Buyer.fx_usd_rate).')
    price_max = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='¥ máx. (RMB)',
        help_text='Preço FIXO (2026-07-07): igual ao mínimo.')
    quote_date = models.DateField(null=True, blank=True, verbose_name='Data da cotação',
                                  help_text='Sem data = tratado como referência antiga (≈).')

    source = models.CharField(max_length=200, blank=True, default='', verbose_name='Fonte')
    notes  = models.TextField(blank=True, default='', verbose_name='Notas')

    # ── Auditoria (Features 2/3 do PRECIFICACAO: só backend/admin) ─────────
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    updated_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+', verbose_name='Atualizado por',
                                     help_text='Setado pelo chamador (admin/dashboard/import).')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Preço'
        verbose_name_plural = 'Preços'
        ordering = ['price_list', 'kind', 'gen', 'tier_value']
        base_manager_name = 'all_companies'
        # default = CRU (ver estoque/models.py: a validação de UniqueConstraint
        # do Django 5 usa _default_manager — fail-closed ali quebrava o admin
        # de plataforma com CompanyScopeMissing, bug 2026-07-09). O caminho
        # escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        indexes = [
            models.Index(fields=['company', 'kind', 'gen'],
                         name='price_company_kind_gen'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['price_list', 'kind', 'gen', 'tier_value', 'tier_unit',
                        'origin'],
                name='unique_price_key_origin'),
            # origem: vocabulário + só eMMC a carrega (2026-08-01)
            models.CheckConstraint(
                name='price_origin_vocab',
                condition=Q(origin__in=['', ORIGIN_PHONE, ORIGIN_PCB])),
            models.CheckConstraint(
                name='price_origin_emmc_only',
                condition=(Q(kind=KIND_EMMC,
                             origin__in=[ORIGIN_PHONE, ORIGIN_PCB])
                           | (~Q(kind=KIND_EMMC) & Q(origin='')))),
            # sorted(): ordem ESTÁVEL — frozenset cru mudaria a ordem a cada
            # processo e o makemigrations veria a constraint como "alterada".
            models.CheckConstraint(name='price_kind_vocab',
                                   condition=Q(kind__in=sorted(KINDS))),
            models.CheckConstraint(
                name='price_status_vocab',
                condition=Q(status__in=[STATUS_QUOTED, STATUS_NO_BUY,
                                        STATUS_UNQUOTED, STATUS_NOT_MADE])),
            models.CheckConstraint(name='price_tier_unit_vocab',
                                   condition=Q(tier_unit__in=[UNIT_GB, UNIT_GBIT])),
            models.CheckConstraint(name='price_tier_positive',
                                   condition=Q(tier_value__gt=0)),
            # Faixa coerente: min ≤ max (quando ambos existem).
            models.CheckConstraint(
                name='price_min_lte_max',
                condition=Q(price_min__isnull=True) | Q(price_max__isnull=True)
                          | Q(price_min__lte=F('price_max'))),
            # PREÇO FIXO (decisão do dono, 2026-07-07): faixa DESATIVADA —
            # cotado exige min == max. As duas colunas ficam (representação
            # interna reversível); reativar faixa = remover esta trava + a
            # regra no clean() (migração 0005 achatou as faixas no ponto médio).
            # Repactuação 2026-07-27: eMCP/uMCP são os ÚNICOS em FAIXA
            # (mín ≤ máx); todo o resto segue preço FIXO (mín = máx).
            models.CheckConstraint(
                name='price_fixed_only',
                condition=~Q(status=STATUS_QUOTED)
                          | Q(price_min=F('price_max'))
                          | Q(kind__in=(KIND_EMCP, KIND_UMCP))),
            models.CheckConstraint(
                name='price_range_ordered',
                condition=Q(price_min__isnull=True)
                          | Q(price_min__lte=F('price_max'))),
            # quoted ⇒ tem valor; no_buy/unquoted ⇒ NÃO tem valor (nunca 0).
            models.CheckConstraint(
                name='price_quoted_has_value',
                condition=~Q(status=STATUS_QUOTED)
                          | (Q(price_min__isnull=False) & Q(price_max__isnull=False))),
            models.CheckConstraint(
                name='price_unpriced_is_null',
                condition=Q(status=STATUS_QUOTED)
                          | (Q(price_min__isnull=True) & Q(price_max__isnull=True))),
        ]

    def __str__(self):
        gen = self.gen or '—'
        return f'{self.price_list} · {self.kind}/{gen} {self.tier_value}{self.tier_unit}'

    # ── Helpers de leitura (F3 usa; sem lógica de negócio além do óbvio) ────
    @property
    def is_range(self) -> bool:
        return (self.status == STATUS_QUOTED and self.price_min is not None
                and self.price_max is not None and self.price_min != self.price_max)

    def clean(self):
        super().clean()
        errors = {}
        # kind × unidade: pacote em GB, die em Gb (convenção inviolável).
        expected_unit = KIND_UNIT.get(self.kind)
        if expected_unit and self.tier_unit != expected_unit:
            errors['tier_unit'] = (f'{self.kind} usa {expected_unit} '
                                   f'(pacote em GB, die em Gb).')
        # kind × gen: forma canônica obrigatória (nunca genérico na chave).
        rule = _GEN_RULE.get(self.kind)
        if rule and not rule.match(self.gen or ''):
            if self.kind in (KIND_EMMC, KIND_UFS, KIND_EMCP, KIND_UMCP):
                errors['gen'] = ('eMMC/UFS/eMCP/uMCP não têm geração na chave '
                                 '— deixe vazio (combo keia SÓ pelo NAND).')
            else:
                errors['gen'] = (f'Geração inválida para {self.kind}: '
                                 f'{self.gen!r} (esperado token canônico, '
                                 f'ex.: LPDDR4X / DDR3L).')
        # Origem (2026-08-01): eMMC EXIGE phone|pcb; os demais, vazio.
        if self.kind == KIND_EMMC:
            if self.origin not in (ORIGIN_PHONE, ORIGIN_PCB):
                errors['origin'] = ('eMMC exige a origem: celular (phone) ou '
                                    'PCB — acordo de 2026-08-01.')
        elif (self.origin or ''):
            errors['origin'] = (f'{self.kind} não carrega origem — ela é '
                                f'exclusiva do eMMC (2026-08-01).')
        # Espelho amigável das CheckConstraints (mensagem melhor que IntegrityError).
        if self.status == STATUS_QUOTED:
            if self.price_min is None or self.price_max is None:
                errors['price_min'] = 'Cotado exige o preço em ¥ (RMB).'
            elif self.price_min > self.price_max:
                errors['price_min'] = 'Faixa invertida: mín > máx.'
            elif (self.price_min != self.price_max
                    and self.kind not in (KIND_EMCP, KIND_UMCP)):
                # Repactuação 2026-07-27 (planilha final do comprador):
                # eMCP/uMCP são os ÚNICOS em FAIXA (ex.: ¥90–100); todo o
                # resto segue FIXO (decisão 2026-07-07 preservada).
                errors['price_min'] = ('Preço é FIXO para este tipo — faixa '
                                       'só em eMCP/uMCP (repactuação '
                                       '2026-07-27). Informe UM valor.')
        else:
            if self.price_min is not None or self.price_max is not None:
                errors['status'] = ('Sem-preço (não cotado / não fabricado / '
                                    'não compro) não carrega valor — limpe o ¥.')
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Fold da geração (dono 2026-07-21): o grid guarda a geração-BASE da
        # categoria (DDR3L→DDR3, LPDDR4X→LPDDR4 — fold_gen, fonte única).
        # Fill-forward silencioso: linha antiga se canoniza no próximo save.
        # Se a linha-BASE já existe na mesma lista, ValidationError amigável
        # (não IntegrityError seco): o merge de preços divergentes é decisão
        # do dono, no admin — o seed lista as linhas dobráveis de antemão.
        _gen_original = (self.gen or '').strip()
        self.gen = fold_gen(self.kind, _gen_original)
        if self.gen != _gen_original and self.price_list_id:
            twin = Price.all_companies.filter(
                price_list_id=self.price_list_id, kind=self.kind,
                gen=self.gen, tier_value=self.tier_value,
                tier_unit=self.tier_unit,
                origin=self.origin or '').exclude(pk=self.pk)
            if twin.exists():
                raise ValidationError({'gen': (
                    f'{_gen_original!r} dobra na geração-base {self.gen!r} '
                    f'(mesma categoria — dono 2026-07-21) e esta lista JÁ tem '
                    f'a linha-base. Funda as duas no admin (decida o ¥) e '
                    f'apague esta.')})
        # company denormalizada: herda da lista; mismatch é bug de chamador.
        if self.price_list_id:
            _brand_id, list_company_id = PriceList.all_companies.values_list(
                'brand_id', 'company_id').get(pk=self.price_list_id)
            # Repactuação 2026-07-27 (ESTRUTURAL): preço unificado NÃO tem
            # marca — linha de eMCP/uMCP/LPDDR só existe na lista GENÉRICA.
            if self.kind in UNIFIED_KINDS and _brand_id is not None:
                raise ValidationError({'kind': (
                    f'{self.kind}: preço UNIFICADO (repactuação 2026-07-27) — '
                    f'a linha vive só na lista genérica; listas de marca não '
                    f'têm mais este tipo.')})
            # eMMC dual (2026-08-01): o subset CELULAR é unificado — só na
            # genérica; o subset PCB é por marca (marca OU genérica-Other).
            if (self.kind == KIND_EMMC and self.origin == ORIGIN_PHONE
                    and _brand_id is not None):
                raise ValidationError({'origin': (
                    'eMMC de CELULAR é unificado — a linha vive só na lista '
                    'genérica (acordo 2026-08-01); listas de marca só têm o '
                    'subset PCB.')})
            if self.company_id and list_company_id != self.company_id:
                raise ValidationError(
                    {'company': 'O preço pertence a uma empresa diferente da lista.'})
            self.company_id = list_company_id
        # Portão no MODELO (padrão KnownPart) — SEM validate_unique/constraints:
        # essas validações CONSULTAM o _default_manager, que aqui é o escopado
        # fail-closed (explodiria fora de request). A unicidade da CHAVE continua
        # garantida pela UniqueConstraint do BANCO (IntegrityError).
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


class FxRate(models.Model):
    """Taxa CNY→USD **mid-market DIÁRIA** (PLANO_FX, decisões 2026-08-01).

    O acordo com o comprador é taxa de MERCADO travada no fechamento do
    lote — o aberto exibe "≈ US$" vivo derivado DAQUI. A taxa contratual
    morreu; `Buyer.fx_usd_rate` ficou como BOOTSTRAP (última defesa
    enquanto esta tabela está vazia — sai do caminho no 1º fetch).

    Um número POR DIA, de referência pública (verificável pelos dois lados
    — mata disputa; intradia do CNY é banda administrada ±2%). Histórico
    append-only auditável; `is_fallback` marca dia em que a fonte caiu e a
    última taxa conhecida foi repetida. Tabela GLOBAL (dado de plataforma,
    como o catálogo — declarada no TenancyDeclarationTests)."""

    date = models.DateField(unique=True, verbose_name='Data')
    rate = models.DecimalField(max_digits=8, decimal_places=4,
                               verbose_name='CNY→USD',
                               help_text='Mid-market do dia (4 casas — '
                                         'PLANO_FX §1.7).')
    source = models.CharField(max_length=80, blank=True, default='',
                              verbose_name='Fonte')
    is_fallback = models.BooleanField(
        default=False, verbose_name='Fallback',
        help_text='Fonte fora do ar — repetiu a última taxa conhecida.')
    fetched_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Buscada em')

    class Meta:
        verbose_name = 'Taxa de câmbio (dia)'
        verbose_name_plural = 'Taxas de câmbio'
        ordering = ['-date']

    def __str__(self):
        fb = ' (fallback)' if self.is_fallback else ''
        return f'{self.date}: 1 ¥ = US$ {self.rate}{fb}'

    @classmethod
    def current(cls):
        """A taxa vigente = a mais recente (hoje, ou a última que entrou).
        None com a tabela vazia (aí vale o bootstrap contratual)."""
        return cls.objects.order_by('-date').first()


@pghistory.track()  # auditoria: o congelamento é o registro "vendi com qual tabela"
class LotPricing(models.Model):
    """F8 — valoração CONGELADA de um lote no fechamento (PRECIFICACAO §1.7).

    A exibição do preço é sempre on-read (tabela viva); ao FECHAR o lote, este
    snapshot grava com qual cotação o lote foi valorado — por comprador. Reabrir
    e fechar de novo cria OUTRO registro (append; o histórico fica). Visível só
    para admin/plataforma; o gerente fecha o lote mas não vê valores (§7).
    Moeda: **USD sempre** (decisão F10 §12.18 — valoração/export são USD; pós-
    virada o USD já vem DERIVADO do ¥ pelo engine; congelados antigos idem).
    """

    lot   = models.ForeignKey('estoque.Lot', on_delete=models.CASCADE,
                              related_name='pricings', verbose_name='Lote')
    buyer = models.ForeignKey(Buyer, on_delete=models.PROTECT,
                              related_name='+', verbose_name='Comprador')
    # Denormalizada do lote (RLS exige coluna local — padrão estoque T3/T4).
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)

    total_low  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total (baixo)')
    total_mid  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total (médio)')
    total_high = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total (alto)')
    priced_units = models.PositiveIntegerField(verbose_name='Unid. precificadas')
    total_units  = models.PositiveIntegerField(verbose_name='Unid. totais')
    priced_lines = models.PositiveIntegerField(verbose_name='Linhas precificadas')
    total_lines  = models.PositiveIntegerField(verbose_name='Linhas totais')
    #: Auditoria por linha: [{pn, qty, status, min, max, reason, via}] — artefato
    #: de registro (não é consultado relacionalmente; pro relacional há o Price).
    lines = models.JSONField(default=list, verbose_name='Linhas (auditoria)')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Congelado em')
    closed_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='Fechado por')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Valoração de lote (congelada)'
        verbose_name_plural = 'Valorações de lote (congeladas)'
        ordering = ['-created_at']
        base_manager_name = 'all_companies'
        # default = CRU (ver estoque/models.py: a validação de UniqueConstraint
        # do Django 5 usa _default_manager — fail-closed ali quebrava o admin
        # de plataforma com CompanyScopeMissing, bug 2026-07-09). O caminho
        # escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        indexes = [models.Index(fields=['company', 'lot'],
                                name='lotpricing_company_lot')]

    def __str__(self):
        return f'Lote #{self.lot_id} · {self.buyer} · {self.created_at:%d/%m/%Y}'

    @property
    def coverage_units(self) -> float:
        return (100.0 * self.priced_units / self.total_units) if self.total_units else 0.0

    def save(self, *args, **kwargs):
        if self.lot_id and not self.company_id:
            self.company_id = self.lot.company_id      # herda do lote (RLS local)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


@pghistory.track()  # a trilha da moderação também é auditável
class PriceChangeRequest(models.Model):
    """F6.1 — MODERAÇÃO (dono, 2026-07-07): mudança feita pelo COMPRADOR no
    /partner/ **não vale na hora** — vira um PEDIDO pendente que o dono
    aprova/rejeita no Django admin. Só a aprovação aplica no `Price` (e aí sim
    reflete em card/bancada/valoração). É o mesmo padrão four-eyes do catálogo
    (KnownPart.review_status): parceiro propõe, plataforma dispõe.

    Regra de unicidade: no máximo UM pedido pendente por linha — o parceiro
    editar de novo ATUALIZA o pedido pendente (não empilha)."""

    REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED = 'pending', 'approved', 'rejected'
    REVIEW_CHOICES = [(REVIEW_PENDING, _lazy('Pendente')),
                      (REVIEW_APPROVED, _lazy('Aprovado')),
                      (REVIEW_REJECTED, _lazy('Rejeitado'))]

    price = models.ForeignKey(Price, on_delete=models.CASCADE,
                              related_name='change_requests', verbose_name='Linha')
    # Denormalizada (RLS exige coluna local — padrão da casa).
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)

    # O PEDIDO (para onde o comprador quer levar a linha) — em ¥ (F10):
    new_status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                  verbose_name='Novo estado')
    # Faixa (repactuação 2026-07-27, só eMCP/uMCP): new_price = mínimo e
    # new_price_max = máximo; NULL em new_price_max = preço fixo (min = max).
    new_price_max = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='¥ máx. proposto (faixa)')
    new_price = models.DecimalField(max_digits=8, decimal_places=2,
                                    null=True, blank=True, verbose_name='Novo ¥')
    # Snapshot do ANTES (para o admin decidir vendo o delta):
    old_status = models.CharField(max_length=10, verbose_name='Estado anterior')
    old_price = models.DecimalField(max_digits=8, decimal_places=2,
                                    null=True, blank=True, verbose_name='¥ anterior')

    review_status = models.CharField(max_length=10, choices=REVIEW_CHOICES,
                                     default=REVIEW_PENDING, verbose_name='Revisão')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+', verbose_name='Pedido por')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Pedido em')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+', verbose_name='Revisado por')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Revisado em')
    #: 🔔 Notificações do parceiro: decisão (aprovado/rejeitado) ainda não vista
    #: no /partner/notifications/. Marcado True quando o parceiro abre a página
    #: (um usuário do comprador vê = o comprador viu — v1).
    seen_by_partner = models.BooleanField(default=False, verbose_name='Visto pelo parceiro')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Mudança de preço (revisão)'
        verbose_name_plural = 'Mudanças de preço (revisão)'
        ordering = ['-created_at']
        base_manager_name = 'all_companies'
        # default = CRU (ver estoque/models.py: a validação de UniqueConstraint
        # do Django 5 usa _default_manager — fail-closed ali quebrava o admin
        # de plataforma com CompanyScopeMissing, bug 2026-07-09). O caminho
        # escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['price'],
                                    condition=Q(review_status='pending'),
                                    name='one_pending_per_price'),
            models.CheckConstraint(
                name='pcr_review_vocab',
                condition=Q(review_status__in=['pending', 'approved', 'rejected'])),
            # Pedido coerente: cotado ⇒ tem USD; demais ⇒ sem USD (nunca 0).
            models.CheckConstraint(
                name='pcr_quoted_has_value',
                condition=~Q(new_status=STATUS_QUOTED) | Q(new_price__isnull=False)),
            models.CheckConstraint(
                name='pcr_unpriced_is_null',
                condition=Q(new_status=STATUS_QUOTED) | Q(new_price__isnull=True)),
        ]

    def __str__(self):
        alvo = (f'¥ {self.new_price}' if self.new_status == STATUS_QUOTED
                else dict(STATUS_CHOICES).get(self.new_status, self.new_status))
        return f'{self.price} → {alvo}'

    def clean(self):
        super().clean()
        if self.new_status == STATUS_QUOTED and self.new_price is None:
            raise ValidationError({'new_price': 'Pedido "Cotado" exige o ¥.'})
        if self.new_status != STATUS_QUOTED and self.new_price is not None:
            raise ValidationError({'new_price': 'Só "Cotado" carrega ¥.'})

    def save(self, *args, **kwargs):
        if self.price_id and not self.company_id:
            self.company_id = Price.all_companies.values_list(
                'company_id', flat=True).get(pk=self.price_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

    # ── Decisão do admin (chamada pelas actions do Django admin) ────────────
    def approve(self, reviewer):
        """Aplica o pedido no Price (via portão do modelo) e fecha a revisão.
        `quote_date` = data da APROVAÇÃO (é quando passa a valer);
        `updated_by` = quem PEDIU (o parceiro — auditoria fiel à origem)."""
        from datetime import date as _date
        from django.utils import timezone as _tz
        p = self.price
        p.status = self.new_status
        if self.new_status == STATUS_QUOTED:
            p.price_min = self.new_price
            p.price_max = (self.new_price_max
                           if self.new_price_max is not None else self.new_price)
            p.quote_date = _date.today()
        else:
            p.price_min = p.price_max = None
            p.quote_date = None
        p.updated_by = self.requested_by
        p.save()
        self.review_status = self.REVIEW_APPROVED
        self.reviewed_by, self.reviewed_at = reviewer, _tz.now()
        self.save()

    def reject(self, reviewer):
        """Rejeita: o Price fica exatamente como estava."""
        from django.utils import timezone as _tz
        self.review_status = self.REVIEW_REJECTED
        self.reviewed_by, self.reviewed_at = reviewer, _tz.now()
        self.save()


class CategoryCode(models.Model):
    """F12 v3 — o código UNIVERSAL da categoria comercial (convenção mundial).

    A convenção (dono, 2026-07-23) vive em ``pricing/convention.py`` — FIXA,
    global e eterna: ``LETRA-##`` com letra fixa por tipo (KIND_LETTER) e
    número congelado da TABELA FUNDADORA. A categoria **deriva do CHIP**
    (tipo + geração + faixa — o que o decoder busca no banco), NUNCA do grid:
    "preço até pode ficar sem, categoria não". Categoria inédita ganha o
    próximo número livre DA LETRA na primeira aprovação (append-only; número
    nunca reordena nem se reusa). ``00`` é reservado (H-00 fila / R-00
    refino — baldes especiais, não são linhas desta tabela).
    """

    kind = models.CharField(max_length=8, verbose_name='Tipo')
    gen  = models.CharField(max_length=12, blank=True, default='',
                            verbose_name='Geração')
    tier_value = models.DecimalField(max_digits=6, decimal_places=1,
                                     verbose_name='Faixa')
    tier_unit = models.CharField(max_length=2, verbose_name='Unidade')
    code = models.PositiveIntegerField(verbose_name='Número (na letra)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Código de categoria (F12)'
        verbose_name_plural = 'Códigos de categoria (F12)'
        ordering = ['kind', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['kind', 'gen', 'tier_value', 'tier_unit'],
                name='unique_categorycode_key'),
            # v3: o número é POR LETRA (kind) — A-07 e B-07 coexistem.
            models.UniqueConstraint(fields=['kind', 'code'],
                                    name='unique_categorycode_kind_code'),
            models.CheckConstraint(name='categorycode_positive',
                                   condition=Q(code__gt=0)),
        ]

    def __str__(self):
        return f'{self.label} = {self.kind}/{self.gen or "—"} ' \
               f'{self.tier_value}{self.tier_unit}'

    @property
    def label(self) -> str:
        """``LETRA-##`` (ex.: A-07) — canônico universal, NUNCA traduz."""
        from .convention import KIND_LETTER
        return f'{KIND_LETTER[self.kind]}-{self.code:02d}'

    @classmethod
    def label_for_key(cls, kind, gen, tier_value, tier_unit,
                      create: bool = True):
        """Código da chave (ou ``None`` se o tipo está fora da convenção —
        ex.: kind extinto em chave legada gravada). A geração DOBRA na base
        (fold_gen). Código já atribuído SEMPRE vale (caixa é física — nunca
        renomeia). Categoria inédita: com ``create=True`` (caminho da
        APROVAÇÃO na bancada) ganha o próximo número livre da letra — SEM
        depender de preço/grid (v3, dono 2026-07-23); com ``create=False``
        (renders de tabela/OV — leitura nunca cunha) devolve ``None``."""
        from .convention import KIND_LETTER
        if kind not in KIND_LETTER:
            return None
        from django.db import IntegrityError, transaction
        from django.db.models import Max
        gen = fold_gen(kind, gen or '')
        obj = cls.objects.filter(kind=kind, gen=gen, tier_value=tier_value,
                                 tier_unit=tier_unit).first()
        if obj:
            return obj.label
        if not create:
            return None
        for _tentativa in range(2):      # corrida rara: retry único
            try:
                with transaction.atomic():
                    nxt = (cls.objects.filter(kind=kind)
                           .aggregate(m=Max('code'))['m'] or 0) + 1
                    obj = cls.objects.create(kind=kind, gen=gen,
                                             tier_value=tier_value,
                                             tier_unit=tier_unit, code=nxt)
                    return obj.label
            except IntegrityError:
                obj = cls.objects.filter(kind=kind, gen=gen,
                                         tier_value=tier_value,
                                         tier_unit=tier_unit).first()
                if obj:
                    return obj.label
        raise IntegrityError('CategoryCode: corrida não resolvida.')


class PricingConfig(models.Model):
    """Configuração do sistema de preços — singleton pk=1, editável no admin,
    efeito imediato (padrão ProfitabilityConfig). GLOBAL por ora; se um dia
    virar por-empresa, o get_config() centraliza o ponto de mudança."""

    SCENARIO_LOW, SCENARIO_MID, SCENARIO_HIGH = 'low', 'mid', 'high'
    SCENARIO_CHOICES = [
        (SCENARIO_LOW, 'Baixo (início da faixa)'),
        (SCENARIO_MID, 'Médio (meio da faixa)'),
        (SCENARIO_HIGH, 'Alto (fim da faixa)'),
    ]

    staleness_days = models.PositiveIntegerField(
        default=90, verbose_name='Cotação velha após (dias)',
        help_text='Cotação mais antiga que isto é exibida como "≈ referência". '
                  'Sem quote_date = sempre referência.')
    default_scenario = models.CharField(
        max_length=4, choices=SCENARIO_CHOICES, default=SCENARIO_MID,
        verbose_name='Cenário padrão de faixa',
        help_text='Qual valor usar por padrão quando o preço é uma faixa.')

    class Meta:
        verbose_name = 'Configuração de Preços'
        verbose_name_plural = 'Configuração de Preços'

    def __str__(self):
        return f'Config de preços (staleness={self.staleness_days}d, cenário={self.default_scenario})'

    @classmethod
    def get_config(cls):
        """Retorna a configuração ativa (singleton pk=1). Cria com defaults se não existir."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
