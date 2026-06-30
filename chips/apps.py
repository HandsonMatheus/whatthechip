from django.apps import AppConfig


class ChipsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chips"
    verbose_name = "Chips — Classificador"

    def ready(self):
        # Passo 1B: sobe o carimbo `catalog_version` quando a GRAMÁTICA
        # (ChipFamily/DecodeMap) ou a rentabilidade (ProfitabilityConfig) muda —
        # admin OU populate_*. O engine vê o número novo e recarrega o cache
        # sozinho em todos os workers, sem reinício. (Escrita em massa não dispara
        # sinal: o loader YAML do passo 4 fará bump explícito.)
        from django.db.models.signals import post_save, post_delete
        from . import models as m

        def _bump(sender, **kwargs):
            try:
                m.CatalogVersion.bump()
            except Exception:
                pass  # tabela pode não existir durante o primeiro migrate

        for _model in (m.ChipFamily, m.DecodeMap, m.ProfitabilityConfig):
            post_save.connect(_bump, sender=_model, weak=False,
                              dispatch_uid=f"wtc_bump_{_model.__name__}_save")
            post_delete.connect(_bump, sender=_model, weak=False,
                                dispatch_uid=f"wtc_bump_{_model.__name__}_del")
