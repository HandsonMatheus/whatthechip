"""
Testes do `corrigir_recebimento_eminer`.

O painel "Pagamento" da tela da venda lê a perna WhatTheChip → CLIENTE
(`net_usd`, `paid_out_usd`, `payout_balance_usd`), enquanto a tela do
comprador e a barra de etapas leem a perna COMPRADOR → WhatTheChip
(`paid_usd` / `balance_usd`). Como nunca houve `Payout` nesta operação, toda
venda paga aparecia com "Falta US$ …" em vermelho.

A taxa de 10% é LEGÍTIMA (dono, 2026-09-01: "a taxa tem que ter em tudo
mesmo, sempre os 10%"). Metade destes testes existe justamente para travar
que o comando NÃO encosta nela — nem na fatura, nem na empresa.
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
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice, Payment,
                           Payout, SalesOrder)

User = get_user_model()
CMD = 'vendas.management.commands.corrigir_recebimento_eminer'
_DIR = tempfile.mkdtemp(prefix='receb-')
_REVERT = os.path.join(_DIR, 'corrigir_recebimento_eminer_revert.json')

#: Os números reais do LOT/001/04/26 — bruto, taxa de 10% e líquido.
BRUTO, TAXA, LIQUIDO = D('1462.48'), D('146.25'), D('1316.23')


class _Cenario(TestCase):
    """Uma venda paga pelo comprador, com a taxa de 10% congelada e nenhum
    repasse — exatamente o estado que o dono encontrou no LOT/001."""

    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='',
                                              service_fee_pct=D('10.00'))
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_receb', password='x')
        with company_scope(self.empresa.id):
            self.lot = Lot.all_companies.create(
                company=self.empresa, number=1, description='EXP01',
                status='closed', operator=self.op, origin='mixed')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('9749.87'),
                total_usd=BRUTO,
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            self.so.save()
            self.inv = Invoice(
                order=self.so, status='paid', fx_usd_rate=D('0.1500'),
                total_rmb=D('9749.87'), total_usd=BRUTO,
                fee_pct=D('10.00'), fee_rmb=D('974.99'), fee_usd=TAXA,
                number=DocSequence.next_number(self.empresa, SEQ_INVOICE))
            self.inv.save()
            self.pag = Payment(invoice=self.inv, amount_usd=BRUTO,
                               paid_at=date(2026, 4, 20),
                               reference='BINANCE HANDSON')
            self.pag.save()
        self.codigo = self.so.code

    def _rodar(self, *args, ordens=None):
        out = StringIO()
        with patch(f'{CMD}.ORDENS', ordens or (self.codigo,)), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('corrigir_recebimento_eminer', *args,
                         stdout=out, stderr=out)
        return out.getvalue()

    def _fatura(self):
        return Invoice.all_companies.get(pk=self.inv.pk)

    def _repasses(self):
        return list(Payout.all_companies.filter(invoice_id=self.inv.pk))


class DiagnosticoTests(_Cenario):
    """Antes do conserto, o estado que o dono viu na tela."""

    def test_o_comprador_ja_pagou_tudo(self):
        self.assertEqual(self._fatura().balance_usd, D('0.00'))

    def test_mas_o_painel_da_venda_mostra_o_liquido_inteiro_em_aberto(self):
        inv = self._fatura()
        self.assertEqual(inv.paid_out_usd, D('0.00'))
        self.assertEqual(inv.payout_balance_usd, LIQUIDO,
                         'é este número vermelho que o dono viu no LOT/001')


class DryRunTests(_Cenario):

    def test_dry_run_nao_grava_nada(self):
        saida = self._rodar()
        self.assertIn('DRY-RUN', saida)
        self.assertEqual(self._repasses(), [])

    def test_dry_run_mostra_a_taxa_como_retida(self):
        self.assertIn('RETIDA', self._rodar())


class CommitTests(_Cenario):

    def test_registra_um_repasse_pelo_liquido(self):
        self._rodar('--commit')
        repasses = self._repasses()
        self.assertEqual(len(repasses), 1)
        self.assertEqual(repasses[0].amount_usd, LIQUIDO,
                         'repassa o bruto MENOS a taxa, não o bruto')

    def test_o_repasse_herda_data_e_referencia_do_pagamento(self):
        """É o MESMO dinheiro, no mesmo dia, na mesma carteira — inventar
        outra data ou outra referência seria mentir no extrato."""
        self._rodar('--commit')
        po = self._repasses()[0]
        self.assertEqual(po.paid_at, self.pag.paid_at)
        self.assertEqual(po.reference, 'BINANCE HANDSON')

    def test_o_painel_da_venda_para_de_mostrar_saldo(self):
        self._rodar('--commit')
        self.assertEqual(self._fatura().payout_balance_usd, D('0.00'))

    def test_as_duas_pernas_passam_a_dizer_a_mesma_coisa(self):
        self._rodar('--commit')
        inv = self._fatura()
        self.assertEqual(inv.balance_usd, D('0.00'))
        self.assertEqual(inv.payout_balance_usd, D('0.00'))

    def test_rodar_duas_vezes_nao_duplica_o_repasse(self):
        self._rodar('--commit')
        saida = self._rodar('--commit')
        self.assertEqual(len(self._repasses()), 1)
        self.assertIn('já bate', saida)

    def test_completa_um_repasse_parcial_em_vez_de_somar_outro_cheio(self):
        with company_scope(self.empresa.id):
            Payout(invoice=self.inv, amount_usd=D('300.00'),
                   paid_at=date(2026, 4, 21), reference='parcial').save()
        self._rodar('--commit')
        self.assertEqual(self._fatura().paid_out_usd, LIQUIDO)
        self.assertEqual(len(self._repasses()), 2)


class TaxaIntocadaTests(_Cenario):
    """A taxa de 10% é legítima. O comando não é lugar de mexer nela."""

    def test_nao_mexe_na_taxa_congelada_da_fatura(self):
        self._rodar('--commit')
        inv = self._fatura()
        self.assertEqual(inv.fee_pct, D('10.00'))
        self.assertEqual(inv.fee_rmb, D('974.99'))
        self.assertEqual(inv.fee_usd, TAXA)

    def test_o_liquido_continua_sendo_o_bruto_menos_a_taxa(self):
        self._rodar('--commit')
        self.assertEqual(self._fatura().net_usd, BRUTO - TAXA)

    def test_a_taxa_fica_retida_pelo_whatthechip(self):
        """Entrou US$ 1462,48 do comprador, saiu US$ 1316,23 para o cliente:
        a diferença é a taxa, e ela tem de sobrar."""
        self._rodar('--commit')
        inv = self._fatura()
        self.assertEqual(inv.paid_usd - inv.paid_out_usd, TAXA)

    def test_nao_mexe_no_service_fee_pct_da_empresa(self):
        self._rodar('--commit')
        self.assertEqual(
            Company.objects.get(slug='eminer').service_fee_pct, D('10.00'))


class NaoPagaTests(_Cenario):
    """Não se inventa recibo de dinheiro que não entrou."""

    def setUp(self):
        super().setUp()
        with company_scope(self.empresa.id):
            Payment.all_companies.filter(pk=self.pag.pk).update(
                amount_usd=D('1000.00'))
            Invoice.all_companies.filter(pk=self.inv.pk).update(status='open')

    def test_pula_a_fatura_parcialmente_paga(self):
        saida = self._rodar('--commit')
        self.assertIn('PULA', saida)
        self.assertEqual(self._repasses(), [])


class EscopoTests(_Cenario):
    """Só as ordens da lista — venda corrente não é tocada."""

    def setUp(self):
        super().setUp()
        with company_scope(self.empresa.id):
            outro = Lot.all_companies.create(
                company=self.empresa, number=9, description='corrente',
                status='closed', operator=self.op, origin='phone')
            self.so2 = SalesOrder(
                lot=outro, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1484'), total_rmb=D('1000.00'),
                total_usd=D('148.40'),
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            self.so2.save()
            self.inv2 = Invoice(
                order=self.so2, status='paid', fx_usd_rate=D('0.1484'),
                total_rmb=D('1000.00'), total_usd=D('148.40'),
                fee_pct=D('10.00'), fee_rmb=D('100.00'), fee_usd=D('14.84'),
                number=DocSequence.next_number(self.empresa, SEQ_INVOICE))
            self.inv2.save()
            Payment(invoice=self.inv2, amount_usd=D('148.40'),
                    paid_at=date(2026, 8, 27), reference='TRONLINK').save()

    def test_a_fatura_de_fora_da_lista_fica_intacta(self):
        self._rodar('--commit')
        inv2 = Invoice.all_companies.get(pk=self.inv2.pk)
        self.assertEqual(inv2.fee_usd, D('14.84'))
        self.assertEqual(inv2.paid_out_usd, D('0.00'))


class RecusaTests(_Cenario):

    def test_recusa_ordem_inexistente(self):
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit', ordens=('SO/999/01/26',))
        self.assertIn('não encontrada', str(e.exception))

    def test_recusa_ordem_sem_fatura_ativa(self):
        with company_scope(self.empresa.id):
            Payment.all_companies.filter(pk=self.pag.pk).delete()
            Invoice.all_companies.filter(pk=self.inv.pk).update(
                status='cancelled')
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit')
        self.assertIn('fatura ativa', str(e.exception))


class RevertTests(_Cenario):

    def test_revert_remove_o_repasse(self):
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertEqual(self._repasses(), [])

    def test_revert_devolve_o_painel_ao_estado_anterior(self):
        self._rodar('--commit')
        self._rodar('--revert')
        self.assertEqual(self._fatura().payout_balance_usd, LIQUIDO)

    def test_revert_sem_arquivo_reclama(self):
        with self.assertRaises(CommandError):
            self._rodar('--revert')

    def test_o_json_de_reversao_e_gravado(self):
        self._rodar('--commit')
        self.assertTrue(os.path.exists(_REVERT))


class PodaTests(_Cenario):
    """O suite não pode encher var/reverts/ — bug de 31/08, 232 arquivos."""

    def test_mantem_no_maximo_os_ultimos_backups(self):
        from vendas.management.commands import corrigir_recebimento_eminer as m
        for _ in range(m.MANTER_ANTIGOS + 4):
            self._rodar('--commit')
            self._rodar('--revert')
        sobras = [f for f in os.listdir(_DIR)
                  if f.startswith(os.path.basename(_REVERT) + '.')]
        self.assertLessEqual(len(sobras), m.MANTER_ANTIGOS)

    def test_o_revert_vive_fora_do_repositorio_no_teste(self):
        self.assertNotIn('var/reverts', _REVERT)
