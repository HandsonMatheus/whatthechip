# -*- coding: utf-8 -*-
"""
O TIPO DO CABEÇALHO DA `.dtab` (dono, 2026-09-02).

  "tanto a fonte como o tamanho da fonte de todos os titulos da tabela no
   sistema esta extremamente inconsistente e nao segue o design dessa pagina"

Ele estava certo, e a causa é uma linha de especificidade:

    .dtab th  →  0,1,1   (elemento + elemento)
    .dtab .n  →  0,2,0   (elemento + classe)   ← ganha

`.dtab .n`, `.v` e `.c` descrevem o CONTEÚDO de uma célula: mono 14px,
tabular-nums. Aplicadas a um `<th class="n">`, atropelam o tipo de TÍTULO
(mono 10,5px, `letter-spacing:.12em`, caixa alta). Na mesma fileira, "TIPO"
saía pequeno e "ENVIADOS" grande, porque só o segundo leva `.n`.

⚠ Não é divergência do design: as regras de célula do `components.css` do app
  são IDÊNTICAS às do `design_v2/dist`. O protótipo nunca mostrou o defeito
  porque lá o `<th>` numérico leva `num` — classe sem estilo nenhum. Quem
  escreveu os nossos reusou a classe da CÉLULA no título.

O conserto na raiz seria renomear `th.n` para `th.num`. Não dá em bloco:
`th.n` é convenção viva em `.ptab`, `.sst`, `.rt--dense` e `.pr__t`, onde
alinha à direita. A regra de reposição resolve na `.dtab` e não encosta nas
outras.
"""

import io
import os
import re
from glob import glob

from django.conf import settings
from django.test import TestCase

CSS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'components.css')
DIST = os.path.join(settings.BASE_DIR, 'design_v2', 'dist',
                    'whatthechip-ds', 'components.css')
REPOSICAO = '.dtab th.n,.dtab th.v,.dtab th.c'


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def _tamanho(css, seletor):
    """O `font-size` do seletor.

    Percorre TODAS as regras daquele seletor e devolve a primeira que declara
    corpo. Pegar só a primeira ocorrência não serve: `.dtab th` aparece antes
    dentro do bloco de tema escuro (`[data-theme="dark"] .dtab th{color:#fff}`),
    que não fala de corpo nenhum — e o teste passaria comparando None com None,
    que é o jeito mais silencioso de não testar nada.
    """
    for m in re.finditer(re.escape(seletor) + r'\{([^}]*)\}', css):
        t = re.search(r'font-size:([^;}]+)', m.group(1))
        if t:
            return t.group(1).strip()
    return None


def _classes_de_th():
    """Toda classe que aparece num `<th>` em qualquer template do projeto."""
    achadas = set()
    for arq in glob(os.path.join(settings.BASE_DIR, '*', 'templates', '**',
                                 '*.html'), recursive=True):
        for atributo in re.findall(r'<th[^>]*class="([^"]*)"', _ler(arq)):
            achadas.update(c for c in atributo.split() if c)
    return achadas


class CabecalhoTests(TestCase):

    def setUp(self):
        self.css = _ler(CSS)

    def test_existe_a_reposicao_para_o_th(self):
        self.assertIn(REPOSICAO + '{', self.css)

    def test_o_titulo_tem_o_corpo_do_th_e_nao_o_da_celula(self):
        """A trava contra os dois andarem separados: se alguém mudar o corpo
        do `.dtab th` e esquecer da reposição, os títulos voltam a ter dois
        tamanhos na mesma fileira — só que agora ao contrário."""
        base = _tamanho(self.css, '.dtab th')
        self.assertIsNotNone(base, 'o .dtab th perdeu o font-size')
        self.assertEqual(_tamanho(self.css, REPOSICAO), base,
                         'a reposição saiu de sincronia com o .dtab th')
        self.assertNotEqual(base, _tamanho(self.css, '.dtab .n'),
                            'se célula e título tiverem o mesmo corpo, esta '
                            'reposição virou inútil — apague-a em vez de '
                            'manter regra morta')


class TodaClasseUsadaEmThTests(TestCase):
    """O teste que pega o PRÓXIMO caso, não este.

    O risco não é toda classe da folha — é a classe que define TIPO sob
    `.dtab` **e** é usada num `<th>` de verdade. `.act`, `.wtc`, `.cap` e
    companhia também definem corpo, mas vivem em spans dentro da célula;
    exigir reposição para elas encheria a folha de regra que não protege
    nada. A interseção com o markup real é o que importa.
    """

    def test_nenhuma_classe_de_celula_fica_solta_num_th(self):
        css = _ler(CSS)
        com_tipo = set(re.findall(r'\.dtab \.([a-z]+)\{[^}]*font-size', css))
        em_th = _classes_de_th()
        repostas = set(re.findall(r'\.dtab th\.([a-z]+)', css))
        faltando = sorted((com_tipo & em_th) - repostas)
        self.assertFalse(
            faltando,
            'estas classes definem tipo de célula sob .dtab E são usadas num '
            '<th>: %s. Cada uma vence o `.dtab th` por especificidade, e o '
            'título sai com corpo de célula. Acrescente-as à reposição.'
            % faltando)

    def test_o_markup_do_projeto_ainda_usa_n_no_th(self):
        """Documenta por que a reposição existe. No dia em que todos os `<th>`
        numéricos virarem `num` — como no protótipo —, este teste cai e a
        reposição pode ser apagada junto."""
        self.assertIn('n', _classes_de_th(),
                      'nenhum <th> usa mais `n`: a reposição virou regra '
                      'morta, apague-a e apague este teste')


class OrigemDoDefeitoTests(TestCase):
    """Documenta a origem, para o conserto não se perder numa ressincronia."""

    def test_as_regras_de_celula_sao_as_do_design(self):
        if not os.path.exists(DIST):
            self.skipTest('o dist do design não está nesta árvore')
        css, dist = _ler(CSS), _ler(DIST)
        for classe in ('n', 'v', 'c'):
            self.assertEqual(_tamanho(dist, '.dtab .%s' % classe),
                             _tamanho(css, '.dtab .%s' % classe),
                             'a regra de célula .%s divergiu do design — o '
                             'defeito era compartilhado, o conserto não pode '
                             'virar divergência' % classe)

    def test_a_reposicao_e_nossa_e_nao_do_dist(self):
        """Se o dist ganhar a reposição, a nossa vira duplicata: traga a de lá
        e apague esta, para não existirem duas fontes da mesma regra."""
        if not os.path.exists(DIST):
            self.skipTest('o dist do design não está nesta árvore')
        self.assertNotIn('.dtab th.n', _ler(DIST))
