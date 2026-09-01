"""
Carteira por empresa — `Wallet.company` (dono, 2026-09-01).

*"deve existir ambas possibilidades, do comprador pagar direto ao cliente e
também direto a WTC"*. A tabela passou a ter dois sabores e quem escolhe é a
`Company.payout_on_payment`, o mesmo interruptor do repasse automático.

O que está sob teste é a tela que decide PARA ONDE VAI DINHEIRO. Por isso as
duas garantias mais importantes aqui são negativas — o que a função se recusa
a fazer:

  · cliente sem carteira NÃO cai na carteira da plataforma;
  · empresa no arranjo padrão NÃO enxerga a carteira de cliente nenhum.

Um fallback em qualquer das duas direções manda a transferência para a parte
errada em silêncio, e transferência em blockchain não volta.

⚠ Em SQLite não há RLS: o isolamento provado aqui é o da Camada A (o filtro
  explícito). A Camada B (leitura ampla da linha de plataforma) mora na
  migração `vendas/0020` e só existe no Postgres.
"""

from decimal import Decimal as D
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice,
                           SalesOrder, Settlement, Wallet)

User = get_user_model()

PLATAFORMA = 'TAbc111111111111111111111111111111'
DA_EMINER = 'TXyz999999999999999999999999999999'


class _Base(TestCase):

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer',
                                          code='')
        self.outra = Company.objects.create(name='eRecyclo', slug='erecyclo')

    def _carteira_plataforma(self, ativa=True):
        return Wallet.all_companies.create(
            company=None, owner='WhatTheChip Ltd.', net='USDT · TRC-20',
            addr=PLATAFORMA, active=ativa)

    def _carteira_do_cliente(self, empresa=None, ativa=True):
        return Wallet.all_companies.create(
            company=empresa or self.emp, owner='eMiner S.A.',
            net='USDT · TRC-20', addr=DA_EMINER, active=ativa)

    def _ligar(self, empresa=None):
        empresa = empresa or self.emp
        empresa.payout_on_payment = True
        empresa.save(update_fields=['payout_on_payment'])
        return empresa


class EscolhaTests(_Base):

    def test_chave_desligada_devolve_a_carteira_da_plataforma(self):
        self._carteira_plataforma()
        self._carteira_do_cliente()
        self.assertEqual(Wallet.for_company(self.emp).addr, PLATAFORMA)

    def test_chave_ligada_devolve_a_carteira_do_cliente(self):
        self._ligar()
        self._carteira_plataforma()
        self._carteira_do_cliente()
        self.assertEqual(Wallet.for_company(self.emp).addr, DA_EMINER)

    def test_cliente_SEM_carteira_nao_cai_na_da_plataforma(self):
        """A garantia que vale dinheiro. Com a chave ligada o comprador tem de
        pagar o cliente; devolver o endereço do WhatTheChip aqui mandaria a
        transferência para a parte errada, calado."""
        self._ligar()
        self._carteira_plataforma()
        self.assertIsNone(Wallet.for_company(self.emp))

    def test_arranjo_padrao_nao_cai_na_carteira_do_cliente(self):
        """O espelho: com a chave desligada o dinheiro é do WhatTheChip, e a
        carteira do cliente ali seria a plataforma pagando a si mesma de
        fora."""
        self._carteira_do_cliente()
        self.assertIsNone(Wallet.for_company(self.emp))

    def test_carteira_inativa_e_ignorada_dos_dois_lados(self):
        """`active=False` existe para APOSENTAR endereço sem apagar o
        histórico — endereço aposentado não pode voltar à tela."""
        self._carteira_plataforma(ativa=False)
        self.assertIsNone(Wallet.for_company(self.emp))
        self._ligar()
        self._carteira_do_cliente(ativa=False)
        self.assertIsNone(Wallet.for_company(self.emp))

    def test_a_carteira_de_um_cliente_nao_vaza_para_outro(self):
        self._ligar()
        self._ligar(self.outra)
        self._carteira_do_cliente(self.emp)
        self.assertEqual(Wallet.for_company(self.emp).addr, DA_EMINER)
        self.assertIsNone(Wallet.for_company(self.outra))

    def test_sem_empresa_nao_inventa_carteira(self):
        self._carteira_plataforma()
        self.assertIsNone(Wallet.for_company(None))

    def test_is_platform_separa_os_dois_sabores(self):
        self.assertTrue(self._carteira_plataforma().is_platform)
        self.assertFalse(self._carteira_do_cliente().is_platform)


class TelaTests(_Base):
    """A frase muda junto com o endereço — senão a tela ensina o comprador a
    desconfiar do endereço certo."""

    def setUp(self):
        super().setUp()
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.op = User.objects.create_user('op_wallet', password='x')

    def _compra(self):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=1, description='x', status='closed',
                operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('1000.00'),
                total_usd=D('1000.00'), shipped_at=date(2026, 7, 11),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
            # ⚠ O acerto não é enfeite do fixture: a fatura NASCE dele no
            # fluxo real (`close_settlement`), e o card de etapas lê
            # `inv.settlement.created_at`. Fatura órfã derruba a tela inteira
            # — foi assim que a 1ª versão destes testes quebrou.
            st = Settlement(order=so, created_by=self.op)
            st.save()
            Invoice(order=so, settlement=st, status='open',
                    fx_usd_rate=D('0.1500'),
                    total_rmb=D('1000.00'), total_usd=D('1000.00'),
                    number=DocSequence.next_number(self.emp,
                                                   SEQ_INVOICE)).save()
        self.client.force_login(self.parceiro)
        return self.client.get(reverse('compras:detail', args=[so.pk]))

    def test_arranjo_padrao_avisa_para_nunca_pagar_o_vendedor(self):
        self._carteira_plataforma()
        html = self._compra().content.decode()
        self.assertIn(PLATAFORMA, html)
        self.assertIn('nunca o vendedor direto', html)

    def test_pagando_direto_ao_cliente_a_frase_e_outra(self):
        self._ligar()
        self._carteira_do_cliente()
        html = self._compra().content.decode()
        self.assertIn(DA_EMINER, html)
        self.assertIn('sem passar pelo', html)
        # …e o aviso anti-golpe da plataforma NÃO pode aparecer aqui: nesta
        # compra pagar o vendedor direto é justamente o combinado.
        self.assertNotIn('nunca o vendedor direto', html)

    def test_sem_carteira_a_tela_manda_falar_com_o_whatthechip(self):
        self._ligar()
        html = self._compra().content.decode()
        self.assertNotIn(PLATAFORMA, html)
        self.assertIn('ainda não cadastrada', html)
