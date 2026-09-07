# -*- coding: utf-8 -*-
"""
O DÓLAR DO HERÓI — bug GRAVE de 2026-09-07.

  "bug GRAVE encontrado, como é possivel eu ter rechazado chips e o resultado
   final em USD dar US$ 6246.12, contra US$ 6235.30 esperado? Está somando!"
                                                              — dono, 07/09

Ele recusou chips e o dólar SUBIU. Não estava somando: estavam sendo feitas
DUAS contas diferentes para o mesmo fato, uma ao lado da outra no mesmo cartão.

  ESPERADO  = `so.total_usd`, a SOMA dos `unit_usd` congelados linha a linha
              (`services.confirm`, que proíbe a outra conta com todas as
              letras: "NÃO total_rmb × taxa, que divergiria por arredondamento
              por linha").
  RESULTADO = era `pagar * fx` no JavaScript — o total em ¥ vezes a taxa.
              Exatamente a conta proibida.

No lote dele o grosso era DDR3 2Gb a ¥3: ¥3 × 0,1481 = 0,4443, que congela em
0,44. Cada unidade perde 0,0043 de dólar na soma congelada, e são milhares —
o total em ¥ vezes a taxa dava ~US$ 20 A MAIS que a soma das linhas. Recusar
¥63 de chips derrubava o dólar em 9,33, muito menos que os 20 de vantagem que
a conta errada já carregava. Resultado na tela: recusa que AUMENTA a conta.

⚠ E o `recalcular()` roda no CARREGAMENTO. O número já saía errado antes de
  ele digitar coisa alguma: o servidor escrevia 6235.30 no HTML e o script
  trocava por 6255.45 no mesmo instante.

Por que passou pelos testes: `tests_par_de_moedas` cobra a conta certa com
`assertIn` — "o JS lê `i.dataset.unitUsd`", "existe `valUsd = ok * unitUsd`".
Tudo verdade, e tudo continuava verdade com o `pagar * fx` cinco linhas
abaixo. Regra do tipo "NUNCA faça X" não se prova mostrando que Y existe: se
prova mostrando que X não existe, e melhor ainda RODANDO a tela.

Este arquivo faz os dois. As classes de leitura estática valem em qualquer
máquina; a `NavegadorTests` roda o script de verdade num DOM (jsdom) e pula
sozinha onde não houver node — nunca reprova por falta de ambiente.
"""

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from decimal import ROUND_HALF_UP, Decimal as D

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

FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def _sem_comentarios(js):
    """O arquivo SEM as linhas de comentário.

    Necessário porque a correção documenta o bug CITANDO a conta errada — sem
    isto o teste que proíbe `* fx` reprovaria justamente o comentário que
    explica por que `* fx` está proibido. Só linhas que COMEÇAM com `//` saem:
    cortar `//` no meio da linha estragaria qualquer `https://` do HTML.
    """
    return '\n'.join(l for l in js.split('\n')
                     if not l.lstrip().startswith('//'))


class _Base(TestCase):
    """Um lote em que as DUAS contas DIVERGEM — de propósito.

    ¥3,00 × 0,1481 = 0,4443, que congela em 0,44 (meio pra cima, como o
    `confirm`). Com 10.000 unidades:

        soma congelada  = 0,44 × 10.000       = US$ 4.400,00   ← a verdade
        ¥ × taxa        = ¥30.000 × 0,1481    = US$ 4.443,00   ← o bug

    US$ 43,00 de diferença, no mesmo cartão. Com um unitário "redondo" os dois
    números baterem esconderia o bug — é o caso REAL dele (¥3 a 0,1481) que
    está reproduzido aqui, em escala menor.
    """

    UNIT_RMB, FX = D('3.00'), D('0.1481')
    UNIT_USD = D('0.44')          # (3.00 × 0.1481).quantize(.01) — congelado
    QTD = 10000

    #: O que a conta ERRADA daria, sem recusa nenhuma. Escrito por extenso
    #: para o teste falhar dizendo o número, e não uma expressão.
    USD_PELA_TAXA = D('4443.00')
    USD_CONGELADO = D('4400.00')

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


class AsDuasContasDivergemTests(_Base):
    """Antes de cobrar a correção, PROVAR que o problema existe.

    Um teste que exige a conta certa não vale nada se, nos dados dele, as duas
    contas dão o mesmo número — passaria com o bug dentro. Esta classe é a
    prova de que o cenário montado acima realmente separa as duas.
    """

    def test_a_soma_congelada_nao_e_o_yuan_vezes_a_taxa(self):
        pela_taxa = (self.so.total_rmb * self.FX).quantize(
            D('0.01'), ROUND_HALF_UP)
        self.assertEqual(pela_taxa, self.USD_PELA_TAXA)
        self.assertEqual(self.so.total_usd, self.USD_CONGELADO)
        self.assertNotEqual(
            self.so.total_usd, pela_taxa,
            'o cenário não separa as duas contas — o teste ficaria cego')

    def test_o_erro_e_grande_o_bastante_para_doer(self):
        """US$ 43 num lote de US$ 4.400. Não é resíduo de centavo."""
        self.assertGreater(self.USD_PELA_TAXA - self.so.total_usd, D('40'))

    def test_recusar_pela_conta_errada_ainda_ficava_ACIMA_do_esperado(self):
        """O sintoma que ele viu, reproduzido em números.

        Recusa de 50 unidades (¥150) — a mesma ORDEM DE GRANDEZA da dele:
        ¥63 num lote de ¥42.238. Pela conta certa o dólar CAI. Pela errada ele
        cai também, mas de um patamar tão inflado que continua ACIMA do
        ESPERADO ao lado. Foi isto que ele leu como "está somando".

        ⚠ A recusa tem de ser pequena, e isso não é conveniência: com 300
        unidades (3% do lote) até a conta errada já cai abaixo do esperado, e
        o teste passaria sem reproduzir sintoma nenhum. A primeira versão
        deste arquivo usava 300 e reprovou aqui — foi o teste dizendo que o
        cenário não provava o que dizia provar.
        """
        rej = 50
        certo = self.UNIT_USD * (self.QTD - rej)                  # 4.378,00
        errado = (self.UNIT_RMB * (self.QTD - rej) * self.FX).quantize(
            D('0.01'), ROUND_HALF_UP)                             # 4.420,79
        self.assertLess(certo, self.so.total_usd)          # recusa faz CAIR
        self.assertGreater(errado, self.so.total_usd,      # …mas subia
                           'a reprodução falhou: o cenário não mostra o '
                           'resultado ficando ACIMA do esperado')


class OScriptTests(TestCase):
    """A leitura do JS. Estes rodam em qualquer lugar e são o portão."""

    def setUp(self):
        self.js = _sem_comentarios(_ler(FICHA))

    def test_o_recalculo_NAO_multiplica_nada_pela_taxa(self):
        """A regra do `confirm`, cobrada onde ela foi quebrada.

        `assertNotIn`, e não `assertIn` de outra coisa: era exatamente essa
        troca que deixava o bug passar por `tests_par_de_moedas`.
        """
        for proibido in ('pagar * fx', 'pagar*fx', '* fx)', '*fx)'):
            self.assertNotIn(
                proibido, self.js,
                'US$ derivado da taxa no recálculo ao vivo — a conta que o '
                '`services.confirm` proíbe (bug de 2026-09-07)')

    def test_nao_existe_taxa_no_escopo_do_recalculo(self):
        """Sem a variável não há como reintroduzir a conta por descuido.

        A taxa segue no `data-fx` do form (é o câmbio TRAVADO desta OV e o
        papel a declara) — o que não existe mais é ela virar número no laço
        que soma dinheiro.
        """
        self.assertNotIn('var fx = parseFloat(form.dataset.fx)', self.js)

    def test_o_heroi_escreve_a_MESMA_variavel_do_rodape(self):
        """Um número só, escrito em dois lugares. Duas variáveis é como o
        cartão passa a discordar do rodapé da tabela na mesma tela."""
        self.assertIn("kUsd.textContent = temUsd ? 'US$ ' + pagarUsd", self.js)
        self.assertIn("elPagarUsd.textContent = 'US$ ' + pagarUsd", self.js)

    def test_o_total_em_usd_e_somado_linha_a_linha(self):
        self.assertIn('valUsd = ok * unitUsd', self.js)
        self.assertIn('pagarUsd += valUsd', self.js)

    def test_linha_sem_usd_congelado_vira_travessao_e_nao_zero(self):
        """§2.7: número que falta não se chuta — e muito menos se soma como 0,
        que sairia MENOR que a verdade, calado e plausível."""
        self.assertIn('var temUsd = true', self.js)
        self.assertIn('if (!(unitUsd > 0)) temUsd = false', self.js)
        self.assertIn("temUsd ? 'US$ ' + pagarUsd.toFixed(2) : '—'", self.js)


class OServidorTests(_Base):
    """O outro lado do cartão: o ESPERADO que o servidor manda."""

    def test_o_esperado_do_heroi_e_a_soma_congelada(self):
        with company_scope(self.emp.id):
            r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertEqual(r.context['esperado_usd'], self.USD_CONGELADO)

    def test_o_html_abre_com_o_valor_congelado_nos_DOIS_lugares(self):
        """Herói e rodapé têm de nascer iguais. Se já nascem diferentes, o JS
        não tem como consertar depois."""
        html = self._html()
        self.assertIn('US$ 4400.00', html)
        self.assertNotIn('US$ 4443.00', html)


class VarreduraTests(TestCase):
    """A pergunta dele: "tem que ver se não se propagou em outros pontos".

    A resposta foi NÃO — nenhum valor GRAVADO usava a conta errada; era só a
    tela. Este teste é o que mantém a resposta verdadeira amanhã.
    """

    def test_o_total_da_OV_e_a_soma_das_linhas_congeladas(self):
        fonte = _ler(os.path.join(settings.BASE_DIR, 'vendas', 'services.py'))
        self.assertIn('total_usd += line.unit_usd * line.quantity', fonte)
        self.assertNotIn('so.total_usd = (total_rmb *', fonte)

    def test_a_fatura_soma_por_linha_e_nao_o_total_pela_taxa(self):
        fonte = _ler(os.path.join(settings.BASE_DIR, 'vendas', 'services.py'))
        self.assertIn('total_usd += unit_usd * qty', fonte)
        self.assertNotIn('total_usd = (total_rmb * rate)', fonte)

    def test_a_planilha_soma_o_usd_congelado_coluna_por_coluna(self):
        """O XLSX faz a mesma conta por construção: SUMPRODUCT(aceitos ×
        unit_usd congelado), nunca resultado_em_yuan × taxa."""
        fonte = _ler(os.path.join(settings.BASE_DIR, 'vendas', 'planilha.py'))
        self.assertIn('SUMPRODUCT', fonte)

    def test_nenhum_template_converte_um_TOTAL_pela_taxa(self):
        """Varredura de verdade, não de um arquivo só.

        `_rmb_de` e a caixa de pagamento fazem o caminho INVERSO (US$ → ¥) e
        são leitura derivada declarada (§2.4): dividem, não multiplicam.
        """
        raiz = os.path.join(settings.BASE_DIR, 'vendas', 'templates')
        achados = []
        for dirpath, _dirs, arquivos in os.walk(raiz):
            for nome in arquivos:
                if not nome.endswith('.html'):
                    continue
                caminho = os.path.join(dirpath, nome)
                for n, linha in enumerate(_sem_comentarios(
                        _ler(caminho)).split('\n'), 1):
                    if re.search(r'\*\s*fx\b|\bfx\s*\*', linha):
                        achados.append('%s:%d' % (nome, n))
        self.assertEqual(achados, [], 'multiplicação pela taxa em: %s'
                                      % ', '.join(achados))


# ── O HARNESS DE NAVEGADOR ───────────────────────────────────────────────────
HARNESS = os.path.join(settings.BASE_DIR, 'vendas', 'tests_js', 'heroi.mjs')

#: Onde procurar o `jsdom`. Ele não é dependência do projeto — o Django não
#: precisa dele para rodar, e exigir node de quem só quer subir o servidor
#: seria trocar um teste por um obstáculo. Sem ele a classe PULA; o portão de
#: verdade continua sendo o `OScriptTests`, que roda em qualquer lugar.
_NODE_PATHS = [
    os.path.join(settings.BASE_DIR, 'node_modules'),
    '/tmp/node_modules',
    os.environ.get('NODE_PATH') or '',
]


def _node_com_jsdom():
    """`(executável, NODE_PATH)` se der para rodar o harness; senão None."""
    node = shutil.which('node')
    if not node:
        return None
    for caminho in _NODE_PATHS:
        if not caminho:
            continue
        env = dict(os.environ, NODE_PATH=caminho)
        try:
            r = subprocess.run(
                [node, '--input-type=module', '-e',
                 "import('jsdom').then(()=>process.exit(0),()=>process.exit(1))"],
                env=env, capture_output=True, timeout=60)
        except Exception:
            continue
        if r.returncode == 0:
            return (node, caminho)
    return None


_NODE = _node_com_jsdom()


@unittest.skipIf(_NODE is None, 'node com jsdom não disponível — '
                                'ver TESTES_DOLAR_DO_HEROI.md')
class NavegadorTests(_Base):
    """A ficha RODANDO. O teste que teria pego o bug de qualquer jeito.

    Os estáticos acima proíbem a conta errada pelo nome. Este não proíbe nada:
    carrega a página, deixa o script rodar, digita a recusa e LÊ o número na
    tela. Se amanhã alguém inventar uma terceira maneira de derivar o dólar da
    taxa, os estáticos não veem e este vê.
    """

    def _rodar(self, recusas):
        node, node_path = _NODE
        pasta = tempfile.mkdtemp()
        try:
            ficha = os.path.join(pasta, 'ficha.html')
            with io.open(ficha, 'w', encoding='utf-8') as f:
                f.write(self._html())
            r = subprocess.run(
                [node, HARNESS, ficha, json.dumps(recusas)],
                env=dict(os.environ, NODE_PATH=node_path),
                capture_output=True, timeout=180)
            self.assertEqual(r.returncode, 0,
                             'o harness quebrou:\n' + r.stderr.decode()[-2000:])
            saida = json.loads(r.stdout.decode().strip().split('\n')[-1])
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        self.assertEqual(saida['campos'], 1,
                         'a ficha não trouxe o campo de recusa — o teste '
                         'estaria medindo uma tela sem conferência')
        return saida

    def test_no_CARREGAMENTO_o_heroi_ja_bate_com_o_esperado(self):
        """O bug aparecia ANTES da primeira tecla.

        O servidor escreve `so.total_usd` no HTML e o `recalcular()` roda no
        load — com a conta errada, o script trocava o número certo pelo errado
        no mesmo instante. Sem recusa nenhuma, o herói TEM de continuar dizendo
        o que o servidor disse.
        """
        antes = self._rodar({})['antes']
        self.assertEqual(antes['kUsd'], 'US$ 4400.00')
        self.assertEqual(antes['kRmb'], '¥ 30000.00')

    def test_o_heroi_e_o_rodape_dizem_o_MESMO_numero(self):
        """Dois lugares na mesma tela, no mesmo instante. Foi vendo estes dois
        discordarem numa captura que o problema ficou visível."""
        # Nenhuma recusa, uma pequena, e o lote inteiro recusado.
        for rej in (0, 50, self.QTD):
            r = self._rodar({str(self.linha.pk): rej} if rej else {})
            for quando in ('antes', 'depois'):
                self.assertEqual(r[quando]['kUsd'], r[quando]['tUsd'],
                                 'herói e rodapé discordam em US$ '
                                 '(%s, recusa=%d)' % (quando, rej))
                self.assertEqual(r[quando]['kRmb'], r[quando]['tRmb'],
                                 'herói e rodapé discordam em ¥ '
                                 '(%s, recusa=%d)' % (quando, rej))
        # Lote inteiro recusado: zero, e zero escrito como número — não um
        # travessão, que é o desenho de "não sei".
        tudo = self._rodar({str(self.linha.pk): self.QTD})['depois']
        self.assertEqual(tudo['kUsd'], 'US$ 0.00')
        self.assertEqual(tudo['kRmb'], '¥ 0.00')

    def test_recusar_chips_FAZ_O_DOLAR_CAIR(self):
        """A frase dele, virada invariante: recusar não pode aumentar a conta.

        Recusa pequena de propósito (50 un., ¥150 em ¥30.000) — é a faixa em
        que a conta errada continuava ACIMA do esperado. Com uma recusa grande
        até o número errado cai, e o teste passaria sem provar nada.
        """
        r = self._rodar({str(self.linha.pk): 50})
        depois = D(r['depois']['kUsd'].replace('US$ ', ''))
        self.assertLess(depois, self.so.total_usd,
                        'recusar chips AUMENTOU o resultado em US$ — é o bug '
                        'de 2026-09-07 de volta')
        self.assertEqual(depois, D('4378.00'))       # 0,44 × 9.950

    def test_o_numero_da_tela_e_o_da_FATURA(self):
        """O fecho do arco: o que ele lê enquanto digita tem de ser o que o
        `settlement_totals` vai gravar quando ele clicar em fechar. Tela e
        fatura discordando é a discussão que o resultado parcial existe para
        evitar."""
        rej = 50
        r = self._rodar({str(self.linha.pk): rej})
        with company_scope(self.emp.id):
            linhas = list(self.so.lines.all())
            _rmb, usd = services.settlement_totals(
                linhas, {self.linha.pk: (rej, None)}, self.FX)
        self.assertEqual(D(r['depois']['kUsd'].replace('US$ ', '')), usd)
        self.assertEqual(D(r['depois']['tUsd'].replace('US$ ', '')), usd)
