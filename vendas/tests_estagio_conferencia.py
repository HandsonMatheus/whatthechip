# -*- coding: utf-8 -*-
"""
EM TRÂNSITO × CONFERÊNCIA — o bug que apareceu em PRODUÇÃO (dono, 2026-09-02).

  "apesar de uma compra ja ter sido dada como recebida, ainda aparece como em
   transito na tabela de compras"

A ficha da SO/004 dizia `Recebido ✓ · Conferência` e a lista, para a MESMA
compra, dizia `EM TRÂNSITO`. Duas telas, dois estados, um registro só.

A causa é antiga e a minha entrega de horas antes é que a tornou visível: o
`order_stage` devolvia um único `a_conferir` para tudo que estava confirmado e
sem fatura — a caixa a caminho e a caixa já na bancada dele. Enquanto o rótulo
era o vago "A conferir", os dois cabiam debaixo dele. Renomear para "Em
trânsito" (pedido do dono, mais claro para o caso comum) transformou a
imprecisão em MENTIRA: uma caixa entregue anunciada como em trânsito.

⚠ Eu tinha sinalizado exatamente isto ao entregar o rename, e não consertei.
  A lição que estes testes guardam não é sobre `received_at`: é que um rótulo
  mais específico sobre um estado que não foi dividido não é uma melhora — é
  um bug esperando a primeira linha de dados que discorde dele.

Quem separa os dois é o `received_at`, o MESMO campo do passo `recebido` do
trilho. Uma segunda regra faria a lista e a ficha discordarem de novo.
"""

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


class _Base(TestCase):

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        self.a_caminho = self._ordem(1, recebida=False)
        self.na_bancada = self._ordem(2, recebida=True)
        self.client.force_login(self.parceiro)

    def _ordem(self, n, recebida):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=n, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1400'), total_rmb=D('1000.00'),
                total_usd=D('140.00'), shipped_at=date(2026, 8, 18),
                received_at=timezone.now() if recebida else None,
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
            SalesOrderLine.all_companies.create(
                order=so, company=self.emp, brand='Samsung', kind='emmc',
                gen='', tier_value=D('64'), tier_unit='GB', quantity=10,
                unit_rmb=D('100.00'))
        return so

    def _lista(self, **params):
        return self.client.get(reverse('compras:list'), params)

    def _stage(self, so):
        with company_scope(self.emp.id):
            return services.order_stage(so)


class EstagioTests(_Base):

    def test_a_caminho_fica_em_transito(self):
        self.assertEqual(self._stage(self.a_caminho),
                         services.STAGE_A_CONFERIR)

    def test_recebida_vira_conferencia(self):
        """O bug de produção, na sua forma mais curta."""
        self.assertEqual(self._stage(self.na_bancada),
                         services.STAGE_CONFERENCIA)

    def test_quem_separa_e_o_received_at_e_nada_mais(self):
        """Mesma fonte do passo `recebido` do trilho. Se alguém trocar por
        outra regra — `shipped_at`, uma flag nova, o que for —, a lista e a
        ficha voltam a poder discordar sobre a mesma compra."""
        self.a_caminho.received_at = timezone.now()
        self.a_caminho.save(update_fields=['received_at'])
        self.assertEqual(self._stage(self.a_caminho),
                         services.STAGE_CONFERENCIA)
        self.a_caminho.received_at = None
        self.a_caminho.save(update_fields=['received_at'])
        self.assertEqual(self._stage(self.a_caminho),
                         services.STAGE_A_CONFERIR)


class ListaTests(_Base):

    def test_a_lista_nao_chama_de_em_transito_o_que_ja_chegou(self):
        html = self._lista().content.decode()
        self.assertIn('Conferência', html)
        self.assertIn('Em trânsito', html)
        # a pastilha de cada uma, e não só as palavras soltas na página
        self.assertIn('act--accept', html)
        self.assertIn('act--ship', html)

    def test_a_lista_e_a_ficha_dizem_a_mesma_coisa(self):
        """O TESTE QUE IMPORTA. Era exatamente isto que estava quebrado em
        produção: a ficha da SO/004 dizia "Recebido ✓ · Conferência" e a
        linha dela na lista dizia "EM TRÂNSITO"."""
        import re
        ficha = self.client.get(
            reverse('compras:detail',
                    args=[self.na_bancada.pk])).content.decode()
        # só o trilho: o resto da ficha fala de envio e recebimento em vários
        # lugares, e um assertNotIn na página inteira passaria (ou falharia)
        # por acidente.
        m = re.search(r'<div id="stat".*?</div>\s*</div>', ficha, re.S)
        self.assertIsNotNone(m, 'o trilho sumiu da ficha')
        trilho = m.group(0)
        self.assertIn('Recebido', trilho)
        self.assertIn('Conferência', trilho)
        self.assertNotIn('Em trânsito', trilho,
                         'o trilho de uma compra RECEBIDA não pode falar em '
                         'trânsito')
        na_lista = self._lista(status=services.STAGE_CONFERENCIA)
        self.assertEqual([o.pk for o in na_lista.context['ordens']],
                         [self.na_bancada.pk])

    def test_a_pastilha_azul_e_a_ambar_dizem_coisas_diferentes(self):
        """Âmbar é chamada, azul é informação — a regra do protótipo ("a
        conferir é ato DESTE lado do balcão"). Antes da divisão as duas saíam
        âmbar, e uma caixa ainda no avião pedia ação que ele não podia tomar.
        """
        html = self._lista().content.decode()
        transito = html.index('act--ship')
        conferencia = html.index('act--accept')
        self.assertNotEqual(transito, conferencia)


class FiltroTests(_Base):

    def test_os_dois_estagios_aparecem_no_seletor_com_contagem(self):
        ctx = self._lista().context
        opcoes = {chave: quantos for chave, _r, quantos in ctx['status_opcoes']}
        self.assertEqual(opcoes[services.STAGE_A_CONFERIR], 1)
        self.assertEqual(opcoes[services.STAGE_CONFERENCIA], 1)

    def test_cada_filtro_traz_so_o_seu(self):
        for chave, esperado in ((services.STAGE_A_CONFERIR, self.a_caminho),
                                (services.STAGE_CONFERENCIA, self.na_bancada)):
            ordens = self._lista(status=chave).context['ordens']
            self.assertEqual([o.pk for o in ordens], [esperado.pk], chave)

    def test_a_chave_antiga_continua_valendo_na_url(self):
        """`?status=a_conferir` é filtro que o comprador salva. A chave não foi
        renomeada por isso — ela apenas passou a significar só o trânsito, que
        é o subconjunto que o nome antigo cobria pior."""
        self.assertEqual(services.STAGE_A_CONFERIR, 'a_conferir')
        self.assertEqual(self._lista(status='a_conferir').status_code, 200)


class RodapeTests(_Base):

    def test_o_rodape_soma_os_dois_e_nao_encolhe(self):
        """O número existe desde antes da divisão e conta a FILA dele: tudo
        que ainda vai passar pela sua conferência, a caminho ou na bancada.
        Se passar a contar só `conferencia`, o número CAI na cara dele sem
        nada ter mudado no mundo — e ninguém pediu isso."""
        self.assertEqual(self._lista().context['a_conferir'], 2)

    def test_faturada_sai_da_conta(self):
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                self.na_bancada,
                {self.na_bancada.lines.get().pk: (0, None)}, self.gerente)
        ctx = self._lista().context
        self.assertEqual(ctx['a_conferir'], 1)
        self.assertNotIn(self.na_bancada.pk,
                         [o.pk for o in
                          self._lista(status=services.STAGE_CONFERENCIA)
                          .context['ordens']])
