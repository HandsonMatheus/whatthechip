# F6.1 — RLS nas tabelas da MODERAÇÃO (mesmo padrão pricing/0002 e 0004): o
# pedido de mudança é dado comercial POR-EMPRESA. Inclui a tabela de EVENTO
# pghistory. Postgres-only; reversível.

from django.db import migrations

TABLES = (
    'pricing_pricechangerequest',
    'pricing_pricechangerequestevent',
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
        return                                    # SQLite (testes): no-op
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
        ('pricing', '0007_pricechangerequest_pricechangerequestevent_and_more'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
