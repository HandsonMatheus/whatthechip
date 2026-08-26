"""RLS + FORCE na mesa nova de pedidos de taxa — e no evento dela.

Mesmo desenho da 0021, que é onde o `pricing_pricechangerequest` mora hoje:

- **leitura AMPLA** na tabela de pedidos (`company_id IS NULL` legível de
  qualquer empresa). É o que faz o comprador de PLATAFORMA — que é o que o Wu
  Quan é — enxergar os próprios pedidos de dentro do `company_scope` de
  qualquer cliente.
- **escrita** com a cláusula do parceiro: linha de plataforma gravável por
  quem está em `pricing_buyer_users`. Sem ela o comprador não conseguiria
  criar o próprio pedido — que é o ponto inteiro desta tabela.
- **evento com leitura ESTRITA**: trilha de auditoria não é dado de
  comprador, é dado de plataforma.

⚠ FORCE junto com ENABLE: sem ele o dono do schema (o papel que a aplicação
usa no Render) ignora a policy e atravessa empresa em silêncio.

Postgres-only: no SQLite dos testes é no-op — a Camada A (o manager
fail-closed) segue cobrindo.
"""

from django.db import migrations

PEDIDO = 'pricing_ratechangerequest'
EVENTO = 'pricing_ratechangerequestevent'

_GUC = "NULLIF(current_setting('app.company_id', true), '')::int"
_PLAT = "current_setting('app.platform', true) = '1'"
_PARTNER = ("(company_id IS NULL AND EXISTS (SELECT 1 FROM pricing_buyer_users"
            " bu WHERE bu.user_id ="
            " NULLIF(current_setting('app.user_id', true), '')::int))")
_READ_WIDE = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL)"
_READ_STRICT = f"(company_id = {_GUC} OR {_PLAT})"
_WRITE = f"(company_id = {_GUC} OR {_PLAT} OR {_PARTNER})"


def _policies(schema_editor, table, read):
    schema_editor.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    schema_editor.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    schema_editor.execute(
        f'CREATE POLICY tenant_read ON {table} FOR SELECT USING ({read})')
    schema_editor.execute(
        f'CREATE POLICY tenant_ins ON {table} FOR INSERT '
        f'WITH CHECK ({_WRITE})')
    schema_editor.execute(
        f'CREATE POLICY tenant_upd ON {table} FOR UPDATE '
        f'USING ({_WRITE}) WITH CHECK ({_WRITE})')
    schema_editor.execute(
        f'CREATE POLICY tenant_del ON {table} FOR DELETE USING ({_WRITE})')


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return                                     # SQLite (testes): no-op
    _policies(schema_editor, PEDIDO, _READ_WIDE)
    _policies(schema_editor, EVENTO, _READ_STRICT)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in (PEDIDO, EVENTO):
        for nome in ('tenant_read', 'tenant_ins', 'tenant_upd', 'tenant_del'):
            schema_editor.execute(
                f'DROP POLICY IF EXISTS {nome} ON {table}')
        schema_editor.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        schema_editor.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0027_ssd_floor_e_pedido_de_taxa'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
