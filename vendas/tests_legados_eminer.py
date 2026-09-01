"""
Testes do `criar_lotes_legados_eminer` — os três envios que só existiam na
planilha e entram no sistema já quitados.

O plano de verdade fala dos lotes 1, 2 e 4 da eMiner. Aqui ele é trocado por um
de brinquedo para que o teste monte o cenário inteiro, inclusive as recusas.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal as D
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from estoque.models import InventoryEntry, Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas import alinhar_eminer_core as core
from vendas.models import (INV_PAID, Invoice, Payment, SalesOrder,
                           SalesOrderLine, Settlement)

User = get_user_model()
CMD = 'vendas.management.commands.criar_lotes_legados_eminer'

_REVERT_TESTE = os.path.join(tempfile.mkdtemp(prefix='legados-revert-'),
                             'criar_lotes_legados_eminer_revert.json')

LEGADOS_TESTE = {
    7: dict(nome='TESTE-A', origin='mixed', descricao='sem detalhe',
            unidades=100, fx=D('0.15'), total_rmb=D('200.00'),
            total_usd=D('30.00'), data=date(2026, 4, 8),
            pago_em=date(2026, 4, 8), carteira='BINANCE HANDSON',
            entradas=(), linha_k9=None, aviso='sem fatura'),
    8: dict(nome='TESTE-K9', origin='k9', descricao='nand cru',
            unidades=50, fx=D('0.15'), total_rmb=D('50.00'),
            total_usd=D('7.50'), data=date(2026, 7, 4),
            pago_em=date(2026, 7, 4), carteira='BINANCE HANDSON',
            entradas=(('K9', 50, '', 'K9', '1'),),
            linha_k9=dict(kind='k9', tier_value=D('1'), tier_unit='',
                          unit_rmb=D('1.00')),
            aviso=None),
}


def _rodar(*args, legados=None, **kw):
    out = StringIO()
    with patch(f'{CMD}.LEGADOS', legados or LEGADOS_TESTE), \
         patch(f'{CMD}.REVERT', _REVERT_TESTE):
        call_command('criar_lotes_legados_eminer', *args, stdout=out,
                     stderr=out, **kw)
    return out.getvalue()


class PlanoLegadoRealTests(TestCase):
    """Os números de verdade. Não tocam no banco."""

    def test_self_check_passa(self):
        self.assertTrue(core.self_check_legados())

    def test_os_tres_estao_no_plano_com_o_numero_do_mapa(self):
        self.assertEqual(sorted(core.LEGADOS), [1, 2, 4])
        self.assertEqual(core.LEGADOS[1]['nome'], 'CHIP-EXP012026')
        self.assertEqual(core.LEGADOS[2]['nome'], 'CHIP-EXP022026')
        self.assertEqual(core.LEGADOS[4]['nome'], 'K9')

    def test_a_taxa_dos_tres_e_015(self):
        """Provada pela aritmética da fatura do EXP02 (os 20 preços dão ¥
        inteiro a 0,15 e nenhum a 0,14) e pelo K9 (US$ 0,15/un = ¥ 1,00)."""
        for n, p in core.LEGADOS.items():
            self.assertEqual(p['fx'], D('0.15'), f'lote {n}')

    def test_o_exp02_reconstroi_a_fatura_no_centavo(self):
        p = core.LEGADOS[2]
        self.assertEqual(p['total_rmb'] * p['fx'], D('6461.4000'))
        self.assertEqual(sum(q for _a, q, _b, _c, _d in p['entradas']), 12892)
        self.assertEqual(len(p['entradas']), 20)

    def test_o_k9_e_um_yuan_por_chip(self):
        p = core.LEGADOS[4]
        self.assertEqual(p['total_rmb'] / p['unidades'], D('1'))
        self.assertEqual(p['linha_k9']['unit_rmb'], D('1.00'))

    def test_as_origens_legadas_existem_no_vocabulario(self):
        for n, p in core.LEGADOS.items():
            self.assertIn(p['origin'], dict(Lot.ORIGIN_CHOICES), f'lote {n}')

    def test_o_exp02_NAO_inventa_chave_de_preco(self):
        """A fatura traz o PN na forma curta; deduzir capacidade do preço seria
        inventar catálogo. As entradas nascem sem chave, de propósito."""
        self.assertIsNone(core.LEGADOS[2]['linha_k9'])

    def test_self_check_pega_soma_de_entrada_errada(self):
        ruim = {9: dict(core.LEGADOS[4], unidades=999)}
        with self.assertRaisesMessage(AssertionError, 'entradas somam'):
            core.self_check_legados(ruim)

    def test_self_check_pega_yuan_que_nao_da_o_dolar(self):
        ruim = {9: dict(core.LEGADOS[4], total_usd=D('999.00'))}
        with self.assertRaisesMessage(AssertionError, 'mas a mestra diz'):
            core.self_check_legados(ruim)


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='', service_fee_pct=D('10.00'))
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_legado', password='x')
        # precisa de UM lote existente: é de onde o comando herda o operador
        with company_scope(self.empresa.id):
            Lot.all_companies.create(company=self.empresa, number=39,
                                     description='existente', status='closed',
                                     operator=self.op, origin='phone')


class CriacaoTests(_Cenario):

    def test_dry_run_nao_cria_nada(self):
        saida = _rodar()
        self.assertEqual(Lot.all_companies.count(), 1)
        self.assertEqual(SalesOrder.all_companies.count(), 0)
        self.assertIn('DRY-RUN', saida)

    def test_cria_a_cadeia_inteira_quitada(self):
        _rodar('--commit')
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.count(), 3)
            for n, p in LEGADOS_TESTE.items():
                l = Lot.objects.get(number=n)
                self.assertEqual(l.status, 'closed')
                self.assertEqual(l.origin, p['origin'])
                self.assertEqual(l.closed_at.date(), p['data'])
                o = l.sales_orders.get()
                self.assertEqual(o.status, 'confirmed')
                self.assertEqual(o.buyer, self.buyer)
                self.assertEqual(o.total_usd, p['total_usd'])
                self.assertEqual(o.fx_usd_rate, p['fx'])
                i = o.invoices.get()
                self.assertEqual(i.status, INV_PAID)
                self.assertEqual(i.balance_usd, D('0.00'))
                self.assertEqual(i.fee_pct, D('10.00'))
                self.assertEqual(o.settlements.count(), 1)
                self.assertEqual(i.payments.get().paid_at, p['pago_em'])

    def test_o_codigo_leva_o_mes_do_lote_e_nao_o_de_hoje(self):
        """Documento legado datado de hoje seria mentira na tela.

        Asserta o SUFIXO e não o código inteiro: o prefixo da empresa depende
        de `Company.code`, que é vazio nas empresas de produção (anteriores à
        mudança de 2026-08-18) e gerado nas novas. O que este teste protege é a
        DATA — que tem que ser a do lote, não a de hoje."""
        _rodar('--commit')
        hoje = timezone.localdate()
        with company_scope(self.empresa.id):
            l7 = Lot.objects.get(number=7)
            self.assertTrue(l7.code.endswith('/007/04/26'), l7.code)
            self.assertNotIn(f'/{hoje:%m/%y}', l7.code.replace('/007/', '/'))
            l8 = Lot.objects.get(number=8)
            self.assertTrue(l8.code.endswith('/008/07/26'), l8.code)
            o = l8.sales_orders.get()
            self.assertTrue(o.code.endswith('/07/26'), o.code)
            self.assertTrue(o.invoices.get().code.endswith('/07/26'))

    def test_o_k9_ganha_linha_de_verdade(self):
        _rodar('--commit')
        with company_scope(self.empresa.id):
            o = Lot.objects.get(number=8).sales_orders.get()
            l = o.lines.get()
            self.assertEqual(l.kind, 'k9')
            self.assertEqual(l.quantity, 50)
            self.assertEqual(l.unit_rmb, D('1.00'))
            self.assertEqual(l.unit_rmb * l.quantity, o.total_rmb)
            self.assertEqual(o.unkeyed_units, 0)

    def test_lote_sem_detalhe_nasce_sem_entrada_e_sem_linha(self):
        _rodar('--commit')
        with company_scope(self.empresa.id):
            l = Lot.objects.get(number=7)
            self.assertEqual(l.entries.count(), 0)
            o = l.sales_orders.get()
            self.assertEqual(o.lines.count(), 0)
            self.assertEqual(o.total_usd, D('30.00'),
                             'o valor tem que viver no cabeçalho')

    def test_entrada_sem_chave_de_preco_vira_unkeyed_units(self):
        """O EXP02 real: 20 part numbers, nenhuma chave. A ordem tem que dizer
        quantas unidades ficaram fora da conta, senão a tela mente."""
        legados = {7: dict(LEGADOS_TESTE[7], unidades=12,
                           entradas=(('AAA', 5, 'Samsung', 'DDR3', '3'),
                                     ('BBB', 7, '', '', '3')))}
        _rodar('--commit', legados=legados)
        with company_scope(self.empresa.id):
            l = Lot.objects.get(number=7)
            self.assertEqual(l.entries.count(), 2)
            self.assertEqual(sum(e.quantity for e in l.entries.all()), 12)
            for e in l.entries.all():
                self.assertIsNone(e.price_tier_value)
            self.assertEqual(l.sales_orders.get().unkeyed_units, 12)

    def test_recusa_se_o_numero_ja_esta_ocupado(self):
        """Número ocupado significa que a renumeração já rodou e o mapa mudou —
        criar por cima seria pior que parar."""
        legados = {39: dict(LEGADOS_TESTE[7])}
        with self.assertRaisesMessage(CommandError, 'Já existe lote 39'):
            _rodar(legados=legados)

    def test_recusa_sem_o_comprador(self):
        Buyer.all_companies.filter(pk=self.buyer.pk).update(active=False)
        with self.assertRaisesMessage(CommandError, 'Wu Quan'):
            _rodar()

    def test_recusa_lote_fora_do_plano(self):
        with self.assertRaisesMessage(CommandError, 'fora do plano legado'):
            _rodar('--lote', '77')


class RevertLegadoTests(_Cenario):

    def test_revert_apaga_tudo_o_que_criou(self):
        _rodar('--commit')
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.count(), 3)
        _rodar('--revert')
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.count(), 1, 'sobrou lote criado')
            self.assertEqual(SalesOrder.objects.count(), 0)
            self.assertEqual(Invoice.objects.count(), 0)
            self.assertEqual(Payment.objects.count(), 0)
            self.assertEqual(Settlement.objects.count(), 0)
            self.assertEqual(SalesOrderLine.all_companies.count(), 0)
            self.assertEqual(InventoryEntry.all_companies.count(), 0)

    def test_revert_nao_toca_no_que_ja_existia(self):
        _rodar('--commit')
        _rodar('--revert')
        with company_scope(self.empresa.id):
            self.assertTrue(Lot.objects.filter(number=39).exists())

    def test_revert_sem_nada_reclama(self):
        with self.assertRaisesMessage(CommandError, 'nada a desfazer'):
            _rodar('--revert')


class TravaDeBancoTests(TestCase):
    def test_herda_o_safe_write_command(self):
        from core.safe_command import SafeWriteCommand
        from vendas.management.commands.criar_lotes_legados_eminer import Command
        self.assertTrue(issubclass(Command, SafeWriteCommand))
        self.assertTrue(Command.confirm_on_commit)
