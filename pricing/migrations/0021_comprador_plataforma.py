# Comprador de PLATAFORMA (dono, 2026-08-03 — REVISA a decisão F2).
#
# "O comprador serve pra todo o sistema, não por empresa": a tabela de preços
# do comprador (Wu Quan) precifica o lote de QUALQUER empresa do sistema — o
# modelo de negócio é comissão sobre o total. A ENTIDADE continua invisível ao
# cliente (rótulo fixo 'WhatTheChip', F11.3) e a gestão é só-plataforma.
#
# O que muda aqui (Camada B + dados; a Camada A é o PlatformSharedManager):
#   1. POLICIES: a `tenant_isolation` (0002/0008) vira um par leitura/escrita —
#      - LEITURA (buyer/pricelist/price/pcr): empresa OU plataforma OU
#        `company IS NULL` (a linha de plataforma é legível por todos);
#      - LEITURA (tabelas de EVENTO pghistory): continua estrita (empresa OU
#        plataforma) — histórico é dado interno da plataforma;
#      - ESCRITA (todas): empresa dona OU plataforma OU usuário-PARCEIRO
#        (conta em pricing_buyer_users — o /partner/ grava pedido/evento em
#        linha de plataforma sem GUC de empresa). Residual documentado: em
#        nível de BANCO um parceiro de um comprador poderia escrever linha de
#        OUTRO comprador de plataforma — hoje há UM comprador; o app escopa
#        por buyer nas views. Apertar por-tabela (join até o buyer) se um dia
#        houver 2+ compradores com parceiros distintos.
#   2. DADOS: todo Buyer existente (e PriceList/Price/PriceChangeRequest,
#      `company` denormalizada) vira plataforma (`company=NULL`). Eventos
#      históricos NÃO são reescritos.
#
# ⚠ RunPython em tabela com RLS: abre com SET LOCAL app.platform (lição do
# deploy 2026-08-01 — sem GUC o UPDATE vê 0 linhas em silêncio; CLAUDE.md §7).
# Reverso: policies voltam ao formato 0002/0008; os dados NÃO voltam (não se
# sabe de que empresa cada linha era — re-atribuir é decisão manual do dono).

import django.db.models.deletion
from django.db import migrations, models

# Tabelas com leitura AMPLA (linha de plataforma legível por toda empresa).
WIDE = ('pricing_buyer', 'pricing_pricelist', 'pricing_price',
        'pricing_pricechangerequest')
# Tabelas de EVENTO: leitura continua estrita (empresa OU plataforma).
STRICT = ('pricing_buyerevent', 'pricing_pricelistevent', 'pricing_priceevent',
          'pricing_pricechangerequestevent')

_GUC = "NULLIF(current_setting('app.company_id', true), '')::int"
_PLAT = "current_setting('app.platform', true) = '1'"
_PARTNER = ("(company_id IS NULL AND EXISTS (SELECT 1 FROM pricing_buyer_users"
            " bu WHERE bu.user_id ="
            " NULLIF(current_setting('app.user_id', true), '')::int))")
_READ_WIDE = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL)"
_READ_STRICT = f"(company_id = {_GUC} OR {_PLAT})"
_WRITE = f"(company_id = {_GUC} OR {_PLAT} OR {_PARTNER})"

# Formato 0002/0008 — recriado no reverso.
_OLD = f"(company_id = {_GUC} OR {_PLAT})"


def _forward_policies(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return                                     # SQLite (testes): no-op
    for table, read in [(t, _READ_WIDE) for t in WIDE] + \
                       [(t, _READ_STRICT) for t in STRICT]:
        schema_editor.execute(
            f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
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


def _reverse_policies(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in WIDE + STRICT:
        for p in ('tenant_read', 'tenant_ins', 'tenant_upd', 'tenant_del'):
            schema_editor.execute(f'DROP POLICY IF EXISTS {p} ON {table}')
        schema_editor.execute(
            f'CREATE POLICY tenant_isolation ON {table} USING ({_OLD})')


def _flip_para_plataforma(apps, schema_editor):
    """Todo comprador existente vira PLATAFORMA (com os filhos denormalizados).
    Mundo real de hoje: um único comprador (wu-quan) — a doutrina nova diz que
    comprador É da plataforma, então o flip é total, não seletivo."""
    if schema_editor.connection.vendor == 'postgresql':
        # RLS fail-closed + migrate sem GUC (lição 2026-08-01, CLAUDE.md §7).
        schema_editor.execute("SET LOCAL app.platform = '1'")
    for nome in ('Buyer', 'PriceList', 'Price', 'PriceChangeRequest'):
        apps.get_model('pricing', nome)._default_manager.update(company=None)


def _noop(apps, schema_editor):
    pass  # reverso dos dados: re-atribuir empresa é decisão manual (ver topo)


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0020_fxrate'),
        ('tenancy', '0004_remove_company_insert_insert_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buyer',
            name='company',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='buyers', to='tenancy.company',
                verbose_name='Empresa',
                help_text='De quem é este comprador. VAZIO = comprador de '
                          'PLATAFORMA (dono, 2026-08-03): a tabela dele '
                          'precifica o lote de TODAS as empresas (comissão '
                          'sobre o total); a entidade e a gestão continuam '
                          'só-plataforma (cliente vê "WhatTheChip").'),
        ),
        migrations.RunPython(_forward_policies, _reverse_policies),
        migrations.RunPython(_flip_para_plataforma, _noop),
    ]
