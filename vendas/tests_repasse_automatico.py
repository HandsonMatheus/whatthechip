"""
Repasse automático — `Company.payout_on_payment` (dono, 2026-09-01).

O que está sob teste é uma chave que muda o SIGNIFICADO da tela do cliente:
ligada, quitar a fatura do comprador já lança o `Payout` do líquido; desligada,
o repasse continua sendo um ato manual do WhatTheChip. Errar o lado dessa chave
não dá erro nenhum — dá um extrato que promete dinheiro que ninguém transferiu,
que é o pior defeito possível num sistema de dinheiro.

Por isso o teste que mais importa aqui é o mais chato: **o padrão é
DESLIGADO**. Os outros protegem a aritmética; esse protege quem nunca ouviu
falar dessa chave.

⚠ Como em `tests_saldo_comprador.py`, a suíte roda em SQLite e não tem RLS.
  O que se prova aqui é a REGRA (quando dispara, por quanto, com que data),
  não o comportamento do banco sob escopo.
"""

from decimal import Decimal as D
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas import services
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice, Payout,
                           Payment, SalesOrder)

User = get_user_model()

#: Comprovante mínimo que o `_sniff_receipt` aceita (magic de PDF).
PDF = b'%PDF-1.4\n%%EOF\n'


class _Cenario(TestCase):
    """Uma venda de US$ 1.000,00 com 10% de taxa → líquido US$ 900,00.

    Números redondos de propósito: quando um teste falhar, a conta tem que
    caber na cabeça de quem está lendo o relatório às 3 da manhã.
    """

    TOTAL = D('1000.00')
    TAXA = D('10.00')
    LIQUIDO = D('900.00')

    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_repasse', password='x')
        self.comprador = User.objects.create_user('u_wuquan', password='x')
        self.buyer.users.add(self.comprador)

    def _ligar(self):
        """Liga a chave — e devolve a empresa recarregada."""
        self.empresa.payout_on_payment = True
        self.empresa.save(update_fields=['payout_on_payment'])
        return self.empresa

    def _venda(self, numero=1, total=None, taxa=None):
        """OV despachada + fatura em aberto. Devolve a fatura."""
        total = self.TOTAL if total is None else total
        taxa = self.TAXA if taxa is None else taxa
        fee = (total * taxa / D('100')).quantize(D('0.01'))
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=numero, description='x',
                status='closed', operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=total, total_usd=total,
                shipped_at=date(2026, 7, 11),
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            so.save()
            inv = Invoice(
                order=so, status='open', fx_usd_rate=D('0.1500'),
                total_rmb=total, total_usd=total,
                fee_pct=taxa, fee_rmb=fee, fee_usd=fee,
                number=DocSequence.next_number(self.empresa, SEQ_INVOICE))
            inv.save()
        self.so = so
        return inv

    def _pagar(self, inv, quanto=None, quando=None, ref='TRONLINK'):
        with company_scope(self.empresa.id):
            return services.register_payment(
                inv, self.TOTAL if quanto is None else quanto,
                quando or date(2026, 8, 18), self.op, reference=ref)

    def _repasses(self, inv):
        with company_scope(self.empresa.id):
            return list(Payout.all_companies.filter(invoice=inv))


class PadraoDesligadoTests(_Cenario):
    """A garantia que protege quem nunca ouviu falar dessa chave."""

    def test_empresa_nova_nasce_com_a_chave_DESLIGADA(self):
        nova = Company.objects.create(name='eRecyclo', slug='erecyclo')
        self.assertFalse(nova.payout_on_payment)

    def test_desligada_quitar_a_fatura_NAO_lanca_repasse(self):
        """O modelo padrão tem três passos, e o terceiro é um ato do WTC.
        Antecipá-lo seria a tela do cliente mentir."""
        inv = self._venda()
        self._pagar(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'paid')          # o comprador quitou
        self.assertEqual(self._repasses(inv), [])     # o cliente não recebeu


class ValorEDataTests(_Cenario):

    def test_repassa_o_LIQUIDO_e_nao_o_total(self):
        """A taxa fica retida. Repassar o cheio seria a plataforma pagar do
        próprio bolso a comissão que acabou de cobrar."""
        self._ligar()
        inv = self._venda()
        self._pagar(inv)
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.amount_usd, self.LIQUIDO)
        self.assertEqual(rep.amount_usd, inv.net_usd)

    def test_a_data_e_a_do_PAGAMENTO_nao_a_de_hoje(self):
        """Repasse lançado com a data de hoje quebra a conciliação de quem
        importa a planilha meses depois."""
        self._ligar()
        inv = self._venda()
        self._pagar(inv, quando=date(2026, 7, 11))
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.paid_at, date(2026, 7, 11))

    def test_taxa_zero_repassa_o_total(self):
        self._ligar()
        inv = self._venda(taxa=D('0.00'))
        self._pagar(inv)
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.amount_usd, self.TOTAL)

    def test_zera_o_saldo_a_repassar(self):
        self._ligar()
        inv = self._venda()
        self._pagar(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.payout_balance_usd, D('0.00'))


class ProcedenciaTests(_Cenario):
    """Quem declarou o quê — a pergunta que uma auditoria faz primeiro."""

    def test_repasse_automatico_NAO_tem_autor(self):
        """Ninguém digitou este repasse: ele decorre do pagamento. Pôr o
        usuário do comprador aqui faria o extrato dizer que a contraparte
        declarou o repasse do WhatTheChip."""
        self._ligar()
        inv = self._venda()
        with company_scope(self.empresa.id):
            services.register_payment(inv, self.TOTAL, date(2026, 8, 18),
                                      self.comprador, reference='TRONLINK')
        (rep,) = self._repasses(inv)
        self.assertIsNone(rep.created_by)
        # …e quem pagou continua registrado do outro lado.
        with company_scope(self.empresa.id):
            self.assertEqual(Payment.all_companies.get(invoice=inv).created_by,
                             self.comprador)

    def test_a_referencia_do_pagamento_viaja_junto(self):
        """É por ela que o cliente reconhece a transferência no extrato dele —
        no arranjo em que essa chave se liga, é a MESMA transferência."""
        self._ligar()
        inv = self._venda()
        self._pagar(inv, ref='BINANCE HANDSON 4471')
        (rep,) = self._repasses(inv)
        self.assertIn('BINANCE HANDSON 4471', rep.reference)
        self.assertIn(services.MARCA_REPASSE_AUTOMATICO, rep.reference)

    def test_pagamento_sem_referencia_ainda_marca_a_origem(self):
        self._ligar()
        inv = self._venda()
        self._pagar(inv, ref='')
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.reference, services.MARCA_REPASSE_AUTOMATICO)

    def test_referencia_no_limite_nao_estoura_o_campo(self):
        """Pior caso REAL: `Payment.reference` também tem teto de 120, então
        a maior entrada possível já enche a coluna sozinha e a marca não cabe.

        O corte come a MARCA, nunca a frente: é a referência que casa com o
        extrato bancário do cliente, e um identificador de wire truncado não
        casa com nada. A marca é conveniência de leitura — a prova de que o
        repasse foi automático é o `created_by` vazio, que não trunca."""
        self._ligar()
        inv = self._venda()
        self._pagar(inv, ref='W' * 120)
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.reference, 'W' * 120)
        self.assertIsNone(rep.created_by)


class ParcelaTests(_Cenario):
    """Parcial não dispara nada — e o motivo não é preguiça."""

    def test_pagamento_parcial_nao_lanca_repasse(self):
        """Metade do bruto não é metade do líquido: a taxa não é proporcional
        a prestação nenhuma. Ratear seria inventar um número que ninguém
        combinou."""
        self._ligar()
        inv = self._venda()
        self._pagar(inv, quanto=D('400.00'))
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'open')
        self.assertEqual(self._repasses(inv), [])

    def test_a_parcela_que_QUITA_lanca_o_liquido_inteiro_de_uma_vez(self):
        self._ligar()
        inv = self._venda()
        self._pagar(inv, quanto=D('400.00'), quando=date(2026, 7, 1))
        self._pagar(inv, quanto=D('600.00'), quando=date(2026, 8, 18))
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.amount_usd, self.LIQUIDO)
        # A data é a do fechamento da conta, não a da primeira parcela.
        self.assertEqual(rep.paid_at, date(2026, 8, 18))


class NaoDobraTests(_Cenario):
    """Ligar a chave numa empresa COM HISTÓRICO não pode dobrar o extrato."""

    def test_repasse_ja_lancado_a_mao_impede_o_automatico(self):
        self._ligar()
        inv = self._venda()
        with company_scope(self.empresa.id):
            services.register_payout(inv, self.LIQUIDO, date(2026, 8, 1),
                                     self.op, reference='wire manual')
        self._pagar(inv)
        self.assertEqual(len(self._repasses(inv)), 1)     # continua um só
        inv.refresh_from_db()
        self.assertEqual(inv.paid_out_usd, self.LIQUIDO)

    def test_repasse_parcial_a_mao_completa_so_o_que_falta(self):
        self._ligar()
        inv = self._venda()
        with company_scope(self.empresa.id):
            services.register_payout(inv, D('300.00'), date(2026, 8, 1),
                                     self.op, reference='adiantamento')
        self._pagar(inv)
        automatico = [r for r in self._repasses(inv) if r.created_by is None]
        self.assertEqual(len(automatico), 1)
        self.assertEqual(automatico[0].amount_usd, D('600.00'))
        inv.refresh_from_db()
        self.assertEqual(inv.paid_out_usd, self.LIQUIDO)


class MesmaTransacaoTests(_Cenario):
    """Nesse arranjo as duas pernas são o MESMO fato.

    Se alguém envolver a chamada num `try/except` "defensivo", o sistema volta
    ao estado que esta feature veio consertar — só que em silêncio, que é pior.
    Este teste é a trava contra esse conserto bem-intencionado.
    """

    def test_repasse_que_falha_derruba_o_pagamento_junto(self):
        self._ligar()
        inv = self._venda()
        with mock.patch.object(services, 'register_payout',
                               side_effect=ValidationError('boom')):
            with self.assertRaises(ValidationError):
                self._pagar(inv)
        inv.refresh_from_db()
        with company_scope(self.empresa.id):
            self.assertEqual(Payment.all_companies.filter(invoice=inv).count(),
                             0)
        self.assertEqual(inv.status, 'open')
        self.assertEqual(self._repasses(inv), [])


class TelaTests(_Cenario):
    """Pelo caminho de verdade: o comprador pagando na tela dele."""

    def _postar(self, inv, valor='1000.00'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.comprador)
        # ⚠ O comprovante é obrigatório na view (pagamento sem comprovante é
        # recusado antes de chegar ao service) — por isso o PDF mínimo.
        return self.client.post(
            reverse('compras:pagar', args=[self.so.pk]),
            {'amount_usd': valor, 'paid_at': '2026-08-18',
             'reference': 'TRONLINK',
             'receipt': SimpleUploadedFile('wire.pdf', PDF,
                                           content_type='application/pdf')})

    def test_comprador_paga_na_tela_e_o_repasse_sai_junto(self):
        self._ligar()
        inv = self._venda()
        self._postar(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'paid')
        (rep,) = self._repasses(inv)
        self.assertEqual(rep.amount_usd, self.LIQUIDO)
        self.assertEqual(rep.paid_at, date(2026, 8, 18))
        self.assertIsNone(rep.created_by)

    def test_com_a_chave_desligada_a_mesma_tela_nao_lanca_nada(self):
        inv = self._venda()
        self._postar(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'paid')
        self.assertEqual(self._repasses(inv), [])
