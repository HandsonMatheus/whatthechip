# F2 — Camada B do isolamento no PRICING (PRECIFICACAO.md §12.1): RLS.
#
# Espelho fiel da estoque/0014_t4_rls: depois desta migração, NEM QUERY BUGADA
# cruza empresa nas tabelas de preço — o Postgres filtra sozinho.
#
#   - ENABLE + FORCE: ⚠ SEM o FORCE o RLS não vale — o DONO da tabela bypassa
#     policies, e a app (Render) conecta como dono.
#   - Policy: company_id = GUC ``app.company_id``  OU  ``app.platform = '1'``
#     (plataforma/Django admin). GUC ausente → NULL → **ZERO linhas**
#     (fail-closed no banco). Linhas com company_id NULL (comprador de
#     plataforma, marketplace futuro) só aparecem para a plataforma — decisão
#     F2 registrada no PRECIFICACAO §12.
#   - Inclui as tabelas de EVENTO pghistory (preço é rastreado; o histórico é
#     tão sensível quanto o dado — armadilha §6.2.3 do PLANO_MULTITENANT.md).
#   - Fora do RLS: pricing_pricingconfig (singleton GLOBAL, sem company) e a
#     M2M pricing_buyer_users (só pares de ids user↔buyer; o acesso do parceiro
#     é decidido na view da F6, nunca por listar esta tabela).
#   - Postgres-only: no SQLite dos testes é NO-OP (a Camada A cobre lá).
#   - Reversível: o reverse dropa as policies e desliga o RLS.

from django.db import migrations

TABLES = (
    'pricing_buyer',
    'pricing_pricelist',
    'pricing_price',
    'pricing_buyerevent',
    'pricing_pricelistevent',
    'pricing_priceevent',
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
        ('pricing', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
