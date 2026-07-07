from django.apps import AppConfig


class TenancyConfig(AppConfig):
    """
    tenancy/ — a fundação multi-empresa do WhatTheChip (PLANO_MULTITENANT.md, T1).

    Company é a fronteira do isolamento; Branch é sub-unidade organizacional;
    Membership dá o papel (admin/manager/operator) de um usuário numa empresa.
    O catálogo (chips/) continua GLOBAL — só o comércio/estoque é por-empresa.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenancy'
    verbose_name = 'Empresas & Papéis'
