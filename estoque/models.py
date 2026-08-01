"""
WhatTheChip — Estoque de Operadores
====================================
Modelo de inventário por lote.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _lazy

from tenancy.scope import CompanyScopedManager

import pghistory


@pghistory.track()  # PLANO_FX Fase C: cada trava/retrava de câmbio é evento
class Lot(models.Model):
    # Origem do lote (acordo com o comprador, 2026-08-01): TODO lote declara
    # de que classe de placa os chips saíram — celular × PCB (set-top, TV,
    # notebook, industrial…). Escolha OBRIGATÓRIA na abertura, sem default
    # (é a promessa comercial: eMMC de lote PCB vale a tabela por marca).
    # Chave canônica NUNCA traduz; o rótulo sim (i18n).
    ORIGIN_PHONE  = 'phone'
    ORIGIN_PCB    = 'pcb'
    ORIGIN_CHOICES = [
        (ORIGIN_PHONE, _lazy('Celular')),
        (ORIGIN_PCB,   'PCB'),
    ]

    STATUS_OPEN   = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN,   'Aberto'),
        (STATUS_CLOSED, 'Fechado'),
    ]

    # T3: numeração POR EMPRESA — unique (company, number), não mais global.
    number      = models.PositiveIntegerField(verbose_name="Número")
    # T3 (PLANO_MULTITENANT.md §5.2): o lote é ativo da EMPRESA — a chave do
    # isolamento (e do futuro RLS). PROTECT: apagar empresa não leva lotes.
    company     = models.ForeignKey(
        'tenancy.Company', on_delete=models.PROTECT,
        related_name='lots', verbose_name='Empresa',
    )
    branch      = models.ForeignKey(
        'tenancy.Branch', on_delete=models.PROTECT,
        null=True, blank=True,               # filial é OPCIONAL no v1 (sempre)
        related_name='lots', verbose_name='Filial',
    )
    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lots',
        verbose_name='Operador',
        help_text='Quem abriu o lote (o lote pertence à EMPRESA, não a ele).',
    )
    description = models.CharField(max_length=255, blank=True, default='', verbose_name='Descrição')
    origin      = models.CharField(max_length=5, choices=ORIGIN_CHOICES,
                                   verbose_name='Origem',
                                   help_text='Classe de placa de onde os chips '
                                             'saíram (celular × PCB) — define a '
                                             'tabela de preço do eMMC.')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, verbose_name='Status')
    # ── Trava de câmbio (PLANO_FX Fase C, 2026-08-01): capturada ATOMICAMENTE
    #    no fechamento; imutável até reabertura (só superuser), quando volta
    #    ao vivo e o RE-fechamento captura taxa nova — o pghistory loga as
    #    duas travas. OV/fatura/pagamentos (2 pontas) usam a taxa DAQUI. ──
    fx_rate      = models.DecimalField(max_digits=8, decimal_places=4,
                                       null=True, blank=True,
                                       verbose_name='Câmbio travado (1¥→US$)')
    fx_source    = models.CharField(max_length=80, blank=True, default='',
                                    verbose_name='Fonte do câmbio')
    fx_locked_at = models.DateTimeField(null=True, blank=True,
                                        verbose_name='Câmbio travado em')
    fx_is_fallback = models.BooleanField(default=False,
                                         verbose_name='Câmbio de fallback')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Aberto em')

    @property
    def code(self) -> str:
        """``LOT/NUM/MM/YY`` — nomenclatura UNIVERSAL canônica (dono,
        2026-07-16; PRECIFICACAO §12.19): inglês, NUNCA traduz; NUM = a mesma
        sequência perpétua por empresa de sempre ("lote 41" continua sendo o
        41); MM/YY do mês de ABERTURA, informativo. É também o texto que o
        gerente digita para confirmar o fechamento (type-to-confirm)."""
        d = self.created_at
        return (f'LOT/{self.number:03d}/{d:%m}/{d:%y}' if d
                else f'LOT/{self.number:03d}')
    closed_at   = models.DateTimeField(null=True, blank=True, verbose_name='Fechado em')

    # T3: o caminho PADRÃO já vem filtrado pela empresa corrente (fail-closed —
    # sem escopo EXPLODE); all_companies é o escape EXPLÍCITO de plataforma
    # (admin/comandos), auditável por grep. base_manager_name evita que as
    # travessias internas do Django passem pelo manager fail-closed.
    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        ordering = ['-number']
        base_manager_name = 'all_companies'
        # ⚠ default = CRU (padrão da doc do Django: default manager NÃO filtra).
        # Motivo concreto: Django 5 valida UniqueConstraint de formulário via
        # _default_manager — com o fail-closed ali, o admin de plataforma
        # EXPLODIA (CompanyScopeMissing em /admin/.../add/, bug 2026-07-09).
        # O caminho escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        constraints = [
            # Cada empresa tem a SUA sequência (Lote #001 da Brasil Reciclagem
            # coexiste com o #001 da eMiner). Substitui o unique global.
            models.UniqueConstraint(fields=['company', 'number'],
                                    name='unique_lot_company_number'),
            # Origem obrigatória e canônica (2026-08-01) — pega criação por
            # fora do open_for_company (shell/teste) ainda no INSERT.
            models.CheckConstraint(
                name='lot_origin_vocab',
                condition=models.Q(origin__in=['phone', 'pcb'])),
        ]
        indexes = [
            # Toda consulta do app começa por company (§5.2).
            models.Index(fields=['company', '-number'],
                         name='lot_company_number_desc'),
        ]

    def __str__(self):
        return f'Lote #{self.number:03d}'

    def save(self, *args, **kwargs):
        # Portão no MODELO: filial tem que ser da mesma empresa do lote.
        if self.branch_id and self.company_id and \
                self.branch.company_id != self.company_id:
            raise ValidationError(
                {'branch': 'A filial deve pertencer à empresa do lote.'})
        return super().save(*args, **kwargs)

    @classmethod
    def open_for_company(cls, company, operator, description='', branch=None,
                         *, origin):
        """T2 (PLANO_MULTITENANT.md §7): abre um lote com numeração ATÔMICA por
        empresa. Substitui o antigo ``next_number()`` (``Max('number')+1``), que
        era uma CORRIDA real: dois gerentes clicando juntos liam o mesmo max e um
        levava ``IntegrityError`` na cara.

        Como funciona: trava a linha da Company (``select_for_update``) e
        incrementa ``last_lot_number`` — criações simultâneas serializam no lock
        e saem com números consecutivos, sem buraco e sem erro. O
        ``max(contador, Max(number))`` é auto-cura de drift (lotes criados antes
        do ``bootstrap_tenancy`` seedar o contador, ou contador atrasado por
        qualquer motivo) enquanto o ``number`` ainda é unique GLOBAL — na T3 ele
        vira ``unique (company, number)`` e o ``Max`` passa a filtrar por empresa.

        ⚠ ``select_for_update`` é NO-OP no SQLite — o teste de corrida
        (``LotNumberRaceTests``) só prova algo rodando contra Postgres."""
        from django.db.models import Max
        from tenancy.models import Company

        with transaction.atomic():
            locked = Company.objects.select_for_update().get(pk=company.pk)
            # T3: numeração POR EMPRESA — o floor olha só os lotes DELA
            # (all_companies de propósito: o método recebe a empresa explícita
            # e não depende do escopo ambiente — comandos/testes chamam direto).
            floor = (cls.all_companies.filter(company=locked)
                     .aggregate(Max('number'))['number__max'])
            next_n = max(locked.last_lot_number,
                         floor if floor is not None else -1) + 1
            if origin not in (cls.ORIGIN_PHONE, cls.ORIGIN_PCB):
                raise ValidationError({'origin': (
                    'Origem do lote é OBRIGATÓRIA (celular ou PCB) — acordo '
                    'com o comprador, 2026-08-01. Sem default de propósito.')})
            locked.last_lot_number = next_n
            locked.save(update_fields=['last_lot_number'])
            return cls.all_companies.create(number=next_n, company=locked,
                                            origin=origin,
                                            branch=branch, operator=operator,
                                            description=description)

    @property
    def chip_count(self):
        return self.entries.count()

    @property
    def total_qty(self):
        from django.db.models import Sum
        result = self.entries.aggregate(Sum('quantity'))['quantity__sum']
        return result or 0

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN


class CompanyBoundByLot(models.Model):
    """Base das linhas do estoque (T3): DENORMALIZA a empresa do lote na própria
    tabela — o RLS (T4) exige a coluna local, e os índices compostos
    ``(company, …)`` também (PLANO_MULTITENANT.md §5.2). ``save()`` deriva a
    empresa do lote e REJEITA mismatch (consistência pai-filho no modelo, não na
    view). Managers: ``objects`` fail-closed; ``all_companies`` = plataforma."""

    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                related_name='+', verbose_name='Empresa')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = 'all_companies'
        # ⚠ default = CRU (padrão da doc do Django: default manager NÃO filtra).
        # Motivo concreto: Django 5 valida UniqueConstraint de formulário via
        # _default_manager — com o fail-closed ali, o admin de plataforma
        # EXPLODIA (CompanyScopeMissing em /admin/.../add/, bug 2026-07-09).
        # O caminho escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'

    def save(self, *args, **kwargs):
        if self.lot_id:
            lot_company_id = self.lot.company_id
            if not self.company_id:
                self.company_id = lot_company_id      # herda do lote
            elif lot_company_id and self.company_id != lot_company_id:
                raise ValidationError(
                    {'company': 'A entrada pertence a uma empresa diferente do lote.'})
        return super().save(*args, **kwargs)


class InventoryEntry(CompanyBoundByLot):
    lot = models.ForeignKey(
        Lot,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')

    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    # Passo 2: edição do catálogo sob a qual este snapshot foi calculado. Se for <
    # CatalogVersion.current(), a entrada está DEFASADA (resnapshot_lote/on-read revaluam).
    snapshot_catalog_version = models.IntegerField(default=0, verbose_name='Versão do snapshot')

    # ── F11.1 (2026-07-16): CHAVE DE PREÇO materializada no LANÇAMENTO ──────
    # O classify já roda na bancada; gravamos aqui a chave (kind/gen/tier —
    # vocabulário do pricing, estável: quem muda é o PREÇO, não a chave) e a
    # valoração/export resolvem contra a tabela Price VIVA por join — o
    # classify sai do caminho de LEITURA (incidente lote 41/42). Chave vazia
    # COM price_key_reason = chip sem chave (NO_KEY, motivo gravado); tudo
    # vazio = entrada LEGADA (valoração cai no fallback classify; cura
    # definitiva = resnapshot_lote, que faz o backfill). A defasagem segue a
    # régua do snapshot_catalog_version, como o resto do snapshot.
    price_kind = models.CharField(max_length=8, blank=True, default='',
                                  verbose_name='Chave de preço: tipo')
    price_gen = models.CharField(max_length=12, blank=True, default='',
                                 verbose_name='Chave de preço: geração')
    price_tier_value = models.DecimalField(max_digits=6, decimal_places=1,
                                           null=True, blank=True,
                                           verbose_name='Chave de preço: faixa')
    price_tier_unit = models.CharField(max_length=2, blank=True, default='',
                                       verbose_name='Chave de preço: unidade')
    price_key_reason = models.CharField(max_length=200, blank=True, default='',
                                        verbose_name='Sem chave (motivo)')

    quantity     = models.PositiveIntegerField(default=1, verbose_name='Quantidade')
    added_at     = models.DateTimeField(auto_now_add=True, verbose_name='Adicionado em')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Entrada de Estoque'
        verbose_name_plural = 'Entradas de Estoque'
        ordering = ['-last_updated']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_lot_pn',
            )
        ]
        indexes = [
            # §5.2: consultas lideradas por company (busca de PN e por lote).
            models.Index(fields=['company', 'part_number'],
                         name='inv_company_pn'),
            models.Index(fields=['company', 'lot'],
                         name='inv_company_lot'),
        ]

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (Lote #{self.lot.number:03d})'

    @property
    def display_capacity(self):
        if self.is_emcp:
            parts = [p for p in [self.emcp_nand, self.emcp_ram] if p]
            return ' / '.join(parts) if parts else '—'
        return self.capacity or '—'

    @property
    def display_interface(self):
        if self.is_emcp and not self.interface:
            if self.emcp_ram:
                return self.emcp_ram.split()[0] if self.emcp_ram else '—'
        return self.interface or '—'


class PendingEntry(CompanyBoundByLot):
    """
    Fila de conferência: chip que o operador tentou adicionar mas que NÃO está
    confirmado no banco (classification_source != "banco de dados" e confidence
    fora de confirmed/manual). Em vez de contaminar o estoque, fica aqui para o
    gestor aprovar (vira InventoryEntry) ou reprovar (descarta). Ver add_chip e
    o bloqueio "só confirmados" (CLAUDE.md §2, regras de ouro).
    """
    lot         = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name='pending', verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')
    quantity    = models.PositiveIntegerField(default=1, verbose_name='Quantidade')

    # Snapshot da classificação no momento da tentativa (para o gestor revisar).
    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    confidence  = models.CharField(max_length=20, blank=True, default='', verbose_name='Confiança')

    # Dica de revisão: PN confirmado mais parecido (provável erro de digitação).
    nearest_confirmed = models.CharField(max_length=100, blank=True, default='', verbose_name='Provável typo de')

    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pending_entries', verbose_name='Operador',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Tentado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Pendente de Conferência'
        verbose_name_plural = 'Pendentes de Conferência'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_pending_lot_pn',
            )
        ]

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (pendente · Lote #{self.lot.number:03d})'


class RejectedEntry(CompanyBoundByLot):
    """
    Log de auditoria (append-only): chip CONFIRMADO no banco e com specs completas,
    mas que o operador tentou adicionar e foi barrado por NÃO RENTÁVEL na etapa 3 do
    gateway. Não entra no estoque nem na fila — segue para resíduo eletrônico. Serve
    só para auditoria e calibração das regras de rentabilidade (ver
    chips.engine.assess_profitability e estoque.views._compute_gateway).

    Por que sem unique(lot, part_number): cada tentativa de descarte é um evento
    distinto na linha do tempo. Acumular numa só linha esconderia a frequência — que
    é justamente o sinal de calibração. Logamos um registro por reprovação.
    """
    lot         = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name='rejected', verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')
    quantity    = models.PositiveIntegerField(default=1, verbose_name='Quantidade')

    # Snapshot da classificação no momento da reprovação (para auditoria posterior).
    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    confidence  = models.CharField(max_length=20, blank=True, default='', verbose_name='Confiança')

    # Razão da reprovação. Hoje sempre "NÃO RENTÁVEL"; campo deixado extensível.
    rejection_reason = models.CharField(max_length=100, default='NÃO RENTÁVEL', verbose_name='Razão')

    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rejected_entries', verbose_name='Operador',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Reprovado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Reprovado'
        verbose_name_plural = 'Reprovados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (reprovado · Lote #{self.lot.number:03d})'
