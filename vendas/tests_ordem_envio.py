"""
Testes da ordenação da lista de compras pelo DESPACHO.

Pedido do dono em 2026-09-01: *"o adequado é a ordem que mostra lá seja a
ordem de ENVIO, ou seja, os mais novos enviados em cima e os mais velhos
embaixo"*. Antes a chave `n` era `created_at` — o instante em que o LOTE
FECHOU, um fato do vendedor. Para quem compra, a linha do tempo é a da caixa.

O que estes testes travam: a ordem, o lugar de quem ainda não despachou (topo,
não fundo) e a data que a tela mostra ao lado do código.
"""

from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import DocSequence, SEQ_SO, SalesOrder
from vendas.services import orders_for_buyer, sort_purchases

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_envio', password='x')
        self.n = 0

    def _ordem(self, enviada=None, criada_ha_dias=0):
        self.n += 1
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=self.n, description='x',
                status='closed', operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('100.00'),
                total_usd=D('15.00'), shipped_at=enviada,
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            so.save()
            if criada_ha_dias:
                SalesOrder.all_companies.filter(pk=so.pk).update(
                    created_at=timezone.now() - timedelta(days=criada_ha_dias))
        return SalesOrder.all_companies.get(pk=so.pk)


class OrdemPorEnvioTests(_Base):

    def test_o_enviado_mais_recente_vem_primeiro(self):
        junho = self._ordem(enviada=date(2026, 6, 9))
        agosto = self._ordem(enviada=date(2026, 8, 27))
        julho = self._ordem(enviada=date(2026, 7, 11))
        ordenado = sort_purchases([junho, agosto, julho], 'n', True)
        self.assertEqual([o.pk for o in ordenado],
                         [agosto.pk, julho.pk, junho.pk])

    def test_o_mais_velho_fica_embaixo(self):
        junho = self._ordem(enviada=date(2026, 6, 9))
        agosto = self._ordem(enviada=date(2026, 8, 27))
        ordenado = sort_purchases([junho, agosto], 'n', True)
        self.assertEqual(ordenado[-1].pk, junho.pk)

    def test_a_criacao_da_ordem_nao_manda_mais(self):
        """O caso do LOT/003: ordem criada em agosto para um envio de julho.
        Pela data de criação ela subiria; pela do embarque, não."""
        criada_agora_enviada_em_julho = self._ordem(enviada=date(2026, 7, 11))
        criada_antiga_enviada_em_agosto = self._ordem(
            enviada=date(2026, 8, 27), criada_ha_dias=90)
        ordenado = sort_purchases(
            [criada_agora_enviada_em_julho, criada_antiga_enviada_em_agosto],
            'n', True)
        self.assertEqual(ordenado[0].pk, criada_antiga_enviada_em_agosto.pk)


class SemDespachoTests(_Base):
    """Sem data de envio a linha se ancora na data da ORDEM.

    ⚠ A 1ª versão mandava toda ordem sem despacho para o topo. O dono
    reprovou na hora: *"é impossível que o primeiro lote de todos tenha sido
    o antipenúltimo a despachar"*. Estes testes travam a regra que substituiu
    aquela — e o caso do LOT/001 é o que reprovou a anterior."""

    def test_o_registro_legado_antigo_NAO_sobe_ao_topo(self):
        """LOT/001: envio de abril, sem despacho registrado. É o mais VELHO
        da operação — tem de ficar embaixo, não em cima."""
        legado_de_abril = self._ordem(criada_ha_dias=145)
        recente = self._ordem(enviada=date(2026, 8, 27))
        ordenado = sort_purchases([legado_de_abril, recente], 'n', True)
        self.assertEqual(ordenado[-1].pk, legado_de_abril.pk)

    def test_lote_fechado_hoje_e_nao_despachado_fica_no_topo(self):
        """A mesma regra, o outro caso: aqui 'sem despacho' significa mesmo
        'ainda não saiu', e a data da ordem já diz isso sozinha."""
        antigo = self._ordem(enviada=date(2026, 7, 11))
        fechado_hoje = self._ordem()
        ordenado = sort_purchases([antigo, fechado_hoje], 'n', True)
        self.assertEqual(ordenado[0].pk, fechado_hoje.pk)

    def test_pendente_se_intercala_com_os_despachados(self):
        """Não existe grupo de pendentes: cada linha entra no seu lugar."""
        agosto = self._ordem(enviada=date(2026, 8, 27))
        pendente_de_julho = self._ordem(criada_ha_dias=52)   # ~11/07
        junho = self._ordem(enviada=date(2026, 6, 9))
        ordenado = sort_purchases([junho, agosto, pendente_de_julho], 'n', True)
        self.assertEqual([o.pk for o in ordenado],
                         [agosto.pk, pendente_de_julho.pk, junho.pk])

    def test_a_chave_nunca_devolve_none(self):
        from vendas.services import data_de_despacho
        self.assertIsNotNone(data_de_despacho(self._ordem()))


class ListaJaNasceOrdenadaTests(_Base):
    """`orders_for_buyer` e a tela têm de concordar — export e testes leem a
    função direto."""

    def test_a_funcao_devolve_na_ordem_do_despacho(self):
        self._ordem(enviada=date(2026, 6, 9))
        agosto = self._ordem(enviada=date(2026, 8, 27))
        self._ordem(enviada=date(2026, 7, 11))
        self.assertEqual(orders_for_buyer(self.buyer)[0].pk, agosto.pk)


class DataNaTelaTests(_Base):
    """A data ao lado do código é a do embarque, não a da criação."""

    def _html(self):
        from django.template.loader import render_to_string
        pedidos = orders_for_buyer(self.buyer)
        return render_to_string('vendas/partner_compras.html', {
            'linhas': pedidos, 'ordens': pedidos,
            'f': {'qs': '', 'sort': 'n', 'dir': 'desc'},
        })

    def test_mostra_a_data_de_envio(self):
        self._ordem(enviada=date(2026, 7, 11), criada_ha_dias=1)
        self.assertIn('11/07', self._html())

    def test_sem_envio_mostra_travessao(self):
        """⚠ Não dá para asserir a AUSÊNCIA da data de criação buscando
        '01/09' na página inteira: o código do lote (LOT/EMI/001/09/26) contém
        essa sequência. A asserção é a CÉLULA."""
        so = self._ordem()
        html = self._html()
        self.assertIn(so.code, html)
        self.assertIn('<span class="when">—</span>', html)

    def test_a_celula_nao_traz_a_data_de_criacao(self):
        criada = self._ordem(enviada=date(2026, 7, 11), criada_ha_dias=40)
        html = self._html()
        celula = f'<span class="when">{criada.created_at:%d/%m}</span>'
        self.assertNotIn(celula, html)
