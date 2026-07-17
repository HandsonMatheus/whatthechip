# F11.4 — RLS+FORCE nas tabelas de ACERTO/FATURA/PAGAMENTO (mesmo padrão
# vendas/0002): dinheiro por-empresa; inclui eventos pghistory. Postgres-only.

from django.db import migrations

TABLES = (
    'vendas_settlement',
    'vendas_settlementevent',
    'vendas_settlementline',
    'vendas_settlementlineevent',
    'vendas_invoice',
    'vendas_invoiceevent',
    'vendas_payment',
    'vendas_paymentevent',
)

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
        ('vendas', '0003_invoice_payment_paymentevent_settlement_invoiceevent_and_more'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
