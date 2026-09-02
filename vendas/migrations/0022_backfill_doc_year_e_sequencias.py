"""
Preenche o ANO dos documentos e move os CONTADORES para o novo formato
(CONVENCAO_IDENTIFICADORES.md; decisões do dono em 2026-09-02).

Três coisas, e nenhuma delas é opcional para o esquema da 0021/0023 funcionar:

  1. **`Lot.doc_year`** — o ano de ABERTURA, em horário LOCAL. ⚠ Não o do
     banco: um lote aberto 31/dez 21:00 em Assunção já é 1º de janeiro em UTC.
  2. **`Lot.ever_closed`** — marca "este lote já virou documento alguma vez".
     Fechar emite o PDF de conferência com o código dentro, e a partir daí o
     número dele não volta mais para a sequência (é a trava da devolução de
     número na exclusão). Conservador de propósito: fechado AGORA, `closed_at`
     preenchido, OU com valoração congelada (`LotPricing`, escrita no ato do
     fechamento) — qualquer uma marca. Errar para "já fechou" custa um número
     não reaproveitado; errar para o outro lado reemite um código impresso.
  3. **`SalesOrder.doc_year`** — o ano do LOTE dela, nunca o da própria criação
     (§2.2 da convenção).
  4. **Contadores** — a sequência passa a ser por (empresa, tipo, ANO):
     · `lot` nasce do MAIOR NÚMERO REAL de cada ano. ⚠ Decisão explícita do
       dono (D11): a eMiner tinha `last_lot_number=50` com o maior lote em 13 —
       resíduo da renumeração de 01/09, que comprimiu 39–50 em 1–13 e não
       recuou o contador. Semear com 50 abriria um buraco de 37 números no
       primeiro dia depois de ele ter recontado justamente para não ter buraco.
     · `so` nasce do maior número real de cada ano, com o contador PERPÉTUO
       antigo como PISO no ano mais recente — se alguma ordem tiver sido
       apagada, o número dela não pode ser reemitido.
     · `inv` NÃO é tocada: fica na linha perpétua (`year=0`). A fatura está
       sendo aposentada em entrega separada e não pode mudar de comportamento
       de raspão.

⚠ RLS: `vendas_*` e `estoque_lot` têm RLS ENABLE+FORCE. O `migrate` do build
(Render) roda SEM GUC e com usuário NÃO-superuser → sem o `SET LOCAL
app.platform` a policy devolveria ZERO linhas e a migração diria "pronto" sem
ter tocado em nada. Local engana: superuser bypassa FORCE (CLAUDE.md §7).

Reversível: o reverse zera os campos e devolve os contadores para a linha
perpétua — o estado exato de antes.
"""

from django.db import migrations, models
from django.utils import timezone


def _liberar_rls(schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL app.platform = '1'")


def _ano_local(dt):
    """Ano no fuso do NEGÓCIO (settings.TIME_ZONE), não no do banco."""
    if dt is None:
        return timezone.localdate().year
    return timezone.localtime(dt).year if timezone.is_aware(dt) else dt.year


def aplicar(apps, schema_editor):
    _liberar_rls(schema_editor)
    Lot = apps.get_model('estoque', 'Lot')
    LotPricing = apps.get_model('pricing', 'LotPricing')
    SalesOrder = apps.get_model('vendas', 'SalesOrder')
    DocSequence = apps.get_model('vendas', 'DocSequence')
    Company = apps.get_model('tenancy', 'Company')

    # ── 1+2. lote: ano de abertura e "já foi fechado" ────────────────────
    com_valoracao = set(LotPricing._default_manager.values_list('lot_id', flat=True))
    for lot in Lot._default_manager.all().iterator():
        ano = _ano_local(lot.created_at)
        fechou = bool(lot.status == 'closed' or lot.closed_at
                      or lot.pk in com_valoracao)
        if lot.doc_year == ano and lot.ever_closed == fechou:
            continue                                    # idempotente
        lot.doc_year, lot.ever_closed = ano, fechou
        lot.save(update_fields=['doc_year', 'ever_closed'])

    # ── 3. ordem de venda: o ano vem do LOTE ─────────────────────────────
    anos_de_lote = dict(Lot._default_manager.values_list('pk', 'doc_year'))
    for so in SalesOrder._default_manager.all().iterator():
        ano = anos_de_lote.get(so.lot_id) or _ano_local(so.created_at)
        if so.doc_year == ano:
            continue
        so.doc_year = ano
        so.save(update_fields=['doc_year'])

    # ── 4. contadores por ano ────────────────────────────────────────────
    for kind, Modelo in (('lot', Lot), ('so', SalesOrder)):
        # o contador perpétuo antigo, que vira PISO do ano mais recente (só na
        # OV — no lote o dono decidiu semear pelo dado real, D11)
        perpetuos = {
            d['company_id']: d['last_number']
            for d in DocSequence._default_manager.filter(kind=kind, year=0)
                                .values('company_id', 'last_number')
        } if kind == 'so' else {}

        por_empresa = {}
        for linha in (Modelo._default_manager.values('company_id', 'doc_year')
                      .annotate(m=models.Max('number'))):
            if not linha['doc_year']:
                continue
            por_empresa.setdefault(linha['company_id'], {})[
                linha['doc_year']] = linha['m']

        for company_id, por_ano in por_empresa.items():
            recente = max(por_ano)
            for ano, maximo in por_ano.items():
                piso = perpetuos.get(company_id, 0) if ano == recente else 0
                seq, _ = DocSequence._default_manager.get_or_create(
                    company_id=company_id, kind=kind, year=ano,
                    defaults={'last_number': 0})
                alvo = max(maximo, piso, seq.last_number)
                if seq.last_number != alvo:
                    seq.last_number = alvo
                    seq.save(update_fields=['last_number'])

        # a linha perpétua de LOT/SO deixa de existir (a da INV fica)
        DocSequence._default_manager.filter(kind=kind, year=0).delete()

    # ── espelho no cadastro: o admin não pode exibir um contador que mente ─
    for linha in (Lot._default_manager.values('company_id')
                  .annotate(m=models.Max('number'))):
        Company._default_manager.filter(pk=linha['company_id']).exclude(
            last_lot_number=linha['m']).update(last_lot_number=linha['m'])


def desfazer(apps, schema_editor):
    _liberar_rls(schema_editor)
    Lot = apps.get_model('estoque', 'Lot')
    SalesOrder = apps.get_model('vendas', 'SalesOrder')
    DocSequence = apps.get_model('vendas', 'DocSequence')

    Lot._default_manager.all().update(doc_year=0, ever_closed=False)
    SalesOrder._default_manager.all().update(doc_year=0)
    # devolve os contadores de lote/OV para a linha perpétua, com o maior
    # número que cada empresa tinha em qualquer ano.
    for kind in ('lot', 'so'):
        maximos = {}
        for d in (DocSequence._default_manager.filter(kind=kind)
                  .exclude(year=0).values('company_id', 'last_number')):
            maximos[d['company_id']] = max(maximos.get(d['company_id'], 0),
                                           d['last_number'])
        DocSequence._default_manager.filter(kind=kind).exclude(year=0).delete()
        for company_id, ultimo in maximos.items():
            seq, _ = DocSequence._default_manager.get_or_create(
                company_id=company_id, kind=kind, year=0,
                defaults={'last_number': 0})
            if seq.last_number < ultimo:
                seq.last_number = ultimo
                seq.save(update_fields=['last_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0021_remove_salesorder_insert_insert_and_more'),
        ('estoque', '0023_remove_lot_insert_insert_remove_lot_update_update_and_more'),
        ('pricing', '0028_ratechangerequest_rls'),
        ('tenancy', '0013_alter_company_code_alter_companyevent_code'),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
