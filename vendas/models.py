"""
WhatTheChip — Vendas (F11.2, PRECIFICACAO §12.19)
=================================================
O lado COMERCIAL do lote, padrão Odoo (decisões do dono, 2026-07-16):

- **Fechamento do lote → Cotação DRAFT** (uma, para o comprador ativo único).
  No draft os valores são VIVOS: cada linha re-resolve contra a tabela
  ``pricing.Price`` na leitura (nada gravado).
- **Confirmar → Ordem de Venda:** congela linha a linha o ¥ unitário, a taxa
  contratual da confirmação e o US$ derivado ("vendi a 0.14" — auditoria
  cambial completa). A OV confirmada NUNCA é editada; o resultado do
  comprador entra como ACERTO (F11.4).
- **Linha = CATEGORIA por MARCA** (a chave de preço: kind/gen/tier + brand).
  A marca é obrigatória na linha porque o comprador cota POR MARCA (grid da
  F6: "eMMC 16GB" Samsung ≠ SanDisk); o detalhado por PN fica no inventário.
- **Reabrir lote:** cancela a cotação draft; com OV CONFIRMADA a reabertura é
  BLOQUEADA até cancelar a ordem (auditável).
- **Nomenclatura universal (canônica, NUNCA traduz):** ``SO/NUM/MM/YY`` —
  NUM perpétuo por empresa (``DocSequence``), zero-padded 3.
- **Sigilo:** o comprador é segredo de PLATAFORMA — telas de empresa não
  mostram nome/slug (F11.3 formaliza o codinome; o menu Vendas já é
  admin-only, regra "gerente não vê valor").

Tenancy (padrão pricing/estoque T3/T4): company NOT NULL denormalizada,
``objects`` = CompanyScopedManager fail-closed, ``all_companies`` cru como
default/base (validação de unique do Django 5 usa _default_manager — bug de
prod 2026-07-09), RLS+FORCE na migração 0002. pghistory em SO/linha (dinheiro).
"""

from decimal import Decimal

import pghistory

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from tenancy.scope import CompanyScopedManager

STATUS_DRAFT, STATUS_CONFIRMED, STATUS_CANCELLED = 'draft', 'confirmed', 'cancelled'
STATUS_CHOICES = [
    (STATUS_DRAFT, 'Cotação (draft)'),
    (STATUS_CONFIRMED, 'Confirmada'),
    (STATUS_CANCELLED, 'Cancelada'),
]

SEQ_SO, SEQ_INVOICE = 'so', 'inv'


class DocSequence(models.Model):
    """Sequência PERPÉTUA de documento por empresa (SO/INV — dono, 2026-07-16:
    o NUM nunca reinicia). Mesmo padrão atômico do ``Lot.open_for_company``:
    ``select_for_update`` na linha da sequência serializa criações simultâneas
    (⚠ no-op no SQLite — a prova de corrida é Postgres-only)."""

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE,
                                related_name='doc_sequences', verbose_name='Empresa')
    kind = models.CharField(max_length=8, verbose_name='Documento')   # 'so' | 'inv'
    last_number = models.PositiveIntegerField(default=0, verbose_name='Último número')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Sequência de documento'
        verbose_name_plural = 'Sequências de documento'
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['company', 'kind'],
                                    name='unique_docseq_company_kind'),
        ]

    def __str__(self):
        return f'{self.company} · {self.kind} · {self.last_number}'

    @classmethod
    def next_number(cls, company, kind) -> int:
        with transaction.atomic():
            seq, _ = cls.all_companies.get_or_create(company=company, kind=kind)
            seq = cls.all_companies.select_for_update().get(pk=seq.pk)
            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            return seq.last_number


@pghistory.track()   # dinheiro: criar/confirmar/cancelar OV é evento auditado
class SalesOrder(models.Model):
    """Cotação (draft, valores vivos) → Ordem de Venda (confirmada, congelada).

    Moeda (padrão F10): ¥ canônico; ``fx_usd_rate``/``total_usd`` congelam na
    CONFIRMAÇÃO. No draft, totais são calculados on-read (vendas/services.py).
    """

    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                related_name='sales_orders', verbose_name='Empresa',
                                editable=False)
    number = models.PositiveIntegerField(verbose_name='Número')
    lot = models.ForeignKey('estoque.Lot', on_delete=models.PROTECT,
                            related_name='sales_orders', verbose_name='Lote')
    buyer = models.ForeignKey('pricing.Buyer', on_delete=models.PROTECT,
                              related_name='sales_orders', verbose_name='Comprador')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default=STATUS_DRAFT, verbose_name='Status')

    # Congelados na CONFIRMAÇÃO (NULL no draft — draft é vivo):
    fx_usd_rate = models.DecimalField(max_digits=8, decimal_places=4,
                                      null=True, blank=True,
                                      verbose_name='Taxa ¥→US$ (congelada)')
    total_rmb = models.DecimalField(max_digits=12, decimal_places=2,
                                    null=True, blank=True, verbose_name='Total ¥')
    total_usd = models.DecimalField(max_digits=12, decimal_places=2,
                                    null=True, blank=True, verbose_name='Total US$')

    # Transparência do sem-chave (chips no lote fora do mercado de preço):
    unkeyed_units = models.PositiveIntegerField(default=0,
                                                verbose_name='Unid. sem chave')

    # ── Código do documento, CONGELADO na criação (dono, 2026-08-18) ───────
    # Era propriedade calculada. Virou campo porque o formato mudou (ganhou o
    # prefixo da empresa, `LOT/EMI/041/08/26`) e o dono escolheu aplicar SÓ A
    # DOCUMENTO NOVO: papel já impresso não pode divergir da tela. Vazio =
    # documento anterior à mudança → a propriedade `code` cai no formato
    # antigo. De quebra, o identificador virou IMUTÁVEL — renomear o código da
    # empresa não reescreve o passado, que é como número de documento deve se
    # comportar.
    code_str = models.CharField(max_length=32, blank=True, default='',
                                editable=False, verbose_name='Código')
    notes = models.TextField(blank=True, default='', verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criada em')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='Confirmada em')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+',
                                     verbose_name='Confirmada por')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Cancelada em')
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+',
                                     verbose_name='Cancelada por')
    # ── A CAIXA CHEGOU (dono, 2026-08-18) ────────────────────────────────────
    # Primeiro pedaço do despacho (F4) a existir, porque é o que o card de
    # etapas precisa para dizer em que pé está a compra. Quem marca é o
    # COMPRADOR, que é quem recebe. Transportadora, rastreio e data de ENVIO
    # ficam para a F4 inteira — dependem de decisão de quem preenche.
    # Nullable e sem backfill: compra anterior a isto simplesmente não tem a
    # data, e o card mostra a etapa sem carimbo.
    received_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Recebida em',
        help_text='Quando o comprador confirmou que a caixa chegou.')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Ordem de venda'
        verbose_name_plural = 'Ordens de venda'
        ordering = ['-created_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['company', 'number'],
                                    name='unique_so_company_number'),
            # Lote vendido INTEIRO a UM comprador: no máximo UMA cotação/OV
            # não-cancelada por lote (reabrir cancela; re-fechar cria outra).
            models.UniqueConstraint(fields=['lot'],
                                    condition=~Q(status='cancelled'),
                                    name='one_active_so_per_lot'),
            models.CheckConstraint(
                name='so_status_vocab',
                condition=Q(status__in=['draft', 'confirmed', 'cancelled'])),
            # Confirmada ⇒ tem taxa e totais congelados.
            models.CheckConstraint(
                name='so_confirmed_is_frozen',
                condition=~Q(status='confirmed')
                          | (Q(fx_usd_rate__isnull=False)
                             & Q(total_rmb__isnull=False)
                             & Q(total_usd__isnull=False))),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        """``SO/EMI/NUM/MM/YY`` — canônico universal (dono, 2026-07-16):
        inglês, NUNCA traduz; NUM perpétuo; MM/YY do mês de criação. O código
        da empresa entrou em 2026-08-18 (a numeração é por empresa e colidia
        entre clientes); documento antigo fica no formato de então."""
        if self.code_str:
            return self.code_str
        d = self.created_at
        return f'SO/{self.number:03d}/{d:%m}/{d:%y}' if d else f'SO/{self.number:03d}'

    @property
    def is_draft(self) -> bool:
        return self.status == STATUS_DRAFT

    def save(self, *args, **kwargs):
        # company denormalizada: herda do LOTE (a venda é da empresa do lote).
        if self.lot_id and not self.company_id:
            from estoque.models import Lot
            self.company_id = Lot.all_companies.values_list(
                'company_id', flat=True).get(pk=self.lot_id)
        # Congela o código na CRIAÇÃO (ver tenancy/doc_code.py). Usa
        # timezone.now() em vez do created_at porque o auto_now_add só existe
        # DEPOIS do insert — e um segundo save() aqui dobraria o evento de
        # histórico do pghistory à toa.
        if self._state.adding and not self.code_str:
            from django.utils import timezone
            from tenancy.doc_code import doc_code
            self.code_str = doc_code('SO', self.company.code, self.number,
                                     timezone.now())
        # Portão no MODELO (padrão pricing): sem validate_unique/constraints —
        # consultam o _default_manager; a unicidade fica com o BANCO.
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


@pghistory.track()   # linha carrega valor congelado — auditável
class SalesOrderLine(models.Model):
    """Linha da OV = CATEGORIA por MARCA: a chave de preço (kind/gen/tier —
    vocabulário do pricing) + marca + quantidade agregada do lote. ``unit_rmb``/
    ``unit_usd`` NULL no draft (valor vivo, resolvido on-read) e congelados na
    confirmação. Rótulo p/ humanos: "Samsung · eMCP LPDDR4X 64GB"."""

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE,
                              related_name='lines', verbose_name='Ordem')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)

    brand = models.CharField(max_length=100, blank=True, default='',
                             verbose_name='Marca')
    kind = models.CharField(max_length=8, verbose_name='Tipo')
    gen = models.CharField(max_length=12, blank=True, default='',
                           verbose_name='Geração')
    tier_value = models.DecimalField(max_digits=6, decimal_places=1,
                                     verbose_name='Faixa')
    # blank=True (correção de prod, 2026-08-18): há tipo com chave PLANA —
    # o K9 (NAND cru TSOP) é preço fixo por UNIDADE, sem capacidade, e grava
    # tier_value=1 / tier_unit='' de propósito (pricing/convention.py). Sem o
    # blank, o full_clean() do save() recusava a linha, o except do
    # create_draft_for_lot engolia e o lote fechava SEM OV, em silêncio.
    # `brand` e `gen` já nasceram assim; só este ficou para trás.
    tier_unit = models.CharField(max_length=2, blank=True, default='',
                                 verbose_name='Unidade')
    quantity = models.PositiveIntegerField(verbose_name='Quantidade')

    unit_rmb = models.DecimalField(max_digits=8, decimal_places=2,
                                   null=True, blank=True,
                                   verbose_name='¥ unitário (congelado)')
    unit_usd = models.DecimalField(max_digits=8, decimal_places=2,
                                   null=True, blank=True,
                                   verbose_name='US$ unitário (congelado)')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Linha da ordem de venda'
        verbose_name_plural = 'Linhas da ordem de venda'
        ordering = ['kind', 'brand', 'gen', 'tier_value']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'brand', 'kind', 'gen', 'tier_value', 'tier_unit'],
                name='unique_so_line_key'),
        ]

    def __str__(self):
        return f'{self.order_id} · {self.label} × {self.quantity}'

    @property
    def label(self) -> str:
        """Rótulo humano da categoria — specs canônicas nunca traduzem."""
        from pricing.models import KIND_CHOICES
        kind_label = dict(KIND_CHOICES).get(self.kind, self.kind)
        tier = f'{self.tier_value.normalize():f}{self.tier_unit}'
        parts = [kind_label]
        if self.gen:
            parts.append(self.gen)
        parts.append(tier)
        core = ' '.join(parts)
        return f'{self.brand} · {core}' if self.brand else core

    # ── Resumo por TIPO × CAPACIDADE (PDF do gerente, dono 2026-08-18) ──────
    # Duas colunas separadas em vez do ``label`` de cima: o resumo agrega as
    # marcas e precisa de "eMMC" numa coluna e "64GB" na outra. Canônico —
    # NUNCA traduz (mesma regra do ``label``).

    @property
    def type_label(self) -> str:
        """Tipo do chip como o mercado o chama: ``eMMC``/``eMCP``/``uMCP``/
        ``UFS``/``SSD``/``K9`` e, na DRAM discreta, a GERAÇÃO (``DDR4``,
        ``LPDDR4``) — nela o kind sozinho ("DDR") não identifica nada."""
        from pricing.models import KIND_CHOICES
        return self.gen or dict(KIND_CHOICES).get(self.kind, self.kind)

    @property
    def capacity_label(self) -> str:
        """``64GB`` (pacote) / ``8Gb`` (die) — vazio quando a chave é PLANA
        (K9: tier fixo 1/'' de propósito, o tipo não tem capacidade)."""
        if not self.tier_unit:
            return ''
        return f'{self.tier_value.normalize():f}{self.tier_unit}'

    @property
    def total_rmb(self):
        if self.unit_rmb is None:
            return None
        return (self.unit_rmb * self.quantity).quantize(Decimal('0.01'))

    @property
    def total_usd(self):
        if self.unit_usd is None:
            return None
        return (self.unit_usd * self.quantity).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        if self.order_id and not self.company_id:
            self.company_id = SalesOrder.all_companies.values_list(
                'company_id', flat=True).get(pk=self.order_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


# ═══ F11.4 — Acerto → Fatura → Pagamentos (padrão Odoo, dono 2026-07-16) ═══

@pghistory.track()
class Settlement(models.Model):
    """ACERTO — o RESULTADO do comprador sobre uma OV CONFIRMADA (mortos por
    categoria, repreciação). **A OV nunca é editada** (padrão Odoo: fatura
    pelo aceito + nota de crédito): o acerto registra os deltas e a FATURA
    nasce com o valor final. Histórico de acertos por comprador = dado de
    negociação (quanto de morto ele reporta por categoria)."""

    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT,
                              related_name='settlements', verbose_name='Ordem')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    notes = models.TextField(blank=True, default='', verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Registrado em')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='+',
                                   verbose_name='Registrado por')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Acerto (resultado do comprador)'
        verbose_name_plural = 'Acertos (resultado do comprador)'
        ordering = ['-created_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'

    def __str__(self):
        return f'Acerto da {self.order}'

    def save(self, *args, **kwargs):
        if self.order_id and not self.company_id:
            self.company_id = SalesOrder.all_companies.values_list(
                'company_id', flat=True).get(pk=self.order_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


@pghistory.track()
class SettlementLine(models.Model):
    """Ajuste de UMA categoria da OV: quantidade rejeitada (mortos) e/ou novo
    ¥ unitário (repreciação). Linha final = (qty − rejeitados) × (novo ¥ ou o
    ¥ congelado da OV)."""

    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE,
                                   related_name='lines', verbose_name='Acerto')
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT,
                                   related_name='adjustments',
                                   verbose_name='Linha da ordem')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    qty_rejected = models.PositiveIntegerField(default=0,
                                               verbose_name='Un. rejeitadas')
    new_unit_rmb = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Novo ¥ unitário',
        help_text='Vazio = mantém o ¥ congelado da OV.')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Linha do acerto'
        verbose_name_plural = 'Linhas do acerto'
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['settlement', 'order_line'],
                                    name='unique_settlement_order_line'),
        ]

    def __str__(self):
        return f'{self.order_line} · −{self.qty_rejected}'

    def save(self, *args, **kwargs):
        if self.settlement_id and not self.company_id:
            self.company_id = Settlement.all_companies.values_list(
                'company_id', flat=True).get(pk=self.settlement_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


INV_OPEN, INV_PAID, INV_CANCELLED = 'open', 'paid', 'cancelled'
INV_STATUS_CHOICES = [(INV_OPEN, 'Em aberto'), (INV_PAID, 'Paga'),
                      (INV_CANCELLED, 'Cancelada')]


@pghistory.track()
class Invoice(models.Model):
    """FATURA (``INV/NUM/MM/YY``) — o valor FINAL a receber da OV após o
    acerto; congelado na emissão (¥ + taxa da OV + US$). Pagamentos em US$
    abatem; saldo zero → paga. Cancelável só SEM pagamentos (re-acerto emite
    outra)."""

    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT,
                              related_name='invoices', verbose_name='Ordem')
    settlement = models.ForeignKey(Settlement, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name='invoices',
                                   verbose_name='Acerto')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    number = models.PositiveIntegerField(verbose_name='Número')
    status = models.CharField(max_length=10, choices=INV_STATUS_CHOICES,
                              default=INV_OPEN, verbose_name='Status')
    fx_usd_rate = models.DecimalField(max_digits=8, decimal_places=4,
                                      verbose_name='Taxa ¥→US$ (congelada)')
    total_rmb = models.DecimalField(max_digits=12, decimal_places=2,
                                    verbose_name='Total ¥')
    total_usd = models.DecimalField(max_digits=12, decimal_places=2,
                                    verbose_name='Total US$')
    # ── Código do documento, CONGELADO na criação (dono, 2026-08-18) ───────
    # Era propriedade calculada. Virou campo porque o formato mudou (ganhou o
    # prefixo da empresa, `LOT/EMI/041/08/26`) e o dono escolheu aplicar SÓ A
    # DOCUMENTO NOVO: papel já impresso não pode divergir da tela. Vazio =
    # documento anterior à mudança → a propriedade `code` cai no formato
    # antigo. De quebra, o identificador virou IMUTÁVEL — renomear o código da
    # empresa não reescreve o passado, que é como número de documento deve se
    # comportar.
    code_str = models.CharField(max_length=32, blank=True, default='',
                                editable=False, verbose_name='Código')
    issued_at = models.DateTimeField(auto_now_add=True, verbose_name='Emitida em')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name='+',
                                  verbose_name='Emitida por')
    cancelled_at = models.DateTimeField(null=True, blank=True,
                                        verbose_name='Cancelada em')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Fatura'
        verbose_name_plural = 'Faturas'
        ordering = ['-issued_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['company', 'number'],
                                    name='unique_invoice_company_number'),
            # Uma fatura ATIVA por OV (re-acerto = cancelar e emitir outra).
            models.UniqueConstraint(fields=['order'],
                                    condition=~Q(status='cancelled'),
                                    name='one_active_invoice_per_order'),
            models.CheckConstraint(
                name='invoice_status_vocab',
                condition=Q(status__in=['open', 'paid', 'cancelled'])),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        """``INV/EMI/NUM/MM/YY`` — canônico universal (INV confirmado pelo
        dono; BILL no Odoo é conta de FORNECEDOR). NUM perpétuo por empresa; o
        código da empresa entrou em 2026-08-18 (ver `Lot.code`)."""
        if self.code_str:
            return self.code_str
        d = self.issued_at
        return (f'INV/{self.number:03d}/{d:%m}/{d:%y}' if d
                else f'INV/{self.number:03d}')

    @property
    def paid_usd(self) -> Decimal:
        return (self.payments.aggregate(t=models.Sum('amount_usd'))['t']
                or Decimal('0.00'))

    @property
    def balance_usd(self) -> Decimal:
        return self.total_usd - self.paid_usd

    def save(self, *args, **kwargs):
        if self.order_id and not self.company_id:
            self.company_id = SalesOrder.all_companies.values_list(
                'company_id', flat=True).get(pk=self.order_id)
        # Congela o código na CRIAÇÃO (ver tenancy/doc_code.py). Usa
        # timezone.now() em vez do issued_at porque o auto_now_add só existe
        # DEPOIS do insert — e um segundo save() aqui dobraria o evento de
        # histórico do pghistory à toa.
        if self._state.adding and not self.code_str:
            from django.utils import timezone
            from tenancy.doc_code import doc_code
            self.code_str = doc_code('INV', self.company.code, self.number,
                                     timezone.now())
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


@pghistory.track()
class Payment(models.Model):
    """Pagamento recebido do comprador — SEMPRE em US$ (decisão do dono,
    2026-07-16). Parciais permitidos; saldo zero vira fatura PAGA."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                related_name='payments', verbose_name='Fatura')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2,
                                     verbose_name='Valor US$')
    paid_at = models.DateField(verbose_name='Data do pagamento')
    reference = models.CharField(max_length=120, blank=True, default='',
                                 verbose_name='Referência',
                                 help_text='Wire/recibo/observação curta.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Registrado em')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='+',
                                   verbose_name='Registrado por')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['-paid_at', '-created_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.CheckConstraint(name='payment_positive',
                                   condition=Q(amount_usd__gt=0)),
        ]

    def __str__(self):
        return f'{self.invoice_id} · US$ {self.amount_usd} · {self.paid_at}'

    def save(self, *args, **kwargs):
        if self.invoice_id and not self.company_id:
            self.company_id = Invoice.all_companies.values_list(
                'company_id', flat=True).get(pk=self.invoice_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)
