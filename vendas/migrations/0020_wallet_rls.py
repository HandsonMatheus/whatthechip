# RLS+FORCE na CARTEIRA — e aqui a leitura é AMPLA, ao contrário das outras
# tabelas de `vendas` (dono, 2026-09-01).
#
# Por quê: desde a 0019 a carteira tem dois sabores. `company IS NULL` é a
# carteira da PLATAFORMA e TODA empresa precisa poder lê-la — é o endereço que
# o comprador dela paga no arranjo padrão. `company = X` é a carteira daquele
# cliente e só ele enxerga. É exatamente o par leitura/escrita do
# `pricing/0021` (comprador de plataforma), pelo mesmo motivo: linha de
# plataforma é legível por todos, mas escrita só pelo dono ou pela plataforma.
#
#   LEITURA  (USING):      empresa OU plataforma OU `company IS NULL`
#   ESCRITA  (WITH CHECK): empresa OU plataforma
#
# ⚠ Sem a leitura ampla, o comprador de uma empresa no arranjo PADRÃO veria
#   "carteira não cadastrada" para a carteira do WhatTheChip, que existe — o
#   zero silencioso do RLS de novo (CLAUDE.md §7), agora numa tela que decide
#   para onde vai dinheiro.
#
# Postgres-only: no SQLite dos testes é no-op (a Camada A, o
# PlatformSharedManager, segue cobrindo).

from django.db import migrations

TABLE = 'vendas_wallet'

_GUC = "NULLIF(current_setting('app.company_id', true), '')::int"
_PLAT = "current_setting('app.platform', true) = '1'"
_READ = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL)"
_WRITE = f"(company_id = {_GUC} OR {_PLAT})"

POLICY = f"""
CREATE POLICY tenant_isolation ON {TABLE}
    USING {_READ}
    WITH CHECK {_WRITE}
"""


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(f'ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY')
    schema_editor.execute(f'ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY')
    schema_editor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {TABLE}')
    schema_editor.execute(POLICY)


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {TABLE}')
    schema_editor.execute(f'ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY')
    schema_editor.execute(f'ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0019_wallet_company'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
