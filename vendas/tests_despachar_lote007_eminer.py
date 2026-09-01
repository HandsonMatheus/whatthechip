"""
Testes do `despachar_lote007_eminer`.

O LOT/007 viajou em 18/08 e a ordem ficou em rascunho. O dono corrigiu pela
TELA em 01/09 às 03:27; este comando existe para produção receber o mesmo por
caminho auditável, já que ação de tela não se reproduz sozinha.

O teste que mais importa aqui é o do PORTÃO: o `confirm()` lê o grid VIVO do
comprador, então rodar isto contra um banco cuja tabela de preços seja outra
congelaria a venda num valor diferente — em silêncio. O comando compara com o
esperado dentro da transação e desfaz tudo se divergir; `PortaoTests` prova
que ele desfaz mesmo.
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
from tenancy.models import Membership
from tenancy.scope import company_scope, set_current_company
from vendas import services
from vendas.models import SalesOrder
from vendas.tests import _entries, _setup

User = get_user_model()
CMD = 'vendas.management.commands.despachar_lote007_eminer'
_DIR = tempfile.mkdtemp(prefix='desp7-')
_REVERT = os.path.join(_DIR, 'despachar_lote007_eminer_revert.json')

#: 5 eMMC × ¥15 = ¥75; em US$, arredondando POR UNIDADE a 0,1482:
#: 15 × 0,1482 = 2,223 → 2,22 · 5 × 2,22 = 11,10.
#: ⚠ `com_emcp=False` de propósito: o eMCP do fixture entra com
#: `price_gen='LPDDR4X'` e a linha do grid é genérica (`gen=''`), então ele
#: fica SEM cotação e o `confirm()` recusa a ordem inteira — o mesmo motivo
#: pelo qual o `VendasGateTests` também o desliga.
FX = D('0.1482')
ESPERADO = dict(fx=FX, total_rmb=D('75.00'), total_usd=D('11.10'))
DESPACHO = dict(carrier='DHL', tracking='2486463965', data=date(2026, 8, 18))


class _Cenario(TestCase):
    def setUp(self):
        self.empresa, self.buyer, self.marca = _setup('vd-desp7')
        self.user = User.objects.create_user('raphaelbastos', password='x')
        Membership.objects.create(user=self.user, company=self.empresa,
                                  role='admin')
        set_current_company(self.empresa.pk)
        self.addCleanup(set_current_company, None)
        # ⚠ origem 'phone', não 'pcb': a linha de eMMC do fixture é
        # `origin='phone'` e o eMMC é o ÚNICO tipo cujo preço depende da
        # procedência do lote (`pricing::_row_origin`). Com 'pcb' não há
        # cotação, o `confirm()` recusa a ordem inteira e o teste mediria
        # outra coisa. O LOT/007 real é PCB; aqui o que se testa é o
        # comando, não a grade.
        self.lot = Lot.open_for_company(self.empresa, self.user, 'sete',
                                        origin='phone')
        _entries(self.lot, self.marca, com_emcp=False)
        # A taxa TRAVADA no fechamento é o que a confirmação herda.
        Lot.all_companies.filter(pk=self.lot.pk).update(fx_rate=FX)
        self.lot.refresh_from_db()
        self.so = services.create_draft_for_lot(self.lot, self.user)
        self.codigo = self.so.code

    def _rodar(self, *args, esperado=None, ordem=None):
        out = StringIO()
        with patch(f'{CMD}.ORDEM', ordem or self.codigo), \
             patch(f'{CMD}.DESPACHO', DESPACHO), \
             patch(f'{CMD}.ESPERADO', esperado or ESPERADO), \
             patch(f'{CMD}.EMPRESA_SLUG', self.empresa.slug), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('despachar_lote007_eminer', *args,
                         stdout=out, stderr=out)
        return out.getvalue()

    def _ordem(self):
        return SalesOrder.all_companies.get(pk=self.so.pk)


class DespachoTests(_Cenario):

    def test_dry_run_nao_grava(self):
        saida = self._rodar()
        self.assertIn('DRY-RUN', saida)
        self.assertEqual(self._ordem().status, 'draft')
        self.assertIsNone(self._ordem().shipped_at)

    def test_registra_transportadora_rastreio_e_data(self):
        self._rodar('--commit')
        so = self._ordem()
        self.assertEqual(so.carrier, 'DHL')
        self.assertEqual(so.tracking, '2486463965')
        self.assertEqual(so.shipped_at, date(2026, 8, 18))

    def test_o_despacho_congela_a_venda(self):
        """É o despacho que confirma — não um passo separado."""
        self._rodar('--commit')
        self.assertEqual(self._ordem().status, 'confirmed')

    def test_congela_nos_valores_esperados(self):
        self._rodar('--commit')
        so = self._ordem()
        self.assertEqual(so.fx_usd_rate, ESPERADO['fx'])
        self.assertEqual(so.total_rmb, ESPERADO['total_rmb'])
        self.assertEqual(so.total_usd, ESPERADO['total_usd'])

    def test_as_linhas_ganham_preco_unitario(self):
        self._rodar('--commit')
        precos = [l.unit_rmb for l in self._ordem().lines.all()]
        self.assertTrue(all(p is not None for p in precos))

    def test_user_assina_o_despacho(self):
        self._rodar('--commit', '--user', 'raphaelbastos')
        self.assertEqual(self._ordem().shipped_by_id, self.user.pk)

    def test_user_inexistente_reclama(self):
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit', '--user', 'ninguem')
        self.assertIn('não existe', str(e.exception))


class PortaoTests(_Cenario):
    """O grid do banco pode não ser o mesmo de onde os valores vieram."""

    def test_aborta_quando_o_total_nao_bate(self):
        outro = dict(ESPERADO, total_usd=D('99.99'))
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit', esperado=outro)
        self.assertIn('não bateu', str(e.exception))

    def test_e_NADA_fica_gravado(self):
        """Aborta dentro da transação: nem despacho, nem congelamento."""
        outro = dict(ESPERADO, total_usd=D('99.99'))
        with self.assertRaises(CommandError):
            self._rodar('--commit', esperado=outro)
        so = self._ordem()
        self.assertEqual(so.status, 'draft')
        self.assertIsNone(so.shipped_at)
        self.assertIsNone(so.total_usd)
        self.assertTrue(all(l.unit_rmb is None for l in so.lines.all()))

    def test_a_mensagem_diz_qual_numero_divergiu(self):
        outro = dict(ESPERADO, total_rmb=D('1.00'))
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit', esperado=outro)
        self.assertIn('75.00', str(e.exception), 'diz o valor que SAIU')
        self.assertIn('1.00', str(e.exception), 'e o que se esperava')


class IdempotenciaTests(_Cenario):

    def test_rodar_duas_vezes_nao_faz_nada(self):
        self._rodar('--commit')
        saida = self._rodar('--commit')
        self.assertIn('Nada a fazer', saida)

    def test_recusa_venda_congelada_com_outro_valor(self):
        """Não se sobrescreve venda já congelada."""
        self._rodar('--commit')
        SalesOrder.all_companies.filter(pk=self.so.pk).update(
            total_usd=D('999.00'))
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit')
        self.assertIn('não sobrescrevo venda congelada'.lower(),
                      str(e.exception).lower())


class RevertTests(_Cenario):

    def test_revert_devolve_ao_rascunho(self):
        self._rodar('--commit')
        self._rodar('--revert')
        so = self._ordem()
        self.assertEqual(so.status, 'draft')
        self.assertIsNone(so.total_usd)
        self.assertIsNone(so.shipped_at)

    def test_revert_descongela_as_linhas(self):
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertTrue(
            all(l.unit_rmb is None for l in self._ordem().lines.all()))

    def test_revert_sem_arquivo_reclama(self):
        with self.assertRaises(CommandError):
            self._rodar('--revert')
