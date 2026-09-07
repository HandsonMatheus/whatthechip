# RLS+FORCE no RASCUNHO da conferência (mesmo padrão de vendas/0002, 0004,
# 0009 e 0016).
#
# O rascunho não é documento nem dinheiro — é o que o comprador digitou e
# ainda não fechou. Mas é exatamente a leitura que o dono decidiu NÃO expor
# fora da tela dele (2026-09-07), e a Camada A sozinha protege só enquanto
# ninguém escrever uma query com `all_companies`. Aqui vale a regra padrão da
# casa: quem não é da empresa nem é plataforma não enxerga a linha.
#
# Política PADRÃO (não a ampla da carteira): a `USING` sem `WITH CHECK` faz o
# Postgres reusar a mesma expressão na escrita, que é o que se quer — rascunho
# não tem sabor de plataforma.
#
# Postgres-only: no SQLite dos testes é no-op (a Camada A, o manager
# fail-closed, segue cobrindo).

from django.db import migrations

TABLES = ('vendas_settlementdraft',)

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
        schema_editor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
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
        ('vendas', '0023_settlementdraft'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
