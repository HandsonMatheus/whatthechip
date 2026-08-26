# As observações que JÁ EXISTEM viram a primeira nota de cada compra.
#
# Sem isto, a aba Observações nasceria vazia em toda compra já fechada — e a
# nota que o comprador escreveu no fechamento continuaria existindo, invisível,
# dentro do acerto. Pior do que não ter a aba: ter a aba mentindo que ele nunca
# escreveu nada, com o texto ainda saindo no PDF por outro caminho.
#
# ⚠ RunPython em tabela com RLS abre com `SET LOCAL app.platform` (lição do
# deploy 2026-08-01, CLAUDE.md §7): sem o GUC o INSERT vê zero linhas de origem
# e "roda" sem fazer nada, em silêncio.
#
# ⚠ `created_at` é auto_now_add — o `create()` carimba a hora de HOJE e a nota
# apareceria como escrita na migração. O UPDATE logo depois devolve a data do
# ACERTO, que é quando ela foi escrita de verdade. Data errada num documento
# que o cliente recebe é pior do que nenhuma.
#
# Idempotente por conteúdo: pula acerto que já tem nota igual na mesma ordem —
# rodar duas vezes não duplica. Reverso apaga só o que esta migração criou
# (mesmo texto, mesma ordem); o `Settlement.notes` nunca é tocado, então o
# reverso é seguro em qualquer ordem.

from django.db import migrations


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL app.platform = '1'")
    Settlement = apps.get_model('vendas', 'Settlement')
    OrderNote = apps.get_model('vendas', 'OrderNote')
    criadas = 0
    for acerto in Settlement._default_manager.exclude(notes='').iterator():
        texto = (acerto.notes or '').strip()
        if not texto:
            continue
        if OrderNote._default_manager.filter(order_id=acerto.order_id,
                                             text=texto).exists():
            continue
        nota = OrderNote._default_manager.create(
            order_id=acerto.order_id, company_id=acerto.company_id,
            text=texto, created_by_id=acerto.created_by_id)
        # devolve a data do acerto (o auto_now_add carimbou hoje)
        OrderNote._default_manager.filter(pk=nota.pk).update(
            created_at=acerto.created_at)
        criadas += 1
    if criadas:
        print(f'  OrderNote: {criadas} observação(ões) trazida(s) do acerto.')


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL app.platform = '1'")
    Settlement = apps.get_model('vendas', 'Settlement')
    OrderNote = apps.get_model('vendas', 'OrderNote')
    for acerto in Settlement._default_manager.exclude(notes='').iterator():
        texto = (acerto.notes or '').strip()
        if texto:
            OrderNote._default_manager.filter(order_id=acerto.order_id,
                                              text=texto).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0016_ordernote_rls'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
