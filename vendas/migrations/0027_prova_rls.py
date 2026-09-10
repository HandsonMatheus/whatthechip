# RLS+FORCE nas tabelas da PROVA — mesmo padrão de vendas/0002, 0009, 0016 e
# 0024. Prova de recusa é dado comercial por-empresa: a foto do chip da eMiner
# não pode aparecer numa consulta da eRecyclo, nem o contrário.
#
# ⚠ A `vendas_defeitotipo` NÃO entra, e a ausência é a decisão: o vocabulário
#   de defeitos é GLOBAL (curado pelo dono), como a `estoque_politicaorigemtipo`
#   e a `pricing_categorycode`. Pôr RLS nela esconderia a tabela de todo mundo,
#   porque ela não tem `company_id` para a política comparar.

from django.db import migrations

TABLES = (
    'vendas_prova',
    'vendas_provafoto',
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

    dependencies = [('vendas', '0026_prova_da_conferencia')]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
