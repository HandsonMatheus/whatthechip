# -*- coding: utf-8 -*-
"""Recalcula o US$ CONGELADO das OVs ainda abertas, pela regra de 10/09.

    O QUE ISTO CONSERTA
    ───────────────────
    Até 09/09 o dólar de uma linha era o unitário arredondado em centavos
    vezes a quantidade. ¥3 × 0,1482 = 0,4446 congelava em 0,44, e meio centavo
    por unidade, numa linha de 3.192 peças, são US$ 14,68. Na EMIN-SO-2026-0004
    inteira deu US$ 28,67 — 0,27% da fatura, sempre contra a casa.

    A regra nova multiplica primeiro e arredonda no fim, POR LINHA.

    POR QUE É OBRIGATÓRIO RODAR JUNTO COM O DEPLOY
    ─────────────────────────────────────────────
    O `total_usd` das OVs já confirmadas está gravado com a conta ANTIGA. O
    código novo calcula o RESULTADO pela conta nova. Se um subir sem o outro,
    toda venda aberta passa a mostrar RESULTADO maior que ESPERADO **sem
    recusa nenhuma** — que é exatamente o sintoma que o dono chamou de "bug
    GRAVE" em 07/09, o dólar subindo quando deveria cair. Foi um teste
    (`test_recusar_chips_FAZ_O_DOLAR_CAIR`) que apontou isso.

    O QUE ELE NÃO TOCA
    ──────────────────
    · OV com FATURA ativa. O número já foi para o cliente e pode já ter sido
      pago; mexer nele reescreveria um documento emitido.
    · OV em rascunho. Não há nada congelado ainda — ela congela certo no
      `confirm`, com o código novo.
    · O `unit_usd` da linha. Ele continua sendo `round(¥ × taxa, 2)` e virou
      EXIBIÇÃO: mostra "quanto custa um". Quem faz conta é o ¥.

    A TRAVA DE SEGURANÇA
    ────────────────────
    Antes de gravar qualquer coisa, confere linha a linha que o `unit_usd`
    gravado É `round(unit_rmb × taxa da OV, 2)`. Se não for, aquela OV tem
    dólar de OUTRA origem (importação legada, taxa histórica) e recalcular
    pelo ¥ não seria arredondamento — seria trocar o valor. Nesse caso a OV é
    PULADA e relatada, nunca corrigida no escuro.

    (Conferido no dump de produção de 31/08: 356 linhas com dólar, ZERO
    divergentes. A trava é para o caso que ainda não existe.)

    USO
    ───
        python manage.py realinhar_dolar_por_linha              # dry-run
        python manage.py realinhar_dolar_por_linha --commit
        python manage.py realinhar_dolar_por_linha --ov EMIN-SO-2026-0005
"""
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

CENT = Decimal('0.01')


class Command(SafeWriteCommand):
    help = ('Recalcula o US$ congelado das OVs abertas pela regra de 10/09 '
            '(multiplica antes de arredondar). Dry-run por padrão.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true',
                            help='GRAVA. Sem isto, só mostra o que faria.')
        parser.add_argument('--ov', default='',
                            help='Só esta OV (pelo código). Vazio = todas.')

    def handle(self, *args, **opts):
        from vendas.models import SalesOrder, STATUS_CONFIRMED
        from vendas.services import usd_da_linha

        commit, alvo = opts['commit'], (opts['ov'] or '').strip()
        empresas = list(Company.objects.all())
        if not empresas:
            raise CommandError('Nenhuma empresa no banco.')

        total_ovs = corrigidas = puladas = 0
        delta_geral = Decimal('0.00')

        for empresa in empresas:
            with company_scope(empresa.id):
                qs = (SalesOrder.objects
                      .filter(status=STATUS_CONFIRMED)
                      .prefetch_related('lines', 'invoices')
                      .order_by('number'))
                if alvo:
                    # ⚠ `code` é PROPRIEDADE (lê o `code_str` congelado), não
                    #   coluna — filtrar por `number=` casaria com o número
                    #   interno e não com o EMIN-SO-... que o dono digita. São
                    #   poucas OVs abertas; filtrar em Python é honesto aqui.
                    qs = [o for o in qs if o.code == alvo or str(o.number) == alvo]
                for so in qs:
                    # Fatura ativa = documento já emitido. Não se mexe.
                    if any(i.status != 'cancelled' for i in so.invoices.all()):
                        continue
                    total_ovs += 1
                    r = self._uma(so, usd_da_linha)
                    if r is None:
                        puladas += 1
                        continue
                    novo_total, delta, linhas_conferidas = r
                    if delta == 0:
                        continue
                    corrigidas += 1
                    delta_geral += delta
                    self.stdout.write(
                        '  %-22s %4d linhas · US$ %10s → %10s  (%+.2f)'
                        % (so.code, linhas_conferidas,
                           f'{so.total_usd:,.2f}', f'{novo_total:,.2f}', delta))
                    if commit:
                        with transaction.atomic():
                            SalesOrder.all_companies.filter(pk=so.pk).update(
                                total_usd=novo_total)

        self.stdout.write('')
        self.stdout.write('  OVs abertas examinadas ...... %d' % total_ovs)
        self.stdout.write('  corrigidas .................. %d' % corrigidas)
        self.stdout.write('  PULADAS (dólar de outra origem) %d' % puladas)
        self.stdout.write('  diferença total ............. US$ %+.2f'
                          % delta_geral)
        if not commit:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '  DRY-RUN — nada foi gravado. Repita com --commit.'))

    # ── uma OV ──────────────────────────────────────────────────────────
    def _uma(self, so, usd_da_linha):
        """`(novo_total, delta, n_linhas)` — ou ``None`` se a OV for pulada."""
        taxa = so.fx_usd_rate
        if taxa is None:
            self.stderr.write(self.style.WARNING(
                '  PULADA %s: confirmada e sem taxa (não deveria existir).'
                % so.code))
            return None

        novo_total, n = Decimal('0.00'), 0
        for line in so.lines.all():
            if line.unit_rmb is None:
                continue
            # ⚠ A TRAVA: o dólar gravado tem de ser derivável da taxa DESTA
            #   OV. Se não for, ele veio de outro lugar e recalcular pelo ¥
            #   trocaria o valor em vez de corrigir o arredondamento.
            if line.unit_usd is not None:
                derivado = (line.unit_rmb * taxa).quantize(CENT, ROUND_HALF_UP)
                if derivado != line.unit_usd:
                    self.stderr.write(self.style.WARNING(
                        '  PULADA %s: linha %s tem US$ %s, mas ¥%s × %s dá '
                        '%s — dólar de outra origem, não mexo.'
                        % (so.code, line.pk, line.unit_usd, line.unit_rmb,
                           taxa, derivado)))
                    return None
            novo_total += usd_da_linha(line.unit_rmb, line.quantity, taxa)
            n += 1

        novo_total = novo_total.quantize(CENT, ROUND_HALF_UP)
        atual = so.total_usd if so.total_usd is not None else Decimal('0.00')
        return (novo_total, novo_total - atual, n)
