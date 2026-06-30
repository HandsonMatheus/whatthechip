"""
WhatTheChip — Estoque de Operadores
====================================
Modelo de inventário por lote.
"""

from django.conf import settings
from django.db import models


class Lot(models.Model):
    STATUS_OPEN   = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN,   'Aberto'),
        (STATUS_CLOSED, 'Fechado'),
    ]

    number      = models.PositiveIntegerField(unique=True, verbose_name="Número")
    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lots',
        verbose_name='Operador',
    )
    description = models.CharField(max_length=255, blank=True, default='', verbose_name='Descrição')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, verbose_name='Status')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Aberto em')
    closed_at   = models.DateTimeField(null=True, blank=True, verbose_name='Fechado em')

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        ordering = ['-number']

    def __str__(self):
        return f'Lote #{self.number:03d}'

    @classmethod
    def next_number(cls):
        from django.db.models import Max
        max_n = cls.objects.aggregate(Max('number'))['number__max']
        return (max_n if max_n is not None else -1) + 1

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


class InventoryEntry(models.Model):
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

    quantity     = models.PositiveIntegerField(default=1, verbose_name='Quantidade')
    added_at     = models.DateTimeField(auto_now_add=True, verbose_name='Adicionado em')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Entrada de Estoque'
        verbose_name_plural = 'Entradas de Estoque'
        ordering = ['-last_updated']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_lot_pn',
            )
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


class PendingEntry(models.Model):
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

    class Meta:
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


class RejectedEntry(models.Model):
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

    class Meta:
        verbose_name = 'Reprovado'
        verbose_name_plural = 'Reprovados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (reprovado · Lote #{self.lot.number:03d})'
