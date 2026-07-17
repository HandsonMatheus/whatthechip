from django.apps import AppConfig


class VendasConfig(AppConfig):
    """F11.2 (PRECIFICACAO §12.19): o lado COMERCIAL do lote — Cotação → OV →
    (F11.4: Acerto → Fatura → Pagamentos). Valor mora em documento comercial;
    estoque é quantidade (padrão Odoo, decisão do dono 2026-07-16)."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendas'
    verbose_name = 'Vendas'
