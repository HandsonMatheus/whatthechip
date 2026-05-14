"""
WhatTheChip — Estoque de Operadores
====================================
Modelo de inventário por operador.

Fluxo:
    Operador digita/escaneia PN
    → Motor classifica
    → Se tem capacidade: salva/incrementa InventoryEntry
    → Se não tem capacidade: salva em chips.UnknownChip
"""

from django.conf import settings
from django.db import models


class InventoryEntry(models.Model):
    """
    Uma linha de estoque: um PN único por operador.
    Ao adicionar um PN já existente, apenas quantity é incrementado.
    """

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory",
        verbose_name="Operador",
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name="Part Number")

    # Dados preenchidos pelo motor de classificação
    chip_type   = models.CharField(max_length=50,  blank=True, default="", verbose_name="Tipo")
    brand       = models.CharField(max_length=100, blank=True, default="", verbose_name="Fabricante")
    capacity    = models.CharField(max_length=100, blank=True, default="", verbose_name="Capacidade")
    emcp_ram    = models.CharField(max_length=100, blank=True, default="", verbose_name="RAM (eMCP)")
    emcp_nand   = models.CharField(max_length=100, blank=True, default="", verbose_name="NAND (eMCP)")
    is_emcp     = models.BooleanField(default=False, verbose_name="É eMCP/uMCP")
    interface   = models.CharField(max_length=100, blank=True, default="", verbose_name="Interface")
    classification_source = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Fonte da classificação"
    )

    quantity    = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    added_at    = models.DateTimeField(auto_now_add=True, verbose_name="Adicionado em")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Entrada de Estoque"
        verbose_name_plural = "Entradas de Estoque"
        ordering = ["-last_updated"]
        constraints = [
            models.UniqueConstraint(
                fields=["operator", "part_number"],
                name="unique_operator_pn",
            )
        ]

    def __str__(self):
        return f"{self.part_number} × {self.quantity} ({self.operator.username})"

    @property
    def display_capacity(self):
        """Retorna capacidade formatada independentemente de ser eMCP ou não."""
        if self.is_emcp:
            parts = [p for p in [self.emcp_nand, self.emcp_ram] if p]
            return " / ".join(parts) if parts else "—"
        return self.capacity or "—"

    @property
    def display_interface(self):
        if self.is_emcp and not self.interface:
            # Para eMCP, a interface está embutida em emcp_ram (ex: "LPDDR4X 4GB")
            if self.emcp_ram:
                # extrai o tipo de RAM da string "LPDDR4X 4GB"
                return self.emcp_ram.split()[0] if self.emcp_ram else "—"
        return self.interface or "—"
