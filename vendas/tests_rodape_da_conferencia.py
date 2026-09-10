# -*- coding: utf-8 -*-
"""O RODAPÉ da tabela tem de dizer o mesmo que o cartão do topo.

Dono, 2026-09-10, olhando a EMIN-SO-2026-0004 fechada:

> "o resultado final no hero diz um numero, enquanto na tabela diz outro, o
> correto é o do hero que foi calculado de acordo com as perdas desta compra,
> o do bottom da tabela ta mostrando o cru"

O rodapé nascia CRAVADO no template como "nada recusado ainda" — recusados 0,
aprovados = enviados, resultado = o total congelado da OV — e quem o corrigia
era o JavaScript, enquanto o comprador digitava.

⚠ E o JavaScript não roda quando não há o que digitar. Com o resultado FECHADO
  a tela perde os campos de recusa, o `recalcular()` não tem o que percorrer, e
  o rodapé ficava congelado na mentira: 0 recusados numa compra com milhares de
  recusas, e o ESPERADO repetido na coluna do RESULTADO.
"""
import re
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import services
from vendas.models import (DocSequence, SEQ_SO, SalesOrder, SalesOrderLine,
                           STATUS_CONFIRMED)

User = get_user_model()


def _celula(html, ident):
    """O TEXTO da célula `id=...` do rodapé, sem o rótulo do `<small>`."""
    m = re.search(r'id="%s"[^>]*>(.*?)</td>' % ident, html, re.S)
    if m is None:
        return None
    txt = re.sub(r'<small>.*?</small>', '', m.group(1), flags=re.S)
    return re.sub(r'<[^>]+>', '', txt).strip()


class _Base(TestCase):
    U, FX, Q = D('3.00'), D('0.1481'), 1000

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=7, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=self.FX, total_rmb=self.U * self.Q,
                total_usd=(self.U * self.Q * self.FX).quantize(D('0.01')),
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            self.linha = SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Micron', kind='ddr3',
                gen='', tier_value=D('2'), tier_unit='GB', quantity=self.Q,
                unit_rmb=self.U, unit_usd=D('0.44'))
        self.client.force_login(self.parceiro)

    def _html(self):
        return self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()


class ComOResultadoFECHADOTests(_Base):
    """O caso do dono: sem campos na tela, o JavaScript não conserta nada."""

    def setUp(self):
        super().setUp()
        with company_scope(self.emp.id):
            services.settle_and_invoice(self.so, {self.linha.pk: (400, None)},
                                        self.parceiro)

    def test_o_rodape_mostra_as_RECUSAS_e_nao_zero(self):
        self.assertEqual(_celula(self._html(), 't-rej'), '400')

    def test_o_rodape_mostra_os_APROVADOS_e_nao_os_enviados(self):
        self.assertEqual(_celula(self._html(), 't-ace'), '600')

    def test_o_RESULTADO_do_rodape_nao_e_o_esperado(self):
        """¥3 × 600 = 1.800, e não os ¥3.000 congelados da OV. Era aqui que a
        tabela dizia um número e o cartão do topo dizia outro."""
        self.assertEqual(_celula(self._html(), 't-pagar-rmb'), '¥ 1800.00')

    def test_o_rodape_bate_com_o_CARTAO_do_topo(self):
        """A invariante que o dono cobrou: os dois lêem a mesma compra."""
        with company_scope(self.emp.id):
            r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        rodape = _celula(r.content.decode(), 't-pagar-rmb')
        self.assertEqual(rodape, '¥ %s' % r.context['final_rmb'])

    def test_o_rodape_bate_com_a_soma_das_FAIXAS(self):
        """Linha → faixa → rodapé: uma cadeia só. Se o rodapé tivesse conta
        própria, ele poderia divergir das faixas sem ninguém notar."""
        with company_scope(self.emp.id):
            r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        grupos = r.context['grupos']
        self.assertEqual(r.context['total_pago_rmb'],
                         sum(g['pago_rmb'] for g in grupos))
        self.assertEqual(r.context['total_rej'],
                         sum(g['rejected'] for g in grupos))
        self.assertEqual(r.context['total_ace'],
                         sum(g['accepted'] for g in grupos))


class ComAConferenciaABERTATests(_Base):
    """O caso que já funcionava — não pode ter piorado."""

    def test_sem_rascunho_o_rodape_abre_com_a_compra_cheia(self):
        html = self._html()
        self.assertEqual(_celula(html, 't-rej'), '0')
        self.assertEqual(_celula(html, 't-ace'), str(self.Q))
        self.assertEqual(_celula(html, 't-pagar-rmb'), '¥ 3000.00')

    def test_COM_rascunho_salvo_o_rodape_ja_abre_certo(self):
        """Ganho de tapa: antes o rodapé nascia com o valor cheio e só o
        JavaScript o corrigia — o número piscava a cada F5."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {self.linha.pk: 250}, self.parceiro)
        html = self._html()
        self.assertEqual(_celula(html, 't-rej'), '250')
        self.assertEqual(_celula(html, 't-ace'), '750')
        self.assertEqual(_celula(html, 't-pagar-rmb'), '¥ 2250.00')

    def test_o_JavaScript_continua_dono_do_rodape_enquanto_ele_digita(self):
        """O servidor dá o estado INICIAL; quem manda durante a digitação
        continua sendo o `recalcular()`. Se os alvos sumirem, ele escreve no
        vazio e o rodapé para de acompanhar a tecla."""
        html = self._html()
        for ident in ('t-rej', 't-ace', 't-rejv', 't-pagar-rmb'):
            self.assertIn('id="%s"' % ident, html)
        self.assertIn("getElementById('t-pagar-rmb')", html)
