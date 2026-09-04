# -*- coding: utf-8 -*-
"""
US$ EM DESTAQUE NA CONFERÊNCIA (dono, 2026-09-02).

  "aqui dentro da SO da compra do comprador só esta mostrando os valores em
   YUAN, preciso que mostre o valor unitario em USD e ESPERADO e RESULTADO
   também em USD, levando destaque o valor em USD, que é o que ele vai pagar
   de fato, e as colunas em YUAN com um aspecto de tipo desabilitado"

As três colunas de dinheiro passam a abrir em US$ com o ¥ apagado embaixo. Não
é uma coluna nova: são nove colunas hoje e a tela já aperta no telefone —
empilhar o par dentro da mesma célula é o que o `.mval` do pacote sempre fez,
com os papéis trocados.

Dois riscos, e cada um tem teste:

  1. O ¥ do RESULTADO é somado AO VIVO em JavaScript enquanto ele digita as
     recusas. Se o US$ não entrar no mesmo laço, ele congela no valor do
     servidor na primeira tecla e passa a mentir — mentira silenciosa, porque
     o número continua lá, plausível.

  2. O US$ tem de sair do `unit_usd` CONGELADO da linha, nunca de ¥ × taxa. Os
     dois quase batem, e "quase" numa coluna de dinheiro é o número pulando no
     recarregamento depois de fechar o resultado.
"""

import io
import os
import re
from datetime import date
from decimal import Decimal as D

from django.conf import settings
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
CSS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'components.css')
FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


class _Base(TestCase):
    #: ⚠ De propósito NÃO é `unit_rmb * fx_usd_rate` (2.00 × 0.1400 = 0.28).
    #: Um US$ que não é derivável da taxa é o que permite provar que a tela lê
    #: o valor congelado da linha, e não faz a conta por fora.
    UNIT_RMB, UNIT_USD, FX = D('2.00'), D('0.30'), D('0.1400')
    QTD = 22000

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=6, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=self.FX,
                total_rmb=self.UNIT_RMB * self.QTD,
                total_usd=self.UNIT_USD * self.QTD,
                shipped_at=date(2026, 8, 18),
                # ⚠ Sem `received_at` o `pode_acertar` é falso e a tabela sai
                # com SEIS colunas — sem Recusados/Aprovados/Resultado e sem
                # nenhum campo de recusa. A primeira versão deste arquivo não
                # marcava, e o efeito não foi um teste falhando por acaso: foi
                # a coluna RESULTADO, a única que o JS reescreve, nunca ter
                # sido exercida.
                received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            self.linha = SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Kingston', kind='ddr3',
                gen='', tier_value=D('2'), tier_unit='GB', quantity=self.QTD,
                unit_rmb=self.UNIT_RMB, unit_usd=self.UNIT_USD)
        self.client.force_login(self.parceiro)

    def _html(self):
        r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def _resumo(self):
        """Só a `#tab-resumo`. A ficha tem quatro tabelas e as outras três
        seguem em ¥ — asserção de moeda na página inteira mede a tabela
        errada."""
        m = re.search(r'<table[^>]*id="tab-resumo".*?</table>', self._html(),
                      re.S)
        self.assertIsNotNone(m, 'a tabela do resumo sumiu da ficha')
        return m.group(0)

    def _grupos(self):
        with company_scope(self.emp.id):
            return services.result_rows(self.so)


class FonteDoValorTests(_Base):
    """O risco nº 2: de onde sai o US$."""

    def test_o_grupo_soma_o_usd_CONGELADO_das_linhas(self):
        g = self._grupos()[0]
        self.assertEqual(g['usd'], self.UNIT_USD * self.QTD)
        self.assertEqual(g['usd'],
                         sum(l['total_usd'] for l in g['lines']))

    def test_o_usd_do_grupo_nao_e_o_yuan_convertido(self):
        """A trava. Se alguém "simplificar" o `result_rows` para derivar o US$
        do ¥ pela taxa travada, este cenário denuncia: o unitário em US$ é
        0,30 e o ¥ × taxa daria 0,28."""
        g = self._grupos()[0]
        derivado = g['rmb'] * self.FX
        self.assertNotEqual(g['usd'], derivado)
        self.assertEqual(g['usd'], self.UNIT_USD * self.QTD)

    def test_o_grupo_soma_usd_mesmo_quando_o_yuan_falta(self):
        """`g['usd']` tem condição PRÓPRIA, não é o `else` do ¥. Pendurar os
        dois no mesmo `if` faria o grupo somar zero em US$ no caso em que a
        linha tem uma moeda e não a outra."""
        import inspect
        fonte = inspect.getsource(services.result_rows)
        self.assertIn("if unit_usd is not None:", fonte)


class TelaTests(_Base):
    """O que a página escreve."""

    def test_as_tres_colunas_trazem_as_duas_moedas(self):
        html = self._html()
        # o par aparece na linha, na faixa da marca e no rodapé
        self.assertGreaterEqual(html.count('class="cy"'), 3)
        self.assertIn('US$ %s' % (self.UNIT_USD * self.QTD), html)
        self.assertIn('¥ %s' % (self.UNIT_RMB * self.QTD), html)

    def test_o_unitario_traz_as_duas(self):
        html = self._html()
        self.assertIn('US$ %s' % self.UNIT_USD, html)
        self.assertIn('¥ %s' % self.UNIT_RMB, html)

    def test_o_yuan_nao_sumiu(self):
        """Ele foi para segundo plano, não para fora: é a moeda em que a
        compra foi fechada e a que o cliente lê do outro lado do balcão."""
        html = self._html()
        self.assertIn('<span class="cy">¥', html)

    def test_o_titulo_da_coluna_nao_crava_mais_uma_moeda(self):
        """Um `<th>` dizendo "¥ esperado" sobre uma célula que abre em US$
        anuncia a moeda errada na primeira leitura.

        ⚠ Só na tabela do RESUMO. A aba Chips é outra tabela, continua só em
        ¥ e não foi tocada — varrer a página inteira reprovava por causa dela,
        que é exatamente o tipo de asserção que pune o código certo.
        """
        for velho in ('¥ unit.', '¥ esperado', '¥ resultado'):
            self.assertNotIn('>%s<' % velho, self._resumo())

    def test_o_campo_de_recusa_carrega_o_unitario_em_usd(self):
        """Sem `data-unit-usd` o JS não teria como recalcular o US$ — e o
        único caminho que sobraria seria ¥ × taxa, que é o que o teste de
        cima proíbe."""
        html = self._html()
        self.assertIn('data-unit-usd="%s"' % self.UNIT_USD, html)


class ColunaResultadoTests(_Base):
    """A coluna que o JS reescreve — e que a primeira versão deste arquivo
    nunca chegou a ver, porque o cenário não marcava o recebimento.

    Ela é a mais frágil das três: o servidor a desenha uma vez e o JavaScript
    a reescreve inteira a cada tecla. Se o par estiver certo na renderização e
    errado no `par()`, o defeito só aparece com o comprador digitando.
    """

    def _celula_resultado(self):
        m = re.search(r'<td[^>]*data-val="\d+"[^>]*>(.*?)</td>',
                      self._resumo(), re.S)
        self.assertIsNotNone(m, 'a célula do resultado sumiu da linha')
        return m.group(1)

    def test_o_resultado_abre_em_usd_com_o_yuan_apagado(self):
        celula = self._celula_resultado()
        self.assertIn('US$ %s' % (self.UNIT_USD * self.QTD), celula)
        self.assertIn('<span class="cy">¥ %s' % (self.UNIT_RMB * self.QTD),
                      celula)

    def test_o_usd_vem_antes_do_yuan_na_celula(self):
        """A ordem É a hierarquia: o `.cy` só lê como secundário porque vem
        depois. Inverter os dois mantém as duas moedas na tela e troca qual
        delas o comprador lê primeiro."""
        celula = self._celula_resultado()
        self.assertLess(celula.index('US$'), celula.index('¥'))

    def test_as_tres_colunas_de_dinheiro_tem_par_na_linha(self):
        """Unitário, Esperado e Resultado — as três que o dono pediu, e só
        elas. Enviados/Recusados/Aprovados são contagem, não dinheiro."""
        linha = re.search(r'<tr data-g="0">.*?</tr>', self._resumo(), re.S)
        self.assertIsNotNone(linha)
        self.assertEqual(linha.group(0).count('class="cy"'), 3)

    def test_a_faixa_da_marca_tambem_traz_o_par(self):
        """Faixa em uma moeda com as linhas dela em duas é o tipo de
        divergência que só se nota depois de fechado."""
        faixa = re.search(r'<tr class="g">.*?</tr>', self._resumo(), re.S)
        self.assertIsNotNone(faixa)
        self.assertIn('US$ %s' % (self.UNIT_USD * self.QTD), faixa.group(0))
        self.assertIn('class="cy"', faixa.group(0))


class RecalculoAoVivoTests(_Base):
    """O risco nº 1: o JS.

    Não dá para executar o script aqui. O que dá para provar é que ele LÊ o
    dado certo, escreve o par nos três lugares e não usa a taxa — que são
    exatamente os três jeitos de esse número passar a mentir.
    """

    def setUp(self):
        super().setUp()
        self.js = _ler(FICHA)

    def test_existe_uma_funcao_unica_que_escreve_o_par(self):
        """Três cópias do mesmo formato divergem na primeira alteração."""
        self.assertIn('function par(usd, rmb, extra)', self.js)

    def test_os_tres_lugares_usam_a_funcao(self):
        for alvo in ('cVal.innerHTML = par(', 'eVal.innerHTML = par('):
            self.assertIn(alvo, self.js, alvo)
        self.assertIn("elPagarUsd.textContent = 'US$ '", self.js)

    def test_o_js_le_o_usd_congelado_e_nao_multiplica_pela_taxa(self):
        self.assertIn('i.dataset.unitUsd', self.js)
        self.assertIn('valUsd = ok * unitUsd', self.js)

    def test_a_faixa_da_marca_usa_innerHTML(self):
        """`textContent` engoliria o `<span>` do ¥ — a faixa ficaria só com o
        US$ enquanto as linhas dela mostram os dois."""
        self.assertNotIn("eVal.textContent = ", self.js)

    def test_o_rodape_tem_alvo_proprio_para_cada_moeda(self):
        """O `escreverNumero` escreve no ÚLTIMO nó de TEXTO da célula. Com o
        span do ¥ no fim, o último nó deixa de ser texto e ele acrescentaria um
        número solto depois do span."""
        self.assertIn('id="t-pagar-usd"', self.js)
        self.assertIn('id="t-pagar-rmb"', self.js)
        self.assertNotIn("escreverNumero(elPagar,", self.js)


class EstiloTests(TestCase):

    def test_a_moeda_secundaria_e_mais_apagada_que_um_span_comum(self):
        css = _ler(CSS)
        self.assertIn('.dtab .v span.cy,.dtab .n span.cy{color:var(--faint)}',
                      css)

    def test_a_regra_do_cy_vem_DEPOIS_da_regra_geral_do_span(self):
        """As duas valem 0,3,1. Empate de especificidade decide pela ordem —
        subir o `.cy` no arquivo apaga o efeito sem erro nenhum."""
        css = _ler(CSS)
        geral = css.find('.dtab .v span:not(.wtc-pop)')
        cy = css.find('.dtab .v span.cy')
        self.assertNotEqual(geral, -1)
        self.assertNotEqual(cy, -1)
        self.assertLess(geral, cy)


class RegistroLegadoTests(_Base):
    """Compra anterior ao sistema: o valor vive no cabeçalho e as linhas não
    têm ¥. O par não pode inventar um US$ ali."""

    def test_o_legado_continua_com_travessao(self):
        SalesOrderLine.all_companies.filter(order=self.so).update(
            unit_rmb=None, unit_usd=None)
        html = self._html()
        self.assertIn('—', html)
        self.assertNotIn('US$ None', html)
        self.assertNotIn('¥ None', html)
