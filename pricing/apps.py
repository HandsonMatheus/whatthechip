from django.apps import AppConfig


class PricingAppConfig(AppConfig):
    """App de preços (PRECIFICACAO.md): quanto o COMPRADOR paga por chip
    classificado. Nome da classe evita colisão com o modelo PricingConfig."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pricing'
    verbose_name = 'Preços'
