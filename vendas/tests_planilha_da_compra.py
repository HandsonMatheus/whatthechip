# -*- coding: utf-8 -*-
"""
O EXPORT DA FICHA: planilha com Resumo e Chips (dono, 2026-09-02).

  "o botao de exportar esta exportando um CSV com os chips, isso nao serve ao
   comprador, serve mais que seja exportado a aba de RESUMO e CHIPS inteira,
   1 em cada aba de planilha, assim EXATAMENTE como elas sao lá no sistema."

Três defeitos no que existia, e cada um vira teste aqui:

  1. Exportava UMA aba — a que estivesse aberta. Quem exporta uma compra quer
     a compra.
  2. CSV não tem abas, então Resumo e Chips seriam dois downloads.
  3. O CSV NÃO era fiel à tela: a aba Chips mostra `Tipo` e o CSV não
     exportava essa coluna. "Exatamente como na tela" não é figura de
     linguagem — é o que torna a planilha conferível contra o que ele viu.

⚠ Há um quarto, mais sutil, e ele tem teste próprio: o CSV decidia mostrar as
  colunas de recusa por `so.received_at`, e a TELA decide por
  `pode_acertar or tem_resultado`. São condições diferentes. Duas regras para
  a mesma pergunta divergem — é o mesmo defeito do selo que saiu do topo da
  ficha, em outro lugar.
"""

import io
import re
from decimal import Decimal as D
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
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
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=7, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1400'), total_rmb=D('3000.00'),
                total_usd=D('420.00'), shipped_at=date(2026, 8, 27),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            for marca, cap, qtd in (('Samsung', D('64'), 200),
                                    ('Hynix', D('4'), 50)):
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.emp, brand=marca,
                    kind='emmc', gen='', tier_value=cap, tier_unit='GB',
                    quantity=qtd, unit_rmb=D('10.00'),
                    # ⚠ CONGELADO na linha, como em toda OV confirmada. A
                    # primeira versão deste cenário não o tinha, e o cabeçalho
                    # da planilha saía com travessão no US$ — o que está certo
                    # para uma ordem legada e errado para o caso comum.
                    unit_usd=D('1.40'))
        self.client.force_login(self.parceiro)

    def _baixar(self):
        r = self.client.get(reverse('compras:planilha', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        return r

    def _wb(self, r=None):
        import openpyxl
        return openpyxl.load_workbook(io.BytesIO((r or self._baixar()).content))

    def _linha(self, ws, n):
        return [c.value for c in ws[n]]


class ArquivoTests(_Base):

    def test_sai_um_xlsx_de_verdade(self):
        r = self._baixar()
        self.assertEqual(
            r['Content-Type'],
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet')
        self.assertIn('attachment;', r['Content-Disposition'])
        self.assertTrue(r.content[:2] == b'PK', 'não é um zip/xlsx')

    def test_duas_abas_resumo_e_chips(self):
        """O pedido literal: "1 em cada aba de planilha"."""
        self.assertEqual(self._wb().sheetnames, ['Resumo', 'Chips'])

    def test_o_nome_do_arquivo_leva_o_codigo_da_ORDEM(self):
        """E não o do lote, como fazia o CSV. O código do lote perdeu o
        prefixo da empresa em 2026-09-02: o lote 7 de dois clientes daria o
        MESMO nome de arquivo na pasta de Downloads. É a mesma colisão que
        tirou a coluna do lote da lista de compras."""
        nome = self._baixar()['Content-Disposition']
        self.assertIn(self.so.code, nome)
        self.assertNotIn(self.lot.code, nome)

    def test_a_planilha_diz_de_que_compra_e(self):
        """Ela vira anexo de e-mail. Sem identificação, dois arquivos na mesma
        pasta são indistinguíveis.

        ⚠ SÓ O CÓDIGO DA ORDEM desde 2026-09-07 (dono: "nome do comprador e
          numero de lote remova"). É a chave que ele cita e a que a importação
          vai conferir; o resto era ruído no topo de uma tela de trabalho.
        """
        cab = self._wb()['Resumo'].cell(row=1, column=1).value
        self.assertEqual(cab, self.so.code)


class ColunasIguaisAsDaTelaTests(_Base):

    #: EXATAMENTE os `<th>` da tabela do Resumo, na ordem, em caixa alta.
    #:
    #: ⚠ A MARCA NÃO É COLUNA (2026-09-07). Era, "para dar filtro" — e o dono
    #:   pediu o contrário: *"iguais em termos não só de design, como também
    #:   de uso e posicionamento de cada coluna"*. Uma coluna a mais desloca
    #:   todas as outras, que é exatamente o que "posicionamento" proíbe. Na
    #:   planilha, como na tela, a marca é a FAIXA DE GRUPO. Quem precisa
    #:   filtrar por marca tem a aba Chips, que continua com a coluna.
    #:
    #: ⚠ O `¥` no rótulo DEIXOU de ser diferença (2026-09-07). Era: a tela
    #:   trazia o par US$/¥ empilhado na célula e por isso não podia cravar
    #:   moeda no título; a planilha, em ¥, cravava. Com a tabela da tela em
    #:   uma moeda só, os dois títulos passaram a ser o MESMO texto — e há
    #:   teste comparando as duas listas de verdade, renderizando as duas
    #:   (`test_a_planilha_e_a_TELA_tem_a_MESMA_lista_de_titulos`), em vez de
    #:   confiar em duas listas cravadas à mão.
    #: ⚠ ORDEM revista pelo dono em 2026-09-07: *"mover ESPERADO para o lado
    #:   esquerdo de RESULTADO"* e *"trocar ENVIADOS e UNITARIO de lugar"*. O
    #:   preço vem antes da quantidade, e ESPERADO cola em RESULTADO — os dois
    #:   números que ele compara ficam vizinhos. Mudou nas DUAS pontas, tela e
    #:   planilha, que é o contrato desta classe inteira.
    #:
    #: Sem conferência (ordem ainda não recebida) não existem as quatro
    #: colunas do acerto, e o ESPERADO fecha a tabela na 6ª — senão sobrariam
    #: três colunas vazias no meio. É o que `RESUMO` traz; `RESUMO_ACERTO`
    #: traz a tabela inteira.
    RESUMO = ['TIPO', 'CAPACIDADE', 'CAIXA WTC', 'UNITÁRIO ¥', 'ENVIADOS',
              'ESPERADO ¥']
    RESUMO_ACERTO = ['TIPO', 'CAPACIDADE', 'CAIXA WTC', 'UNITÁRIO ¥',
                     'ENVIADOS', 'RECUSADOS', 'RECUSADOS ¥', 'APROVADOS',
                     'ESPERADO ¥', 'RESULTADO ¥']
    #: exatamente os `<th>` da tabela de Chips, na ordem.
    CHIPS = ['PART NUMBER', 'MARCA', 'TIPO', 'SPEC', 'CAIXA WTC', 'QTD.',
             'UNITÁRIO ¥', 'TOTAL ¥']

    def test_as_colunas_do_resumo_sao_as_da_tela(self):
        cab = [c for c in self._linha(self._wb()['Resumo'], L_CAB) if c]
        self.assertEqual(cab[:len(self.RESUMO)], self.RESUMO)

    def test_a_planilha_e_a_TELA_tem_a_MESMA_lista_de_titulos(self):
        """O contrato de 07/09 medido de verdade, e não com duas listas
        cravadas à mão que alguém atualiza uma e esquece a outra.

        Renderiza a ficha do comprador, extrai os `<th>` da tabela do Resumo,
        gera o XLSX, lê a linha de títulos, e compara as duas — em caixa alta,
        que é a única diferença de forma que sobrou (a barra preta da planilha
        é toda maiúscula, como o `<th>` da tela em `text-transform`).

        Este é o teste que faz o pedido *"a ideia é que a planilha seja
        visualmente idêntico a UI"* virar uma coisa que quebra quando deixa de
        ser verdade.
        """
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])

        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        tabela = re.search(r'<table[^>]*id="tab-resumo".*?</thead>', html,
                           re.S)
        self.assertIsNotNone(tabela, 'a tabela do resumo sumiu da ficha')
        # `<th[^>]*>` casaria com `<thead>` (`<th` + `ead`) e contaria uma
        # coluna a mais — o `\b` é o que separa os dois.
        na_tela = [re.sub(r'<[^>]+>', '', t).strip().upper()
                   for t in re.findall(r'<th\b[^>]*>(.*?)</th>',
                                       tabela.group(0), re.S)]
        na_planilha = [c for c in
                       self._linha(self._wb()['Resumo'], L_CAB) if c]
        self.assertEqual(na_tela, na_planilha)
        self.assertEqual(na_tela, self.RESUMO_ACERTO)

    def test_a_marca_nao_e_coluna_e_a_planilha_nao_tem_coluna_a_mais(self):
        """A trava do "posicionamento": qualquer coluna nova antes da recusa
        empurra a coluna que o comprador digita — e é ela que a importação vai
        ler pela POSIÇÃO."""
        cab = [c for c in self._linha(self._wb()['Resumo'], L_CAB) if c]
        self.assertNotIn('Marca', cab)
        self.assertEqual(cab[0], 'TIPO', 'a primeira coluna mudou')

    def test_os_rotulos_sao_os_mesmos_msgid_da_tela(self):
        """Reusa o catálogo em vez de criar msgid paralelo: os rótulos saem
        de `_('Tipo')`, `_('Enviados')`… — as MESMAS entradas que o
        `{% trans %}` do template usa, só que em caixa alta. Um msgid novo
        aqui seria uma tradução a mais para manter, dizendo a mesma coisa."""
        import re
        from pathlib import Path
        from django.conf import settings
        tpl = (Path(settings.BASE_DIR) / 'vendas' / 'templates' / 'vendas'
               / 'partner_compra.html').read_text(encoding='utf-8')
        thead = re.search(r'<thead>.*?</thead>', tpl, re.S).group(0)
        da_tela = re.findall(r'<th[^>]*>\{%\s*trans "([^"]+)"', thead)
        for rotulo in ('Tipo', 'Capacidade', 'Caixa WTC', 'Enviados',
                       'Unitário', 'Esperado', 'Recusados', 'Aprovados',
                       'Resultado'):
            self.assertIn(rotulo, da_tela,
                          '%s deixou de ser <th> da tela' % rotulo)

    def test_as_colunas_de_chips_sao_as_da_tela(self):
        self.assertEqual([c for c in self._linha(self._wb()['Chips'], 3) if c],
                         self.CHIPS)

    def test_chips_traz_a_coluna_TIPO_que_o_csv_esquecia(self):
        """O defeito nº 3. A tela sempre mostrou `Tipo` na aba Chips; o CSV
        exportava sem ela, e ninguém tinha como notar sem comparar as duas
        lado a lado."""
        self.assertIn('TIPO', self._linha(self._wb()['Chips'], 3))


#: As colunas do Resumo, por POSIÇÃO — as mesmas constantes do exportador.
#: Cravadas aqui de propósito: se alguém acrescentar uma coluna no meio, é
#: para estes testes quebrarem, porque é a posição que a importação vai ler.
C_TIPO, C_CAP, C_WTC, C_UNIT, C_ENV = 1, 2, 3, 4, 5
C_REJ, C_REJV, C_ACE, C_ESP, C_RES = 6, 7, 8, 9, 10
#: sem conferência o ESPERADO fecha a tabela na 6ª, sem buraco antes
C_ESP_SEM_ACERTO = 6
#: As LETRAS que as fórmulas citam. Nomeadas porque a ordem já mudou uma vez
#: e um `'G%d'` cravado no meio de um `assertIn` não diz qual coluna era.
LET_UNIT, LET_ENV, LET_REJ = 'D', 'E', 'F'
LET_REJV, LET_ACE, LET_ESP, LET_RES = 'G', 'H', 'I', 'J'
#: ⚠ O CABEÇALHO tem layout PRÓPRIO e não segue a ordem das colunas de dados:
#:   três campos e dois números, duas colunas cada. Reaproveitar `C_REJ`/`C_ACE`
#:   aqui (era o que estes testes faziam) fazia a troca de ordem da tabela
#:   embaralhar o cabeçalho junto.
C_HERO_ESP, C_HERO_RES = 7, 9
#: escondida, depois de todas as visíveis — insumo do US$ do cabeçalho
C_USD = 11
#: O Resumo ganhou cabeçalho informativo em 2026-09-07: cinco linhas de
#: cabeçalho, a dica na sexta, os títulos na sétima. A aba Chips segue com o
#: cabeçalho simples (títulos na terceira).
#:
#: `L_FAIXA` é a PRIMEIRA faixa de marca e `L_1` a primeira linha de dado —
#: nomeados porque a primeira versão destes testes trocou os dois e leu o
#: cabeçalho achando que lia a faixa.
L_CAB, L_FAIXA, L_1 = 7, 8, 9
_LETRA_USD = 'K'


class NumeroEhNumeroTests(_Base):

    def test_dinheiro_sai_como_numero_com_formato(self):
        """O motivo de ser planilha e não print. Texto "¥ 2.000,00" parece
        igual na tela e não soma — e quem exporta soma a coluna."""
        ws = self._wb()['Resumo']
        achou = False
        for linha in range(L_1, ws.max_row + 1):
            c = ws.cell(row=linha, column=C_ESP_SEM_ACERTO)
            if isinstance(c.value, (int, float)):
                self.assertIn('¥', c.number_format)
                achou = True
        self.assertTrue(achou, 'nenhuma célula de dinheiro virou número')

    def test_quantidade_sai_como_inteiro(self):
        """Na LINHA. Na faixa e no rodapé a quantidade é `SUM` — ver
        `PlanilhaVivaTests`."""
        ws = self._wb()['Resumo']
        self.assertIsInstance(ws.cell(row=L_1, column=C_ENV).value, int)

    def test_o_total_bate_com_o_congelado_da_ordem(self):
        """⚠ E é o ÚNICO número do rodapé que não é fórmula, de propósito: o
        esperado é o congelado da ordem — o valor que o cliente tinha na mão
        quando a caixa saiu —, e não a soma de hoje. É o que a tela mostra
        ali. Somar as faixas aqui apagaria a diferença entre o combinado e o
        conferido, que é a informação da tabela."""
        ws = self._wb()['Resumo']
        self.assertEqual(
            ws.cell(row=ws.max_row, column=C_ESP_SEM_ACERTO).value,
            float(self.so.total_rmb))


class ColunasDeAcertoTests(_Base):
    """As colunas Recusados / Aprovados / ¥ resultado.

    ⚠ CORREÇÃO DE UMA AFIRMAÇÃO ERRADA (2026-09-02). Escrevi antes que "uma
    ordem confirmada e sem fatura já mostra as colunas mesmo antes do
    recebimento". É falso, e o teste que nasceu dessa frase quebrou na
    primeira execução — bem quebrado. O `pode_acertar` EXIGE o recebimento
    ("ele deve acusar como recebido primeiro", dono 2026-08-18): não se
    confere caixa que ainda não chegou.

    A divergência entre a tela e o CSV antigo existe, mas é o caso OPOSTO:

        tela .. (confirmada E sem fatura E recebida)  OU  (tem fatura)
        csv .... recebida

    Elas só discordam quando há FATURA e o recebimento nunca foi registrado —
    o estado `pulado` do trilho, em que o resultado fechou sem ninguém marcar
    a chegada. Aí a tela mostra as colunas (a conferência aconteceu, e é o que
    o comprador precisa reler) e o CSV as escondia. A planilha segue a tela.
    """

    def _cabecalho(self):
        return [c for c in self._linha(self._wb()['Resumo'], L_CAB) if c]

    ACERTO = ['RECUSADOS', 'RECUSADOS ¥', 'APROVADOS', 'RESULTADO ¥']

    def test_sem_recebimento_as_colunas_nao_aparecem(self):
        """Não há o que relatar: nada foi conferido. Coluna vazia num export
        é pergunta sem resposta."""
        self.assertIsNone(self.so.received_at)
        cab = self._cabecalho()
        for coluna in self.ACERTO:
            self.assertNotIn(coluna, cab)

    def test_sem_conferencia_o_ESPERADO_fecha_a_tabela_sem_buraco(self):
        """Com conferência o ESPERADO é a 9ª (colado no RESULTADO). Sem ela
        não existem as três colunas do acerto na frente, e deixá-lo na 9ª
        abriria três colunas VAZIAS no meio da tabela — que é a coisa que a
        ordem inteira existe para evitar."""
        self.assertIsNone(self.so.received_at)
        ws = self._wb()['Resumo']
        self.assertEqual(ws.cell(row=L_CAB, column=C_ESP_SEM_ACERTO).value,
                         'ESPERADO ¥')
        self.assertIsNone(ws.cell(row=L_CAB, column=C_ESP_SEM_ACERTO + 1).value)

    def test_a_ordem_das_colunas_e_a_que_o_dono_pediu(self):
        """Dono, 2026-09-07: *"mover ESPERADO para o lado esquerdo de
        RESULTADO"* e *"trocar ENVIADOS e UNITARIO de lugar"* — e valendo nas
        DUAS pontas, tela e planilha.

        A lista inteira, e não só as duas mexidas: é a posição que a
        importação vai ler, e um teste que cobra só o que mudou deixa a
        próxima coluna nova entrar em qualquer lugar.
        """
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        self.assertEqual(self._cabecalho(),
                         ColunasIguaisAsDaTelaTests.RESUMO_ACERTO)

    def test_o_ESPERADO_e_vizinho_do_RESULTADO(self):
        """O motivo do pedido, dito como invariante: os dois números que ele
        compara ficam lado a lado, sem o olho atravessar a tabela."""
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        cab = self._cabecalho()
        self.assertEqual(cab.index('RESULTADO ¥') - cab.index('ESPERADO ¥'), 1)

    def test_o_UNITARIO_vem_antes_dos_ENVIADOS(self):
        """Ele confere o preço primeiro, depois quanto veio."""
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        cab = self._cabecalho()
        self.assertEqual(cab.index('ENVIADOS') - cab.index('UNITÁRIO ¥'), 1)

    def test_marcado_o_recebimento_as_colunas_entram(self):
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        cab = self._cabecalho()
        for coluna in self.ACERTO:
            self.assertIn(coluna, cab)

    def test_a_planilha_usa_a_MESMA_condicao_que_a_tela(self):
        """A trava. Se alguém trocar a condição do exportador por
        `received_at` — que é o que o CSV antigo fazia —, este teste continua
        passando aqui e falha no caso `pulado`; por isso ele compara a
        CONDIÇÃO, e não o efeito: os dois lados têm de ler o mesmo
        `pode_acertar or tem_resultado` do `_detalhe`.

        ⚠ `_detalhe` toca `InventoryEntry`, que é multi-empresa: fora de um
        `company_scope` o próprio ORM levanta `CompanyScopeMissing`. Na view
        quem abre o escopo é o `services.buyer_order`; aqui tem de ser
        explícito. Foi assim que este teste falhou da primeira vez — e a falha
        provou, de graça, que a view está certa em chamar `_detalhe` DENTRO do
        `with`.
        """
        from vendas.views_partner import _detalhe
        for recebido in (False, True):
            self.so.received_at = timezone.now() if recebido else None
            self.so.save(update_fields=['received_at'])
            with company_scope(self.emp.id):
                ctx = _detalhe(self.so)
            esperado = ctx['pode_acertar'] or ctx['tem_resultado']
            self.assertEqual(esperado, recebido,
                             'a condição da tela mudou — reveja a planilha')
            cab = self._cabecalho()
            self.assertEqual('RECUSADOS' in cab, esperado,
                             'a planilha discorda da tela com recebido=%s'
                             % recebido)


class DesenhoIgualAoDaTelaTests(_Base):
    """A planilha é a MESMA tabela (dono, 2026-09-07).

      "é muito comum o comprador exportar os chips e trabalhar na planilha,
       em vez de na UI (...) a ideia é que a planilha seja visualmente
       idêntica à UI, para facilitar a edição e familiaridade lá"

    O que se trava aqui não é "está bonito" — isso é olho, e o olho fez o
    trabalho medindo o arquivo aberto no LibreOffice. O que fica travado é o
    que some sem avisar: as cores saírem do `colors.css` e não de um hex
    parecido, e a célula que ele digita continuar marcada como campo.

    É o mesmo argumento do teste de cores do PDF do resultado, e pelo mesmo
    motivo: a diferença some numa olhada isolada e aparece quando o arquivo
    está do lado da tela.
    """

    def setUp(self):
        super().setUp()
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])

    def _tokens(self):
        import os
        import re
        caminho = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'tokens',
                               'colors.css')
        with io.open(caminho, encoding='utf-8') as f:
            css = f.read()
        # O BLOCO CLARO, que é o que a planilha copia: o arquivo declara os
        # mesmos nomes duas vezes — `:root` é o claro, `[data-theme="dark"]`
        # é o escuro. Ler o arquivo inteiro pegaria a segunda declaração de
        # cada token e o teste cobraria a paleta do tema errado.
        claro = css[:css.index('[data-theme="dark"]')]
        return {n: v.upper() for n, v in
                re.findall(r'--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})', claro)}

    def _cor(self, cel, onde='fill'):
        if onde == 'fill':
            return (cel.fill.fgColor.rgb or '')[-6:] if cel.fill.fill_type \
                else ''
        return (cel.font.color.rgb or '')[-6:] if cel.font.color else ''

    def test_o_cabecalho_e_a_barra_preta_da_tela(self):
        t = self._tokens()
        ws = self._wb()['Resumo']
        self.assertEqual(self._cor(ws.cell(row=L_CAB, column=C_TIPO)),
                         t['ink-90'][1:])
        self.assertEqual(self._cor(ws.cell(row=L_CAB, column=C_TIPO), 'font'),
                         'FFFFFF')
        # e as colunas do acerto no `--ink-100`, como `.dtab th.hr/.hg/.hb`
        for col in (C_REJ, C_REJV, C_ACE, C_RES):
            self.assertEqual(self._cor(ws.cell(row=L_CAB, column=col)),
                             t['ink-100'][1:], 'coluna %s' % col)

    def test_cada_coluna_do_acerto_tem_a_COR_dela(self):
        """Vermelho, verde e azul, os mesmos `--red-50/--green-40/--blue-40`
        do `.dtab th.hr/.hg/.hb`. É por eles que o olho acha a coluna."""
        t = self._tokens()
        ws = self._wb()['Resumo']
        for col, token in ((C_REJ, 'red-50'), (C_REJV, 'red-50'),
                           (C_ACE, 'green-40'), (C_RES, 'blue-40')):
            self.assertEqual(
                self._cor(ws.cell(row=L_CAB, column=col), 'font'),
                t[token][1:], 'a cor da coluna %s saiu do token' % col)

    def test_as_tres_tintas_de_coluna_sao_as_da_tela(self):
        """`.dtab tbody td.hr/.hg/.hb` — `--red-10`, `--green-10`,
        `--blue-10`."""
        t = self._tokens()
        ws = self._wb()['Resumo']
        linha = L_1                                 # a primeira linha de dado
        for col, token in ((C_REJV, 'red-10'), (C_ACE, 'green-10'),
                           (C_RES, 'blue-10')):
            self.assertEqual(self._cor(ws.cell(row=linha, column=col)),
                             t[token][1:], 'a tinta da coluna %s' % col)

    def test_a_FAIXA_e_o_RODAPE_levam_a_tinta_um_tom_abaixo(self):
        """Dono, 07/09, olhando o PDF: *"vc aderiu as cores da coluna também
        na barra de titulo de cada marca, deixando ela so mais escura (...)
        quero que aplique na planilha e também na UI"*.

        As duas linhas que SOMAM — a faixa da marca e o rodapé — levam a
        mesma tinta da coluna um passo abaixo. Sem isso, o subtotal de uma
        marca tem exatamente a cor das linhas que ele soma, e num lote de 40
        linhas o olho não distingue a conta do lançamento.

        Hexes conferidos no arquivo ABERTO e batendo com o `getComputedStyle`
        do Chromium sobre a mesma tabela na tela — ver
        `tests_cor_da_linha_que_soma`, que amarra as três superfícies.
        """
        from vendas.planilha import BLUE_TOT, GREEN_TOT, RED_TOT
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        ws = self._wb()['Resumo']
        for linha in (L_FAIXA, ws.max_row):
            for col, tom in ((C_REJ, RED_TOT), (C_REJV, RED_TOT),
                             (C_ACE, GREEN_TOT), (C_RES, BLUE_TOT)):
                self.assertEqual(
                    self._cor(ws.cell(row=linha, column=col)), tom,
                    'linha %s, coluna %s' % (linha, col))

    def test_a_linha_de_DADO_continua_com_a_tinta_clara(self):
        """A outra metade: se as duas ficassem no mesmo tom, o passo a mais
        não diria nada. É a DIFERENÇA entre as duas que carrega a informação.
        """
        from vendas.planilha import GREEN_TOT, RED_TOT
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        t = self._tokens()
        ws = self._wb()['Resumo']
        self.assertEqual(self._cor(ws.cell(row=L_1, column=C_REJV)),
                         t['red-10'][1:])
        self.assertNotEqual(self._cor(ws.cell(row=L_1, column=C_REJV)),
                            RED_TOT)
        self.assertEqual(self._cor(ws.cell(row=L_1, column=C_ACE)),
                         t['green-10'][1:])
        self.assertNotEqual(self._cor(ws.cell(row=L_1, column=C_ACE)),
                            GREEN_TOT)

    def test_a_celula_que_ele_digita_esta_MARCADA_como_campo(self):
        """Na tela é um `<input>` branco com régua vermelha; aqui a célula É o
        campo, então ela fica branca com a régua vermelha embaixo. Sem essa
        marca a planilha não diz onde se escreve — e é ela que a importação
        vai ler."""
        t = self._tokens()
        c = self._wb()['Resumo'].cell(row=L_1, column=C_REJ)
        self.assertEqual(self._cor(c), 'FFFFFF')
        self.assertEqual((c.border.bottom.color.rgb or '')[-6:],
                         t['red-60'][1:])
        self.assertEqual(c.border.bottom.style, 'medium')

    def test_a_faixa_da_marca_traz_a_marca_e_quantas_linhas(self):
        """A `<tr class="g">` da tela, inclusive o "N linhas" em corpo menor.
        Sem ela a planilha teria de trazer a marca em coluna — que é o que
        deslocava tudo."""
        ws = self._wb()['Resumo']
        faixas = [str(ws.cell(row=r, column=C_TIPO).value)
                  for r in range(L_FAIXA, ws.max_row + 1)]
        for marca in ('Samsung', 'Hynix'):
            self.assertTrue(any(marca in f for f in faixas),
                            'a faixa de %s sumiu' % marca)
        self.assertTrue(any('linha' in f for f in faixas),
                        'o "N linhas" da faixa sumiu')

    def test_a_dica_da_tela_veio_junto(self):
        """A barra azul do `.rhint`, palavra por palavra. É ela que conta a
        regra do campo a quem abre o arquivo dias depois — e é a legenda que
        toda planilha para preencher precisa ter."""
        ws = self._wb()['Resumo']
        self.assertIn('campo em branco vale zero',
                      str(ws.cell(row=L_CAB - 1, column=1).value))

    def test_sem_conferencia_nao_ha_dica_de_digitar(self):
        """Fechada, não há o que digitar: a barra sai, como sai da tela."""
        self.so.received_at = None
        self.so.save(update_fields=['received_at'])
        self.assertIsNone(
            self._wb()['Resumo'].cell(row=L_CAB - 1, column=1).value)


class PlanilhaVivaTests(_Base):
    """As colunas derivadas são FÓRMULA, não o número que o servidor calculou.

    É a diferença entre uma foto e a tela. O dono trabalha NA planilha; se
    digitar 12 ali não move a perda, o aprovado, o resultado, a faixa da marca
    e o rodapé — como move na tela —, ele tem de voltar para a tela para
    conferir, e a planilha não serviu para nada.

    ⚠ Os testes cobram a FÓRMULA, e não o resultado dela: o openpyxl escreve
      fórmula sem valor em cache, e quem calcula é o Excel na mão dele. O
      valor foi conferido à parte, abrindo o arquivo no LibreOffice — 86
      fórmulas, zero erros.
    """

    def setUp(self):
        super().setUp()
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])

    def test_a_perda_o_aprovado_e_o_resultado_saem_da_celula_do_campo(self):
        ws = self._wb()['Resumo']
        r = L_1                                     # primeira linha de dado
        self.assertIn('%s%d' % (LET_REJ, r),
                      ws.cell(row=r, column=C_REJV).value)
        self.assertIn('%s%d' % (LET_REJ, r),
                      ws.cell(row=r, column=C_ACE).value)
        self.assertTrue(ws.cell(row=r, column=C_RES).value.startswith('='))

    def test_o_vazio_vale_ZERO_tambem_na_planilha(self):
        """`N()` devolve zero para vazio E para texto: é o que faz a regra da
        tela valer aqui, e o que impede a coluna inteira de virar `#VALUE!`
        quando ele digitar "ok" numa célula por engano."""
        ws = self._wb()['Resumo']
        self.assertIn('N(%s%d)' % (LET_REJ, L_1),
                      ws.cell(row=L_1, column=C_ACE).value)

    def test_a_faixa_soma_as_linhas_dela(self):
        """O mesmo contrato da tela: faixa dizendo um número e linhas dizendo
        outro é o erro que só aparece depois de fechado."""
        ws = self._wb()['Resumo']
        for col in (C_ENV, C_ESP, C_REJV, C_ACE, C_RES):
            self.assertIn('SUM(', str(ws.cell(row=L_FAIXA, column=col).value),
                          'a faixa parou de somar a coluna %s' % col)

    def test_o_rodape_soma_as_FAIXAS(self):
        """E não as linhas: cada faixa já soma as linhas dela, então o rodapé
        fecha com a tela por construção — e é a mesma cadeia que a tela
        percorre (linha → grupo → total)."""
        ws = self._wb()['Resumo']
        formula = ws.cell(row=ws.max_row, column=C_ACE).value
        self.assertTrue(formula.startswith('='))
        self.assertNotIn('SUM', formula)
        self.assertIn('+', formula)

    def test_a_recusa_e_POSITIVA_na_celula_que_ele_digita(self):
        """Como no campo da tela. Negativa é a LEITURA — faixa e rodapé —, e
        é assim que a tela também mostra. E é o número positivo que a
        importação vai ler de volta."""
        with company_scope(self.emp.id):
            from vendas import services
            from vendas.models import SalesOrderLine
            linha = SalesOrderLine.objects.filter(order=self.so).first()
            services.save_draft(self.so, {linha.pk: 7}, self.parceiro)
        ws = self._wb()['Resumo']
        digitados = [ws.cell(row=r, column=C_REJ).value
                     for r in range(L_FAIXA, ws.max_row + 1)]
        self.assertIn(7, digitados, 'o número digitado não voltou: %r'
                      % digitados)
        self.assertTrue(
            ws.cell(row=L_FAIXA, column=C_REJ).value.startswith('=-'))


class CabecalhoInformativoTests(_Base):
    """O topo do Resumo (dono, 2026-09-07).

      "faca um cabecalho informativo simples com o valor esperado e o valor do
       resultado, esse deve se atualizar conforme ele vai mexendo, deve ter tbm
       nesse cabeclho o numero da ordem de venda, o TIPO do lote, o cliente e a
       TAXA de cambio, essas sao as unicas informacoes q importam, nome do
       comprador e numero de lote remova."
    """

    def setUp(self):
        super().setUp()
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])

    def _topo(self):
        ws = self._wb()['Resumo']
        return [str(ws.cell(row=r, column=c).value)
                for r in range(1, L_CAB) for c in range(1, C_USD + 1)
                if ws.cell(row=r, column=c).value is not None]

    def test_traz_as_quatro_informacoes_que_importam(self):
        topo = self._topo()
        self.assertIn(self.so.code, topo)
        self.assertIn(self.emp.name, topo)                  # cliente
        self.assertIn(self.lot.get_origin_display(), topo)  # tipo do lote
        self.assertIn(float(self.so.fx_usd_rate), [
            v for v in self._wb()['Resumo'].iter_rows(
                min_row=1, max_row=L_CAB - 1, values_only=True)
            for v in v if isinstance(v, float)])

    def test_o_comprador_e_o_lote_SAIRAM(self):
        """Pedido literal. E não é só limpeza: o topo de uma tela de trabalho
        só aguenta o que ele usa para decidir."""
        topo = ' '.join(self._topo())
        self.assertNotIn(self.buyer.name, topo)
        self.assertNotIn(self.lot.code, topo)

    def test_o_resultado_do_topo_ACOMPANHA_o_que_ele_digita(self):
        """"esse deve se atualizar conforme ele vai mexendo" — então é
        fórmula, e ela aponta para o rodapé da tabela, que por sua vez soma as
        faixas. Uma segunda conta aqui divergiria da primeira."""
        ws = self._wb()['Resumo']
        rmb = ws.cell(row=4, column=C_HERO_RES).value
        usd = ws.cell(row=5, column=C_HERO_RES).value
        self.assertTrue(str(rmb).startswith('='), rmb)
        self.assertIn('%s%d' % (LET_RES, ws.max_row), rmb)
        self.assertIn('SUMPRODUCT', str(usd))

    def test_o_esperado_do_topo_NAO_se_move(self):
        """É o congelado da ordem — o número que o cliente tinha na mão
        quando a caixa saiu. Se ele se movesse junto, a diferença entre o
        combinado e o conferido sumiria da tela."""
        ws = self._wb()['Resumo']
        self.assertEqual(ws.cell(row=4, column=C_HERO_ESP).value,
                         float(self.so.total_rmb))
        self.assertEqual(ws.cell(row=5, column=C_HERO_ESP).value,
                         float(self.so.total_usd))

    def test_o_dolar_NAO_e_o_yuan_vezes_a_taxa(self):
        """⚠ A armadilha. Na tela o US$ é a soma dos unitários CONGELADOS, e
        não ¥ × taxa — as duas contas diferem em alguns dólares. Por isso a
        planilha carrega o unitário em US$ numa coluna escondida e soma por
        `SUMPRODUCT`: derivar da taxa daria um número que discorda da tela sem
        nada dizendo qual está certo."""
        ws = self._wb()['Resumo']
        self.assertIn(_LETRA_USD,
                      str(ws.cell(row=5, column=C_HERO_RES).value))
        self.assertTrue(ws.column_dimensions[_LETRA_USD].hidden,
                        'a coluna do US$ unitário ficou visível')
        # a coluna escondida traz o CONGELADO da linha, não uma conta
        self.assertEqual(ws.cell(row=L_1, column=C_USD).value,
                         float(self.so.lines.all()[0].unit_usd))

    def test_sem_nenhum_unitario_em_dolar_o_topo_diz_TRAVESSAO(self):
        """Ordem legada, ou rascunho sem taxa: o `SUMPRODUCT` daria ZERO, e
        "US$ 0.00" é um preço — ausência de preço não é. A tela faz o mesmo."""
        with company_scope(self.emp.id):
            self.so.lines.all().update(unit_usd=None)
        self.assertEqual(
            self._wb()['Resumo'].cell(row=5, column=C_HERO_RES).value, '—')


class SoOCampoEditavelTests(_Base):
    """Dono, 2026-09-07: *"esta sendo possivel digital texto tbm onde digita
    os chips rechazados, proiba"* e *"inabilite todos os outros campos de
    serem editados, exceto o de chips recusados"*.

    Duas travas para duas coisas diferentes: a PROTEÇÃO impede tocar no que
    não é campo (um Ctrl+V no lugar errado apaga uma fórmula e a planilha
    passa a mostrar um número que não é dela, em silêncio); a VALIDAÇÃO
    recusa o que não é inteiro entre 0 e o enviado — o `min`/`max` do
    `<input>` da tela, palavra por palavra.
    """

    def setUp(self):
        super().setUp()
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        self.ws = self._wb()['Resumo']

    def test_a_folha_esta_protegida_e_SEM_senha(self):
        """Sem senha de propósito: isto é guarda de mão trocada, não segredo.
        Uma planilha que ele não consegue destrancar viraria um problema
        dele."""
        self.assertTrue(self.ws.protection.sheet)
        self.assertIsNone(self.ws.protection.password)

    def test_so_a_coluna_da_recusa_esta_destrancada(self):
        soltas = {c.coordinate for linha in self.ws.iter_rows()
                  for c in linha
                  if c.protection and c.protection.locked is False}
        self.assertTrue(soltas, 'nada ficou editável — nem o campo')
        self.assertTrue(all(c.startswith(LET_REJ) for c in soltas),
                        'algo fora da coluna da recusa ficou editável: %s'
                        % sorted(soltas))

    def test_a_faixa_e_o_rodape_continuam_trancados(self):
        """São fórmula: se ele digitar por cima, a tabela passa a somar outra
        coisa e nada avisa."""
        for r in (L_FAIXA, self.ws.max_row):
            self.assertTrue(self.ws.cell(row=r, column=C_REJ).protection.locked,
                            'linha %d ficou editável' % r)

    def test_redimensionar_coluna_continua_liberado(self):
        """Não é editar dado — e uma coluna estreita que não se pode alargar é
        uma tela pior. (`False` no OOXML quer dizer PERMITIDO.)"""
        self.assertFalse(self.ws.protection.formatColumns)
        self.assertFalse(self.ws.protection.formatRows)

    def _dv(self):
        dvs = self.ws.data_validations.dataValidation
        self.assertEqual(len(dvs), 1, 'esperava UMA validação: %r' % dvs)
        return dvs[0]

    def test_texto_nao_entra_no_campo(self):
        dv = self._dv()
        self.assertEqual(dv.type, 'whole')
        self.assertEqual(dv.errorStyle, 'stop', 'aviso não basta: tem de BARRAR')
        self.assertTrue(dv.showErrorMessage)

    def test_nao_da_para_recusar_mais_do_que_veio(self):
        """⚠ `$D8` e não `D8`: o `$` trava a COLUNA e deixa a linha correr, de
        modo que em `G12` a regra vira `$D12`. Sem ele a referência andaria
        também na horizontal se alguém mexesse no `sqref`, e a regra passaria
        a comparar com a coluna errada — silenciosamente."""
        dv = self._dv()
        self.assertEqual(dv.operator, 'between')
        self.assertEqual(dv.formula1, '0')
        self.assertEqual(dv.formula2, '$%s%d' % (LET_ENV, L_1))
        self.assertTrue(dv.allow_blank, 'campo em branco tem de valer zero')

    def test_a_validacao_cobre_TODOS_os_campos_e_so_eles(self):
        from openpyxl.utils import get_column_letter
        dv = self._dv()
        celulas = {'%s%d' % (get_column_letter(col), linha)
                   for faixa in dv.sqref.ranges for linha, col in faixa.cells}
        soltas = {c.coordinate for linha in self.ws.iter_rows()
                  for c in linha
                  if c.protection and c.protection.locked is False}
        self.assertEqual(celulas, soltas,
                         'validação e destravamento discordam sobre onde se '
                         'digita')


class BotaoDaFichaTests(_Base):

    def test_o_botao_aponta_para_a_planilha(self):
        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        self.assertIn(reverse('compras:planilha', args=[self.so.pk]), html)

    def test_o_botao_nao_segue_mais_a_aba(self):
        """Some junto a reescrita do href no JS. Sem destino variável não há o
        que reescrever — e era ela que podia entregar o arquivo da aba
        anterior com o nome da atual."""
        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        self.assertNotIn("exp.href", html)
        self.assertNotIn('id="exp-aba"', html)


class SoDoDonoTests(_Base):

    def test_outro_comprador_nao_baixa(self):
        """A planilha carrega preço e quantidade de um lote inteiro. Quem
        entra pela URL sem ser o dono da ordem não pode receber nada."""
        outro_buyer = Buyer.all_companies.create(company=None, name='Outro',
                                                 slug='outro')
        outro = User.objects.create_user('u_outro', password='x')
        outro_buyer.users.add(outro)
        self.client.force_login(outro)
        r = self.client.get(reverse('compras:planilha', args=[self.so.pk]))
        self.assertIn(r.status_code, (403, 404))


class IdiomaTests(_Base):
    """A planilha herda o idioma ATIVO do usuário (dono, 2026-09-02: "preciso
    que o idioma dela herde do idioma do sistema do usuario no momento, é
    possivel?").

    É — e sai de graça, desde que os rótulos sejam resolvidos na HORA da
    requisição. `gettext` (e não `gettext_lazy` guardado em constante de
    módulo) faz exatamente isso: a constante seria resolvida no import e
    congelaria o idioma do primeiro processo que carregasse o módulo, que é o
    bug clássico e o motivo de o `_stage_labels` ser função e não dicionário.

    Estes testes existem para que uma "otimização" futura — subir a lista de
    colunas para o topo do arquivo, por exemplo — não passe despercebida.
    """

    #: (nome da aba, coluna Marca, coluna Enviados) — os valores SÃO os do
    #: catálogo versionado, conferidos um a um. Cravar aqui é o ponto: se o
    #: `.mo` deixar de ser compilado, o rótulo cai no msgid em português e
    #: este teste é quem avisa.
    ESPERADO = {
        'pt-br':   ('Resumo', 'Marca', 'Enviados'),
        'en':      ('Summary', 'Brand', 'Sent'),
        'es':      ('Resumen', 'Marca', 'Enviados'),
        'zh-hans': ('汇总', '品牌', '发出'),
    }

    def _em(self, idioma):
        c = Client()
        c.force_login(self.parceiro)
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = idioma
        r = c.get(reverse('compras:planilha', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        import openpyxl
        return openpyxl.load_workbook(io.BytesIO(r.content))

    def test_o_nome_das_abas_segue_o_idioma(self):
        for idioma in self.ESPERADO:
            wb = self._em(idioma)
            self.assertEqual(wb.sheetnames[0], self.ESPERADO[idioma][0],
                             'aba Resumo em %s' % idioma)

    def test_os_titulos_das_colunas_seguem_o_idioma(self):
        """⚠ A MARCA é conferida na aba CHIPS: no Resumo ela deixou de ser
        coluna em 2026-09-07 (virou a faixa de grupo, como na tela). Os
        rótulos saem em CAIXA ALTA, como os `<th>` da tela — daí o `.upper()`
        na comparação, que também prova que o `.upper()` do exportador não
        estraga o chinês (não há caixa em ideograma)."""
        for idioma, (aba, marca, enviados) in self.ESPERADO.items():
            wb = self._em(idioma)
            resumo = [c.value for c in wb[aba][L_CAB]]
            self.assertIn(enviados.upper(), resumo,
                          'coluna Enviados em %s' % idioma)
            self.assertNotIn(marca.upper(), resumo,
                             'a Marca voltou a ser coluna do Resumo (%s)'
                             % idioma)
            chips = [c.value for c in wb[wb.sheetnames[1]][3]]
            self.assertIn(marca.upper(), chips,
                          'coluna Marca da aba Chips em %s' % idioma)

    def test_trocar_de_idioma_troca_o_arquivo(self):
        """A prova de que nada ficou preso no import: dois downloads na MESMA
        sessão do processo, em idiomas diferentes, saem diferentes."""
        self.assertNotEqual(self._em('pt-br').sheetnames,
                            self._em('en').sheetnames)

    def test_os_numeros_nao_traduzem(self):
        """Rótulo traduz; DADO não. A quantidade e o dinheiro são os mesmos em
        qualquer idioma — se um dia alguém formatar o número no Python em vez
        de deixar no formato da célula, é aqui que aparece.

        ⚠ Compara a COLUNA INTEIRA entre os idiomas, e não uma célula fixa. A
        primeira versão cravava "linha 4 vale 200" e falhou: o `result_rows`
        devolve os grupos ordenados por marca, então a linha 4 é a faixa do
        Hynix (50), não a do Samsung que o cenário cria primeiro. Cravar
        posição num teste é depender de uma ordenação que o teste não declara
        — e comparar entre idiomas é o que a garantia realmente diz.
        """
        colunas = {}
        for idioma, (aba, _m, _e) in self.ESPERADO.items():
            ws = self._em(idioma)[aba]
            colunas[idioma] = [ws.cell(row=r, column=C_ENV).value
                               for r in range(L_FAIXA, ws.max_row + 1)]
        referencia = colunas['pt-br']
        # ⚠ A coluna tem DOIS tipos desde 2026-09-07: as LINHAS trazem o
        #   inteiro e as faixas/rodapé trazem `=SUM(...)`. Fórmula também não
        #   traduz — e é justamente o que este teste garante quando compara a
        #   coluna inteira entre os idiomas.
        numeros = [v for v in referencia if isinstance(v, int)]
        self.assertEqual(sorted(numeros), [50, 200],
                         'as quantidades das linhas mudaram: %r' % referencia)
        self.assertTrue(all(isinstance(v, str) and v.startswith('=')
                            for v in referencia if not isinstance(v, int)),
                        'faixa/rodapé deixaram de ser fórmula: %r'
                        % referencia)
        for idioma, valores in colunas.items():
            self.assertEqual(valores, referencia,
                             'a coluna Enviados mudou em %s' % idioma)
