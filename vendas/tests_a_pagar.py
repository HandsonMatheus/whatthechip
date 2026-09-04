# -*- coding: utf-8 -*-
"""
"A PAGAR" — a dívida vira coluna, e o status para de ser eufemismo.

Dono, 2026-09-04, olhando produção:

  "a ordem de venda depois de confirmada vira com o status de FATURADO em
   azul, o que causa confusão, tem que ficar claro de que ele DEVE aquela SO
   (...) na tabela de suas compras também precisamos de uma coluna de TOTAL
   ADEUDADO, e que o fim da tabela mostre o total desse importe adeudado, e
   também dos resultados"

DUAS coisas, e a raiz é a mesma: a tela contava a dívida do ponto de vista de
quem EMITE a fatura, não de quem a RECEBE.

  · "Faturado" descreve um ato do vendedor. Para quem lê esta tela — o
    comprador — o fato relevante não é que a fatura existe, é que ele deve.
    Em AZUL, ainda por cima, que nesta folha significa *informação*, enquanto
    o "falta US$ 8.313,75" na célula ao lado saía em âmbar: duas cores para o
    mesmo fato, na mesma linha.

  · O valor devido existia, mas como SUB-LINHA dentro de Resultado. Sub-linha
    não soma, não se varre com o olho e não tem rodapé. Virar coluna é o que
    torna a dívida um número de primeira classe.

⚠ A trava mais importante deste arquivo é o `RodapeTotaliza`: os totais somam
  o RECORTE FILTRADO INTEIRO, não a página. Um total que muda ao virar a
  página responde a uma pergunta que ninguém fez, e é o erro fácil de cometer
  aqui — `pagina.object_list` está à mão no contexto.
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
from vendas.models import (DocSequence, Invoice, SEQ_SO, SalesOrder,
                           SalesOrderLine, STATUS_CONFIRMED)

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
        self.client.force_login(self.parceiro)

    def _ordem(self, n, *, unit='100.00', qtd=10):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=n, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            # ⚠ `quantize`: 100.00 × 10 × 0.14 sai como D('140.0000'), e o
            #   campo é `decimal_places=2` — o `full_clean` do `save()`
            #   recusa. Fixture que não passa pela validação do modelo é
            #   fixture que testa outro sistema.
            total_rmb = D(unit) * qtd
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1400'),
                total_rmb=total_rmb,
                total_usd=(total_rmb * D('0.14')).quantize(D('0.01')),
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
            SalesOrderLine.all_companies.create(
                order=so, company=self.emp, brand='Samsung', kind='emmc',
                gen='', tier_value=D('64'), tier_unit='GB', quantity=qtd,
                unit_rmb=D(unit))
        return so

    def _faturar(self, so, recusados=0):
        with company_scope(self.emp.id):
            linha = so.lines.get()
            services.settle_and_invoice(so, {linha.pk: (recusados, None)},
                                        self.gerente)
            return Invoice.all_companies.get(order=so)

    def _pagar(self, inv, quanto):
        with company_scope(self.emp.id):
            services.register_payment(inv, D(quanto), timezone.now(),
                                      self.gerente)

    def _lista(self, **params):
        r = self.client.get(reverse('compras:list'), params)
        self.assertEqual(r.status_code, 200)
        return r

    def _tbody(self, **params):
        """Só as LINHAS.

        ⚠ Asserção na página inteira mente aqui de dois jeitos: o seletor de
          status carrega TODOS os rótulos (inclusive "Falta preço seu", que
          casa com uma busca por "falta"), e o rodapé repete os valores como
          total. Duas armadilhas que já morderam neste repo.
        """
        html = self._lista(**params).content.decode()
        return html[html.index('<tbody>'):html.index('</tbody>')]


# ═══════════════════════════════════════════════════════════════════════════
# (A) O SELO: ele DEVE, e a tela diz isso
# ═══════════════════════════════════════════════════════════════════════════
class SeloDizQueDeveTests(_Base):

    def test_o_estagio_faturado_se_chama_A_PAGAR(self):
        """A chave canônica NÃO muda — `faturado` continua sendo a chave, e é
        ela que o filtro e o CSV usam. O que muda é o RÓTULO."""
        so = self._ordem(1)
        self._faturar(so)
        with company_scope(self.emp.id):
            self.assertEqual(services.order_stage(so), services.STAGE_FATURADO)
        corpo = self._tbody()
        self.assertIn('A pagar', corpo)
        self.assertNotIn('Faturado', corpo)

    def test_o_selo_e_ambar_e_nao_azul(self):
        """`act--pay`, não `tag--info`.

        A doutrina é do próprio `components.css`: "azul é despachar (movimento
        do lote), âmbar é aceitar (decisão sobre dinheiro, o mesmo âmbar de
        todo saldo em aberto)". Dívida é saldo em aberto.
        """
        self._faturar(self._ordem(1))
        self.assertIn('act act--pay', self._tbody())

    def test_a_classe_ambar_existe_na_folha(self):
        """Selo com classe que o CSS não conhece sai sem cor nenhuma e sem
        erro — o defeito mais silencioso que existe."""
        import io, os
        from django.conf import settings
        css = io.open(os.path.join(settings.BASE_DIR, 'static', 'wtc',
                                   'components.css'), encoding='utf-8').read()
        self.assertIn('.dtab .act--pay{', css)
        self.assertIn('--amber', css[css.index('.dtab .act--pay{'):][:200])

    def test_quem_ja_pagou_nao_diz_A_PAGAR(self):
        so = self._ordem(1)
        inv = self._faturar(so)
        self._pagar(inv, inv.total_usd)
        with company_scope(self.emp.id):
            self.assertEqual(services.order_stage(so), services.STAGE_PAGO)
        self.assertNotIn('act--pay', self._tbody())


# ═══════════════════════════════════════════════════════════════════════════
# (B) A COLUNA
# ═══════════════════════════════════════════════════════════════════════════
class ColunaDoQueSeDeveTests(_Base):

    def test_a_coluna_traz_o_saldo(self):
        inv = self._faturar(self._ordem(1))
        self.assertIn('US$ %s' % inv.balance_usd, self._tbody())

    def test_o_valor_nao_aparece_duas_vezes_na_mesma_linha(self):
        """⚠ O motivo de o `.due` ter saído do Resultado.

        O saldo já estava na tela como sub-linha ("falta US$ …") DENTRO da
        célula de Resultado. Com a coluna nova, manter as duas põe o mesmo
        número em duas células da mesma linha — isso não é reforço, é ruído.

        ⚠ PAGAMENTO PARCIAL de propósito. A 1ª versão deste teste faturava sem
          recusa nem pagamento e contava o saldo esperando 1 — achou 4, e
          estava CERTO o sistema: sem recusa e sem pagamento, esperado ==
          resultado == saldo, então o mesmo número sai legitimamente na coluna
          Total US$, no par do `.key`, no Resultado e no A pagar. O teste é que
          media a coisa errada. Com um pagamento parcial o saldo passa a ser um
          número que não existe em nenhuma outra célula, e aí a contagem
          responde à pergunta que eu queria fazer.
        """
        a = self._faturar(self._ordem(1, unit='100.00'))
        b = self._faturar(self._ordem(2, unit='250.00'))
        self._pagar(a, D('40.00'))          # saldo 100.00, único na linha
        self._pagar(b, D('50.00'))          # saldo 300.00, único na linha
        corpo = self._tbody()
        for inv in (a, b):
            with company_scope(self.emp.id):
                inv.refresh_from_db()
            saldo = 'US$ %s' % inv.balance_usd
            self.assertEqual(corpo.count(saldo), 1,
                             'o saldo %s saiu repetido na linha' % saldo)
        self.assertNotIn('falta', corpo)

    def test_o_saldo_nao_esta_dentro_da_celula_de_resultado(self):
        """A mesma garantia, dita pela ESTRUTURA em vez da contagem — imune a
        dois valores coincidirem."""
        import re
        inv = self._faturar(self._ordem(1, unit='100.00'))
        self._pagar(inv, D('40.00'))
        with company_scope(self.emp.id):
            inv.refresh_from_db()
        celulas = re.findall(r'<td[^>]*data-lbl="([^"]+)"[^>]*>(.*?)</td>',
                             self._tbody(), re.S)
        por_rotulo = dict(celulas)
        self.assertIn('Resultado', por_rotulo)
        self.assertIn('A pagar', por_rotulo)
        self.assertNotIn(str(inv.balance_usd), por_rotulo['Resultado'])
        self.assertIn(str(inv.balance_usd), por_rotulo['A pagar'])

    def test_compra_sem_fatura_nao_inventa_divida(self):
        """Travessão, não zero: zero é um valor e se lê como 'nada a pagar
        porque já pagou'. Quem não tem fatura não tem dívida NEM quitação."""
        self._ordem(1)
        self.assertNotIn('US$ 0.00', self._tbody())

    def test_quitado_continua_dizendo_quitado(self):
        """Informação DIFERENTE da dívida (não há), e por isso sobreviveu ao
        corte do `.due`."""
        inv = self._faturar(self._ordem(1))
        self._pagar(inv, inv.total_usd)
        self.assertIn('quitado', self._tbody())


# ═══════════════════════════════════════════════════════════════════════════
# (C) O RODAPÉ — a trava que mais vale
# ═══════════════════════════════════════════════════════════════════════════
class RodapeTotalizaTests(_Base):

    def test_soma_os_dois_totais(self):
        a = self._faturar(self._ordem(1, unit='100.00'))
        b = self._faturar(self._ordem(2, unit='200.00'))
        self._pagar(b, D('5.00'))
        ctx = self._lista().context
        self.assertEqual(ctx['total_resultado_usd'],
                         a.total_usd + b.total_usd)
        self.assertEqual(ctx['total_a_pagar_usd'],
                         a.balance_usd + b.balance_usd)

    def test_o_total_e_do_RECORTE_e_nao_da_pagina(self):
        """⚠ A trava principal deste arquivo.

        `pagina.object_list` está à mão no contexto e somá-lo é o erro fácil.
        Com 12 compras e página de 10, um total de página mudaria ao virar —
        e um total que muda de valor conforme a página não é um total.
        """
        faturas = [self._faturar(self._ordem(n)) for n in range(1, 13)]
        esperado = sum((f.balance_usd for f in faturas), D('0.00'))
        r = self._lista()
        self.assertEqual(len(r.context['ordens']), 10)     # a página encheu
        self.assertEqual(r.context['total_a_pagar_usd'], esperado)
        # e a página 2 diz o MESMO total
        self.assertEqual(self._lista(page='2').context['total_a_pagar_usd'],
                         esperado)

    def test_o_total_obedece_ao_FILTRO(self):
        """O recorte é o filtrado, não o universo: filtrar por "a pagar" e ler
        um total que inclui o que já foi pago seria pior que não ter total."""
        pago = self._faturar(self._ordem(1))
        self._pagar(pago, pago.total_usd)
        devendo = self._faturar(self._ordem(2))
        ctx = self._lista(status=services.STAGE_FATURADO).context
        self.assertEqual(ctx['total_a_pagar_usd'], devendo.balance_usd)

    def test_tabela_vazia_nao_mostra_rodape_de_total(self):
        """Soma de nada dizendo "US$ 0.00" se lê como dado."""
        html = self._lista(q='nao-existe-nada-assim').content.decode()
        self.assertNotIn('<tfoot>', html)

    def test_o_rodape_diz_de_quantas_compras_e_a_soma(self):
        """Um total de 5 páginas embaixo de 10 linhas precisa dizer que não é
        a soma do que está à vista."""
        for n in range(1, 13):
            self._faturar(self._ordem(n))
        html = self._lista().content.decode()
        self.assertIn('<tfoot>', html)
        self.assertIn('12', html)
