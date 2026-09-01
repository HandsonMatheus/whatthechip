"""
Testes do `sincronizar_valoracao_eminer`.

A tela de ESTOQUE lê um snapshot `LotPricing` congelado no fechamento; a tela do
COMPRADOR lê a venda. Depois da reconciliação as duas discordavam: "—" nos
lotes 1–4 e o valor antigo nos lotes 5 e 6. Este comando as reconcilia
APPENDANDO um snapshot novo, sem apagar o histórico.
"""

import os
import tempfile
from decimal import Decimal as D
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from estoque.models import Lot
from pricing.models import Buyer, LotPricing
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import DocSequence, SEQ_SO, SalesOrder

User = get_user_model()
CMD = 'pricing.management.commands.sincronizar_valoracao_eminer'
_REVERT = os.path.join(tempfile.mkdtemp(prefix='valor-'),
                       'sincronizar_valoracao_eminer_revert.json')


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_valor', password='x')
        with company_scope(self.empresa.id):
            self.lot = Lot.all_companies.create(
                company=self.empresa, number=7, description='x',
                status='closed', operator=self.op, origin='phone')
            self.so = SalesOrder(lot=self.lot, buyer=self.buyer,
                                 status='confirmed', fx_usd_rate=D('0.15'),
                                 total_rmb=D('200.00'), total_usd=D('30.00'),
                                 number=DocSequence.next_number(self.empresa, SEQ_SO))
            self.so.save()
        self.codigo = self.so.code

    def _rodar(self, *args, ordens=None):
        out = StringIO()
        with patch(f'{CMD}.ORDENS', ordens or (self.codigo,)), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('sincronizar_valoracao_eminer', *args,
                         stdout=out, stderr=out)
        return out.getvalue()

    def _snapshot(self):
        with company_scope(self.empresa.id):
            return (LotPricing.objects.filter(lot=self.lot)
                    .order_by('-created_at').first())


class SincronizaTests(_Cenario):

    def test_dry_run_nao_grava(self):
        saida = self._rodar()
        self.assertIsNone(self._snapshot())
        self.assertIn('DRY-RUN', saida)

    def test_congela_a_valoracao_igual_a_venda(self):
        self._rodar('--commit')
        lp = self._snapshot()
        self.assertEqual(lp.total_mid, D('30.00'))
        self.assertEqual(lp.total_low, D('30.00'))
        self.assertEqual(lp.total_high, D('30.00'),
                         'total negociado não tem faixa: baixo=médio=alto')
        self.assertEqual(lp.buyer, self.buyer)

    def test_NAO_apaga_o_snapshot_antigo(self):
        """O modelo guarda histórico; a tela lê o mais recente."""
        with company_scope(self.empresa.id):
            velho = LotPricing.all_companies.create(
                lot=self.lot, buyer=self.buyer, company=self.empresa,
                total_low=D('99'), total_mid=D('99'), total_high=D('99'),
                priced_units=0, total_units=0, priced_lines=0, total_lines=0,
                # `lines` não aceita vazio (full_clean no save do modelo) — o
                # snapshot sempre carrega a auditoria de como foi calculado.
                lines=[{'fonte': 'snapshot antigo de teste'}])
        self._rodar('--commit')
        with company_scope(self.empresa.id):
            self.assertEqual(LotPricing.objects.filter(lot=self.lot).count(), 2)
            self.assertTrue(
                LotPricing.all_companies.filter(pk=velho.pk).exists(),
                'o snapshot antigo foi apagado — o histórico se perdeu')
        self.assertEqual(self._snapshot().total_mid, D('30.00'))

    def test_nao_faz_nada_se_ja_bate(self):
        self._rodar('--commit')
        saida = self._rodar('--commit')
        self.assertIn('já concordam', saida)
        with company_scope(self.empresa.id):
            self.assertEqual(LotPricing.objects.filter(lot=self.lot).count(), 1,
                             'rodar duas vezes empilhou snapshot igual')

    def test_a_auditoria_registra_de_onde_veio(self):
        self._rodar('--commit')
        linhas = self._snapshot().lines
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]['ordem'], self.codigo)
        self.assertIn('reconciliacao', linhas[0]['fonte'])

    def test_recusa_ordem_que_nao_existe(self):
        with self.assertRaisesMessage(CommandError, 'não encontrada'):
            self._rodar(ordens=('SO/999/01/26',))

    def test_nao_toca_em_lote_fora_da_lista(self):
        with company_scope(self.empresa.id):
            outro = Lot.all_companies.create(
                company=self.empresa, number=8, description='fora',
                status='closed', operator=self.op, origin='pcb')
        self._rodar('--commit')
        with company_scope(self.empresa.id):
            self.assertFalse(LotPricing.objects.filter(lot=outro).exists())


class RevertValoracaoTests(_Cenario):

    def test_revert_remove_so_o_que_criou(self):
        with company_scope(self.empresa.id):
            velho = LotPricing.all_companies.create(
                lot=self.lot, buyer=self.buyer, company=self.empresa,
                total_low=D('99'), total_mid=D('99'), total_high=D('99'),
                priced_units=0, total_units=0, priced_lines=0, total_lines=0,
                # `lines` não aceita vazio (full_clean no save do modelo) — o
                # snapshot sempre carrega a auditoria de como foi calculado.
                lines=[{'fonte': 'snapshot antigo de teste'}])
        self._rodar('--commit')
        self._rodar('--revert')
        with company_scope(self.empresa.id):
            self.assertEqual(LotPricing.objects.filter(lot=self.lot).count(), 1)
            self.assertEqual(self._snapshot().pk, velho.pk)

    def test_revert_sem_nada_reclama(self):
        with self.assertRaisesMessage(CommandError, 'nada a desfazer'):
            self._rodar('--revert')


class TravaTests(TestCase):
    def test_herda_o_safe_write_command(self):
        from core.safe_command import SafeWriteCommand
        from pricing.management.commands.sincronizar_valoracao_eminer import Command
        self.assertTrue(issubclass(Command, SafeWriteCommand))
        self.assertTrue(Command.confirm_on_commit)

    def test_a_lista_real_e_explicita_e_sem_repetida(self):
        """Seis da reconciliação + LOT/008 e LOT/009, que o dono mandou
        alinhar em 2026-09-01, mais o LOT/007 quando a ordem dele deixou de
        ser rascunho na mesma madrugada. A trava não é o número em si — é que
        a lista seja EXPLÍCITA e não cresça por acidente."""
        from pricing.management.commands.sincronizar_valoracao_eminer import ORDENS
        self.assertEqual(len(ORDENS), 9)
        self.assertEqual(len(set(ORDENS)), 9, 'ordem repetida na lista')
