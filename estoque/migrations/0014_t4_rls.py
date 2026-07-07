# T4 — Camada B do isolamento (PLANO_MULTITENANT.md §6.2): ROW LEVEL SECURITY.
#
# Depois desta migração, NEM QUERY BUGADA cruza empresa: o Postgres filtra as
# linhas das 4 tabelas do estoque pela policy, independente do código Python.
#
#   - ENABLE + FORCE: ⚠ SEM o FORCE o RLS não vale — o DONO da tabela bypassa
#     policies, e a app (Render) conecta como dono.
#   - Policy: company_id = GUC ``app.company_id``  OU  ``app.platform = '1'``
#     (plataforma/superuser — Django admin enxerga tudo, §8). GUC ausente →
#     current_setting(..., true) devolve NULL → policy avalia falso →
#     **ZERO linhas (fail-closed também no banco)**.
#   - Quem emite os GUCs: TenancyMiddleware (transaction-local, PgBouncer-safe),
#     company_scope() e scope_command_to_company() (sessão do comando).
#   - Postgres-only: no SQLite dos testes é NO-OP (não existe RLS lá; a Camada A
#     — manager fail-closed — segue cobrindo).
#   - Reversível: o reverse dropa as policies e desliga o RLS.
#   - ⚠ Data-migration futura que toque estoque SEM GUC lerá 0 linhas — sete
#     ``app.platform='1'`` na conexão ou use company_scope (armadilha §6.2.2).

from django.db import migrations

TABLES = (
    'estoque_lot',
    'estoque_inventoryentry',
    'estoque_pendingentry',
    'estoque_rejectedentry',
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
        ('estoque', '0013_t3_company_lock'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
