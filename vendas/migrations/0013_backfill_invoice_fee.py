# TAXA DE SERVIÇO em TODA fatura já existente (dono, 2026-08-19):
# "precisamos que TODAS as faturas do sistema contenham esses 10%, para todos
# os clientes, todas as SO já geradas, independente do seu estado".
#
# Por que MIGRAÇÃO e não comando: isto é um INVARIANTE de estado ("nenhuma
# fatura sem taxa"), não uma tarefa de manutenção. Como migração ela roda
# sozinha no build da Render, no mesmo passo em que a coluna nasce — e não há
# como esquecer de rodá-la num ambiente, que é justamente a deriva
# banco-vs-código que derrubou a criação de OV em produção nesta semana.
#
# A taxa aplicada é a VIGENTE no cadastro de cada empresa (`service_fee_pct`,
# padrão 10%). A partir daqui a fatura carrega a sua e congela: emissão nova
# pega a taxa do cadastro no momento em que nasce (services.settle_and_invoice).
#
# Reversível: o reverse zera os três campos, que é o estado anterior exato.

from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations

_CENT = Decimal('0.01')


def _liberar_rls(schema_editor):
    """⚠ vendas_invoice tem RLS ENABLE+FORCE fail-closed: sem GUC a policy
    devolve ZERO linhas. O ``migrate`` do build (Render) roda SEM GUC e com
    usuário NÃO-superuser → o backfill atualizaria 0 linhas EM SILÊNCIO.
    Local engana: conexão superuser bypassa RLS mesmo com FORCE (CLAUDE.md §7).
    SET LOCAL = vale só até o fim da transação desta migração."""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL app.platform = '1'")


def aplicar(apps, schema_editor):
    _liberar_rls(schema_editor)
    # modelo histórico: managers custom não migram — usa o _default_manager
    Invoice = apps.get_model('vendas', 'Invoice')
    # TODAS: aberta, paga ou cancelada. Cancelada não entra em conta nenhuma,
    # mas deixá-la fora criaria a única fatura do sistema sem taxa — e
    # "invariante com exceção" é o começo de um bug de relatório.
    for inv in Invoice._default_manager.select_related('company').iterator():
        pct = getattr(inv.company, 'service_fee_pct', None) or Decimal('0.00')
        fee_rmb = (inv.total_rmb * pct / 100).quantize(_CENT, ROUND_HALF_UP)
        fee_usd = (inv.total_usd * pct / 100).quantize(_CENT, ROUND_HALF_UP)
        if (inv.fee_pct, inv.fee_rmb, inv.fee_usd) == (pct, fee_rmb, fee_usd):
            continue                      # idempotente: nada a fazer
        inv.fee_pct, inv.fee_rmb, inv.fee_usd = pct, fee_rmb, fee_usd
        inv.save(update_fields=['fee_pct', 'fee_rmb', 'fee_usd'])


def desfazer(apps, schema_editor):
    _liberar_rls(schema_editor)
    Invoice = apps.get_model('vendas', 'Invoice')
    Invoice._default_manager.all().update(
        fee_pct=Decimal('0.00'), fee_rmb=Decimal('0.00'),
        fee_usd=Decimal('0.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0012_payout_rls'),
        # a taxa vem do cadastro da empresa: o campo tem que existir antes
        ('tenancy', '0011_company_service_fee'),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
