# F8 — RLS nas tabelas do LotPricing (mesmo padrão da pricing/0002 e da
# estoque/0014): a valoração congelada é dado comercial POR-EMPRESA — nem query
# bugada cruza empresa. Inclui a tabela de EVENTO pghistory (histórico é tão
# sensível quanto o dado). Postgres-only; reversível.

from django.db import migrations

TABLES = (
    'pricing_lotpricing',
    'pricing_lotpricingevent',
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
        ('pricing', '0003_lotpricing_lotpricingevent_and_more'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
