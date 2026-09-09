# -*- coding: utf-8 -*-
"""
US$ EM DESTAQUE NA CONFERÊNCIA (dono, 2026-09-02) — E A VOLTA ATRÁS (07/09).

╔═══════════════════════════════════════════════════════════════════════════╗
║ ⚠ ESTE ARQUIVO GUARDA UMA DECISÃO E A REVERSÃO DELA. Leia os dois.        ║
╚═══════════════════════════════════════════════════════════════════════════╝

Em 02/09 o dono pediu o par US$/¥ nas três colunas de dinheiro da tabela, com
o dólar na frente. Em 07/09 pediu o contrário:

  "remover os precos em USD, vamos deixar somente em YUAN agora como
   primario, que é o que o comprador trabalha, isso somente na tabela, o
   resto da pagina q fala em dolar mantem"

E é uma reversão da TABELA, não do dólar: o cartão do topo, o pagamento e a
fatura seguem no par. Na tabela ele trabalha em ¥ — é a moeda em que compra —
e uma coluna de uma moeda só é uma coluna que soma.

O arquivo NÃO foi apagado, e é de propósito. Quase tudo que ele provava
continua valendo, só que do outro lado:

  · a fonte do US$ (`unit_usd` CONGELADO, nunca ¥ × taxa) — segue idêntica, e
    ficou MAIS crítica: com o dólar fora da tabela, o cartão do topo é o único
    lugar onde ele aparece, e é o `data-unit-usd` de cada linha que o alimenta.
    Foi exatamente aí que o bug de 07/09 morava (ver `tests_dolar_do_heroi`).
  · a coluna da PERDA em ¥ e o desenho dela — intocados.
  · a hierarquia de moeda — invertida: o que era secundário virou único.

Apagar isto e escrever um arquivo novo perderia a única coisa que um teste
guarda melhor que um commit: POR QUE a tela é assim, incluindo o caminho que
ela não seguiu.

────────────────────────────────────────────────────────────────────────────
O pedido de 02/09, para o registro:

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

⚠ E o risco nº 2 ACONTECEU, cinco dias depois, no cartão do topo — que este
  arquivo não cobria. Pior: havia aqui um teste chamado
  `test_o_js_le_o_usd_congelado_e_nao_multiplica_pela_taxa` que passava
  enquanto o bug rodava, porque cobrava a conta certa com `assertIn` em vez de
  proibir a errada com `assertNotIn`. A lição está escrita em
  `TESTES_DOLAR_DO_HEROI.md`: regra do tipo "NUNCA faça X" não se prova
  mostrando que Y existe.
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


def _regra(css, seletor):
    """O corpo `{...}` da regra deste seletor exato.

    Recorta em vez de procurar a linha inteira: assim acrescentar uma
    declaração à regra não reprova o teste que cobra outra.
    """
    i = css.find(seletor + '{')
    assert i != -1, 'seletor %r não existe no CSS' % seletor
    return css[i:css.index('}', i) + 1]


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

    def _com_recusa(self, qtd):
        """Salva a recusa no RASCUNHO e devolve a OV recarregada.

        Pelo rascunho e não pelo acerto de propósito: é o estado em que o
        comprador está quando digita, que é quando a perda importa.
        """
        with company_scope(self.emp.id):
            services.save_draft(self.so, {self.linha.pk: qtd}, self.parceiro)
            return SalesOrder.objects.get(pk=self.so.pk)

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
    """O que a página escreve. INVERTIDO em 07/09 — a tabela é só ¥."""

    def test_a_TABELA_nao_tem_mais_dolar(self):
        """O pedido de 07/09, na forma mais curta que existe.

        ⚠ Na TABELA, e só nela. Varrer a página inteira reprovaria por causa
          do cartão do topo, do bloco de pagamento e da fatura — que seguem no
          par de propósito ("o resto da pagina q fala em dolar mantem").
        """
        self.assertNotIn('US$', self._resumo())

    def test_o_resto_da_pagina_CONTINUA_falando_dolar(self):
        """A outra metade da mesma frase, e ela precisa de teste tanto quanto
        a primeira: tirar o dólar da tabela e levar o da página junto seria
        obedecer pela metade — e o dólar é o que ele PAGA."""
        html = self._html()
        self.assertIn('US$', html)
        self.assertIn('id="k-usd"', html)

    def test_o_yuan_virou_a_moeda_PRIMARIA(self):
        """Não é o mesmo ¥ de antes: era o `<span class="cy">` apagado embaixo
        do dólar, e agora é o número da célula. A ausência do `.cy` é o que
        prova que ele subiu, e não que o dólar apenas sumiu de vista."""
        resumo = self._resumo()
        self.assertNotIn('class="cy"', resumo)
        self.assertIn('¥ %s' % (self.UNIT_RMB * self.QTD), resumo)
        # O unitário é TEXTO na célula (o campo mora atrás do lápis) e o
        # congelado repete-se no placeholder, para o campo abrir já mostrando
        # de onde ele partiu.
        self.assertIn('¥ %s' % self.UNIT_RMB, resumo)
        self.assertIn('placeholder="%s"' % self.UNIT_RMB, resumo)
        self.assertIn('>Unitário ¥<', resumo.replace('</th>', '<'))

    def test_o_titulo_da_coluna_VOLTOU_a_cravar_a_moeda(self):
        """De 02/09 a 07/09 o título não podia dizer a moeda: a célula trazia
        duas. Com uma moeda só o título volta a dizê-la — e passa a ler
        idêntico ao da planilha, que é o pedido de "posicionamento" de 07/09
        levado até o texto. Ver `tests_planilha_da_compra`, que compara as
        duas listas de títulos uma contra a outra."""
        resumo = self._resumo()
        for titulo in ('Unitário ¥', 'Esperado ¥', 'Resultado ¥',
                       'Recusados ¥'):
            self.assertIn('>%s<' % titulo, resumo.replace('</th>', '<'),
                          'sumiu o título %r' % titulo)

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

    def test_o_resultado_abre_em_YUAN_e_so(self):
        celula = self._celula_resultado()
        self.assertIn('¥ %s' % (self.UNIT_RMB * self.QTD), celula)
        self.assertNotIn('US$', celula)

    def test_as_colunas_de_dinheiro_da_linha_sao_TODAS_em_yuan(self):
        """Unitário, Esperado e Resultado. Enviados/Recusados/Aprovados são
        contagem, não dinheiro — e a coluna RECUSADOS ¥ é a quarta, também em
        ¥ desde que nasceu."""
        linha = re.search(r'<tr data-g="0">.*?</tr>', self._resumo(), re.S)
        self.assertIsNotNone(linha)
        html = linha.group(0)
        self.assertNotIn('US$', html)
        # TRÊS textos em ¥ VISÍVEIS — unitário, esperado e resultado.
        #
        # ⚠ Este número foi para 2 e voltou para 3 no mesmo dia, e a ida e a
        #   volta são a mesma decisão sendo refinada: em 09/09 o unitário
        #   virou CAMPO (o comprador repactua) e o ¥ saiu do texto; horas
        #   depois o dono viu a tela — *"tem uma caixinha em todos os precos é
        #   foda, instiga o comprador a querer mexer em tudo"* — e o campo foi
        #   para trás de um LÁPIS. O número voltou a ser número.
        #
        # ⚠ E existe um QUARTO ¥ no HTML desde 09/09: o preço ANTIGO riscado,
        #   que nasce `hidden` e só aparece quando há repactuação. Ele fica no
        #   DOM desde o carregamento porque quem o acende é o JS, enquanto o
        #   comprador digita — não dá para renderizá-lo sob demanda sem ida ao
        #   servidor. Contar o HTML cru diria 4 e esconderia o que importa:
        #   o que este teste guarda é quantos ¥ o comprador VÊ. Por isso o
        #   `.uant` sai da conta aqui e ganha asserção própria logo abaixo.
        sem_antigo = re.sub(r'<span class="uant"[^>]*>.*?</span>', '', html,
                            flags=re.S)
        self.assertEqual(sem_antigo.count('¥ '), 3)
        # …e o quarto está lá, riscado e fechado, esperando a repactuação.
        antigo = re.search(r'<span class="uant"[^>]*>.*?</span>', html, re.S)
        self.assertIsNotNone(antigo, 'o preço antigo sumiu da célula')
        self.assertIn('hidden', antigo.group(0))
        self.assertIn('<s>¥ ', antigo.group(0))
        self.assertNotIn('US$', antigo.group(0))
        self.assertIn('class="cell pcin"', html)             # o campo existe…
        self.assertIn('hidden', html)                        # …e nasce fechado
        self.assertIn('class="upen"', html)                  # atrás do lápis

    def test_a_faixa_da_marca_segue_a_linha(self):
        """Faixa em uma moeda com as linhas dela em outra é o tipo de
        divergência que só se nota depois de fechado."""
        faixa = re.search(r'<tr class="g">.*?</tr>', self._resumo(), re.S)
        self.assertIsNotNone(faixa)
        self.assertIn('¥ %s' % (self.UNIT_RMB * self.QTD), faixa.group(0))
        self.assertNotIn('US$', faixa.group(0))


class RecalculoAoVivoTests(_Base):
    """O risco nº 1: o JS.

    Não dá para executar o script aqui. O que dá para provar é que ele LÊ o
    dado certo, escreve o par nos três lugares e não usa a taxa — que são
    exatamente os três jeitos de esse número passar a mentir.
    """

    def setUp(self):
        super().setUp()
        self.js = _ler(FICHA)

    def test_existe_uma_funcao_unica_que_escreve_o_dinheiro(self):
        """Três cópias do mesmo formato divergem na primeira alteração.

        Era o `par(usd, rmb)`; virou `dinheiro(rmb)` em 07/09, quando a tabela
        passou a ter uma moeda só. O que não mudou é haver UMA função: o mesmo
        formato é escrito na linha, na faixa e no rodapé.
        """
        self.assertIn('function dinheiro(rmb)', self.js)
        self.assertNotIn('function par(', self.js)

    def test_os_tres_lugares_usam_a_funcao(self):
        for alvo in ('cVal.textContent = dinheiro(',
                     'eVal.textContent = dinheiro(',
                     'elPagarRmb.textContent = dinheiro('):
            self.assertIn(alvo, self.js, alvo)

    def test_o_js_le_o_usd_congelado_e_nao_multiplica_pela_taxa(self):
        self.assertIn('i.dataset.unitUsd', self.js)
        self.assertIn('valUsd = ok * unitUsd', self.js)

    def test_a_faixa_da_marca_voltou_a_usar_textContent(self):
        """Era `innerHTML` porque o par levava um `<span>` dentro. Com uma
        moeda só entra número puro, e `innerHTML` com dado seria a porta
        aberta de sempre — mesmo que aqui o dado seja um float nosso."""
        self.assertIn("eVal.textContent = ", self.js)
        self.assertNotIn("eVal.innerHTML", self.js)

    def test_o_rodape_tem_alvo_proprio_para_o_numero(self):
        """O `escreverNumero` escreve no ÚLTIMO nó de TEXTO da célula, e o
        `<small>` do rótulo vem antes — sem um alvo próprio ele sobrescreveria
        o rótulo em vez do número."""
        self.assertIn('id="t-pagar-rmb"', self.js)
        self.assertNotIn('id="t-pagar-usd"', self.js)
        self.assertNotIn("escreverNumero(elPagar,", self.js)

    def test_a_perda_NAO_entra_mais_na_celula_do_dinheiro(self):
        """A correção de 07/09, na sua forma mais curta.

        A perda morava na célula do RESULTADO, que já empilha US$ e ¥ — um
        terceiro número numa célula de dois, e ainda por cima virando bloco
        alinhado à direita (`.dl2` do `patterns/parceiro.css`). O dono: *"sai
        na coluna de resultado quebrando tudo (...) ele esta no lugar
        correto?"*. Não estava: foi para a célula da RECUSA, que é o que a
        causa, e que tinha a folga.
        """
        self.assertIn('cVal.textContent = dinheiro(val);', self.js)
        # a célula do dinheiro não escreve mais `.dl2` nenhum
        antes, _, depois = self.js.partition('var cVal =')
        trecho = depois[:depois.index('var cPerda')]
        self.assertNotIn('dl2', trecho)

    def test_a_perda_tem_alvo_PROPRIO_em_cada_altura(self):
        """`textContent` numa célula só dela — linha, faixa e rodapé —, e não
        `innerHTML` numa célula compartilhada: aqui só entra número, e é o
        MESMO número que o servidor escreve no carregamento."""
        self.assertIn("[data-perda=", self.js)
        self.assertIn("cPerda.textContent", self.js)
        self.assertIn("[data-gperda=", self.js)
        self.assertIn("escreverNumero(elRejV,", self.js)

    def test_a_faixa_da_marca_soma_a_perda_das_linhas_dela(self):
        """Faixa dizendo um número e linhas dizendo outro é o erro que só
        aparece depois de fechado."""
        self.assertIn('g.perda += r * unit;', self.js)
        self.assertIn("ePerda.textContent", self.js)


class EstiloTests(TestCase):

    def test_o_cy_SAIU_do_css_junto_com_o_dolar_da_tabela(self):
        """Aqui havia dois testes cobrando a regra do `.cy` e a ordem dela no
        arquivo. Com a tabela em uma moeda só, ninguém mais emite `.cy`: a
        regra saiu em vez de virar enfeite.

        A troca de asserção é deliberada. CSS sem consumidor não some sozinho,
        e é sobre ele que a próxima pessoa desenha achando que está vivo —
        exatamente o defeito do `order:6` que este mesmo arquivo documenta
        mais abaixo. Quem precisar de par com ¥ na frente tem o `.cusd`, que a
        lista de compras usa.
        """
        self.assertNotIn('span.cy', _ler(CSS))
        self.assertNotIn('class="cy"', _ler(FICHA))

    def test_a_coluna_da_perda_e_UMA_LINHA_de_css(self):
        """A prova de que ela virou COLUNA, e não mais um ajuste.

        Como `<td class="n">`, ela herda do pacote a mono 14, o
        `tabular-nums` e o alinhamento — o dono pediu exatamente isso ("do
        tamanho dos outros na tabela mesmo, mesmo padrao"). A única coisa que
        sobra para esta folha é a TINTA.

        As duas tentativas anteriores enfiaram o número na célula de outro
        dado e precisaram de três ou quatro declarações para brigar com o
        `.dl2` do `patterns/parceiro.css` — sem nunca resolver o problema, que
        era de layout de tabela e não de display.
        """
        regra = _regra(_ler(CSS), '.dtab .rv')
        self.assertEqual(regra, '.dtab .rv{color:var(--red-60)}')
        # e o `.dl2` deixou de ser usado nesta tela
        self.assertNotIn('dl2', _ler(FICHA))

    def test_no_cartao_do_celular_a_coluna_vira_fileira(self):
        """No telefone o campo ocupa a largura toda: ao lado dele nada cabe.
        A célula desce para uma fileira própria logo abaixo, e some inteira
        quando está vazia — senão TODO cartão da tela ficaria 9px mais alto
        por causa de uma célula sem conteúdo, que é o mesmo defeito de sempre
        pelo outro lado.

        ⚠ As regras têm de existir DUAS vezes: o pacote repete todo o bloco de
          600px em `@media` e em `@container`, e uma cópia só deixa metade das
          telas para trás.
        """
        pat = _ler(os.path.join(settings.BASE_DIR, 'static', 'wtc',
                                'patterns', 'parceiro.css'))
        self.assertEqual(pat.count('.dtab--conf .c-rejv{flex:1 0 100%'), 2)
        self.assertEqual(pat.count('.dtab--conf .c-rejv:empty{display:none}'), 2)

    def test_ninguem_tentou_ordenar_a_celula_com_order(self):
        """⚠ ARMADILHA MEDIDA, não suposta: o pacote crava `order:6` em TODA
        célula do corpo, com uma regra que vale (0,5,2). Qualquer `order` de
        duas classes aqui é código morto que PARECE funcionar na leitura. Quem
        decide a posição no cartão é a ordem do DOM — que é a das colunas."""
        pat = _ler(os.path.join(settings.BASE_DIR, 'static', 'wtc',
                                'patterns', 'parceiro.css'))
        self.assertNotIn('.dtab--conf .c-rejv{flex:0 0 auto;order', pat)
        self.assertIn('td:not(.cbx):not(.c):not(.key):not(.go){order:6',
                      _ler(CSS))


class PerdaDaLinhaTests(_Base):
    """A perda em ¥ — o que a recusa tirou. Agora vem do SERVIDOR.

    Antes ela só existia enquanto ele digitava: aparecia com a tecla e sumia
    no F5. Um número que some ao recarregar está no lugar errado por
    definição — a tela contradizia a si mesma sobre um fato que não muda.
    """

    def _linha(self, grupos, pk):
        return next(l for g in grupos for l in g['lines'] if l['pk'] == pk)

    def test_sem_recusa_nao_ha_perda(self):
        """`None`, e não zero: a célula fica VAZIA. Um "−¥ 0.00" ao lado de
        cada campo em branco seria ruído em toda linha da tabela."""
        for g in self._grupos():
            for l in g['lines']:
                self.assertIsNone(l['perda_rmb'])
            self.assertEqual(g['perda_rmb'], D('0.00'))

    def test_a_perda_e_a_recusa_vezes_o_unitario(self):
        so = self._com_recusa(3)
        with company_scope(self.emp.id):
            grupos = services.result_rows(so, com_rascunho=True)
        l = self._linha(grupos, self.linha.pk)
        self.assertEqual(l['rejected'], 3)
        self.assertEqual(l['perda_rmb'], self.UNIT_RMB * 3)

    def test_a_faixa_da_marca_soma_as_linhas_dela(self):
        so = self._com_recusa(3)
        with company_scope(self.emp.id):
            grupos = services.result_rows(so, com_rascunho=True)
        for g in grupos:
            self.assertEqual(
                g['perda_rmb'],
                sum((l['perda_rmb'] or D('0.00')) for l in g['lines']))

    def test_o_numero_chega_desenhado_na_COLUNA_dele(self):
        """Célula própria: `td.c-rejv`. Nem na do dinheiro, nem espremido na
        do campo — foram as duas tentativas que o dono reprovou."""
        import re
        so = self._com_recusa(3)
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        celula = re.search(r'<td class="n hr rv c-rejv".*?</td>', html, re.S)
        self.assertIsNotNone(celula, 'coluna da perda não encontrada')
        self.assertIn('data-perda="%s"' % self.linha.pk, celula.group(0))
        self.assertIn('−¥ %s' % (self.UNIT_RMB * 3), celula.group(0))

    def test_a_celula_do_CAMPO_so_tem_o_campo(self):
        import re
        so = self._com_recusa(3)
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        celula = re.search(r'<td class="n hr c-rej".*?</td>', html, re.S)
        self.assertNotIn('−¥', celula.group(0))

    def test_o_rodape_soma_a_coluna(self):
        so = self._com_recusa(3)
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        import re
        rodape = re.search(r'<tfoot>.*?</tfoot>', html, re.S).group(0)
        self.assertIn('id="t-rejv"', rodape)
        self.assertIn('−¥ %s' % (self.UNIT_RMB * 3), rodape)

    def test_as_TRES_faixas_da_tabela_tem_o_mesmo_numero_de_colunas(self):
        """A conta que uma coluna nova quebra primeiro, e que ninguém vê até
        a terceira coluna sair do prumo: `thead`, cada `tr` do `tbody` e o
        `tfoot` têm de somar a mesma largura, contando `colspan`."""
        import re
        so = self._com_recusa(3)
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        tabela = re.search(r'<table[^>]*id="tab-resumo".*?</table>', html,
                           re.S).group(0)

        def largura(trecho, tag):
            # ⚠ `<%s[^>]*>` NÃO serve: `<thead>` casa com `<th` + `ead`, e
            #   o cabeçalho passa a ter uma coluna a mais do que tem. A
            #   primeira versão deste teste reprovou a tabela por causa
            #   disso — o defeito era da regex, não do template.
            marcas = re.finditer(r'<(t[hd])(\s[^>]*)?>', trecho)
            return sum(
                int(re.search(r'colspan="(\d+)"', m.group(0)).group(1))
                if 'colspan=' in m.group(0) else 1
                for m in marcas if m.group(1) == tag)

        cab = largura(re.search(r'<thead>.*?</thead>', tabela, re.S).group(0),
                      'th')
        pe = largura(re.search(r'<tfoot>.*?</tfoot>', tabela, re.S).group(0),
                     'td')
        corpo = re.search(r'<tbody>.*?</tbody>', tabela, re.S).group(0)
        linhas = {largura(tr, 'td')
                  for tr in re.findall(r'<tr[^>]*>.*?</tr>', corpo, re.S)}
        self.assertEqual(linhas, {cab}, 'linha do corpo fora do prumo')
        self.assertEqual(pe, cab, 'rodapé fora do prumo')

    def test_a_celula_do_dinheiro_NAO_traz_a_perda(self):
        import re
        so = self._com_recusa(3)
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        for celula in re.findall(r'<td class="v hb c-val[^>]*>.*?</td>',
                                 html, re.S):
            self.assertNotIn('dl2', celula)


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
