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

from tenancy.scope import CompanyScopedManager, PlatformSharedManager

STATUS_DRAFT, STATUS_CONFIRMED, STATUS_CANCELLED = 'draft', 'confirmed', 'cancelled'
STATUS_CHOICES = [
    (STATUS_DRAFT, 'Cotação (draft)'),
    (STATUS_CONFIRMED, 'Confirmada'),
    (STATUS_CANCELLED, 'Cancelada'),
]

SEQ_SO, SEQ_INVOICE = 'so', 'inv'
#: O LOTE também tem sequência aqui desde 2026-09-02. Antes o contador dele era
#: um escalar na `Company` (`last_lot_number`), que não sabia de ANO — e o ano é
#: o que a convenção nova exige (`LOT-2026-0041`, reiniciando em 1º de janeiro).
SEQ_LOT = 'lot'


def _ano_do_lote(lot) -> int:
    """Ano de ABERTURA do lote — a fonte do ano de toda a cadeia de documentos.

    O ``doc_year`` do lote é a fonte. O cálculo a partir do ``created_at`` é
    rede para a janela entre a migração de esquema e o backfill, e para fixture
    crua; fora disso não roda."""
    from tenancy.doc_code import _ano_de
    return lot.doc_year or _ano_de(lot.created_at)


class DocSequence(models.Model):
    """Sequência de documento por empresa, **por ano** (LOT/SO) ou perpétua (INV).

    ``select_for_update`` na linha da sequência serializa criações simultâneas
    (⚠ no-op no SQLite — a prova de corrida é Postgres-only). É a MESMA linha que
    a devolução de número trava ao excluir um lote, e é isso que faz "apagar" e
    "abrir" simultâneos não se atropelarem.

    ── O ano na chave (dono, 2026-09-02) ────────────────────────────────────
    O número reinicia a cada ano (`LOT-2026-0041` → `LOT-2027-0001`), então a
    sequência deixa de ser (empresa, tipo) e passa a ser (empresa, tipo, ANO).

    ``year=0`` é a linha PERPÉTUA, e é onde a fatura continua vivendo: a INV não
    entrou na convenção nova (ela está sendo aposentada) e não pode ter o
    comportamento alterado de raspão por esta mudança.

    ⚠ O contador de um ano PODE ANDAR depois que o ano acabou, e isso não é bug:
    a ordem de venda herda o ano do LOTE, então um lote de dezembro/2026 vendido
    em fevereiro/2027 consome o próximo número de **2026**, em 2027.
    """

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE,
                                related_name='doc_sequences', verbose_name='Empresa')
    kind = models.CharField(max_length=8, verbose_name='Documento')   # 'lot'|'so'|'inv'
    #: Ano da sequência; ``0`` = perpétua (a INV legada).
    year = models.PositiveSmallIntegerField(default=0, verbose_name='Ano')
    last_number = models.PositiveIntegerField(default=0, verbose_name='Último número')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Sequência de documento'
        verbose_name_plural = 'Sequências de documento'
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.UniqueConstraint(fields=['company', 'kind', 'year'],
                                    name='unique_docseq_company_kind_year'),
        ]

    def __str__(self):
        ano = self.year or 'perpétua'
        return f'{self.company} · {self.kind} · {ano} · {self.last_number}'

    @classmethod
    def next_number(cls, company, kind, year=0, floor=0) -> int:
        """Próximo número da sequência (empresa, tipo, ano).

        ``year=0`` de propósito no default: é a sequência PERPÉTUA, que é o que
        a INV usa. Quem emite LOT ou SO passa o ano SEMPRE — e, na ordem de
        venda, o ano é o do LOTE, nunca o de hoje (§2.2 da convenção).

        ``floor`` é a AUTO-CURA do drift: o maior número que já existe de fato.
        O contador nunca pode ficar atrás do dado — e a correção acontece DENTRO
        do lock, senão duas aberturas simultâneas curariam o mesmo buraco e
        sairiam com o mesmo número. (O contador de lote da eMiner estava em 50
        com o maior lote em 13, resíduo da renumeração de 01/09: é este
        parâmetro que impede o caso simétrico de virar documento duplicado.)
        """
        # `company` aceita instância OU pk: os chamadores vêm dos dois jeitos
        # (a abertura de lote tem a Company travada na mão; a ordem de venda só
        # tem o `lot.company_id`, e buscar a linha inteira da empresa só para
        # satisfazer o ORM seria uma query a mais em cada emissão).
        company_id = getattr(company, 'pk', company)
        with transaction.atomic():
            seq, _ = cls.all_companies.get_or_create(company_id=company_id,
                                                     kind=kind, year=year)
            seq = cls.all_companies.select_for_update().get(pk=seq.pk)
            seq.last_number = max(seq.last_number, floor) + 1
            seq.save(update_fields=['last_number'])
            return seq.last_number

    @classmethod
    def release_number(cls, company, kind, year, number) -> bool:
        """Devolve ``number`` à sequência — só se ele for o ÚLTIMO emitido.

        Existe para o caso "abri um lote e apaguei em seguida": sem isto o
        número fica queimado e o próximo lote pula (dono, 2026-09-02).

        Devolve ``False``, sem erro, quando o contador já andou (outro documento
        nasceu no meio) — devolver aí abriria a porta para dois documentos com o
        mesmo número, que é o oposto do que se quer. Trava a MESMA linha que a
        emissão, então excluir e abrir ao mesmo tempo serializam.
        """
        company_id = getattr(company, 'pk', company)
        with transaction.atomic():
            seq = (cls.all_companies.select_for_update()
                   .filter(company_id=company_id, kind=kind, year=year).first())
            if seq is None or seq.last_number != number:
                return False
            seq.last_number = number - 1
            seq.save(update_fields=['last_number'])
            return True


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

    # ── ANO DO DOCUMENTO — herdado do LOTE (dono, 2026-09-02) ─────────────
    # ⚠ NÃO é o ano de `created_at`. A venda é o acerto DAQUELE lote: um lote
    # aberto em dezembro de 2026 e vendido em janeiro não virou campanha de
    # 2027, e o código dele continua dizendo 2026 (§2.2 da convenção).
    # Campo GRAVADO, e não derivado: ele entra na chave de unicidade (empresa,
    # ano, número), e um identificador de documento não pode mudar de valor
    # porque alguém atravessou uma FK diferente para calculá-lo.
    doc_year = models.PositiveSmallIntegerField(
        default=0, editable=False, verbose_name='Ano do documento')
    # ── Código do documento, CONGELADO na criação (dono, 2026-08-18) ───────
    # Era propriedade calculada. Virou campo porque o formato mudou e o
    # identificador tem de ser IMUTÁVEL — renomear o código da empresa não
    # reescreve o passado, que é como número de documento deve se comportar.
    # O passado só muda por `manage.py backfill_doc_codes`, no ato deliberado
    # em que o dono decide que tela e papel voltam a usar a mesma grafia.
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
    # ── O DESPACHO (F4, dono 2026-08-18) ─────────────────────────────────────
    # Quem embarca é o CLIENTE — é ele que tem a transportadora, o rastreio e
    # a data. UMA caixa por lote (decisão do dono): campos aqui, sem modelo de
    # volume. Se um dia um lote sair em dois pacotes, vira um modelo próprio.
    # ⚠ EDITÁVEL, ao contrário do `received_at`: rastreio digitado errado tem
    # que ser corrigível, e o número às vezes só aparece horas depois de
    # despachar. Nada aqui bloqueia o comprador de marcar o recebimento — se
    # o cliente esquecer de registrar o envio, a caixa chega do mesmo jeito.
    carrier = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Transportadora',
        help_text='DHL, FedEx, UPS… como aparece na etiqueta.')
    tracking = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Rastreio',
        help_text='O número que o comprador acompanha. Pode ser preenchido '
                  'depois do envio.')
    shipped_at = models.DateField(
        null=True, blank=True, verbose_name='Despachada em',
        help_text='O dia em que a caixa saiu.')
    shipped_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='+',
                                   verbose_name='Despachada por')

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
            # ⚠ O ANO entra na chave (2026-09-02): a numeração reinicia a cada
            # ano, então a OV 1 de 2026 e a OV 1 de 2027 coexistem.
            models.UniqueConstraint(fields=['company', 'doc_year', 'number'],
                                    name='unique_so_company_year_number'),
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
        """``EMIN-SO-2026-0004`` — canônico universal: inglês, NUNCA traduz.

        Lê o ``code_str`` congelado. O fallback cobre só o instante entre montar
        o objeto e salvá-lo (e fixture crua): depois do backfill não há documento
        sem ``code_str``, e um fallback que devolvesse a grafia ANTIGA seria
        armadilha — mostraria na tela um código que não existe mais em lugar
        nenhum do sistema."""
        if self.code_str:
            return self.code_str
        from tenancy.doc_code import doc_code
        return doc_code('SO', self.company.code if self.company_id else '',
                        self.number, self.created_at, ano=self.doc_year or None)

    @property
    def is_draft(self) -> bool:
        return self.status == STATUS_DRAFT

    @classmethod
    def next_for_lot(cls, lot):
        """``(doc_year, number)`` da próxima ordem DESTE lote.

        Um lugar só que sabe de qual contador o número sai — o do ANO DO LOTE,
        nunca o de hoje. Sem isto, cada chamador (fechamento, backfill, comandos
        de legado) teria de lembrar da regra §2.2 sozinho, e o que se esquece
        aqui só aparece em janeiro, num número que já foi impresso."""
        ano = _ano_do_lote(lot)
        return ano, DocSequence.next_number(lot.company_id, SEQ_SO, ano)

    def save(self, *args, **kwargs):
        # company denormalizada: herda do LOTE (a venda é da empresa do lote).
        if self.lot_id and not self.company_id:
            from estoque.models import Lot
            self.company_id = Lot.all_companies.values_list(
                'company_id', flat=True).get(pk=self.lot_id)
        # O ANO vem do LOTE (§2.2) — nunca do próprio created_at.
        if self._state.adding and not self.doc_year and self.lot_id:
            self.doc_year = _ano_do_lote(self.lot)
        # Congela o código na CRIAÇÃO (ver tenancy/doc_code.py). Usa
        # timezone.now() em vez do created_at porque o auto_now_add só existe
        # DEPOIS do insert — e um segundo save() aqui dobraria o evento de
        # histórico do pghistory à toa.
        if self._state.adding and not self.code_str:
            from django.utils import timezone
            from tenancy.doc_code import doc_code
            self.code_str = doc_code('SO', self.company.code, self.number,
                                     timezone.now(), ano=self.doc_year or None)
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
    # ── TAXA DE SERVIÇO, CONGELADA NA EMISSÃO (dono, 2026-08-19) ──────────
    # O comprador paga o WhatTheChip o total CHEIO; o WhatTheChip repassa ao
    # cliente o LÍQUIDO. A taxa vem de `Company.service_fee_pct` no momento em
    # que a fatura nasce e fica gravada aqui — mesma disciplina do câmbio:
    # mudar o cadastro nunca reescreve venda já acertada.
    #
    # ⚠ O `total_*` continua sendo o que o COMPRADOR deve. O líquido do
    # cliente é `net_*` (propriedade) — nunca subtraia a taxa do total, senão
    # a cobrança do comprador encolhe junto.
    fee_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Taxa de serviço (%)')
    fee_rmb = models.DecimalField(max_digits=12, decimal_places=2,
                                  default=Decimal('0.00'),
                                  verbose_name='Taxa ¥')
    fee_usd = models.DecimalField(max_digits=12, decimal_places=2,
                                  default=Decimal('0.00'),
                                  verbose_name='Taxa US$')
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

    # ── O lado do CLIENTE: bruto − taxa = líquido ─────────────────────────
    # Duas contas que não se misturam: `total/paid/balance` é a perna
    # COMPRADOR → WhatTheChip; `net/paid_out/payout_balance` é a perna
    # WhatTheChip → CLIENTE. O cliente nunca vê a primeira (o comprador paga o
    # WTC, não a ele), e é por isso que "pago" numa tela não é "pago" na
    # outra.
    @property
    def net_rmb(self) -> Decimal:
        return self.total_rmb - self.fee_rmb

    @property
    def net_usd(self) -> Decimal:
        return self.total_usd - self.fee_usd

    @property
    def paid_out_usd(self) -> Decimal:
        return (self.payouts.aggregate(t=models.Sum('amount_usd'))['t']
                or Decimal('0.00'))

    @property
    def payout_balance_usd(self) -> Decimal:
        return self.net_usd - self.paid_out_usd

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

    # IDEMPOTÊNCIA (spec v2 §5.4, 2026-08-26): o comprador está em rede
    # instável e clica duas vezes. `mark_received` já era idempotente e o
    # `settle_and_invoice` se protege pela fatura ativa — o PAGAMENTO não
    # tinha nada, e um parcial duplicado passa nas duas validações de saldo.
    # A chave nasce no RENDER do formulário (uma por página servida): dois
    # cliques no mesmo botão mandam a mesma chave; recarregar a página é
    # intenção nova e gera outra. Vazio = registro sem chave (admin, shell,
    # linhas antigas) — por isso a UniqueConstraint EXCLUI a string vazia,
    # senão o 2º pagamento manual de qualquer fatura seria recusado.
    idempotency_key = models.CharField(
        max_length=64, blank=True, default='', editable=False,
        verbose_name='Chave de idempotência')

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
            # A trava REAL do duplo-clique: o check na view é só o caminho
            # rápido; quem barra a corrida de dois POSTs simultâneos é o
            # banco. Parcial (~Q vazio) para não travar registro sem chave.
            models.UniqueConstraint(
                fields=['invoice', 'idempotency_key'],
                condition=~Q(idempotency_key=''),
                name='payment_idempotency_per_invoice'),
        ]

    def __str__(self):
        return f'{self.invoice_id} · US$ {self.amount_usd} · {self.paid_at}'

    def save(self, *args, **kwargs):
        if self.invoice_id and not self.company_id:
            self.company_id = Invoice.all_companies.values_list(
                'company_id', flat=True).get(pk=self.invoice_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)



@pghistory.track()
class OrderNote(models.Model):
    """Observação da CONFERÊNCIA — o que o comprador escreve sobre a compra.

    Até 2026-08-26 existia UMA nota por compra, escondida num campo do acerto
    (``Settlement.notes``): sem autor visível, sem data visível, escrita uma
    vez no diálogo de fechar resultado e nunca mais. Se ele lembrasse de algo
    depois, não havia onde pôr.

    ⚠ **Sai no PDF do resultado, e é isso que a faz valer como registro.** O
    documento atravessa o balcão: quem escreve é o comprador, quem lê é o
    CLIENTE. Por isso a autoria vira **"Conferência"** no papel (spec v2
    §7.1) — o cliente sabe que alguém conferiu, não pode saber quem comprou.
    O nome real fica na tela do comprador e no admin.

    A observação opcional do diálogo de fechamento entra NESTA lista, não num
    campo próprio: dois lugares para procurar o que o comprador escreveu é um
    a mais. O ``Settlement.notes`` continua gravado como registro interno do
    acerto (auditoria de quem fechou o quê), mas a TELA lê só daqui.
    """

    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT,
                              related_name='order_notes',
                              verbose_name='Ordem de venda')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    text = models.TextField(verbose_name='Observação')
    # Autor e data são do SERVIDOR, sempre: o cliente não manda nem um nem
    # outro (spec §3.10). `created_by` é SET_NULL porque conta de parceiro
    # desativada não pode apagar o histórico da compra.
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Registrada em')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='+',
                                   verbose_name='Autor')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Observação da conferência'
        verbose_name_plural = 'Observações da conferência'
        # CRONOLÓGICA: é um registro que se lê de cima para baixo, como
        # conversa. A mais nova por último, do jeito que foi escrita.
        ordering = ['created_at', 'pk']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'

    def __str__(self):
        return f'{self.order_id} · {self.created_at:%d/%m/%Y}'

    def save(self, *args, **kwargs):
        if self.order_id and not self.company_id:
            self.company_id = SalesOrder.all_companies.values_list(
                'company_id', flat=True).get(pk=self.order_id)
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)



class Wallet(models.Model):
    """A carteira que RECEBE o pagamento do comprador (spec v2 §3.12).

    **Duas possibilidades, e é a EMPRESA que diz qual** (dono, 2026-09-01:
    *"deve existir ambas possibilidades, do comprador pagar direto ao cliente
    e também direto a WTC"*):

    · ``company`` VAZIO → a carteira da PLATAFORMA. O comprador paga o
      WhatTheChip, que depois repassa ao cliente o líquido. Arranjo padrão.
    · ``company`` PREENCHIDO → a carteira daquele CLIENTE. O comprador paga
      direto a ele; o WTC nunca toca no dinheiro, só cobra a taxa por fora.
      É o arranjo da eMiner (BINANCE HANDSON, TRONLINK).

    Quem escolhe entre as duas não é esta tabela: é a
    ``Company.payout_on_payment`` — o MESMO interruptor que decide se o
    repasse é lançado sozinho. **Um interruptor, duas consequências, de
    propósito.** Dois permitiriam a combinação incoerente "o comprador paga o
    WhatTheChip e mesmo assim o sistema declara o cliente pago".

    ⚠ **Era GLOBAL até 2026-09-01** — uma linha só, e a tela dizia a TODO
    comprador *"Você paga o WhatTheChip, nunca o vendedor direto"*. Essa
    frase contradizia a operação real da eMiner, onde o Wu Quan deposita nas
    carteiras dela. Com um cliente só a linha global estava certa por
    acidente; no segundo, o comprador dele veria o endereço do primeiro — e
    endereço errado nesta tela é dinheiro que não volta. Foi o
    ``TenancyDeclarationTests`` que apontou, e era alarme com causa.

    Model e não ``settings`` porque endereço de carteira muda sem deploy —
    mesma decisão do ``Buyer.ship_to``. Nasce VAZIO: inventar um endereço
    padrão seria pôr dinheiro de verdade a caminho de um lugar imaginário.
    """

    # VAZIO = carteira da plataforma, legível por toda empresa (leitura ampla
    # no RLS, como o Buyer de plataforma — vendas/0020).
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.PROTECT, null=True, blank=True,
        related_name='wallets', verbose_name='Empresa',
        help_text='VAZIO = carteira do WhatTheChip (o comprador paga a '
                  'plataforma). PREENCHIDO = carteira deste cliente, para '
                  'quando o comprador paga direto a ele.')
    owner = models.CharField(max_length=120, default='WhatTheChip Ltd.',
                             verbose_name='Titular')
    net = models.CharField(max_length=60, default='USDT · TRC-20',
                           verbose_name='Rede',
                           help_text='Ex.: USDT · TRC-20. Aparece ao lado do '
                                     'endereço, porque rede errada perde a '
                                     'transferência.')
    addr = models.CharField(max_length=120, verbose_name='Endereço')
    memo = models.TextField(
        blank=True, default='', verbose_name='Instrução de memo',
        help_text='O que o comprador deve pôr no campo memo/referência da '
                  'transferência — normalmente o código da ordem (SO).')
    active = models.BooleanField(default=True, verbose_name='Ativa')
    updated_at = models.DateTimeField(auto_now=True,
                                      verbose_name='Atualizada em')

    objects       = PlatformSharedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Carteira de recebimento'
        verbose_name_plural = 'Carteiras de recebimento'
        ordering = ['-updated_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'

    def __str__(self):
        dono = self.company.name if self.company_id else 'plataforma'
        return f'{self.owner} · {self.net} ({dono})'

    @property
    def is_platform(self) -> bool:
        """True = carteira do WhatTheChip. A tela usa isto para escolher a
        frase: "você paga o WTC, nunca o vendedor" só vale aqui."""
        return self.company_id is None

    @classmethod
    def for_company(cls, company):
        """O endereço que o comprador desta venda tem de pagar, ou ``None``.

        ⚠ **Nunca cai da carteira do cliente para a da plataforma.** Um
        fallback aqui mandaria dinheiro para a parte errada em silêncio, que é
        o pior defeito possível nesta tela. Sem endereço cadastrado a tela DIZ
        que não há e manda falar com o WhatTheChip: é lento, e é certo.

        ⚠ Lê com ``all_companies`` + filtro EXPLÍCITO em vez do manager
        compartilhado: o `PlatformSharedManager` devolveria as duas (a do
        cliente E a da plataforma) e a escolha viraria "a primeira que vier".
        Aqui a pergunta é qual das duas, e a resposta não pode depender de
        ordenação. (No Postgres o RLS ainda se aplica — a leitura da linha de
        plataforma é liberada em vendas/0020.)
        """
        if company is None:
            return None
        vivas = cls.all_companies.filter(active=True)
        if company.payout_on_payment:
            return vivas.filter(company=company).first()
        return vivas.filter(company__isnull=True).first()


class Payout(models.Model):
    """REPASSE ao cliente — a perna WhatTheChip → CLIENTE (dono, 2026-08-19).

    O comprador paga o WhatTheChip; o WhatTheChip paga o cliente, já deduzida
    a taxa de serviço. São DUAS pernas, e confundi-las seria mentir no extrato
    de alguém:

    · ``Payment``  — comprador → WhatTheChip. Tem comprovante. O CLIENTE NÃO
      VÊ: nem valor, nem data, nem referência (é a conta do WTC com a
      contraparte dele, e quem é a contraparte é segredo de mercado).
    · ``Payout``   — WhatTheChip → cliente. É isto que a tela do cliente
      mostra como "recebido": dinheiro que SAIU da conta do WTC. Assim o
      extrato dele nunca promete o que ainda não foi transferido.

    Quem registra é a PLATAFORMA (só superusuário) — é o WTC declarando o que
    pagou. Parcial é permitido, como no outro lado.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                related_name='payouts', verbose_name='Fatura')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2,
                                     verbose_name='Valor US$')
    paid_at = models.DateField(verbose_name='Data do repasse')
    reference = models.CharField(max_length=120, blank=True, default='',
                                 verbose_name='Referência',
                                 help_text='Wire/recibo/observação curta.')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Registrado em')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='+',
                                   verbose_name='Registrado por')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Repasse ao cliente'
        verbose_name_plural = 'Repasses ao cliente'
        ordering = ['-paid_at', '-created_at']
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'
        constraints = [
            models.CheckConstraint(name='payout_positive',
                                   condition=Q(amount_usd__gt=0)),
        ]

    def __str__(self):
        return f'{self.invoice_id} · US$ {self.amount_usd} · {self.paid_at}'

    def save(self, *args, **kwargs):
        if self.invoice_id and not self.company_id:
            self.company_id = Invoice.all_companies.values_list(
                'company_id', flat=True).get(pk=self.invoice_id)
        super().save(*args, **kwargs)


class PaymentReceipt(models.Model):
    """O COMPROVANTE do pagamento — bytes no BANCO (dono, 2026-08-18).

    ⚠ **No banco, não em disco.** Mesma razão do logo da empresa (E4/B7): o
    filesystem da Render é EFÊMERO — um deploy apaga o arquivo — e ``/media/``
    nem é servido com ``DEBUG=False``. Comprovante de pagamento é a última
    coisa do sistema que pode evaporar num deploy.

    Tabela PRÓPRIA, 1-pra-1 com o Payment, pelo mesmo motivo do CompanyLogo: a
    lista de pagamentos é lida em toda visita à compra e não pode arrastar
    blobs de MBs; aqui eles só saem pela view do comprovante.

    Com ``company`` e RLS como o resto de vendas (dinheiro é por-empresa —
    ver ``0008_paymentreceipt_rls``). Sem pghistory: histórico de blob só
    incharia o event store, e o comprovante é imutável por construção (trocar
    exige apagar o pagamento).
    """

    payment = models.OneToOneField(Payment, on_delete=models.CASCADE,
                                   primary_key=True, related_name='receipt',
                                   verbose_name='Pagamento')
    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='+',
                                verbose_name='Empresa', editable=False)
    data = models.BinaryField(verbose_name='Bytes do comprovante')
    mime = models.CharField(max_length=32, verbose_name='MIME')
    filename = models.CharField(max_length=160, blank=True, default='',
                                verbose_name='Nome do arquivo')
    size = models.PositiveIntegerField(default=0, verbose_name='Tamanho (bytes)')
    uploaded_at = models.DateTimeField(auto_now_add=True,
                                       verbose_name='Anexado em')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Comprovante'
        verbose_name_plural = 'Comprovantes'
        base_manager_name = 'all_companies'
        default_manager_name = 'all_companies'

    def __str__(self):
        return f'Comprovante de {self.payment_id}'

    def save(self, *args, **kwargs):
        if self.payment_id and not self.company_id:
            self.company_id = Payment.all_companies.values_list(
                'company_id', flat=True).get(pk=self.payment_id)
        return super().save(*args, **kwargs)
