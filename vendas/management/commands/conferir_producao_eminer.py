"""
conferir_producao_eminer
========================
SÓ LEITURA. Confere se o banco alvo está no estado que a corrente de
reconciliação espera encontrar — antes de qualquer comando escrever nele.

Por que existe (2026-09-01). Todo o plano foi calculado contra um dump de
produção tirado em 31/08. Três dos comandos carregam CÓDIGOS DE ORDEM
escritos à mão (`SO/009/04/26`, `SO/010/06/26`, `SO/011/07/26`) que só vão
existir se o contador de ordens estiver exatamente em 8 quando o
`criar_lotes_legados_eminer` rodar. Se alguém fechou um lote em produção
desde o dump, o contador andou, os legados nascem com outro número e esses
três comandos morrem com "ordem não encontrada" — **depois** de os três
primeiros já terem gravado. Metade aplicada é o pior lugar para se estar.

Este comando não conserta nada. Ele imprime uma tabela do tipo
`esperado × encontrado` e um veredito. Rode nos DOIS bancos (o seu local e o
de produção) e compare.

⚠ NADA aqui escreve. Sem `--commit`, sem transação de escrita, sem `save()`.
⚠ A leitura da GRADE DE PREÇOS abre `platform_scope()`: comprador, lista e
  preço são linhas de PLATAFORMA sob RLS, e comando sem esse GUC lê ZERO em
  silêncio (armadilha registrada no CLAUDE.md — o `audit_category_codes`
  relatou "nenhum código tem estoque" justamente assim). Zero silencioso vira
  zero barulhento aqui.

Uso:
    python manage.py conferir_producao_eminer
    DATABASE_URL="postgres://…render…" python manage.py conferir_producao_eminer
"""

from decimal import Decimal as D, ROUND_HALF_UP

from django.core.management.base import BaseCommand

from tenancy.models import Company
from tenancy.scope import company_scope, platform_scope

EMPRESA_SLUG = 'eminer'
CENT = D('0.01')

#: ── O que a corrente ESPERA encontrar ────────────────────────────────────
SEQ_ESPERADA = {'so': 8, 'inv': 1}
LOTES_ESPERADOS = {39, 40, 41, 42, 43, 44, 45, 48, 49, 50}
LOTES_ABERTOS = {48, 49, 50}
#: `criar_lotes_legados_eminer` cria estes — não podem existir ainda.
LOTES_A_CRIAR = {1, 2, 4}
#: lote → (número da OV, status)
ORDENS_ESPERADAS = {
    39: [(5, 'confirmed')],
    40: [(1, 'confirmed')],
    41: [(2, 'confirmed')],
    42: [(3, 'cancelled'), (4, 'draft')],
    43: [(8, 'confirmed')],
    44: [(7, 'confirmed')],
    45: [(6, 'confirmed')],
}
#: O que o `despachar_lote007_eminer` vai congelar no lote 42.
LOTE_007 = 42
CONGELAMENTO_ESPERADO = dict(fx=D('0.1482'), rmb=D('79102.00'),
                             usd=D('11694.91'))
MIGRACAO = ('estoque', '0022_origens_legadas_mixed_k9')


class Command(BaseCommand):
    help = ('SÓ LEITURA: confere se o banco está no estado que a corrente de '
            'reconciliação da eMiner espera. Rode antes de aplicar qualquer '
            'comando em produção.')

    def handle(self, *args, **o):
        self.w = self.stdout.write
        self.st = self.style
        self.problemas = []

        empresa = Company.objects.filter(slug=EMPRESA_SLUG).first()
        if empresa is None:
            raise SystemExit(self.st.ERROR(
                f'Empresa "{EMPRESA_SLUG}" não existe neste banco. '
                f'DATABASE_URL aponta para o lugar certo?'))

        self.w('')
        self.w(self.st.MIGRATE_HEADING(
            '━━ conferência de produção · eMiner · SÓ LEITURA ━━'))
        from django.db import connection
        self.w(f'   banco   {connection.settings_dict.get("NAME")} '
               f'@ {connection.settings_dict.get("HOST") or "local"}')
        self.w('')

        with company_scope(empresa.id):
            self._empresa(empresa)
            self._migracao()
            self._contadores(empresa)
            self._lotes()
            self._ordens()
            self._dinheiro()
            self._valoracoes()
            self._congelamento_do_007(empresa)

        self.w('')
        if self.problemas:
            self.w(self.st.ERROR(
                f'   ✗ {len(self.problemas)} divergência(s). A corrente NÃO '
                f'está segura para rodar aqui\n     sem ajuste — cada linha '
                f'acima marcada DIVERGE explica o quê.'))
        else:
            self.w(self.st.SUCCESS(
                '   ✓ Tudo como a corrente espera. Pode aplicar na ordem do '
                'runbook.'))
        self.w('')

    # ── utilitário de relato ─────────────────────────────────────────────
    def _linha(self, rotulo, esperado, encontrado, ok=None):
        # ⚠ compare VALOR com VALOR. A 1ª versão passava o esperado já
        # formatado ('[]') contra uma lista de verdade ([]) e três linhas
        # boas apareciam como DIVERGE — um conferidor que grita sem motivo é
        # pior que nenhum, porque ensina a ignorar o grito.
        ok = (esperado == encontrado) if ok is None else ok
        marca = self.st.SUCCESS('ok     ') if ok else self.st.ERROR('DIVERGE')
        if not ok:
            self.problemas.append(rotulo)
        self.w(f'   {marca}  {rotulo:<36} esperado {esperado}'
               f'   ·   achei {encontrado}')

    def _titulo(self, t):
        self.w('')
        self.w(f'   ── {t} ' + '─' * max(0, 58 - len(t)))

    # ── blocos ───────────────────────────────────────────────────────────
    def _empresa(self, empresa):
        self._titulo('empresa')
        self._linha('código da empresa (vazio = legado)', "''",
                    f"'{empresa.code}'")
        self._linha('taxa de serviço', '10.00',
                    str(empresa.service_fee_pct))

    def _migracao(self):
        from django.db.migrations.recorder import MigrationRecorder
        self._titulo('migração')
        aplicada = MigrationRecorder.Migration.objects.filter(
            app=MIGRACAO[0], name=MIGRACAO[1]).exists()
        # Em produção ela chega no deploy; local já deve estar.
        self._linha(f'{MIGRACAO[1][:24]}… aplicada',
                    'sim (ou vem no deploy)', 'sim' if aplicada else 'NÃO',
                    ok=True)
        if not aplicada:
            self.w(self.st.WARNING(
                '            ⚠ ainda não aplicada — ela vem junto com o push. '
                'Sem ela o\n              criar_lotes_legados_eminer falha na '
                'CheckConstraint de origem.'))

    def _contadores(self, empresa):
        from vendas.models import DocSequence
        self._titulo('contadores de documento')
        for kind, esperado in SEQ_ESPERADA.items():
            seq = DocSequence.objects.filter(company=empresa,
                                             kind=kind).first()
            atual = seq.last_number if seq else 0
            self._linha(f'DocSequence {kind!r}', esperado, atual)
        if any(p.startswith('DocSequence') for p in self.problemas):
            self.w(self.st.WARNING(
                "            ⚠ é ESTE o risco que motivou o script: com o "
                "contador de 'so'\n              diferente de 8, os legados "
                "nascem com outro número e o\n              "
                "sincronizar_valoracao / corrigir_recebimento / datar_despacho"
                "\n              morrem procurando SO/009, SO/010 e SO/011."))

    def _lotes(self):
        from estoque.models import Lot
        self._titulo('lotes')
        lotes = {l.number: l for l in Lot.objects.all()}
        self._linha('conjunto de números',
                    sorted(LOTES_ESPERADOS), sorted(lotes))
        abertos = {n for n, l in lotes.items() if l.status == 'open'}
        self._linha('abertos', sorted(LOTES_ABERTOS), sorted(abertos))
        colisao = sorted(LOTES_A_CRIAR & set(lotes))
        self._linha('números 1, 2 e 4 livres', [], colisao)
        if colisao:
            self.w(self.st.WARNING(
                '            ⚠ criar_lotes_legados_eminer criaria em cima '
                'destes.'))

    def _ordens(self):
        from vendas.models import SalesOrder
        self._titulo('ordens de venda')
        por_lote = {}
        for so in SalesOrder.objects.select_related('lot'):
            por_lote.setdefault(so.lot.number, []).append((so.number,
                                                           so.status))
        for lote, esperado in sorted(ORDENS_ESPERADAS.items()):
            self._linha(f'lote {lote}', sorted(esperado),
                        sorted(por_lote.get(lote, [])))
        extras = sorted(set(por_lote) - set(ORDENS_ESPERADAS))
        self._linha('lotes com ordem fora da lista', [], extras)

    def _dinheiro(self):
        from vendas.models import Invoice, Payment, Payout
        self._titulo('fatura, pagamento e repasse')
        faturas = sorted((i.code, i.status) for i in Invoice.objects.all())
        self._linha('faturas', [('INV/001/08/26', 'open')], faturas)
        self._linha('pagamentos', 0, Payment.objects.count())
        self._linha('repasses', 0, Payout.objects.count())

    def _valoracoes(self):
        from pricing.models import LotPricing
        self._titulo('valorações congeladas (informativo)')
        por_lote = {}
        for lp in LotPricing.objects.select_related('lot').order_by('created_at'):
            por_lote.setdefault(lp.lot.number, []).append(str(lp.total_mid))
        for lote in sorted(por_lote):
            self.w(f'            lote {lote:<3} mid: '
                   f'{", ".join(por_lote[lote])}')
        sem = sorted(LOTES_ESPERADOS - set(por_lote))
        self.w(f'            sem valoração: {sem}')

    def _congelamento_do_007(self, empresa):
        """O que o `despachar_lote007_eminer` PRODUZIRIA, sem gravar nada.

        Replica a aritmética do `services.confirm()` — preço vivo do grid,
        taxa travada do lote, arredondamento POR UNIDADE — para responder a
        pergunta que só o banco alvo responde: a grade de preços daqui dá o
        mesmo número de onde os valores esperados vieram?
        """
        from vendas.models import SalesOrder
        from vendas.services import live_quotes
        self._titulo('congelamento do LOT/007 (simulado, nada grava)')

        so = next((x for x in SalesOrder.objects.select_related('lot')
                   if x.lot.number == LOTE_007 and x.status == 'draft'), None)
        if so is None:
            self.w('            nenhuma ordem em rascunho no lote '
                   f'{LOTE_007} — nada a simular.')
            self.w('            (se ela já estiver confirmada, o comando de '
                   'despacho não faz nada)')
            return

        # ⚠ platform_scope: comprador/lista/preço são linhas de PLATAFORMA sob
        #   RLS. Sem o GUC a leitura volta VAZIA e a simulação diria "sem
        #   preço" para um grid que está inteiro.
        with platform_scope():
            pares = list(live_quotes(so))
        rate = so.lot.fx_rate
        pendentes = [l for l, q in pares if q.status != 'PRICED']
        rmb = sum((q.value_rmb() * l.quantity for l, q in pares
                   if q.status == 'PRICED'), D('0.00'))
        usd = sum(((q.value_rmb() * rate).quantize(CENT, ROUND_HALF_UP)
                   * l.quantity for l, q in pares if q.status == 'PRICED'),
                  D('0.00')) if rate else None

        self._linha('taxa travada no lote', str(CONGELAMENTO_ESPERADO['fx']),
                    str(rate))
        self._linha('linhas sem preço no grid', 0, len(pendentes))
        self._linha('¥ que sairia', str(CONGELAMENTO_ESPERADO['rmb']),
                    str(rmb))
        self._linha('US$ que sairia', str(CONGELAMENTO_ESPERADO['usd']),
                    str(usd))
        if pendentes:
            self.w(self.st.WARNING(
                '            ⚠ o eMMC é o único tipo cujo preço depende da '
                'ORIGEM do lote,\n              e o LOT/007 é PCB. Grade '
                'incompleta aí trava o congelamento —\n              o comando '
                'aborta em vez de gravar torto, mas não avança.'))
