# RLS+FORCE no comprovante (mesmo padrão de vendas/0002 e 0004): comprovante
# de pagamento é dinheiro por-empresa. Sem isto, uma query bugada cruzaria
# empresa — e aqui o que vaza é o extrato bancário de um cliente.
#
# Postgres-only: no SQLite dos testes é no-op (a Camada A, o manager
# fail-closed, segue cobrindo).

from django.db import migrations

TABLES = ('vendas_paymentreceipt',)

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
        ('vendas', '0008_paymentreceipt'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
