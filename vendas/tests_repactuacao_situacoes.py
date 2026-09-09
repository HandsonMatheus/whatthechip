# -*- coding: utf-8 -*-
"""
REPACTUAÇÃO DE PREÇO — a varredura de situações (dono, 2026-09-09).

  "agora preciso que escreva testes pra eu rodar no terminal testando varias
   situacoes possiveis desta funcionalidade, de mudanca de precos"

O `tests_repactuacao.py` prova que a feature FUNCIONA. Este arquivo prova que
ela não quebra no caminho torto: número de ponta, recusa junto, várias marcas,
o dinheiro da empresa, o papel, a planilha, e o que NÃO pode acontecer.

    python manage.py test vendas.tests_repactuacao_situacoes -v 2

⚠ A regra que cada classe daqui está protegendo, dita uma vez:

      CONGELADO → ESPERADO. Não se move.
      APLICADO  → RESULTADO. É o congelado, ou o repactuado.

  Toda vez que um número aqui parece estranho, é essa distinção que está
  sendo medida.
"""

import io
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import services
from vendas.models import (DocSequence, SEQ_SO, SalesOrder, SalesOrderLine,
                           STATUS_CONFIRMED, STATUS_DRAFT)

User = get_user_model()


class _Base(TestCase):
    """Três linhas, DUAS marcas — o mínimo para exercer faixa de grupo.

    ⚠ ¥3,00 com taxa 0,1481 congela em US$ 0,44 (0,4443 arredondado). É o
      cenário do bug de 07/09, e mantê-lo aqui garante que a repactuação não o
      ressuscite por outro caminho.
    """

    FX = D('0.1481')
    #  (marca,  kind,  ¥ unit,  US$ unit,  qtd)
    LINHAS = [('Micron', 'ddr3', D('3.00'), D('0.44'), 10000),
              ('Micron', 'ddr4', D('10.00'), D('1.48'), 500),
              ('Nanya', 'emmc', D('7.00'), D('1.04'), 250)]

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer',
                                          code='', service_fee_pct=D('10.00'))
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=11, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=self.FX,
                total_rmb=sum(u * q for _m, _k, u, _uu, q in self.LINHAS),
                total_usd=sum(uu * q for _m, _k, _u, uu, q in self.LINHAS),
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            self.ls = [
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.emp, brand=m, kind=k, gen='',
                    tier_value=D(2 + i), tier_unit='GB', quantity=q,
                    unit_rmb=u, unit_usd=uu)
                for i, (m, k, u, uu, q) in enumerate(self.LINHAS)]
        self.client.force_login(self.parceiro)

    # ── atalhos ──────────────────────────────────────────────────────────
    def _linhas(self, **kw):
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so, **kw)
        return {l['pk']: l for g in grupos for l in g['lines']}

    def _grupos(self, **kw):
        with company_scope(self.emp.id):
            return {g['brand']: g for g in services.result_rows(self.so, **kw)}

    def _fechar(self, ajustes):
        with company_scope(self.emp.id):
            return services.settle_and_invoice(self.so, ajustes,
                                               self.parceiro)

    def _rascunho(self, **kw):
        with company_scope(self.emp.id):
            return services.save_draft(self.so, kw.pop('rejections', {}),
                                       self.parceiro, **kw)

    def _post(self, dados):
        return self.client.post(
            reverse('compras:resultado', args=[self.so.pk]), dados)

    def _outra_ordem(self, numero_do_lote, **extra):
        """Uma SEGUNDA OV, com LOTE PRÓPRIO.

        ⚠ `one_active_so_per_lot`: o banco recusa duas ordens ativas no mesmo
          lote — e é uma regra de negócio, não detalhe técnico: o lote é a
          caixa, e uma caixa se vende uma vez. A primeira versão deste arquivo
          reusava `self.lot` e batia na constraint.

        ⚠ `so_confirmed_is_frozen`: OV confirmada sem totais congelados também
          é recusada. É o que faz "confirmada" significar "preço fechado".
        """
        with company_scope(self.emp.id):
            lote = Lot.all_companies.create(
                company=self.emp, number=numero_do_lote, description='x',
                status='closed', operator=self.gerente, origin='pcb')
            so = SalesOrder(lot=lote, buyer=self.buyer,
                            status=STATUS_CONFIRMED, fx_usd_rate=self.FX,
                            total_rmb=D('10.00'), total_usd=D('1.50'),
                            number=DocSequence.next_number(self.emp, SEQ_SO),
                            **extra)
            so.save()
            linha = SalesOrderLine.all_companies.create(
                order=so, company=self.emp, brand='X', kind='ddr3', gen='',
                tier_value=D('2'), tier_unit='GB', quantity=10,
                unit_rmb=D('1.00'), unit_usd=D('0.15'))
        return so, linha


# ════════════════════════════════════════════════════════════════════════════
class NumeroDePontaTests(_Base):
    """Como o número entra: formato, casas, sinal e teto."""

    def test_virgula_decimal_e_aceita(self):
        """Ele digita num teclado pt-BR/zh e "2,55" é o que sai. Recusar isso
        seria transformar a vírgula em erro de preço."""
        self._post({f'price_{self.ls[0].pk}': '2,55'})
        self.assertEqual(self._linhas()[self.ls[0].pk]['novo_rmb'], D('2.55'))

    def test_mais_de_duas_casas_ARREDONDA_e_nao_recusa(self):
        """`max_digits=8, decimal_places=2` é o campo. 2,555 vira 2,56 —
        recusar seria pedir que ele fizesse o arredondamento de cabeça."""
        self._post({f'price_{self.ls[0].pk}': '2.555'})
        self.assertEqual(self._linhas()[self.ls[0].pk]['novo_rmb'], D('2.56'))

    def test_espacos_em_volta_nao_atrapalham(self):
        self._post({f'price_{self.ls[0].pk}': '  2.55  '})
        self.assertEqual(self._linhas()[self.ls[0].pk]['novo_rmb'], D('2.55'))

    def test_o_menor_preco_possivel_passa(self):
        """¥0,01 é preço, e baixo não é inválido — quem decide o preço é ele."""
        self._post({f'price_{self.ls[0].pk}': '0.01'})
        self.assertEqual(self._linhas()[self.ls[0].pk]['novo_rmb'], D('0.01'))

    def test_ZERO_nao_passa(self):
        """Zero não é preço, é recusa — e recusa tem coluna própria. Aceitar
        aqui daria dois caminhos para o mesmo fato, e o relatório de recusa
        não veria metade deles."""
        self._post({f'price_{self.ls[0].pk}': '0'})
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())

    def test_NEGATIVO_nao_passa(self):
        self._post({f'price_{self.ls[0].pk}': '-3.00'})
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())

    def test_acima_do_TETO_do_campo_nao_passa(self):
        """`max_digits=8` com 2 casas → 999.999,99. Passar disso estoura no
        banco, com um erro que não explica nada a quem está conferindo."""
        self._post({f'price_{self.ls[0].pk}': '1000000'})
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())

    def test_texto_no_lugar_do_preco_nao_passa(self):
        self._post({f'price_{self.ls[0].pk}': 'dois e meio'})
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())

    def test_o_SERVICO_tambem_recusa_preco_fora_de_faixa(self):
        """⚠ A guarda da tela protege o formulário; esta protege o CONTRATO.
        `new_unit_rmb` não tem validador de modelo e `.save()` não valida —
        um preço negativo vindo de importação, comando ou admin viraria fatura
        negativa sem uma linha sequer reclamando."""
        for ruim in (D('0'), D('-1'), D('1000000')):
            with self.assertRaises(ValidationError):
                self._fechar({self.ls[0].pk: (0, ruim)})


# ════════════════════════════════════════════════════════════════════════════
class RecusaMaisRepactuacaoTests(_Base):
    """As duas coisas na mesma linha. É onde a conta erra fácil."""

    def test_a_conta_e_aprovados_vezes_preco_NOVO(self):
        self._fechar({self.ls[0].pk: (100, D('2.55'))})
        l = self._linhas()[self.ls[0].pk]
        self.assertEqual(l['pago_rmb'], D('2.55') * 9900)

    def test_a_PERDA_da_recusa_sai_no_preco_aplicado(self):
        """A coluna RECUSADOS ¥ diz quanto a recusa tirou. Se ele repactuou,
        aqueles chips valeriam o preço NOVO — usar o congelado inflaria a
        perda com a repactuação, que já aparece no par ESPERADO × RESULTADO."""
        self._fechar({self.ls[0].pk: (100, D('2.55'))})
        self.assertEqual(self._linhas()[self.ls[0].pk]['perda_rmb'],
                         D('2.55') * 100)

    def test_recusar_TUDO_zera_a_linha_seja_qual_for_o_preco(self):
        self._fechar({self.ls[0].pk: (10000, D('2.55'))})
        l = self._linhas()[self.ls[0].pk]
        self.assertEqual(l['accepted'], 0)
        self.assertEqual(l['pago_rmb'], D('0.00'))
        self.assertEqual(l['pago_usd'], D('0.00'))

    def test_recusar_mais_do_que_veio_derruba_o_fechamento(self):
        with self.assertRaises(ValidationError):
            self._fechar({self.ls[0].pk: (10001, D('2.55'))})

    def test_o_ESPERADO_ignora_as_duas_coisas(self):
        """Nem recusa nem repactuação mexem no combinado."""
        self._fechar({self.ls[0].pk: (100, D('2.55'))})
        self.assertEqual(self._linhas()[self.ls[0].pk]['total_rmb'],
                         D('3.00') * 10000)


# ════════════════════════════════════════════════════════════════════════════
class VariasLinhasEMarcasTests(_Base):
    """Faixa dizendo um número e linhas dizendo outro é o erro que só aparece
    depois de fechado."""

    def test_repactuar_UMA_linha_nao_move_as_outras(self):
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        linhas = self._linhas()
        self.assertEqual(linhas[self.ls[1].pk]['unit_rmb'], D('10.00'))
        self.assertIsNone(linhas[self.ls[2].pk]['novo_rmb'])

    def test_repactuar_TODAS_as_linhas(self):
        self._fechar({self.ls[0].pk: (0, D('2.55')),
                      self.ls[1].pk: (0, D('9.00')),
                      self.ls[2].pk: (0, D('8.00'))})
        esperado = D('2.55') * 10000 + D('9.00') * 500 + D('8.00') * 250
        soma = sum(l['pago_rmb'] for l in self._linhas().values())
        self.assertEqual(soma, esperado)

    def test_uma_para_CIMA_e_outra_para_BAIXO_no_mesmo_acerto(self):
        """O caso que produz as duas setas na mesma tela."""
        self._fechar({self.ls[0].pk: (0, D('2.55')),
                      self.ls[1].pk: (0, D('12.00'))})
        linhas = self._linhas()
        self.assertLess(linhas[self.ls[0].pk]['novo_rmb'],
                        linhas[self.ls[0].pk]['congelado_rmb'])
        self.assertGreater(linhas[self.ls[1].pk]['novo_rmb'],
                           linhas[self.ls[1].pk]['congelado_rmb'])

    def test_a_faixa_de_CADA_marca_soma_as_linhas_dela(self):
        self._fechar({self.ls[0].pk: (50, D('2.55')),
                      self.ls[2].pk: (0, D('8.00'))})
        for g in self._grupos().values():
            self.assertEqual(g['pago_rmb'],
                             sum(l['pago_rmb'] for l in g['lines']))
            self.assertEqual(g['rmb'],
                             sum(l['total_rmb'] for l in g['lines']))

    def test_a_marca_NAO_repactuada_fica_com_esperado_igual_ao_resultado(self):
        """Nanya não foi tocada: o combinado e o conferido têm de coincidir.
        Se divergirem, alguma coisa vazou de uma marca para a outra."""
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        nanya = self._grupos()['Nanya']
        self.assertEqual(nanya['rmb'], nanya['pago_rmb'])


# ════════════════════════════════════════════════════════════════════════════
class ODinheiroDaEmpresaTests(_Base):
    """A consequência de negócio: a repactuação encolhe a comissão junto."""

    def test_a_fatura_sai_com_o_valor_REPACTUADO(self):
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55'))})
        esperado = D('2.55') * 10000 + D('10.00') * 500 + D('7.00') * 250
        self.assertEqual(inv.total_rmb, esperado)

    def test_a_COMISSAO_cai_junto_com_o_preco(self):
        """10% sobre o que de fato saiu, não sobre o combinado. É o número que
        mostra ao dono quanto a repactuação lhe custou de receita."""
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55'))})
        self.assertEqual(inv.fee_rmb, (inv.total_rmb / 10).quantize(D('0.01')))
        self.assertLess(inv.fee_rmb, (self.so.total_rmb / 10))

    def test_a_OV_confirmada_continua_com_o_combinado(self):
        antes = (self.so.total_rmb, self.so.total_usd)
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        self.so.refresh_from_db()
        self.assertEqual((self.so.total_rmb, self.so.total_usd), antes)

    def test_o_total_em_USD_e_soma_de_linhas_e_nao_yuan_vezes_taxa(self):
        """A regra do dinheiro, cobrada com repactuação no meio. Neste
        cenário as duas contas divergem — é o caso do bug de 07/09."""
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55'))})
        por_linha = sum(l['pago_usd'] for l in self._linhas().values())
        self.assertEqual(inv.total_usd, por_linha)
        self.assertNotEqual(inv.total_usd,
                            (inv.total_rmb * self.FX).quantize(D('0.01')))


# ════════════════════════════════════════════════════════════════════════════
class OPapelEAPlanilhaTests(_Base):
    """O preço novo tem de chegar no que sai da tela — senão o cliente recebe
    um documento que discorda do sistema."""

    def test_o_PDF_do_resultado_leva_o_preco_novo(self):
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55'))})
        with company_scope(self.emp.id):
            doc = services.result_document(self.so, inv)
        linha = next(l for l in doc['lines'] if l['unit_rmb'] == D('2.55'))
        self.assertEqual(linha['total_rmb'], D('2.55') * 10000)

    def test_o_PDF_deriva_o_dolar_da_linha_repactuada(self):
        """Ela não tem par em US$ congelado — é a única linha do documento em
        que o dólar não vem congelado, e o `_monta_documento` diz isso."""
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55'))})
        with company_scope(self.emp.id):
            doc = services.result_document(self.so, inv)
        linha = next(l for l in doc['lines'] if l['unit_rmb'] == D('2.55'))
        self.assertEqual(linha['unit_usd'], D('2.55') * self.FX)

    def test_o_PDF_desenha_a_SETA_e_o_preco_riscado(self):
        """Dono, 2026-09-09: *"preciso que o sistema de setas seja aplicado
        tambem no PDF de resultado parcial e no de resultado final"*.

        O documento é a prestação de contas que o cliente recebe. Se a tela
        mostra que o preço mudou e o papel não, o papel é o que fica na mão
        dele — e é o papel que ele vai citar de volta.

        ⚠ Lê o TEXTO do PDF, não o desenho: `↓` e `↑` chegam ao arquivo como
          caracteres da `WTC-Mono`. A Helvetica base do reportlab NÃO os tem
          no vetor WinAnsi — sairiam como 0x7F, o mesmo defeito que fez o
          `_MASK` ser `***` e não `•••`.
        """
        from pdfminer.high_level import extract_text
        from vendas import pdf as vpdf
        _st, inv = self._fechar({self.ls[0].pk: (0, D('2.55')),
                                 self.ls[1].pk: (0, D('12.00'))})
        with company_scope(self.emp.id):
            bruto = vpdf.render_result_pdf(
                services.result_document(self.so, inv))
        texto = extract_text(io.BytesIO(bruto))
        self.assertIn('\u2193', texto, 'a seta de queda não saiu no papel')
        self.assertIn('\u2191', texto, 'a seta de alta não saiu no papel')
        self.assertIn('3.00', texto, 'o preço antigo não saiu no papel')
        self.assertIn('2.55', texto, 'o preço novo não saiu no papel')

    def test_o_PDF_PARCIAL_tambem_leva_a_seta(self):
        """Ele manda o parcial ao cliente ANTES de fechar — é justamente o
        documento em que a repactuação ainda está em discussão, e o que mais
        precisa dizer que o preço mudou."""
        from pdfminer.high_level import extract_text
        from vendas import pdf as vpdf
        with company_scope(self.emp.id):
            doc = services.result_preview(
                self.so, {self.ls[0].pk: (0, D('2.55'))}, nota='')
            bruto = vpdf.render_result_pdf(doc)
        texto = extract_text(io.BytesIO(bruto))
        self.assertIn('\u2193', texto)
        self.assertIn('3.00', texto)

    def test_o_PDF_de_uma_OV_SEM_repactuacao_nao_ganha_seta(self):
        """A trava do outro lado: a linha não tocada tem de imprimir
        exatamente como imprimia."""
        from pdfminer.high_level import extract_text
        from vendas import pdf as vpdf
        _st, inv = self._fechar({self.ls[0].pk: (10, None)})
        with company_scope(self.emp.id):
            bruto = vpdf.render_result_pdf(
                services.result_document(self.so, inv))
        texto = extract_text(io.BytesIO(bruto))
        self.assertNotIn('\u2193', texto)
        self.assertNotIn('\u2191', texto)

    def test_a_PLANILHA_abre_e_o_unitario_e_o_aplicado(self):
        """A fórmula do RESULTADO na planilha é `aprovados × unitário`. Com o
        congelado ali, o arquivo que ele exporta daria outro total."""
        import openpyxl
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        r = self.client.get(reverse('compras:planilha', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        ws = wb['Resumo']
        unitarios = [ws.cell(row=r_, column=4).value
                     for r_ in range(8, ws.max_row + 1)]
        self.assertIn(2.55, unitarios)

    def test_a_planilha_mantem_o_ESPERADO_congelado(self):
        """Coluna I: o combinado. Se ela andasse junto, a planilha perderia a
        mesma comparação que a tela guarda."""
        import openpyxl
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        r = self.client.get(reverse('compras:planilha', args=[self.so.pk]))
        ws = openpyxl.load_workbook(io.BytesIO(r.content))['Resumo']
        esperados = [ws.cell(row=r_, column=9).value
                     for r_ in range(8, ws.max_row + 1)]
        self.assertIn(30000.0, esperados)          # 3,00 × 10.000, congelado


# ════════════════════════════════════════════════════════════════════════════
class QuandoNaoPodeTests(_Base):
    """O que NÃO pode acontecer — e é aqui que um sistema multi-empresa
    costuma vazar."""

    def test_sem_recebimento_nao_ha_campo_de_preco(self):
        """`pode_acertar` exige a chegada da caixa. Não se repactua o que
        ainda não foi conferido."""
        with company_scope(self.emp.id):
            self.so.received_at = None
            self.so.save(update_fields=['received_at'])
        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        self.assertNotIn('class="upen"', html)

    def test_OV_em_rascunho_nao_aceita_acerto(self):
        with company_scope(self.emp.id):
            self.so.status = STATUS_DRAFT
            self.so.save(update_fields=['status'])
        with self.assertRaises(ValidationError):
            self._fechar({self.ls[0].pk: (0, D('2.55'))})

    def test_nao_da_para_repactuar_linha_de_OUTRA_ordem(self):
        _outra, alheia = self._outra_ordem(12)
        with self.assertRaises(ValidationError):
            self._fechar({alheia.pk: (0, D('2.55'))})

    def test_OUTRO_comprador_nao_alcanca_esta_compra(self):
        outro_b = Buyer.all_companies.create(company=None, name='Outro',
                                             slug='outro')
        intruso = User.objects.create_user('intruso', password='x')
        outro_b.users.add(intruso)
        self.client.force_login(intruso)
        r = self._post({f'price_{self.ls[0].pk}': '2.55'})
        self.assertIn(r.status_code, (403, 404, 302))
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())

    def test_o_rascunho_de_um_NAO_vaza_para_o_outro(self):
        """Duas OVs, dois rascunhos. O `SettlementDraft` é OneToOne com a
        ordem, e é isso que este teste guarda."""
        outra, l2 = self._outra_ordem(13, received_at=timezone.now())
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.ls[0].pk: '2.55'})
            services.save_draft(outra, {}, self.parceiro,
                                prices={l2.pk: '0.50'})
            self.assertEqual(services.draft_prices(self.so),
                             {self.ls[0].pk: D('2.55')})
            self.assertEqual(services.draft_prices(outra), {l2.pk: D('0.50')})


# ════════════════════════════════════════════════════════════════════════════
class DepoisDeFecharTests(_Base):
    """O acerto é irreversível por desenho. O que acontece depois importa."""

    def test_o_RASCUNHO_e_apagado_ao_fechar(self):
        """Fatura emitida com rascunho sobrevivente é a tela lendo duas fontes
        para o mesmo número — e a que ela escolheria é a errada."""
        self._rascunho(prices={self.ls[0].pk: '2.55'})
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        with company_scope(self.emp.id):
            self.assertEqual(services.draft_prices(self.so), {})

    def test_fechar_DUAS_vezes_nao_passa(self):
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        with self.assertRaises(ValidationError):
            self._fechar({self.ls[0].pk: (0, D('2.00'))})

    def test_depois_de_fechado_a_tela_mostra_sem_campo(self):
        """A tela não muda de forma quando a etapa passa: os mesmos números,
        sem o que aceita toque."""
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        self.assertNotIn('class="upen"', html)
        self.assertIn('class="rep rep--down"', html)   # a seta FICA
        self.assertIn('¥ 2.55', html)

    def test_o_preco_repactuado_SOBREVIVE_ao_recarregamento(self):
        """O que o dono relatou em 09/09 ("ao atualizar tudo volta em
        branco"), aqui no estado FECHADO: o acerto é a fonte, e ele não
        depende de rascunho nenhum."""
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        for _ in range(2):
            self.assertEqual(self._linhas()[self.ls[0].pk]['novo_rmb'],
                             D('2.55'))


# ════════════════════════════════════════════════════════════════════════════
class OsCentavosTests(_Base):
    """Arredondamento — onde tela e fatura se separam sem ninguém ver."""

    def test_o_dolar_arredonda_por_LINHA_antes_de_multiplicar(self):
        """2,55 × 0,1481 = 0,377655 → 0,38 → × 10.000 = 3.800,00.
        Multiplicar primeiro daria 3.776,55: R$ 23 numa linha só."""
        self._fechar({self.ls[0].pk: (0, D('2.55'))})
        l = self._linhas()[self.ls[0].pk]
        self.assertEqual(l['unit_usd'], D('0.38'))
        self.assertEqual(l['pago_usd'], D('3800.00'))

    def test_preco_que_arredonda_para_BAIXO(self):
        """2,50 × 0,1481 = 0,370250 → 0,37."""
        self._fechar({self.ls[0].pk: (0, D('2.50'))})
        self.assertEqual(self._linhas()[self.ls[0].pk]['unit_usd'], D('0.37'))

    def test_meio_centavo_sobe(self):
        """ROUND_HALF_UP, e não o "meio para o par" do Python puro. Numa
        coluna de dinheiro a regra tem de ser a mesma em todo lugar."""
        # 3,3761 × 0,1481 = 0,50000... → 0,50
        self._fechar({self.ls[0].pk: (0, D('3.38'))})
        self.assertEqual(self._linhas()[self.ls[0].pk]['unit_usd'], D('0.50'))

    def test_linha_de_UMA_unidade(self):
        """Quantidade 1 é onde o arredondamento por linha aparece inteiro."""
        with company_scope(self.emp.id):
            self.ls[2].quantity = 1
            self.ls[2].save(update_fields=['quantity'])
        self._fechar({self.ls[2].pk: (0, D('6.33'))})
        l = self._linhas()[self.ls[2].pk]
        self.assertEqual(l['unit_usd'], D('0.94'))     # 6,33 × 0,1481 = 0,9375
        self.assertEqual(l['pago_usd'], D('0.94'))

    def test_a_soma_das_linhas_E_o_total_da_fatura(self):
        """A trava final: qualquer divergência de centavo aparece aqui."""
        _st, inv = self._fechar({self.ls[0].pk: (37, D('2.55')),
                                 self.ls[1].pk: (3, D('9.99')),
                                 self.ls[2].pk: (1, D('6.33'))})
        linhas = self._linhas()
        self.assertEqual(inv.total_rmb,
                         sum(l['pago_rmb'] for l in linhas.values()))
        self.assertEqual(inv.total_usd,
                         sum(l['pago_usd'] for l in linhas.values()))
