# RLS+FORCE no REPASSE (mesmo padrão de vendas/0002, 0004 e 0009): repasse é
# dinheiro por-empresa — o que sai da conta do WhatTheChip para UM cliente.
# Sem isto, uma query bugada cruzaria empresa e um cliente veria o extrato do
# outro.
#
# Postgres-only: no SQLite dos testes é no-op (a Camada A, o manager
# fail-closed, segue cobrindo).

from django.db import migrations

TABLES = ('vendas_payout',)

POLICY = """
CREATE POLICY tenant_isolation ON {table}
    USING (
        company_id = NULLIF(current_setting('app.company_id', true), '')::int
        OR current_setting('app.platform', true) = '1'
    )
"""


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in TABLES:
        schema_editor.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        schema_editor.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        schema_editor.execute(POLICY.format(table=table))


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in TABLES:
        schema_editor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
        schema_editor.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        schema_editor.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0011_invoice_fee_and_payout'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
