# -*- coding: utf-8 -*-
"""
AS MEDIDAS DA TABELA DA CONFERÊNCIA — auditoria contra o design system.

Dono, 07/09: *"aproveita q estamos mexendo tanto na tabela e confere se as
medidas e tamanho estao de acordo com o design system"*.

A auditoria foi feita no NAVEGADOR (Chromium, `getComputedStyle` e
`getBoundingClientRect` sobre a ficha renderizada), não lendo o CSS. Os
números abaixo são os MEDIDOS, e batem com os tokens:

    linha de dado ....... 48px   `--row-h` (a linha lg do Carbon)
    cabeçalho ........... 44px   `.dtab th`
    faixa de marca ...... 44px   `.dtab tbody tr.g td`
    rodapé .............. 48px   `--row-h`
    campo de recusa ..... 40px   `--ctl-sm` (= `--cds-field`)
    padding de célula ... 0 16px em tudo
    th .................. mono 10.5px 600, ls .12em, caixa alta
    td texto ............ sans 13px 400
    td.n ................ mono 14px 500 tabular-nums
    td.v ................ mono 14px 600 tabular-nums
    faixa td ............ sans 12px 700 · faixa td.n/.v mono 13px 700
    rodapé td.n/.v ...... mono 14px 600

DUAS DIVERGÊNCIAS ENCONTRADAS, as duas corrigidas no mesmo commit:

  1. O RODAPÉ saía em peso 500. `.dtab tfoot td` pede 600 e vale (0,1,2);
     `.dtab .n` vale (0,2,0) e ganhava. A linha de TOTAL ficava mais leve que
     o `.v` das linhas que ela soma e que os 700 da faixa — hierarquia
     invertida. Só apareceu porque foi MEDIDO: lendo o arquivo, a regra do
     rodapé diz 600.

  2. `patterns/ficha.css` trazia o bloco INTEIRO do `.rjin` (34px, mono 14, à
     direita, `--red-70`) e nada daquilo valia: o `.rjin` só existe dentro da
     `.dtab`, e lá o `.dtab .rjin` do pacote (0,2,0) ganha do `.rjin` (0,1,0)
     em toda propriedade compartilhada. Um segundo desenho, plausível na
     leitura, sem efeito nenhum. Saiu; o campo continua idêntico.

DIVERGÊNCIA CONHECIDA E NÃO CORRIGIDA — o ALINHAMENTO dos números:

    tela ......... à ESQUERDA (o pacote é explícito: "cabeçalho grafite, sem
                   borda vertical, TUDO à esquerda")
    planilha ..... à DIREITA (convenção do Excel, e é onde a vírgula alinha)

As duas estão certas para o lugar delas, e mudar qualquer uma é decisão do
dono — está registrado aqui para não virar descoberta de novo daqui a um mês.
"""

import io
import os
import re

from django.conf import settings
from django.test import TestCase

WTC = os.path.join(settings.BASE_DIR, 'static', 'wtc')
CSS = os.path.join(WTC, 'components.css')
FICHA_CSS = os.path.join(WTC, 'patterns', 'ficha.css')
PARCEIRO = os.path.join(WTC, 'patterns', 'parceiro.css')
CONTROLES = os.path.join(WTC, 'tokens', 'controls.css')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def _sem_comentarios(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _desktop(css):
    """O CSS ANTES do primeiro bloco de telefone.

    A `.dtab` vira cartão abaixo de 600px e reescreve altura, padding e
    tipografia de propósito. Auditar o arquivo inteiro faria o cartão reprovar
    por não ser a tabela — que é o oposto do que ele é.
    """
    corte = css.find('@media(max-width:600px)')
    return css if corte == -1 else css[:corte]


class TokensTests(TestCase):
    """Os números vêm de token, não de hex solto no meio da folha."""

    def test_a_linha_da_tabela_e_a_linha_lg_do_carbon(self):
        self.assertIn('--row-h:48px;', _ler(CONTROLES))

    def test_a_altura_do_campo_e_o_degrau_field(self):
        self.assertIn('--ctl-sm:var(--cds-field);', _ler(CONTROLES))


class GeometriaTests(TestCase):
    """O que a tabela mede, e de onde cada medida sai."""

    def setUp(self):
        self.css = _desktop(_ler(CSS))

    def test_a_linha_de_dado_usa_o_token_e_nao_um_numero(self):
        self.assertIn('.dtab td{padding:0 16px;height:var(--row-h);',
                      self.css)

    def test_o_campo_de_recusa_usa_o_token(self):
        self.assertIn('height:var(--ctl-sm)', self.css)

    def test_o_rodape_tem_a_altura_da_linha(self):
        self.assertIn('.dtab tfoot td{position:sticky;bottom:0;z-index:2;'
                      'height:var(--row-h);', self.css)

    def test_o_cabecalho_e_a_faixa_sao_44(self):
        """Os dois são "linha que não é dado" e medem igual — 44 contra os 48
        do dado. É o que faz a tabela ter três alturas e não seis."""
        self.assertIn('height:44px', self.css)
        self.assertIn('.dtab tbody tr.g td{height:44px;', self.css)


class TipografiaTests(TestCase):

    def setUp(self):
        self.css = _desktop(_ler(CSS))

    def test_numero_e_mono_e_tabular(self):
        """`tabular-nums` não é enfeite: sem ele os dígitos têm larguras
        diferentes e a coluna de dinheiro deixa de alinhar na vírgula."""
        for classe, peso in (('n', '500'), ('v', '600')):
            self.assertIn(
                '.dtab .%s{font-family:var(--mono);font-size:14px;'
                'font-weight:%s;white-space:nowrap;'
                'font-variant-numeric:tabular-nums}' % (classe, peso),
                self.css)

    def test_o_rodape_NAO_fica_mais_leve_que_o_que_ele_soma(self):
        """A divergência nº 1 da auditoria. `.dtab .n` vale (0,2,0) e o
        rodapé (0,1,2): a linha de TOTAL saía em 500, mais leve que o `.v`
        das linhas dela e que os 700 da faixa. (0,2,2) devolve o 600.
        """
        self.assertIn('.dtab tfoot td.n,.dtab tfoot td.v{font-weight:600}',
                      self.css)
        rodape = self.css.find('.dtab tfoot td{')
        correcao = self.css.find('.dtab tfoot td.n,.dtab tfoot td.v')
        self.assertNotEqual(rodape, -1)
        self.assertLess(rodape, correcao)


class SemSegundoDesenhoTests(TestCase):
    """A divergência nº 2, e a regra que ela vira.

    Uma medida escrita DUAS vezes em folhas diferentes é uma que vai divergir
    — e a que perde na cascata some sem erro nenhum, o que é a pior forma:
    quem lê o arquivo acredita nela.
    """

    def test_o_campo_de_recusa_tem_UMA_definicao_de_geometria(self):
        ficha = _sem_comentarios(_ler(FICHA_CSS))
        self.assertNotIn('.rjin{', ficha,
                         'voltou um segundo desenho do campo em ficha.css — '
                         'o `.dtab .rjin` do pacote ganha dele e ele não '
                         'pinta nada')
        self.assertIn('.dtab .rjin,.dtab .cell{', _ler(CSS))

    def test_o_que_SOBROU_em_ficha_css_e_o_que_esta_vivo(self):
        """O `:hover` do campo: o pacote não tem `.dtab .rjin:hover`, então
        esta linha é a única que pinta a borda ao passar o mouse."""
        self.assertIn('.rjin:hover{border-color:var(--red-50)}',
                      _ler(FICHA_CSS))
        self.assertNotIn('.dtab .rjin:hover', _ler(CSS))

    def test_a_folha_do_parceiro_nao_redesenha_a_tabela_no_desktop(self):
        """`patterns/parceiro.css` só toca na `.dtab--conf` DENTRO dos blocos
        de telefone, onde a tabela vira cartão. Uma altura ou um corpo de
        letra fora dali seria um segundo desenho da mesma tabela."""
        for linha in _desktop(_ler(PARCEIRO)).split('\n'):
            if '.dtab--conf' not in linha or linha.lstrip().startswith('/*'):
                continue
            self.assertNotRegex(
                linha, r'(height|font-size):',
                'parceiro.css redesenha a tabela fora do bloco de telefone')
