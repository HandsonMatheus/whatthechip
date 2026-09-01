"""
Testes do `apagar_ordem_rascunho_eminer`.

O LOT/007 fechou, o packing list saiu, a caixa viajou — e a ordem de venda
nunca foi confirmada. O dono decidiu em 2026-09-01: *"a ordem em rascunho
deleta"*.

O que estes testes travam, e é o essencial num comando que APAGA: a recusa em
tocar ordem confirmada (documento não se apaga, se cancela), a recusa quando
há fatura/acerto/nota pendurados, e a reversão que recria a ordem INTEIRA —
cabeçalho e linhas. Um `delete` sem reversão provada é um `delete` sem volta.
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

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice,
                           SalesOrder, SalesOrderLine, Settlement)

User = get_user_model()
CMD = 'vendas.management.commands.apagar_ordem_rascunho_eminer'
_DIR = tempfile.mkdtemp(prefix='rasc-')
_REVERT = os.path.join(_DIR, 'apagar_ordem_rascunho_eminer_revert.json')


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_rasc', password='x')
        with company_scope(self.empresa.id):
            self.lot = Lot.all_companies.create(
                company=self.empresa, number=7, description='x',
                status='closed', operator=self.op, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status='draft',
                unkeyed_units=20,
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            self.so.save()
            for i, (kind, tier, qtd) in enumerate(
                    [('emmc', D('8'), 363), ('emcp', D('16'), 450),
                     ('lpddr', D('4'), 78)]):
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.empresa, brand='Samsung',
                    kind=kind, gen='', tier_value=tier, tier_unit='GB',
                    quantity=qtd)
        self.codigo = self.so.code

    def _rodar(self, *args, ordem=None):
        out = StringIO()
        with patch(f'{CMD}.ORDEM', ordem or self.codigo), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('apagar_ordem_rascunho_eminer', *args,
                         stdout=out, stderr=out)
        return out.getvalue()

    def _existe(self):
        return SalesOrder.all_companies.filter(pk=self.so.pk).exists()

    def _recriada(self):
        with company_scope(self.empresa.id):
            return next((x for x in SalesOrder.objects.all()
                         if x.code == self.codigo), None)


class ApagaTests(_Cenario):

    def test_dry_run_nao_apaga(self):
        saida = self._rodar()
        self.assertIn('DRY-RUN', saida)
        self.assertTrue(self._existe())

    def test_dry_run_avisa_que_o_lote_fica_sem_ordem(self):
        self.assertIn('SEM ordem de venda', self._rodar())

    def test_apaga_a_ordem_e_as_linhas(self):
        self._rodar('--commit')
        self.assertFalse(self._existe())
        self.assertFalse(
            SalesOrderLine.all_companies.filter(order_id=self.so.pk).exists())

    def test_o_lote_continua_existindo(self):
        self._rodar('--commit')
        self.assertTrue(Lot.all_companies.filter(pk=self.lot.pk).exists())

    def test_ordem_inexistente_nao_estoura(self):
        saida = self._rodar('--commit', ordem='SO/999/01/26')
        self.assertIn('não existe', saida)
        self.assertTrue(self._existe())


class RecusaTests(_Cenario):
    """Documento não se apaga."""

    def test_recusa_ordem_confirmada(self):
        with company_scope(self.empresa.id):
            SalesOrder.all_companies.filter(pk=self.so.pk).update(
                status='confirmed', fx_usd_rate=D('0.1482'),
                total_rmb=D('79102.00'), total_usd=D('11694.91'))
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit')
        self.assertIn('CANCELAR', str(e.exception))
        self.assertTrue(self._existe())

    def test_recusa_quando_ha_fatura(self):
        with company_scope(self.empresa.id):
            Invoice(order=self.so, status='open', fx_usd_rate=D('0.15'),
                    total_rmb=D('10.00'), total_usd=D('1.50'),
                    number=DocSequence.next_number(self.empresa,
                                                   SEQ_INVOICE)).save()
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit')
        self.assertIn('fatura', str(e.exception))
        self.assertTrue(self._existe())

    def test_recusa_quando_ha_acerto(self):
        with company_scope(self.empresa.id):
            Settlement(order=self.so, notes='conferido').save()
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit')
        self.assertIn('acerto', str(e.exception))
        self.assertTrue(self._existe())


class RevertTests(_Cenario):
    """Delete sem reversão provada é delete sem volta."""

    def test_revert_recria_a_ordem_com_o_mesmo_codigo(self):
        self._rodar('--commit')
        self._rodar('--revert')
        nova = self._recriada()
        self.assertIsNotNone(nova)
        self.assertEqual(nova.code, self.codigo)

    def test_revert_recria_todas_as_linhas(self):
        self._rodar('--commit')
        self._rodar('--revert')
        nova = self._recriada()
        self.assertEqual(nova.lines.count(), 3)
        self.assertEqual(sum(l.quantity for l in nova.lines.all()), 891)

    def test_revert_preserva_as_unidades_sem_chave(self):
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertEqual(self._recriada().unkeyed_units, 20)

    def test_revert_devolve_a_data_de_criacao(self):
        antes = SalesOrder.all_companies.get(pk=self.so.pk).created_at
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertEqual(self._recriada().created_at, antes)

    def test_revert_mantem_o_rascunho_como_rascunho(self):
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertEqual(self._recriada().status, 'draft')

    def test_revert_sem_arquivo_reclama(self):
        with self.assertRaises(CommandError):
            self._rodar('--revert')
