# -*- coding: utf-8 -*-
"""
O PDF DO RESULTADO, no design system (dono, 2026-09-04).

  "sobre o PDF do resultado, vc poderia adequar ele ao design do nosso design
   system? com as cores correspodentes, tabelas, campos, espacamentos, tudo
   conforme os nossos padroes? (...) Os numeros de resultados finais pode
   deixar no topo, depois das informacoes, antes do detalhamento"

Quatro garantias, e nenhuma delas é "está bonito" — isso é olho, e o olho fez
o trabalho no PDF de amostra. O que fica travado aqui é o que some sem avisar:

  1. A ORDEM das seções. Os números ficavam na página 4, depois de 100 linhas.
  2. Os SUBTOTAIS por marca batem com as linhas da marca.
  3. A COR da diferença responde ao sinal.
  4. As CORES saem do `colors.css`, e não de um hex inventado parecido.

⚠ A garantia 4 é a que mais vale a longo prazo. O defeito original não era
  feiúra: era que os cinzas do papel (#8d8d8d, #d0d0d0, #f4f4f4) eram os
  NEUTROS do Carbon e os nossos são FRIOS (#697077, #dde1e6, #f2f4f8). A
  diferença some numa olhada isolada e aparece quando o papel está do lado da
  tela. Nenhum olho pega isso duas vezes; um teste pega sempre.
"""

import io
import os
import re
from datetime import date, datetime
from decimal import Decimal as D

from django.conf import settings
from django.test import TestCase

from vendas import pdf as vpdf

TOKENS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'tokens',
                      'colors.css')


def _doc(linhas, esperado=None, notas=()):
    env = sum(l['sent'] for l in linhas)
    rej = sum(l['rejected'] for l in linhas)
    ace = sum(l['accepted'] for l in linhas)
    tot = sum((l['total_rmb'] for l in linhas
               if l['total_rmb'] is not None), D('0.00'))
    esperado = tot if esperado is None else esperado
    return {
        'lot_code': 'LOT-2026-0008', 'so_code': 'EMIN-SO-2026-0008',
        'company': 'eMiner', 'company_logo': None,
        'closed_at': date(2026, 8, 27), 'received_at': date(2026, 9, 2),
        'settled_at': datetime(2026, 9, 4, 12, 9),
        'fx_rate': D('0.1484'), 'lines': linhas,
        'sent': env, 'rejected': rej, 'accepted': ace,
        'order_rmb': esperado, 'order_usd': D('100.00'),
        'total_rmb': tot, 'total_usd': D('90.00'),
        'delta_rmb': tot - esperado, 'delta_usd': D('-10.00'),
        'notes': list(notas),
    }


def _linha(marca, tipo, qtd, rej, unit, unit_usd='0.30'):
    #: ⚠ O US$ NÃO é o ¥ × taxa de propósito (0.30 não é 2.00 × 0.1484): é o
    #: que prova que o documento lê o `unit_usd` CONGELADO da linha, e não faz
    #: a conta por fora. Mesma trava do teste da tela.
    return {'brand': marca, 'type': tipo, 'capacity': '16GB', 'wtc': 'B-06',
            'sent': qtd, 'rejected': rej, 'accepted': qtd - rej,
            'unit_rmb': D(unit), 'total_rmb': D(unit) * (qtd - rej),
            'unit_usd': D(unit_usd),
            'total_usd': D(unit_usd) * (qtd - rej)}


def _texto(dados):
    """O texto do PDF, página a página.

    ⚠ `pdfplumber` e não `pypdf`: o pdfplumber JÁ é dependência declarada
    (`requirements.txt`, para ler datasheet), e o pypdf não é. Um teste que
    obriga a instalar biblioteca nova no servidor de produção para conferir a
    cor de uma caixa custa mais do que garante.
    """
    import pdfplumber
    with pdfplumber.open(io.BytesIO(dados)) as arq:
        return '\n'.join(p.extract_text() or '' for p in arq.pages)


LINHAS = [
    _linha('Kingston', 'eMMC', 100, 0, '2.00'),
    _linha('Kingston', 'eMCP', 50, 10, '4.00'),
    _linha('Samsung', 'DDR3', 200, 0, '3.00'),
]


class OrdemDasSecoesTests(TestCase):
    """A mudança que o dono pediu por escrito."""

    def test_o_resultado_vem_antes_do_detalhamento(self):
        """Os números eram a ÚLTIMA coisa do documento, depois de quatro
        páginas de tabela. Quem abre um resultado quer saber quanto deu antes
        de saber de onde veio."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        i_final = txt.index('FINAL')
        i_detalhe = txt.index('Result detail')
        self.assertLess(i_final, i_detalhe)

    def test_as_informacoes_vem_antes_do_resultado(self):
        """A ordem pedida é: informações → números → detalhamento.

        ⚠ Rótulo em CAIXA ALTA porque é o `.rmx__l` do frontend
        (`text-transform:uppercase`, peso 800). Se voltar a ser "Expected",
        alguém desfez a cópia do componente.
        """
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertLess(txt.index('Ship from'), txt.index('EXPECTED'))

    def test_nenhuma_marcacao_vaza_para_o_papel(self):
        """O `_rich` escapa a string inteira antes de marcar os trechos CJK.
        Markup entregue a ele sai IMPRESSO: a primeira versão da faixa de
        marca escreveu `<font color='#878d96'>· 4</font>` na cara do cliente,
        e só o PDF de amostra pegou."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertNotIn('<font', txt)
        self.assertNotIn('</font>', txt)


class CabecalhoTests(TestCase):
    """O topo, depois da segunda rodada de desenho (dono, 2026-09-04)."""

    def test_o_titulo_do_documento_substituiu_o_codigo_do_lote(self):
        """O lote não some da vida: ele está no RODAPÉ de toda página, que é
        onde o cliente procura o papel meses depois. O que saiu foi a
        duplicata dele no lugar mais nobre da folha, dizendo um número que
        ninguém procura antes de saber o que o papel é."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        cabecalho = txt[:txt.index('Ship from')]
        self.assertIn('Purchase result', cabecalho)
        self.assertNotIn('LOT-2026-0008', cabecalho)
        self.assertIn('LOT-2026-0008', txt)          # segue no rodapé

    def test_o_identificador_do_topo_e_a_ordem_de_venda(self):
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        cabecalho = txt[:txt.index('Ship from')]
        self.assertIn('Sales Order', cabecalho)
        self.assertIn('EMIN-SO-2026-0008', cabecalho)

    def test_o_rotulo_do_PACKING_LIST_nao_foi_reetiquetado(self):
        """A TRAVA que justifica a chave separada.

        O `so` diz "Reference" desde 2026-08-20 por decisão explícita do dono
        — *"não fale nada de aduana de Macao, nem que isso vai ser vendido"*.
        Quem carrega aquele rótulo é o packing list, que VIAJA COM A CARGA.
        Trocar "Sales Order" no documento do resultado não pode arrastar o
        outro junto: papel de remessa que se anuncia como venda internacional
        pede tratamento de venda internacional.
        """
        self.assertEqual(vpdf._L['so'][0], 'Reference')
        self.assertEqual(vpdf._L['so_result'][0], 'Sales Order')


class RotulosDoTopoTests(TestCase):
    """A terceira rodada de acabamento (dono, 2026-09-04)."""

    def test_o_ship_from_do_resultado_nao_e_caixa_alta(self):
        """"SHIP FROM esta todo maiusculo, corrija isso".

        Ele era o único campo gritando no meio de "Lot closed on", "Box
        received on" e "Exchange rate" — e caixa alta, num campo, é ênfase:
        estava enfatizando o remetente, que é a informação menos disputada da
        folha.
        """
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertIn('Ship from', txt)
        self.assertNotIn('SHIP FROM', txt)

    def test_o_ship_from_do_EMBARQUE_continua_em_caixa_alta(self):
        """A TRAVA que justifica a chave separada — irmã do teste do
        `so`/`so_result`.

        "SHIP FROM"/"SHIP TO" em caixa alta é a convenção do documento de
        embarque no mundo inteiro; transportadora e alfândega procuram por
        ela. O pedido do dono foi sobre o papel do RESULTADO, que não viaja
        com caixa nenhuma. Se um dia alguém "arrumar" o `_L['ship_from']`
        achando que é o mesmo rótulo, quebra aqui e não na aduana.
        """
        self.assertEqual(vpdf._L['ship_from'][0], 'SHIP FROM')
        self.assertEqual(vpdf._L['ship_to'][0], 'SHIP TO')
        self.assertEqual(vpdf._L['ship_from_r'][0], 'Ship from')
        # e os dois apontam para o mesmo chinês: é o mesmo campo, outra caixa
        self.assertEqual(vpdf._L['ship_from'][1], vpdf._L['ship_from_r'][1])

    def test_o_numero_final_diz_final_do_que(self):
        """"mude o nome para FINAL RESULT e com o completo em mandarim".

        "Final" sozinho é adjetivo — final de quê? — e 最終 tem exatamente o
        mesmo problema em chinês. 最終結果 é o substantivo inteiro.
        """
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertIn('FINAL RESULT', txt)
        self.assertIn('最終結果', txt)


class DataPorExtensoTests(TestCase):
    """O rodapé escreve a data, nas duas línguas (dono, 2026-09-04).

    `04/09/2026` é ambíguo entre quem lê dd/mm e quem lê mm/dd, e este papel
    sai do Paraguai e é lido na China. Escrito não tem como ler errado.
    """

    def test_o_rodape_traz_as_duas_formas(self):
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        hoje = date.today()
        en = '%d %s %d' % (hoje.day, vpdf._MESES_EN[hoje.month - 1], hoje.year)
        zh = '%d年%d月%d日' % (hoje.year, hoje.month, hoje.day)
        self.assertIn(en, txt)
        self.assertIn(zh, txt)

    def test_a_forma_chinesa_nao_leva_zero_a_esquerda(self):
        """2026年9月4日, nunca 2026年09月04日 — a convenção chinesa não
        preenche com zero, e o zero ali lê como número de série."""
        self.assertEqual(vpdf._fmt_extenso(date(2026, 9, 4)),
                         '4 September 2026 (2026年9月4日)')

    def test_o_mes_nao_depende_da_locale_do_servidor(self):
        """⚠ O motivo de `_MESES_EN` existir em vez de `strftime('%B')`.

        O `%B` obedece à locale do PROCESSO. No Render o servidor pode subir
        em C, pt_BR ou zh_CN, e o rodapé sairia "4 setembro 2026" sem ninguém
        perceber — um documento que se anuncia bilíngue inglês/中文 falando
        português. Este teste força a locale e cobra o inglês.
        """
        import locale
        for tentativa in ('pt_BR.UTF-8', 'C'):
            try:
                locale.setlocale(locale.LC_TIME, tentativa)
            except locale.Error:
                continue
            try:
                self.assertIn('September',
                              vpdf._fmt_extenso(date(2026, 9, 4)))
            finally:
                locale.setlocale(locale.LC_TIME, 'C')

    def test_os_outros_documentos_seguem_no_formato_curto(self):
        """Packing list e documento do gerente vão para transportadora e
        alfândega, onde dd/mm/aaaa é o esperado. Restilizá-los de carona não
        é escopo — é efeito colateral."""
        fonte = io.open(vpdf.__file__.replace('.pyc', '.py'),
                        encoding='utf-8').read()
        antes = fonte[:fonte.index('def render_result_pdf')]
        self.assertNotIn('_fmt_extenso(', antes.split('def _fmt_extenso')[0])


class DinheiroTests(TestCase):

    def test_o_usd_vem_antes_do_yuan_no_resultado(self):
        """Dono, 2026-09-04: "deixe USD first, e o Yuan como secundário". É a
        moeda em que o dinheiro muda de mão."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        trecho = txt[txt.index('EXPECTED'):txt.index('Result detail')]
        self.assertLess(trecho.index('US$'), trecho.index('¥'))

    def test_o_dinheiro_tem_separador_de_milhar(self):
        """`US$ 170137.63` obriga a contar casas com o dedo, e contar casa em
        documento de dinheiro é como se erra uma ordem de grandeza."""
        grande = [_linha('Samsung', 'eMMC', 100000, 0, '20.00', '3.00')]
        txt = _texto(vpdf.render_result_pdf(_doc(grande)))
        self.assertIn('300,000.00', txt)      # US$
        self.assertIn('2,000,000.00', txt)    # ¥

    def test_a_tabela_traz_o_usd_congelado_da_linha(self):
        """0.30 não é 2.00 × 0.1484: se o documento derivasse o dólar da taxa,
        este número não apareceria."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertIn('US$ 0.30', txt)

    def test_o_titulo_da_coluna_nao_crava_a_moeda(self):
        """A célula abre em US$ — um "Unit ¥" em cima anuncia a moeda errada
        na primeira leitura. Mesmo defeito que a tela teve na mesma entrega."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertNotIn('Unit ¥', txt)
        self.assertIn('UNIT', txt)   # caixa alta: é o `.dtab th`


class AgrupamentoPorMarcaTests(TestCase):

    def test_a_marca_aparece_uma_vez_por_grupo(self):
        """"Samsung" saía repetido em 40 das 100 linhas. Agora é faixa."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        self.assertEqual(txt.count('Kingston'), 1)

    def test_o_subtotal_da_marca_bate_com_as_linhas_dela(self):
        """Faixa dizendo um número e linhas dizendo outro é o erro que só
        aparece depois do documento assinado."""
        txt = _texto(vpdf.render_result_pdf(_doc(LINHAS)))
        # Kingston em ¥: 100×2.00 + 40×4.00 = 360.00
        self.assertIn('360.00', txt)
        # Kingston em US$: 140 aceitos × 0.30 = 42.00
        self.assertIn('US$ 42.00', txt)
        # e o total geral em ¥: 360 + 600 = 960.00
        self.assertIn('960.00', txt)

    def test_o_documento_sai_com_uma_marca_so(self):
        """Guarda de borda: um lote de marca única não pode virar faixa sem
        linhas nem linhas sem faixa."""
        dados = vpdf.render_result_pdf(
            _doc([_linha('Samsung', 'eMMC', 10, 0, '1.00')]))
        self.assertTrue(dados[:4] == b'%PDF')


class CorDaDiferencaTests(TestCase):
    """A única REGRA do documento — o resto é desenho.

    Vive no nível do módulo justamente para ter teste: regra enterrada numa
    função de 200 linhas que devolve bytes de PDF não se testa, só se olha.
    """

    def test_a_menos_e_ambar(self):
        fundo, _regua, tinta = vpdf.cor_da_diferenca(D('-10.00'))
        self.assertEqual(fundo, vpdf._T_SAND)
        self.assertEqual(tinta, vpdf._T_AMBER)

    def test_zero_e_verde(self):
        """⚠ O defeito que motivou isto: era âmbar SEMPRE, e âmbar no nosso
        sistema é atenção — o documento alertava em amarelo justamente quando
        não havia nada a explicar, que é o caso mais comum."""
        fundo, _regua, tinta = vpdf.cor_da_diferenca(D('0.00'))
        self.assertEqual(fundo, vpdf._T_MINT)
        self.assertEqual(tinta, vpdf._T_GREEN)

    def test_a_mais_tambem_e_verde(self):
        self.assertEqual(vpdf.cor_da_diferenca(D('5.00'))[0], vpdf._T_MINT)

    def test_sem_esperado_nao_julga(self):
        """Sem número com que comparar, uma caixa colorida afirmaria um
        julgamento que o documento não tem."""
        fundo, _r, tinta = vpdf.cor_da_diferenca(None)
        self.assertEqual(fundo, vpdf._T_SURF3)
        self.assertEqual(tinta, vpdf._T_MUTED)


class CabecalhoDaTabelaTests(TestCase):
    """O topo preto da tabela, monoespaçado como na tela (dono, 2026-09-04).

      "as fontes do topo da tabela que tem o fundo preto deixa monoespacada,
       como é no frontend"

    A tela: `.dtab th{font-family:var(--mono);text-transform:uppercase}`, com
    `.dtab th.hr{color:var(--red-50)}` e `.hg{color:var(--green-40)}`.

    ⚠ Os dois rótulos coloridos são a QUARTA aparição da mesma armadilha do
      reportlab neste arquivo: `('TEXTCOLOR', ...)` no TableStyle **não
      atravessa um Paragraph**. As duas linhas existiam desde a primeira
      versão e nunca pintaram nada — o `textColor=white` do estilo vencia, e
      os rótulos saíam brancos. Só o PDF de amostra pegou. Este teste olha a
      COR DO CARACTERE no papel, não o código que tenta pintá-la, porque é
      exatamente aí que a armadilha se esconde.
    """

    def _chars_do_cabecalho(self):
        import pdfplumber
        dados = vpdf.render_result_pdf(_doc(LINHAS))
        with pdfplumber.open(io.BytesIO(dados)) as arq:
            pg = arq.pages[0]
            # a faixa preta: a única linha da página com fundo --ink-90
            faixa = [r for r in pg.rects
                     if r['non_stroking_color']
                     and max(r['non_stroking_color']) < .2
                     and r['width'] > 400]
            self.assertTrue(faixa, 'o cabeçalho escuro sumiu da tabela')
            topo, base = faixa[0]['top'], faixa[0]['bottom']
            return [c for c in pg.chars if topo <= c['top'] <= base]

    def test_o_topo_preto_usa_a_mono_do_design_system(self):
        """`--font-mono:'IBM Plex Mono'` — a mesma da tela, embutida.

        Aceita a Courier só como FALLBACK declarado: se a TTF não subir no
        deploy, o PDF tem de sair mesmo assim (um cabeçalho na mono errada é
        defeito visual; um PDF que não abre é venda parada).
        """
        chars = self._chars_do_cabecalho()
        self.assertTrue(chars, 'o cabeçalho saiu sem texto')
        latinos = [c for c in chars if ord(c['text']) < 0x2e80]
        self.assertTrue(latinos)
        fora = sorted({c['fontname'] for c in latinos
                       if not any(m in c['fontname']
                                  for m in ('PlexMono', 'Courier'))})
        self.assertFalse(
            fora, 'o cabeçalho da tabela voltou a ser proporcional: %s' % fora)
        self.assertTrue(vpdf._MONO_TTF.exists(),
                        'a TTF da mono sumiu de vendas/assets — o papel caiu '
                        'no fallback Courier sem ninguém notar')

    def test_os_rotulos_sao_caixa_alta(self):
        """`text-transform:uppercase` do `.dtab th` (dono: "tudo MAIÚSCULO").

        Só o latino: ideograma não tem caixa.
        """
        latinos = [c['text'] for c in self._chars_do_cabecalho()
                   if c['text'].isalpha() and ord(c['text']) < 0x2e80]
        self.assertTrue(latinos)
        minusculas = sorted({c for c in latinos if c.islower()})
        self.assertFalse(minusculas,
                         'sobrou letra minúscula no cabeçalho: %s' % minusculas)

    def test_o_cabecalho_cabe_em_uma_linha_so(self):
        """"que o texto nao overlape pra linha debaixo" (dono, 2026-09-04).

        Todos os caracteres do cabeçalho na MESMA linha de base. O CJK sobe
        uns décimos por ter outra métrica vertical, daí a tolerância de 3pt —
        uma quebra de verdade separa por uma entrelinha inteira (8pt).
        """
        tops = [c['top'] for c in self._chars_do_cabecalho()]
        self.assertLess(
            max(tops) - min(tops), 3,
            'o cabeçalho quebrou em duas linhas — refaça a medição das '
            'larguras em vendas/pdf.py')

    def test_cada_rotulo_cabe_na_coluna_medida(self):
        """A conta que sustenta a linha única, coluna a coluna.

        O teste de cima diz QUE quebrou; este diz QUAL coluna e por quantos
        pontos — que é o que se precisa saber para consertar. Se alguém mexer
        no `_L` da tabela ou nas `larguras`, é aqui que aparece.
        """
        from reportlab.pdfbase import pdfmetrics
        mono, cjk = vpdf._mono_font(), vpdf._cjk_font(force=True)
        avail = 595.2756 - 28 * 72 / 25.4
        padding = 12          # LEFTPADDING + RIGHTPADDING do TableStyle
        corpo = 6.5           # fontSize do st_th

        def largura(txt):
            import re
            total = 0.0
            for parte in re.split(r'([\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]+)',
                                  txt):
                if parte:
                    f = cjk if re.fullmatch(
                        r'[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]+',
                        parte) else mono
                    total += pdfmetrics.stringWidth(parte, f, corpo)
            return total

        colunas = ['type', 'category', 'sent', 'rejected', 'accepted',
                   'unit', 'total']
        larguras = self._larguras_do_fonte()
        self.assertEqual(len(larguras), len(colunas))
        for chave, fracao in zip(colunas, larguras):
            rotulo = vpdf._t_up(chave)
            cabe = fracao * avail - padding
            self.assertLessEqual(
                largura(rotulo), cabe,
                '%r não cabe em %.3f da faixa: precisa de %.1fpt e tem %.1fpt'
                % (rotulo, fracao, largura(rotulo), cabe))

    def _larguras_do_fonte(self):
        """As `larguras` como estão no código — a lista é a especificação."""
        fonte = io.open(vpdf.__file__.replace('.pyc', '.py'),
                        encoding='utf-8').read()
        m = re.search(r'\n    larguras = \[([^\]]+)\]', fonte)
        self.assertIsNotNone(m, 'a lista de larguras sumiu de render_result_pdf')
        return [float(x) for x in m.group(1).split(',')]

    def test_os_dois_rotulos_do_julgamento_sao_tingidos(self):
        cores = {tuple(round(v, 3) for v in (c['non_stroking_color'] or ()))
                 for c in self._chars_do_cabecalho()}
        for nome, token in (('recusados', vpdf._T_RED50),
                            ('aprovados', vpdf._T_GREEN40)):
            alvo = (round(token.red, 3), round(token.green, 3),
                    round(token.blue, 3))
            self.assertIn(
                alvo, cores,
                'o rótulo dos %s saiu branco — o TEXTCOLOR do TableStyle não '
                'atravessa Paragraph, a cor tem de estar no estilo' % nome)


class LinhaDeTotalTests(TestCase):
    """A faixa da marca e o total geral, um tom abaixo (dono, 2026-09-04).

      "a barra de titulo de cada marca, nas colunas accepted e rejected, tem
       que ter um vermelho e um verde um pouco mais escuro nesse ponto pra se
       entender que tá mostrando o total"

    O total geral entra junto por coerência: se só as faixas escurecessem, a
    linha que soma TUDO ficaria mais clara que os subtotais que ela soma.
    """

    def _fundos(self, doc):
        import pdfplumber
        dados = vpdf.render_result_pdf(doc)
        with pdfplumber.open(io.BytesIO(dados)) as arq:
            return [tuple(r['non_stroking_color']) for p in arq.pages
                    for r in p.rects if r['non_stroking_color']]

    def _quantos(self, fundos, cor, tol=.01):
        alvo = (cor.red, cor.green, cor.blue)
        return sum(1 for f in fundos if len(f) == 3
                   and all(abs(a - b) <= tol for a, b in zip(f, alvo)))

    def test_cada_faixa_de_marca_e_o_total_levam_a_tinta_forte(self):
        # LINHAS tem 2 marcas → 2 faixas + 1 total geral = 3 de cada cor
        fundos = self._fundos(_doc(LINHAS))
        self.assertEqual(self._quantos(fundos, vpdf._T_ROSE_TOT), 3)
        self.assertEqual(self._quantos(fundos, vpdf._T_MINT_TOT), 3)

    def test_a_tinta_fraca_continua_cobrindo_a_coluna_inteira(self):
        """A tinta clara é UM retângulo por coluna, do topo ao fim — se ela
        sumisse, as linhas comuns perderiam a cor que identifica a coluna."""
        fundos = self._fundos(_doc(LINHAS))
        self.assertGreaterEqual(self._quantos(fundos, vpdf._T_ROSE), 1)
        self.assertGreaterEqual(self._quantos(fundos, vpdf._T_MINT), 1)

    def test_a_faixa_da_marca_nao_cobre_as_duas_colunas(self):
        """⚠ A ordem dos estilos no reportlab é o que segura isto: a faixa
        pinta a linha inteira de `--ink-10` e é declarada ANTES. Se um dia
        alguém mover as tintas para cima, a faixa cobre as duas colunas e a
        marca aparece sem o vermelho e o verde que todas as linhas dela têm —
        e o teste acima continuaria passando, porque as tintas fracas
        seguiriam lá."""
        fonte = io.open(vpdf.__file__.replace('.pyc', '.py'),
                        encoding='utf-8').read()
        corpo = fonte[fonte.index('def render_result_pdf'):]
        self.assertLess(corpo.index('estilos_extra + ['),
                        corpo.index("('BACKGROUND', (3, 1), (3, -1)"),
                        'as tintas das colunas têm de vir DEPOIS da faixa')


class CoresSaoTokensTests(TestCase):
    """O teste que mais vale a longo prazo.

    O defeito original não era feiúra: eram cinzas NEUTROS onde o sistema usa
    cinzas FRIOS. Ninguém pega isso de olho duas vezes.
    """

    def _css(self):
        with io.open(TOKENS, encoding='utf-8') as f:
            return f.read().lower()

    def test_todo_token_do_pdf_existe_no_colors_css(self):
        css = self._css()
        usados = {nome: getattr(vpdf, nome) for nome in dir(vpdf)
                  if nome.startswith('_T_') and not nome.endswith('_TOT')}
        self.assertGreaterEqual(len(usados), 15, 'os tokens sumiram do módulo')
        fora = sorted(nome for nome, cor in usados.items()
                      if cor.hexval()[2:].lower() not in css)
        self.assertFalse(
            fora,
            'estes não são cores do design system, são hex parecidos: %s'
            % fora)

    def test_a_tinta_do_total_e_a_receita_do_css_e_nao_um_hex_novo(self):
        """Os dois `_TOT` não estão no `colors.css` — e não devem estar.

        A rampa do sistema não tem passo 20 de vermelho nem de verde. Quando a
        tela precisa da mesma tinta um tom abaixo, ela MISTURA os dois passos
        que existem, no realce das mesmas duas colunas::

            .dtab tbody tr:hover td.hr{background:color-mix(in srgb,var(--red-10) 88%,var(--red-50))}

        Este teste prende o papel a essa receita: se alguém trocar `--red-10`
        no CSS e não mexer no PDF, o `_T_ROSE` muda junto e a conta continua
        de pé; se alguém cravar um `#feddde` no lugar da mistura, aqui quebra.
        O peso é lido do próprio CSS, não cravado aqui.
        """
        comp = os.path.join(settings.BASE_DIR, 'static', 'wtc',
                            'components.css')
        with io.open(comp, encoding='utf-8') as f:
            css = f.read()
        receitas = re.findall(
            r'color-mix\(in srgb,var\(--(red|green)-10\) (\d+)%,'
            r'var\(--(?:red|green)-50\)\)', css)
        self.assertEqual(
            len(receitas), 2,
            'a receita do realce sumiu do components.css — se ela mudou, '
            'o PDF tem de mudar junto')
        pesos = {cor: 1 - int(pct) / 100.0 for cor, pct in receitas}
        self.assertEqual(pesos['red'], pesos['green'],
                         'os dois lados do julgamento têm de escurecer igual')
        self.assertEqual(
            vpdf._T_ROSE_TOT.hexval(),
            vpdf._mistura(vpdf._T_ROSE, vpdf._T_RED50, pesos['red']).hexval())
        self.assertEqual(
            vpdf._T_MINT_TOT.hexval(),
            vpdf._mistura(vpdf._T_MINT, vpdf._T_GREEN50,
                          pesos['green']).hexval())

    def test_a_linha_que_soma_e_mais_escura_que_a_que_ela_soma(self):
        """O ponto do pedido: "pra se entender que tá mostrando o total".

        Não basta ser DIFERENTE — tem de ser mais escura, senão o subtotal
        fica mais claro que os lançamentos e a hierarquia inverte.
        """
        def luz(c):
            return c.red * .2126 + c.green * .7152 + c.blue * .0722
        self.assertLess(luz(vpdf._T_ROSE_TOT), luz(vpdf._T_ROSE))
        self.assertLess(luz(vpdf._T_MINT_TOT), luz(vpdf._T_MINT))
        # e não tão escura a ponto de brigar com o número preto em cima dela
        self.assertGreater(luz(vpdf._T_ROSE_TOT), .70)
        self.assertGreater(luz(vpdf._T_MINT_TOT), .70)

    def test_os_cinzas_antigos_nao_voltaram_para_o_resultado(self):
        """`_GREY`/`_LINE`/`_ZEBRA` continuam no arquivo porque o packing list
        e o documento do gerente ainda os usam. O que não pode é o PDF do
        RESULTADO voltar a lê-los."""
        fonte = io.open(vpdf.__file__.replace('.pyc', '.py'),
                        encoding='utf-8').read()
        corpo = fonte[fonte.index('def render_result_pdf'):]
        for antigo in ('_GREY', '_ZEBRA', '_SAND ', '_SKY '):
            self.assertNotIn(antigo, corpo,
                             '%s é do palette antigo' % antigo.strip())

    def test_o_papel_nao_usa_mais_zebra(self):
        """O pacote separa linha com FIO, não com faixa. Em 100 linhas a
        zebra vira textura e para de ser informação."""
        fonte = io.open(vpdf.__file__.replace('.pyc', '.py'),
                        encoding='utf-8').read()
        corpo = fonte[fonte.index('def render_result_pdf'):]
        self.assertNotIn('_ZEBRA', corpo)
