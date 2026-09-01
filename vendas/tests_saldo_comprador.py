"""
Testes do saldo na lista do comprador — o bug de produção de 2026-09-01.

A tela mostrava `PAGO` e `falta US$ 6.251,00` na MESMA linha. O status é
coluna já carregada; o saldo era `Invoice.balance_usd`, uma property que
dispara um `aggregate` no momento em que alguém lê — e quem lê é o template,
já FORA do `company_scope` que o `orders_for_buyer` abre por empresa. Sem
escopo não há GUC, o RLS devolve zero pagamento em silêncio, e o saldo vira o
total inteiro.

⚠ ESTES TESTES NÃO CONSEGUEM REPRODUZIR O RLS: a suíte roda em SQLite, que
  não tem row-level security. Nem adianta tentar — em SQLite o bug é
  invisível, exatamente como era invisível no localhost do dono, cuja conexão
  Postgres é superusuária e ignora RLS mesmo com FORCE.

  O que dá para travar, e é o que importa, é a PROPRIEDADE que torna o valor
  imune a escopo: depois que `orders_for_buyer` devolve, ler o saldo não pode
  tocar o banco. Se alguém devolver a property preguiçosa para o template, o
  `assertNumQueries(0)` acusa.
"""

from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice, Payment,
                           SalesOrder)
from vendas.services import orders_for_buyer

User = get_user_model()


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_saldo', password='x')

    def _venda(self, numero, total, pago=None):
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=numero, description='x',
                status='closed', operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('1000.00'),
                total_usd=total, shipped_at='2026-07-11',
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            so.save()
            inv = Invoice(
                order=so, status='paid' if pago == total else 'open',
                fx_usd_rate=D('0.1500'), total_rmb=D('1000.00'),
                total_usd=total,
                number=DocSequence.next_number(self.empresa, SEQ_INVOICE))
            inv.save()
            if pago:
                Payment(invoice=inv, amount_usd=pago,
                        paid_at='2026-07-11', reference='TRONLINK').save()
        return so


class SaldoMaterializadoTests(_Cenario):
    """A garantia real: o saldo já vem calculado, não é consulta preguiçosa."""

    def test_ler_o_saldo_depois_NAO_toca_o_banco(self):
        """É esta a propriedade que sobrevive ao RLS. Se alguém trocar de
        volta por `o.fatura.balance_usd`, este teste acusa."""
        self._venda(1, D('6251.00'), pago=D('6251.00'))
        pedidos = orders_for_buyer(self.buyer)
        with self.assertNumQueries(0):
            [o.fatura_saldo for o in pedidos]

    def test_ler_o_pago_depois_tambem_nao_toca_o_banco(self):
        self._venda(2, D('826.05'), pago=D('826.05'))
        pedidos = orders_for_buyer(self.buyer)
        with self.assertNumQueries(0):
            [o.fatura_pago for o in pedidos]

    def test_a_property_do_modelo_CONSULTA_e_por_isso_nao_serve(self):
        """Documenta o motivo do conserto: `balance_usd` toca o banco toda
        vez. Fora do escopo, esse toque volta zerado."""
        self._venda(3, D('6937.00'), pago=D('6937.00'))
        pedidos = orders_for_buyer(self.buyer)
        with self.assertNumQueries(1):
            pedidos[0].fatura.balance_usd


class ValorTests(_Cenario):

    def test_fatura_quitada_tem_saldo_zero(self):
        self._venda(4, D('6251.00'), pago=D('6251.00'))
        o = orders_for_buyer(self.buyer)[0]
        self.assertEqual(o.fatura_pago, D('6251.00'))
        self.assertEqual(o.fatura_saldo, D('0.00'))

    def test_fatura_paga_pela_metade_mostra_o_que_falta(self):
        self._venda(5, D('1000.00'), pago=D('400.00'))
        o = orders_for_buyer(self.buyer)[0]
        self.assertEqual(o.fatura_saldo, D('600.00'))

    def test_fatura_sem_pagamento_mostra_o_total(self):
        self._venda(6, D('826.05'))
        o = orders_for_buyer(self.buyer)[0]
        self.assertEqual(o.fatura_saldo, D('826.05'))

    def test_ordem_sem_fatura_nao_inventa_saldo(self):
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=7, description='x',
                status='closed', operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('1.00'),
                total_usd=D('1.00'), shipped_at='2026-07-11',
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            so.save()
        o = orders_for_buyer(self.buyer)[0]
        self.assertIsNone(o.fatura)
        self.assertIsNone(o.fatura_saldo)


class TelaTests(_Cenario):
    """A contradição que o dono viu: PAGO e "falta" na mesma linha."""

    def _html(self, pedidos):
        from django.template.loader import render_to_string
        return render_to_string('vendas/partner_compras.html', {
            'linhas': pedidos, 'ordens': pedidos,
            'f': {'qs': '', 'sort': 'n', 'dir': 'desc'},
        })

    def test_quitada_escreve_quitado_e_nunca_falta(self):
        self._venda(8, D('6251.00'), pago=D('6251.00'))
        html = self._html(orders_for_buyer(self.buyer))
        self.assertIn('quitado', html)
        self.assertNotIn('falta US$ 6251.00', html)

    def test_em_aberto_escreve_o_que_falta(self):
        self._venda(9, D('1000.00'), pago=D('400.00'))
        self.assertIn('600.00', self._html(orders_for_buyer(self.buyer)))
