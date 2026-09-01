"""
Testes de `order_units` — a coluna "Chips" das duas listas.

Bug de 2026-09-01 (dono, olhando a tela do comprador): "lote 2 nao ta
mostrando a quantidade de chips pro COMPRADOR na tela de compras, na tabela".

A conta somava só as LINHAS da ordem, e linha só existe onde há chave de
preço. No registro legado nenhuma unidade tem chave — tudo mora em
`unkeyed_units` —, então 12.892 chips viravam "0". Nos lotes normais o erro
era pequeno e silencioso, que é pior: 10.556 no lugar de 10.645.

A regra travada aqui: **linhas + sem-chave**, que é a mesma conta do packing
list e a que bate com `Lot.total_qty`.
"""

from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase

from estoque.models import InventoryEntry, Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import DocSequence, SEQ_SO, SalesOrder, SalesOrderLine
from vendas.services import annotate_sales, order_units, orders_for_buyer

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_cont', password='x')

    def _lote(self, numero, origin='phone'):
        return Lot.all_companies.create(
            company=self.empresa, number=numero, description=f'lote {numero}',
            status='closed', operator=self.op, origin=origin)

    def _ordem(self, lot, unkeyed=0, total_usd=D('100.00')):
        so = SalesOrder(
            lot=lot, buyer=self.buyer, status='confirmed',
            fx_usd_rate=D('0.1500'), total_rmb=D('666.67'),
            total_usd=total_usd, unkeyed_units=unkeyed,
            number=DocSequence.next_number(self.empresa, SEQ_SO))
        so.save()
        return so

    def _linha(self, so, qtd, kind='emmc', tier=D('8')):
        return SalesOrderLine.all_companies.create(
            order=so, company=self.empresa, brand='Samsung', kind=kind,
            gen='', tier_value=tier, tier_unit='GB', quantity=qtd,
            unit_rmb=D('10.00'), unit_usd=D('1.50'))


class OrderUnitsTests(_Base):

    def test_soma_linhas_mais_sem_chave(self):
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(39), unkeyed=89)
            self._linha(so, 10556)
            self.assertEqual(order_units(so), 10645)

    def test_registro_legado_sem_nenhuma_linha(self):
        """O caso que o dono viu: 12.892 chips, zero linhas — e a tela dizia 0."""
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(2, origin='pcb'), unkeyed=12892)
            self.assertEqual(so.lines.count(), 0)
            self.assertEqual(order_units(so), 12892)

    def test_ordem_sem_sem_chave_continua_igual(self):
        """Quem já estava certo não pode mudar de número."""
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(8), unkeyed=0)
            self._linha(so, 10000)
            self.assertEqual(order_units(so), 10000)

    def test_unkeyed_nulo_nao_quebra(self):
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(4))
            SalesOrder.all_companies.filter(pk=so.pk).update(unkeyed_units=0)
            self._linha(so, 5507)
            so.refresh_from_db()
            self.assertEqual(order_units(so), 5507)

    def test_ordem_vazia_da_zero(self):
        with company_scope(self.empresa.id):
            self.assertEqual(order_units(self._ordem(self._lote(50))), 0)


class BateComOLoteTests(_Base):
    """A conta da lista tem de fechar com o lote físico — foi assim que o erro
    ficou invisível por tanto tempo, e é o que trava daqui em diante."""

    def test_o_total_da_ordem_bate_com_total_qty_do_lote(self):
        with company_scope(self.empresa.id):
            lot = self._lote(41)
            InventoryEntry.all_companies.create(
                lot=lot, company=self.empresa, part_number='K4U6E3S4AB',
                quantity=4595, brand='Samsung', chip_type='LPDDR4',
                price_tier_value=D('4'), price_tier_unit='GB')
            InventoryEntry.all_companies.create(
                lot=lot, company=self.empresa, part_number='DESCONHECIDO1',
                quantity=68, brand='', chip_type='')
            so = self._ordem(lot, unkeyed=68)
            self._linha(so, 4595, kind='lpddr', tier=D('4'))
            self.assertEqual(order_units(so), lot.total_qty)
            self.assertEqual(order_units(so), 4663)


class ListaDoClienteTests(_Base):
    """`annotate_sales` — a coluna Chips da tela de vendas."""

    def test_annotate_sales_usa_o_total(self):
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(2, origin='pcb'), unkeyed=12892)
            annotate_sales([so])
            self.assertEqual(so.units, 12892)

    def test_annotate_sales_soma_os_dois_lados(self):
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(39), unkeyed=89)
            self._linha(so, 10556)
            annotate_sales([so])
            self.assertEqual(so.units, 10645)


class ListaDoCompradorTests(_Base):
    """`orders_for_buyer` — a coluna Chips da tela de compras (a que o dono
    estava olhando quando achou o bug)."""

    def test_o_registro_legado_mostra_a_quantidade(self):
        with company_scope(self.empresa.id):
            lot = self._lote(2, origin='pcb')
            self._ordem(lot, unkeyed=12892)
        pedidos = orders_for_buyer(self.buyer)
        self.assertEqual([o.units for o in pedidos], [12892],
                         'era isto que aparecia como 0 na tabela do comprador')

    def test_a_ordem_normal_ganha_as_unidades_sem_chave(self):
        with company_scope(self.empresa.id):
            so = self._ordem(self._lote(39), unkeyed=89)
            self._linha(so, 10556)
        pedidos = orders_for_buyer(self.buyer)
        self.assertEqual([o.units for o in pedidos], [10645])
