# Correção de RLS (bug de PRODUÇÃO 2026-07-09): o COMPRADOR precisa enxergar o
# PRÓPRIO registro de Buyer ANTES de existir escopo de empresa.
#
# O paradoxo que quebrou o /partner/: o parceiro NÃO tem Membership → o
# TenancyMiddleware não emite ``app.company_id`` → a policy da 0002 devolvia
# ZERO linhas de ``pricing_buyer`` → os gates (tenancy/access.py e
# ``partner_required``) não achavam o buyer para decidir o redirect/escopo →
# 403. No dev local o role SUPERUSER bypassa RLS e o bug ficava invisível
# (mesma armadilha §6.2.1 do PLANO_MULTITENANT.md).
#
# O conserto (sem afrouxar nada):
#   - o middleware agora emite ``app.user_id`` para TODO autenticado;
#   - esta policy ganha a cláusula de AUTO-ACESSO: o buyer é visível para os
#     usuários do SEU M2M (``pricing_buyer_users`` está fora do RLS de
#     propósito — só pares de ids, documentado na 0002).
#   Empresa continua vendo só os buyers DELA; plataforma vê tudo; as tabelas
#   sensíveis (PriceList/Price/LotPricing/eventos) seguem intocadas.

from django.db import migrations

NEW_POLICY = """
CREATE POLICY tenant_isolation ON pricing_buyer
    USING (
        company_id = NULLIF(current_setting('app.company_id', true), '')::int
        OR current_setting('app.platform', true) = '1'
        OR id IN (SELECT buyer_id FROM pricing_buyer_users
                  WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::int)
    )
"""

OLD_POLICY = """
CREATE POLICY tenant_isolation ON pricing_buyer
    USING (
        company_id = NULLIF(current_setting('app.company_id', true), '')::int
        OR current_setting('app.platform', true) = '1'
    )
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return                                    # SQLite (testes): no-op
    schema_editor.execute('DROP POLICY IF EXISTS tenant_isolation ON pricing_buyer')
    schema_editor.execute(NEW_POLICY)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP POLICY IF EXISTS tenant_isolation ON pricing_buyer')
    schema_editor.execute(OLD_POLICY)


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0009_remove_pricechangerequest_insert_insert_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
