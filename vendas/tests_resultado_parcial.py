# -*- coding: utf-8 -*-
"""
RESULTADO PARCIAL — o papel da conversa sobre a recusa (dono, 2026-09-04).

  "o comprador digita os chips recusados e nao tem como mandar isso pro
   cliente pra comecar uma discussao sobre os recusados, diagnostico,
   explicacoes, etc (...) um botao de Resultado parcial, ao lado do botao de
   fechar resultado, que so aparece na etapa de Conferencia, e baixa
   exatamente o mesmo PDF que gera o botao de imprimir resultado quando o
   resultado ja foi fechado, com a unica diferenca que tanto o nome do
   arquivo quanto o titulo principal do PDF dizem PARCIAL Result"

O buraco era de PROCESSO, não de tela: entre digitar a recusa e fechar o
resultado existe uma conversa com o cliente, e ela não tinha papel. Fechar
para poder mandar o PDF é irreversível — o número vira definitivo e o
pagamento passa a correr sobre ele.

As três garantias que este arquivo trava, na ordem em que quebram:

  1. NÃO PERSISTE NADA. É a mais importante e a mais silenciosa: um parcial
     que gravasse acerto, fatura, observação ou `received_at` transformaria um
     rascunho impresso em estado, e o comprador descobriria isso ao clicar em
     "Fechar resultado" e ouvir que a OV já tem fatura.

  2. O NÚMERO É O MESMO do fechamento. Se o parcial e a fatura calculassem por
     caminhos diferentes, o comprador mandaria um papel dizendo ¥ X e fecharia
     em ¥ Y — com o cliente segurando o primeiro. Por isso os dois passam pelo
     `settlement_totals`, e por isso o teste compara os dois de verdade em vez
     de confiar na leitura do código.

  3. BOTÃO E ROTA SÃO A MESMA PERGUNTA (`services.can_settle`). Botão visível
     numa etapa em que a rota dá 404 é um clique que não faz nada; rota aberta
     numa etapa sem botão é um POST forjado que passa.

⚠ POST, e não GET. As recusas ainda NÃO estão no banco — vivem nos campos do
  formulário. Um link geraria o PDF do que está salvo, que na conferência é
  *nada recusado*: o comprador baixaria um papel dizendo que aceitou tudo,
  exatamente quando ele quer dizer o contrário. É o que o
  `test_o_parcial_le_as_recusas_do_POST_e_nao_do_banco` trava.
"""

import io
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
                           SalesOrderLine, Settlement, STATUS_CANCELLED,
                           STATUS_CONFIRMED, STATUS_DRAFT)

User = get_user_model()


def _texto(dados):
    """O texto do PDF, página a página — mesmo helper do
    `tests_pdf_resultado` (pdfplumber, que já é dependência declarada)."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(dados)) as arq:
        return '\n'.join(p.extract_text() or '' for p in arq.pages)


class _Base(TestCase):
    """Uma compra RECEBIDA e sem fatura — a etapa de Conferência."""

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer',
                                          code='EMIN')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        self.so = self._ordem(1, recebida=True)
        self.l1, self.l2 = self.so._linhas
        self.client.force_login(self.parceiro)

    def _ordem(self, n, recebida=True, status=STATUS_CONFIRMED):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=n, description='x', status='closed',
                operator=self.gerente, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status=status,
                fx_usd_rate=D('0.1400'), total_rmb=D('1400.00'),
                total_usd=D('196.00'), shipped_at=date(2026, 8, 18),
                received_at=timezone.now() if recebida else None,
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
            # ⚠ Penduradas na PRÓPRIA ordem, e não em `self.l1`: quem cria
            #   uma segunda ordem no meio do teste sobrescreveria as linhas da
            #   primeira e o assert passaria a falar de outra compra.
            so._linhas = [
                SalesOrderLine.all_companies.create(
                    order=so, company=self.emp, brand='Samsung', kind='emmc',
                    gen='', tier_value=D('64'), tier_unit='GB', quantity=100,
                    unit_rmb=D('10.00'), unit_usd=D('1.40')),
                SalesOrderLine.all_companies.create(
                    order=so, company=self.emp, brand='Kingston', kind='emmc',
                    gen='', tier_value=D('32'), tier_unit='GB', quantity=40,
                    unit_rmb=D('10.00'), unit_usd=D('1.40'))]
        return so

    def _parcial(self, so=None, **campos):
        so = so or self.so
        return self.client.post(
            reverse('compras:resultado_parcial', args=[so.pk]), campos)

    def _ficha(self, so=None):
        so = so or self.so
        return self.client.get(
            reverse('compras:detail', args=[(so or self.so).pk])
        ).content.decode()


class RotaTests(_Base):

    def test_baixa_um_pdf(self):
        r = self._parcial(**{'rej_%s' % self.l1.pk: '7'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_o_nome_do_arquivo_diz_PARTIAL_e_traz_o_codigo_da_SO(self):
        """Dono: "tanto o nome do arquivo quanto o titulo". O nome é a
        primeira coisa que se lê na pasta do cliente — e é ele que impede o
        parcial de ser arquivado como se fosse o final."""
        r = self._parcial()
        with company_scope(self.emp.id):
            codigo = SalesOrder.objects.get(pk=self.so.pk).code
        esperado = 'PARTIAL-RESULT-%s.pdf' % codigo.replace('/', '-')
        self.assertIn(esperado, r['Content-Disposition'])

    def test_o_nome_do_parcial_nao_se_confunde_com_o_do_final(self):
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), {}, self.gerente)
        final = self.client.get(
            reverse('compras:resultado_pdf', args=[self.so.pk]))
        self.assertIn('RESULT-', final['Content-Disposition'])
        self.assertNotIn('PARTIAL', final['Content-Disposition'])

    def test_GET_nao_serve(self):
        """As recusas vêm no CORPO. Um GET só poderia gerar o papel do que
        está salvo — que na conferência é "nada recusado"."""
        r = self.client.get(
            reverse('compras:resultado_parcial', args=[self.so.pk]))
        self.assertEqual(r.status_code, 405)

    def test_em_transito_da_404(self):
        emt = self._ordem(2, recebida=False)
        self.assertEqual(self._parcial(emt).status_code, 404)

    def test_depois_de_faturada_da_404(self):
        """Aí existe o "Imprimir resultado", que é o mesmo papel sem a
        palavra parcial. Dois caminhos para o mesmo documento seria a chance
        de um deles envelhecer sozinho."""
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), {}, self.gerente)
        self.assertEqual(self._parcial().status_code, 404)

    def test_rascunho_da_404(self):
        rasc = self._ordem(3, recebida=True, status=STATUS_DRAFT)
        self.assertEqual(self._parcial(rasc).status_code, 404)

    def test_cancelada_da_404(self):
        """⚠ Este é o caso que o `order_stage` sozinho deixava passar: uma OV
        CANCELADA e recebida cai em `STAGE_CONFERENCIA` (a regra de lá é só
        "não é rascunho"). Quem fecha o buraco é o `can_settle`, que exige
        CONFIRMADA — a mesma exigência do `settle_and_invoice`."""
        canc = self._ordem(4, recebida=True, status=STATUS_CANCELLED)
        with company_scope(self.emp.id):
            self.assertEqual(services.order_stage(canc),
                             services.STAGE_CONFERENCIA)
        self.assertEqual(self._parcial(canc).status_code, 404)

    def test_de_outro_comprador_da_404(self):
        outro_buyer = Buyer.all_companies.create(company=None, name='Li',
                                                 slug='li')
        outro = User.objects.create_user('u_li', password='x')
        outro_buyer.users.add(outro)
        self.client.force_login(outro)
        self.assertEqual(self._parcial().status_code, 404)

    def test_recusa_maior_que_a_quantidade_nao_vira_papel(self):
        """Mesma leitura do "Fechar resultado" (`_recusas_do_post`): o parcial
        não pode aceitar o que o fechamento recusa, senão o comprador manda um
        PDF que o botão do lado se nega a fechar."""
        r = self._parcial(**{'rej_%s' % self.l1.pk: '101'})
        self.assertEqual(r.status_code, 302)
        r = self._parcial(**{'rej_%s' % self.l1.pk: 'dez'})
        self.assertEqual(r.status_code, 302)


class NaoPersisteTests(_Base):
    """A garantia nº 1. Gerar o parcial dez vezes deixa o banco como estava."""

    def _estado(self):
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            return {
                'acertos': Settlement.all_companies.filter(order=so).count(),
                'faturas': Invoice.all_companies.filter(order=so).count(),
                'recebido': so.received_at,
                'notas': len(services.order_notes(so)),
                'status': so.status,
            }

    def test_dez_parciais_nao_mudam_nada(self):
        antes = self._estado()
        for _ in range(10):
            self._parcial(**{'rej_%s' % self.l1.pk: '9',
                             'notes': 'pino oxidado na bandeja 2'})
        self.assertEqual(self._estado(), antes)

    def test_nao_grava_a_observacao_digitada(self):
        """Ela ENTRA no papel (é onde vive a explicação que o parcial existe
        para transmitir) e NÃO entra no banco: quem salva observação é o
        "Fechar resultado" e a aba de observações."""
        r = self._parcial(notes='foto do chip queimado no e-mail')
        self.assertIn('foto do chip queimado', _texto(r.content))
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.order_notes(so), [])

    def test_depois_do_parcial_ainda_da_para_fechar(self):
        """O sintoma que o comprador veria se o parcial gravasse: clicar em
        "Fechar resultado" e ouvir que a OV já tem fatura ativa."""
        self._parcial(**{'rej_%s' % self.l1.pk: '9'})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            services.settle_and_invoice(so, {self.l1.pk: (9, None)},
                                        self.gerente)
            self.assertEqual(
                Invoice.all_companies.filter(order=so).count(), 1)


class OPapelTests(_Base):
    """O documento — "exatamente o mesmo PDF", com a palavra trocada."""

    def test_o_titulo_diz_PARTIAL_e_nunca_FINAL(self):
        txt = _texto(self._parcial(**{'rej_%s' % self.l1.pk: '7'}).content)
        self.assertIn('Partial result', txt)
        self.assertIn('部分結果', txt)
        self.assertNotIn('Purchase result', txt)

    def test_o_numero_do_topo_tambem_nao_se_chama_final(self):
        """⚠ Achado ao MEDIR o PDF gerado, não ao ler o código: a coluna azul
        do topo dizia "FINAL RESULT (最終結果)" num papel intitulado "Partial
        result". Era o número que o cliente olha primeiro afirmando ser o
        final — a confusão exata que este documento existe para evitar."""
        txt = _texto(self._parcial().content)
        self.assertNotIn('FINAL RESULT', txt)
        self.assertNotIn('最終結果', txt)
        self.assertIn('PARTIAL RESULT', txt)

    def test_o_papel_final_continua_dizendo_final(self):
        """A troca é do parcial, e não uma mudança no documento de sempre."""
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), {}, self.gerente)
        txt = _texto(self.client.get(
            reverse('compras:resultado_pdf', args=[self.so.pk])).content)
        self.assertIn('Purchase result', txt)
        self.assertIn('FINAL RESULT', txt)
        self.assertNotIn('Partial result', txt)

    def test_a_data_de_fechamento_sai_em_branco(self):
        """Não há fechamento — e inventar uma data aqui seria dizer ao cliente
        que o número já é definitivo. É a segunda coisa (depois do título) que
        diz que este papel ainda não é o final."""
        doc = self._doc_parcial({})
        self.assertIsNone(doc['settled_at'])
        self.assertTrue(doc['partial'])

    def test_o_parcial_le_as_recusas_do_POST_e_nao_do_banco(self):
        """O motivo de a rota ser POST. No banco não há recusa nenhuma: se o
        papel saísse de lá, ele diria "0 recusados" no exato momento em que o
        comprador quer dizer o contrário."""
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.result_preview(so, {})['rejected'], 0)
        doc = self._doc_parcial({self.l1.pk: (13, None)})
        self.assertEqual(doc['rejected'], 13)
        self.assertEqual(doc['accepted'], 127)      # 100−13 + 40
        # e chega mesmo ao papel, pela rota. O número sai com SINAL — a
        # recusa é um abatimento, e o `−13` é grafia do documento desde
        # sempre (`pdf.py`), não coisa do parcial.
        txt = _texto(self._parcial(**{'rej_%s' % self.l1.pk: '13'}).content)
        self.assertIn('REJECTED', txt)
        # `-` e não o `−` (U+2212) que o papel desenha: o pdfplumber
        # normaliza o sinal na extração. Quem trava a GRAFIA é o
        # `tests_pdf_resultado`; aqui o que importa é o 13 ter chegado.
        self.assertIn('-13', txt)

    def _doc_parcial(self, ajustes, nota=''):
        with company_scope(self.emp.id):
            return services.result_preview(
                SalesOrder.objects.get(pk=self.so.pk), ajustes, nota=nota)


class OMesmoNumeroTests(_Base):
    """A garantia nº 2, e a que custa dinheiro se quebrar."""

    def test_o_total_do_parcial_e_o_total_da_fatura(self):
        ajustes = {self.l1.pk: (23, None), self.l2.pk: (4, None)}
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            previa = services.result_preview(so, ajustes)
            services.settle_and_invoice(so, ajustes, self.gerente)
            fatura = Invoice.all_companies.get(order=so)
        self.assertEqual(previa['total_rmb'], fatura.total_rmb)
        self.assertEqual(previa['total_usd'], fatura.total_usd)

    def test_sem_recusa_o_parcial_bate_com_o_esperado(self):
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            previa = services.result_preview(so, {})
        self.assertEqual(previa['total_rmb'], D('1400.00'))
        self.assertEqual(previa['delta_rmb'], D('0.00'))

    def test_as_linhas_do_parcial_sao_as_do_documento_final(self):
        """"Exatamente o mesmo PDF": as mesmas linhas, na mesma ordem, com os
        mesmos números — só o cabeçalho muda."""
        ajustes = {self.l1.pk: (23, None)}
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            previa = services.result_preview(so, ajustes)
            services.settle_and_invoice(so, ajustes, self.gerente)
            so = SalesOrder.objects.get(pk=self.so.pk)
            fatura = Invoice.all_companies.get(order=so)
            final = services.result_document(so, fatura)
        self.assertEqual(previa['lines'], final['lines'])
        for campo in ('sent', 'rejected', 'accepted', 'total_rmb',
                      'total_usd', 'order_rmb', 'lot_code', 'so_code',
                      'lot_origin'):
            self.assertEqual(previa[campo], final[campo], campo)


class BotaoNaTelaTests(_Base):
    """A garantia nº 3, do lado do HTML."""

    def _rota(self, so=None):
        return reverse('compras:resultado_parcial', args=[(so or self.so).pk])

    def test_o_botao_aparece_na_conferencia(self):
        html = self._ficha()
        self.assertIn(self._rota(), html)
        self.assertIn('Resultado parcial', html)

    def test_o_botao_desvia_o_formulario_do_resultado(self):
        """`formaction` no MESMO `f-resultado`: as recusas digitadas vão
        junto. Um `<a href>` mandaria o comprador embora com a planilha
        preenchida e voltaria com um papel dizendo que ele aceitou tudo."""
        html = self._ficha()
        self.assertIn('form="f-resultado"', html)
        self.assertIn('formaction="%s"' % self._rota(), html)

    def test_o_botao_nao_aparece_em_transito(self):
        emt = self._ordem(2, recebida=False)
        html = self.client.get(
            reverse('compras:detail', args=[emt.pk])).content.decode()
        self.assertNotIn(self._rota(emt), html)

    def test_o_botao_some_depois_de_fechado(self):
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), {}, self.gerente)
        html = self._ficha()
        self.assertNotIn(self._rota(), html)
        # e no lugar dele fica o papel definitivo
        self.assertIn(reverse('compras:resultado_pdf', args=[self.so.pk]),
                      html)


class CanSettleTests(_Base):
    """Botão e rota fazem a MESMA pergunta — e é esta função.

    Duas cópias da condição foi a versão anterior (a view montava
    `pode_acertar` com a regra escrita à mão). Cópias divergem na primeira
    alteração, e a divergência aqui é invisível: o botão continua na tela e o
    clique passa a dar 404.
    """

    def _pode(self, so):
        with company_scope(self.emp.id):
            return services.can_settle(SalesOrder.objects.get(pk=so.pk))

    def test_recebida_confirmada_e_sem_fatura(self):
        self.assertTrue(self._pode(self.so))

    def test_sem_recebimento_nao(self):
        self.assertFalse(self._pode(self._ordem(2, recebida=False)))

    def test_rascunho_nao(self):
        self.assertFalse(
            self._pode(self._ordem(3, status=STATUS_DRAFT)))

    def test_cancelada_nao(self):
        self.assertFalse(
            self._pode(self._ordem(4, status=STATUS_CANCELLED)))

    def test_com_fatura_nao(self):
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), {}, self.gerente)
        self.assertFalse(self._pode(self.so))

    def test_a_tela_usa_exatamente_esta_resposta(self):
        """O acoplamento que impede a divergência de nascer de novo."""
        resp = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertIs(resp.context['pode_acertar'], self._pode(self.so))
