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

    def _css(self):
        import io as _io, os
        from django.conf import settings
        return _io.open(os.path.join(settings.BASE_DIR, 'static', 'wtc',
                                     'components.css'), encoding='utf-8').read()

    def _csv(self, **params):
        r = self.client.get(reverse('compras:export_csv'), params)
        self.assertEqual(r.status_code, 200)
        return r.content.decode('utf-8-sig')

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
# (B2) A COLUNA NÃO É SUB-LINHA
# ═══════════════════════════════════════════════════════════════════════════
class TipografiaDaColunaTests(_Base):
    """"a fonte e o tamanho da fonte do valor está diferente e fora do padrão
    do resto da tabela" (dono, 2026-09-04).

    A 1ª versão embrulhava o número num `<span class="due">`, e span dentro de
    `.v` é SUB-LINHA por definição nesta folha: `display:block`, 11px, sans,
    `--muted`. O valor principal saía com corpo de rodapé ao lado do mesmo
    número em mono 14px na coluna Resultado.

    A cor mora na CÉLULA agora (`td.v.ha`), que herda `.dtab .v` inteiro.
    """

    def test_o_valor_nao_esta_dentro_de_um_span(self):
        import re
        self._faturar(self._ordem(1))
        corpo = self._tbody()
        m = re.search(r'<td class="v ha"[^>]*>(.*?)</td>', corpo, re.S)
        self.assertIsNotNone(m, 'a célula de A pagar sumiu')
        self.assertNotIn('<span', m.group(1),
                         'o valor voltou a ser sub-linha — vai sair 11px sans')

    def test_a_celula_leva_a_familia_ambar(self):
        self._faturar(self._ordem(1))
        self.assertIn('<td class="v ha"', self._tbody())

    def test_a_folha_pinta_a_celula_e_nao_o_span(self):
        import io as _io, os
        from django.conf import settings
        css = _io.open(os.path.join(settings.BASE_DIR, 'static', 'wtc',
                                    'components.css'), encoding='utf-8').read()
        self.assertIn('.dtab tbody td.ha{color:var(--amber-70)}', css)

    def test_sem_divida_o_travessao_nao_fica_ambar(self):
        """`.none` tem cor própria e vence: dívida que não existe não se pinta
        de cobrança."""
        self._ordem(1)
        self.assertIn('<span class="none">—</span>', self._tbody())


# ═══════════════════════════════════════════════════════════════════════════
# (B3) AS COLUNAS DE ESPERADO
# ═══════════════════════════════════════════════════════════════════════════
class RotuloEsperadoTests(_Base):
    """"mudar as colunas de TOTAL para ESPERADO" (dono, 2026-09-04).

    "Total" não dizia total de quê, e a mesma célula já se chamava "Esperado"
    no cartão do celular (`data-lbl`) desde 02/09 — a tela larga é que estava
    fora de passo consigo mesma.
    """

    def test_os_cabecalhos_dizem_esperado(self):
        html = self._lista().content.decode()
        cab = html[html.index('<thead>'):html.index('</thead>')]
        self.assertIn('Esperado ¥', cab)
        self.assertIn('Esperado US$', cab)
        self.assertNotIn('Total ¥', cab)
        self.assertNotIn('Total US$', cab)


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


# ═══════════════════════════════════════════════════════════════════════════
# (D) SELEÇÃO DE LINHAS — o pedaço que vive no SERVIDOR
# ═══════════════════════════════════════════════════════════════════════════
class SelecaoDeLinhasTests(_Base):
    """Checkbox por linha, no padrão do Odoo (dono, 2026-09-04):

      "conforme eu seleciono, o valor da última linha da tabela muda (...) e
       selecionando só alguns tbm posso exportar somente eles"

    O recálculo do rodapé é JAVASCRIPT e está coberto por um harness de DOM
    à parte — assertar soma em JS por HTML renderizado seria testar o
    navegador. O que vive no servidor, e é o que este arquivo trava, é:

      · a coluna de seleção existe e traz o dado que o JS soma;
      · o `ids` da URL RECORTA de verdade — senão "exportar só os marcados"
        seria uma promessa da interface que o download não cumpre;
      · e o `ids` não é uma porta: ele intersecta o que o comprador já podia
        ver, nunca amplia.
    """

    def test_a_coluna_de_selecao_existe_em_toda_linha(self):
        self._ordem(1)
        self._ordem(2)
        corpo = self._tbody()
        self.assertEqual(corpo.count('<td class="cbx">'), 2)
        self.assertEqual(corpo.count('type="checkbox" class="chk"'), 2)

    def test_a_linha_carrega_o_dado_que_o_rodape_soma(self):
        """⚠ O JS soma o DADO, nunca o texto desenhado: fazer parse de
        "US$ 8313.75" amarraria a conta à formatação e ao idioma."""
        inv = self._faturar(self._ordem(1))
        self._pagar(inv, D('40.00'))
        with company_scope(self.emp.id):
            inv.refresh_from_db()
        corpo = self._tbody()
        self.assertIn('data-res="%s"' % inv.total_usd, corpo)
        self.assertIn('data-due="%s"' % inv.balance_usd, corpo)

    def test_compra_sem_fatura_leva_zero_e_nao_vazio(self):
        """Zero soma sem caso especial; vazio viraria NaN no `parseFloat` e o
        rodapé inteiro sumiria por causa de uma linha sem resultado."""
        self._ordem(1)
        corpo = self._tbody()
        self.assertIn('data-res="0"', corpo)
        self.assertIn('data-due="0"', corpo)

    def test_a_folha_estiliza_a_caixa_e_o_alvo_de_44px(self):
        """"maior e mais no padrão do design system" (dono, 2026-09-04).

        `accent-color` e não caixa desenhada à mão: caixa desenhada custa foco,
        `indeterminate`, leitor de tela e teclado — tudo que o nativo dá de
        graça — e só se paga se o desenho exigir algo que o nativo não faz.
        Aqui o pedido era tamanho e cor.
        """
        css = self._css()
        self.assertIn('.dtab .cbx input[type=checkbox]{', css)
        trecho = css[css.index('.dtab .cbx input[type=checkbox]{'):][:180]
        self.assertIn('accent-color:var(--blue-60)', trecho)
        self.assertIn('18px', trecho)
        self.assertIn('.dtab td.cbx{cursor:pointer}', css)

    def test_o_clique_na_celula_de_selecao_nao_abre_a_compra(self):
        """A célula é um alvo de 44px e só 18px dela são `input`. Sem `.cbx` na
        guarda, clicar no respiro ao lado da caixa marcava a linha E abria a
        compra — alvo grande fazendo outra coisa é pior que alvo pequeno."""
        html = self._lista().content.decode()
        self.assertIn("closest('a,button,input,select,.cbx')", html)

    def test_a_linha_marcada_usa_o_sel_do_design_system(self):
        """`.sel` já existia na folha (inclusive nos blocos de celular) — a
        seleção veste a classe que o sistema já tinha em vez de inventar."""
        html = self._lista().content.decode()
        self.assertIn("classList.toggle('sel'", html)
        self.assertIn('.dtab tbody tr.sel td{background:var(--blue-10)}',
                      self._css())

    def test_o_fio_vertical_de_hover_saiu_do_componente(self):
        """"fica uma borda vertical na esquerda que é horrível, remova isso
        desta tabela, e da tabela padrão e de qualquer outro lugar com hover".

        ⚠ Some do COMPONENTE, então some de toda tabela do sistema — não é
          correção desta tela. O único `box-shadow` que fica na 1ª célula é o
          da variante de rolagem horizontal, e ele é outra coisa: a borda que
          separa a coluna grudada do que rola.
        """
        # ⚠ Sem os COMENTÁRIOS: o comentário que explica a remoção cita o
        #   `box-shadow` removido, e um assertNotIn na folha crua acusaria a
        #   prosa que documenta o conserto. Regra é regra; comentário é texto.
        import re as _re
        css = self._css()
        regras = _re.sub(r'/\*.*?\*/', '', css, flags=_re.S)
        self.assertNotIn('inset 3px 0 0 var(--blue-60)', regras)
        self.assertIn('.dtab__wrap--x .dtab tbody td:first-child', regras)
        trecho = regras[regras.index('.dtab__wrap--x .dtab tbody td:first-child'):][:160]
        self.assertIn('1px 0 0 var(--line-2)', trecho)

    def test_o_rodape_leva_os_dois_moldes_de_plural(self):
        """Gettext escolhe o plural no RENDER, então as duas formas têm de vir
        prontas do servidor — o JS só decide qual usar. Um molde só daria
        "Selecionadas · 1 compras"."""
        self._ordem(1)
        html = self._lista().content.decode()
        self.assertIn('data-sel1=', html)
        self.assertIn('data-seln=', html)
        self.assertIn('data-cheio=', html)

    # ── o `ids` RECORTA ──────────────────────────────────────────────────
    def test_o_csv_leva_so_as_marcadas(self):
        a = self._ordem(1)
        b = self._ordem(2)
        self._ordem(3)
        texto = self._csv(ids='%d,%d' % (a.pk, b.pk))
        self.assertIn(a.code, texto)
        self.assertIn(b.code, texto)
        linhas = [l for l in texto.lstrip('﻿').splitlines() if l]
        self.assertEqual(len(linhas), 3, 'cabeçalho + 2 marcadas')

    def test_sem_ids_o_csv_leva_o_recorte_inteiro(self):
        for n in (1, 2, 3):
            self._ordem(n)
        linhas = [l for l in self._csv().lstrip('﻿').splitlines() if l]
        self.assertEqual(len(linhas), 4, 'cabeçalho + 3')

    def test_ids_lixo_nao_derruba_nem_esvazia(self):
        """Saneamento por construção: só dígitos entram. `ids=abc` não casa
        com nada e devolveria zero linhas — o que é uma tela vazia, não um
        erro; `ids=` vazio não filtra."""
        self._ordem(1)
        self.assertEqual(self.client.get(
            reverse('compras:export_csv'), {'ids': ''}).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('compras:export_csv'), {'ids': "'; DROP TABLE"}).status_code,
            200)
        linhas = [l for l in self._csv().lstrip('﻿').splitlines() if l]
        self.assertEqual(len(linhas), 2)

    def test_o_ids_NAO_e_uma_porta_para_a_ordem_de_outro_comprador(self):
        """⚠ A trava de segurança da feature.

        O `ids` filtra o conjunto que o `orders_for_buyer` JÁ limitou — ele
        intersecta, nunca amplia. Uma OV de outro comprador citada no `ids`
        não aparece: não está no conjunto de partida.
        """
        from pricing.models import Buyer as _B
        outro = _B.all_companies.create(company=None, name='Outro',
                                        slug='outro-comprador')
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=99, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            alheia = SalesOrder(
                lot=lot, buyer=outro, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1400'), total_rmb=D('1000.00'),
                total_usd=D('140.00'), shipped_at=date(2026, 8, 18),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            alheia.save()
        minha = self._ordem(1)
        texto = self._csv(ids='%d,%d' % (minha.pk, alheia.pk))
        self.assertIn(minha.code, texto)
        self.assertNotIn(alheia.code, texto)
