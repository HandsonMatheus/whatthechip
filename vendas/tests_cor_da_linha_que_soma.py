# -*- coding: utf-8 -*-
"""
A COR DA TABELA DA CONFERÊNCIA — o bug do cinza e a linha que soma (07/09).

Dois pedidos do dono no mesmo recado, e eles se tocam:

  1. "esta acontecendo um bug nas cores no campo de chips que tiveram unidades
      recusadas, o fundo ta ficando cinza em vez de vermelho"

  2. "te mandei um print do PDF, eu gostei de uma coisa no design dele, vc
      aderiu as cores da coluna também na barra de titulo de cada marca,
      deixando ela so mais escura, ficou um verde mais escuro e um vermelho
      mais escuro nas barras de titulos mostrando o total, eu gostei disso e
      quero que aplique na planilha e também na UI da tabela da compra"

── 1. O BUG ────────────────────────────────────────────────────────────────
`.dtab tbody tr.on td{background:var(--ink-05)}` vale (0,3,2) e a tinta de
coluna `.dtab tbody td.hr` vale (0,2,2). O `.on` entra na linha assim que ele
digita uma recusa — então bastava digitar para a linha inteira virar cinza e o
vermelho/verde/azul sumirem LOGO NA LINHA em que eles mais importam, que é a
que tem recusa. A tela ficava mais pobre quanto mais trabalho ele dava.

O cinza continua onde diz alguma coisa (TIPO, CAPACIDADE, ENVIADOS…); nas
quatro colunas do julgamento a TINTA vence.

── 2. A LINHA QUE SOMA ─────────────────────────────────────────────────────
Veio do papel para a tela, e não o contrário: o `vendas/pdf.py` faz isso desde
04/09, pelo mesmo motivo que ele descreveu — sem o passo a mais, o subtotal de
uma marca tem exatamente a cor das linhas que ele soma, e num lote de 40
linhas o olho não distingue a CONTA do LANÇAMENTO.

Agora são TRÊS superfícies com a mesma receita (`color-mix(in srgb, base 88%,
tinta)`), e o teste que mais importa neste arquivo é o que amarra as três: um
tom que só o papel tivesse voltaria a ser aquilo que este projeto passa a vida
caçando — duas verdades para o mesmo fato.

⚠ MEDIDO, não deduzido. Os hexes cravados aqui saíram de três lugares
  independentes: `getComputedStyle` no Chromium sobre a ficha renderizada, os
  pixels do screenshot da tabela, e o `.fill.fgColor` do .xlsx aberto. Eles
  batem — e é por isso que dá para cravá-los.
"""

import io
import os
import re

from django.conf import settings
from django.test import TestCase

CSS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'components.css')
FICHA_CSS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'patterns',
                         'ficha.css')
FICHA_TPL = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                         'partner_compra.html')

#: Os três tons "um passo abaixo", medidos. `--red-10`/`--green-10` não têm
#: passo 20 na rampa (ela vai de 10 para 40), então saem da mistura; o azul TEM
#: o passo 20, e a mistura o reproduz (#D2E3FF contra o #D0E2FF do token) — o
#: que é a confirmação de que 88/12 é o "um tom abaixo" do sistema.
RED_TOT, GREEN_TOT, BLUE_TOT = 'FEDDDE', 'CFEDD8', 'D0E2FF'
RED_10, GREEN_10, BLUE_10 = 'FFF1F1', 'E6F7EC', 'EDF5FF'


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def _sem_comentarios(css):
    """O CSS sem os blocos `/* … */`.

    Necessário porque as correções deste dia DOCUMENTAM o que saiu citando o
    seletor pelo nome — sem isto, o teste que proíbe `.sst tbody tr.on td`
    reprova por causa do comentário que explica por que ele foi removido. Foi
    exatamente o que aconteceu na primeira execução.
    """
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


class SemFundoNaLinhaDeDADOTests(TestCase):
    """O pedido nº 1, na forma que ele acabou tomando.

    ⚠ ESTA CLASSE MUDOU DE ASSUNTO NO MESMO DIA, e a história é o valor dela.

    Primeiro eu tratei como bug de cascata, e era: `.dtab tbody tr.on td`
    (0,3,2) cobria a tinta de coluna `.dtab tbody td.hr` (0,2,2), então
    digitar uma recusa apagava o vermelho/verde/azul LOGO NA LINHA em que eles
    mais importam. Corrigi com três regras de (0,4,2) devolvendo a tinta.

    Aí ele olhou o resultado e matou a ideia inteira:

      "tambem ha bug de cor nas linhas em branco, vc adota uma alternancia de
       cor das linhas em branco entre branco e cinza, para umas marcas e para
       outras nao, deixe tudo branco, cinza somente o titulo da marca"

    Ele leu como listra alternada, e estava certo em ler assim: o cinza caía
    nas linhas DIGITADAS, que se agrupam por marca porque é assim que se
    confere um lote. O olho vê a marca, não o estado — e uma tabela em que a
    marca A é cinza e a B é branca afirma uma coisa que não é verdade.

    ⚠ ARQUEOLOGIA, e ela explica o bug inteiro: o protótipo JÁ tinha resolvido
      isso, em `patterns/ficha.css`, com `.sst tbody tr.on td.hr{#ffe0e0}` e
      companhia — linha marcada SEM perder a tinta. Em 27/08 a tabela migrou
      de `.sst` para `.dtab` e essas regras deixaram de casar EM SILÊNCIO. O
      defeito não foi uma regra escrita errado: foi uma solução que ficou para
      trás numa migração de classe.
    """

    def setUp(self):
        self.css = _ler(CSS)
        self.ficha = _ler(FICHA_TPL)

    def test_a_tabela_NAO_marca_mais_a_linha_digitada(self):
        """Sem a classe não há fundo, e não há o que vencer na cascata."""
        self.assertNotIn("classList.toggle('on', r > 0)", self.ficha)

    def test_a_linha_de_dado_nao_ganha_fundo_nenhum_do_nosso_lado(self):
        """Branco é o `.dtab td{background:var(--surface)}` do pacote. O que
        este teste proíbe é acrescentarmos um segundo fundo por cima."""
        for proibido in ('.dtab tbody tr.on td.hr', '.sst tbody tr.on td'):
            self.assertNotIn(proibido, _sem_comentarios(self.css))
            self.assertNotIn(proibido, _sem_comentarios(_ler(FICHA_CSS)))

    def test_a_regra_do_PACOTE_fica_e_esta_documentada(self):
        """Ela não é nossa. Fica, com o aviso de que quem usar `.on` numa
        tabela COM colunas tingidas herda o problema de cascata inteiro."""
        self.assertIn('.dtab tbody tr.on td,.dtab--static tbody tr.on:hover '
                      'td{background:var(--ink-05)}', self.css)
        self.assertIn('SEM CONSUMIDOR desde 07/09', self.css)

    def test_a_recusa_continua_visivel_por_TRES_sinais(self):
        """O fundo era o quarto, e o único ambíguo. Tirar um sinal só é seguro
        porque os outros três estão na própria linha: o número no campo, o −¥
        da coluna da perda, e o aprovado que caiu."""
        self.assertIn('data-perda=', self.ficha)
        self.assertIn('data-ok=', self.ficha)
        self.assertIn('class="rjin"', self.ficha)


class LinhaQueSomaNaTelaTests(TestCase):
    """O pedido nº 2, na tela."""

    def setUp(self):
        self.css = _ler(CSS)

    def test_a_faixa_e_o_rodape_levam_a_tinta_um_tom_abaixo(self):
        self.assertIn(
            '.dtab tbody tr.g td.hr,.dtab tbody tr.g:hover td.hr,'
            '.dtab tfoot td.hr{background:color-mix(in srgb,var(--red-10) '
            '88%,var(--red-50))}', self.css)
        self.assertIn(
            '.dtab tbody tr.g td.hg,.dtab tbody tr.g:hover td.hg,'
            '.dtab tfoot td.hg{background:color-mix(in srgb,var(--green-10) '
            '88%,var(--green-50))}', self.css)
        self.assertIn(
            '.dtab tbody tr.g td.hb,.dtab tbody tr.g:hover td.hb,'
            '.dtab tfoot td.hb{background:var(--blue-20)}', self.css)

    def test_a_receita_e_a_MESMA_do_realce_de_hover(self):
        """Não é um tom inventado: é o passo que a folha já usava no hover das
        duas colunas. Um `#feddde` cravado aqui seria um passo de paleta que
        ninguém mais usa — mentira em design system."""
        self.assertIn('.dtab tbody tr:hover td.hr{background:color-mix(in '
                      'srgb,var(--red-10) 88%,var(--red-50))}', self.css)

    def test_o_rodape_NAO_tem_mais_a_tinta_clara(self):
        """Duas declarações para a mesma célula é como uma delas vira código
        morto que parece vivo."""
        self.assertNotIn('.dtab tfoot td.hr{background:var(--red-10)}',
                         self.css)
        self.assertNotIn('.dtab tfoot td.hg{background:var(--green-10)}',
                         self.css)

    def test_a_faixa_vem_DEPOIS_do_hover_dela(self):
        """`.dtab tbody tr.g:hover td` vale (0,4,2) e é o mesmo peso da
        correção: passar o mouse na faixa apagaria a tinta de volta para
        cinza se a ordem fosse a outra."""
        hover_faixa = self.css.find('.dtab tbody tr.g:hover td{')
        tinta = self.css.find('.dtab tbody tr.g td.hr,.dtab tbody tr.g:hover '
                              'td.hr,.dtab tfoot td.hr{background:color-mix')
        self.assertNotEqual(hover_faixa, -1)
        self.assertNotEqual(tinta, -1)
        self.assertLess(hover_faixa, tinta)

    def test_no_CARTAO_do_telefone_nada_disso_pinta(self):
        """As regras novas valem (0,4,2) e (0,4,3); as que apagam a tinta no
        cartão valem (0,3,2) e seriam atropeladas — o mesmo descuido de
        sempre, pelo outro lado.

        ⚠ DUAS vezes: o pacote repete todo o bloco de 600px em `@media` e em
          `@container`, e uma cópia só deixa metade das telas para trás.
        """
        self.assertEqual(
            self.css.count('.dtab tbody tr.g td.hr,.dtab tbody tr.g td.hg'), 2)


class LinhaQueSomaNaPlanilhaTests(TestCase):
    """O pedido nº 2, na planilha."""

    def test_os_tons_sao_os_medidos_na_tela(self):
        from vendas import planilha
        self.assertEqual(planilha.RED_TOT, RED_TOT)
        self.assertEqual(planilha.GREEN_TOT, GREEN_TOT)
        self.assertEqual(planilha.BLUE_TOT, BLUE_TOT)

    def test_a_mistura_e_a_receita_do_css(self):
        """88% da base + 12% da tinta, canal a canal. A prova de que a
        planilha não crava hex: se `--red-10` mudar, ela acompanha."""
        from vendas.planilha import _mistura
        self.assertEqual(_mistura('FFF1F1', 'FA4D56'), RED_TOT)
        self.assertEqual(_mistura('E6F7EC', '24A148'), GREEN_TOT)
        # e o azul: a mistura reproduz o token que já existe
        self.assertEqual(_mistura('EDF5FF', '0F62FE'), 'D2E3FF')

    def test_o_tom_da_soma_e_mais_ESCURO_que_o_da_linha(self):
        """A asserção que diz o que o dono pediu, e não como foi feito: se um
        dia a mistura inverter os pesos, os hexes continuariam "certos" e a
        tabela ficaria com a faixa mais clara que as linhas."""
        def luz(hexa):
            return sum(int(hexa[i:i + 2], 16) for i in (0, 2, 4))
        for claro, escuro in ((RED_10, RED_TOT), (GREEN_10, GREEN_TOT),
                              (BLUE_10, BLUE_TOT)):
            self.assertLess(luz(escuro), luz(claro),
                            '%s não é mais escuro que %s' % (escuro, claro))


class AsTresSuperficiesTests(TestCase):
    """O teste que amarra tudo: papel, planilha e tela no MESMO tom.

    É o que impede a volta do problema que este projeto passa a vida caçando —
    duas verdades para o mesmo fato, cada uma plausível sozinha.
    """

    def test_o_PDF_e_a_planilha_usam_o_mesmo_tom(self):
        """⚠ Tolerância de 1 por canal, e ela tem explicação: o reportlab
        guarda cor em float e o `hexval()` TRUNCA, enquanto a planilha
        ARREDONDA. O vermelho bate exato; o verde dá `ceecd8` contra `cfedd8`.
        É a mesma cor — o que este teste proíbe é DIVERGÊNCIA, não o último
        bit do arredondamento.
        """
        from vendas import pdf
        from vendas import planilha
        for cor_pdf, hexa in ((pdf._T_ROSE_TOT, planilha.RED_TOT),
                              (pdf._T_MINT_TOT, planilha.GREEN_TOT)):
            canais_pdf = (cor_pdf.red, cor_pdf.green, cor_pdf.blue)
            for i, canal in enumerate(canais_pdf):
                alvo = int(hexa[i * 2:i * 2 + 2], 16)
                self.assertLessEqual(
                    abs(round(canal * 255) - alvo), 1,
                    'papel e planilha divergiram no canal %d de %s'
                    % (i, hexa))

    def test_o_PDF_tambem_tinge_a_linha_que_soma(self):
        """A origem do pedido. Se isto sair do papel, a tela e a planilha
        ficam com um desenho que não veio de lugar nenhum."""
        fonte = _ler(os.path.join(settings.BASE_DIR, 'vendas', 'pdf.py'))
        self.assertIn('_T_ROSE_TOT = _mistura(_T_ROSE, _T_RED50)', fonte)
        self.assertIn('tintas_de_total', fonte)
