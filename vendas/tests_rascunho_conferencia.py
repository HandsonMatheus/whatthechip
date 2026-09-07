# -*- coding: utf-8 -*-
"""
RASCUNHO DA CONFERÊNCIA — o autosave das recusas (dono, 2026-09-07).

  "a pagina nao salva os chips que foram dados como recusados, assim quando
   voltamos pra mesma pagina temos que digitar os chips de novo"

  "vc acha melhor um botao de salvar (...) ou salvar automaticamente? Tipo o
   Odoo. Pode ser uma boa ideia pesquisar como o Odoo faz isso e copiar."

O que a pesquisa do Odoo devolveu, e por que decidiu o desenho: o Odoo salva
SOZINHO ao sair do formulário, sem perguntar. O que ele NÃO faz é confundir
salvar com confirmar — a fatura salva continua em *Draft* até alguém apertar
Confirmar. É esse par que está copiado aqui:

    salvar  = este rascunho, automático, reversível, invisível fora da tela
              do comprador;
    confirmar = "Fechar resultado", botão, com diálogo, irreversível.

As garantias, na ordem em que quebram:

  1. O RASCUNHO NÃO É UM RESULTADO. Não emite fatura, não move a etapa, não
     entra no PDF do cliente e não aparece na tela dele. Se algum dia
     aparecer, o comprador terá mandado uma acusação pela metade sem saber.

  2. ELE VOLTA. É o pedido literal: digitar, sair, voltar e encontrar os
     números onde estavam — inclusive a observação.

  3. ELE SOME AO FECHAR. Depois da fatura quem responde pelas recusas é o
     ACERTO. Rascunho sobrevivente = duas fontes para o mesmo número, e a que
     a tela escolheria é a errada.

  4. O AUTOSAVE NUNCA RECUSA POR CONTEÚDO. Ele dispara a cada pausa de
     digitação; uma mensagem de erro por tecla seria pior do que o problema
     que isto resolve. Valor fora da faixa é LIMITADO, não rejeitado — quem
     recusa de verdade continua sendo o "Fechar resultado".

⚠ O JSON é o único campo do sistema que o banco não valida. Por isso a
  escrita filtra (pk desta ordem, inteiro, dentro do enviado) E a leitura
  filtra de novo: uma tela que quebra por causa de um rascunho é pior do que
  um rascunho perdido.
"""

import json
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
                           SalesOrderLine, SettlementDraft, STATUS_CONFIRMED)

User = get_user_model()


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
        self.so = self._ordem(1)
        self.l1, self.l2 = self.so._linhas
        self.client.force_login(self.parceiro)

    def _ordem(self, n, recebida=True):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=n, description='x', status='closed',
                operator=self.gerente, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1400'), total_rmb=D('1400.00'),
                total_usd=D('196.00'), shipped_at=date(2026, 8, 18),
                received_at=timezone.now() if recebida else None,
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
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

    def _salvar(self, so=None, **campos):
        so = so or self.so
        return self.client.post(
            reverse('compras:rascunho', args=[so.pk]), campos)

    def _rascunho(self, so=None):
        with company_scope(self.emp.id):
            return SettlementDraft.all_companies.filter(
                order=so or self.so).first()

    def _ficha(self, so=None):
        return self.client.get(
            reverse('compras:detail', args=[(so or self.so).pk])).content.decode()

    def _fechar(self, ajustes=None):
        with company_scope(self.emp.id):
            services.settle_and_invoice(
                SalesOrder.objects.get(pk=self.so.pk), ajustes or {},
                self.gerente)


class RotaTests(_Base):

    def test_salva_e_devolve_a_hora_em_ISO(self):
        r = self._salvar(**{'rej_%s' % self.l1.pk: '7'})
        self.assertEqual(r.status_code, 200)
        corpo = json.loads(r.content)
        self.assertTrue(corpo['ok'])
        self.assertEqual(corpo['linhas'], 1)
        # ISO, e não "14:32": quem formata é o navegador DELE. O comprador
        # está na China e o servidor no fuso do Render — a hora do servidor
        # na tela dele seria uma hora errada com cara de certa.
        from django.utils.dateparse import parse_datetime
        self.assertIsNotNone(parse_datetime(corpo['em']))

    def test_GET_nao_serve(self):
        r = self.client.get(reverse('compras:rascunho', args=[self.so.pk]))
        self.assertEqual(r.status_code, 405)

    def test_de_outro_comprador_da_404(self):
        outro_buyer = Buyer.all_companies.create(company=None, name='Li',
                                                 slug='li')
        outro = User.objects.create_user('u_li', password='x')
        outro_buyer.users.add(outro)
        self.client.force_login(outro)
        self.assertEqual(self._salvar(**{'rej_%s' % self.l1.pk: '5'}).status_code,
                         404)
        self.assertIsNone(self._rascunho())

    def test_fora_da_conferencia_responde_409_e_nao_grava(self):
        """409 e não 404: a compra existe e é dele — o que acabou é a ETAPA.
        A tela usa isso para PARAR de tentar, em vez de insistir contra uma
        porta fechada e pintar erro a cada tecla."""
        emt = self._ordem(2, recebida=False)
        r = self._salvar(emt, **{'rej_%s' % emt._linhas[0].pk: '5'})
        self.assertEqual(r.status_code, 409)
        self.assertIsNone(self._rascunho(emt))

    def test_depois_de_faturada_responde_409(self):
        self._fechar()
        self.assertEqual(self._salvar(**{'rej_%s' % self.l1.pk: '5'}).status_code,
                         409)


class NaoRecusaPorConteudoTests(_Base):
    """A garantia nº 4. Autosave que responde erro é autosave que atrapalha."""

    def test_texto_no_lugar_de_numero_nao_quebra_o_salvamento(self):
        r = self._salvar(**{'rej_%s' % self.l1.pk: 'dez',
                            'rej_%s' % self.l2.pk: '3'})
        self.assertEqual(r.status_code, 200)
        # a linha boa entrou; a ruim ficou de fora, sem derrubar a outra
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.draft_rejections(so), {self.l2.pk: 3})

    def test_acima_do_enviado_e_LIMITADO_e_nao_descartado(self):
        """Descartar deixaria na tela o valor ANTERIOR, que ele não digitou.
        Limitar mostra o teto real da linha — o mesmo que o campo já impõe no
        navegador."""
        self._salvar(**{'rej_%s' % self.l1.pk: '999'})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.draft_rejections(so), {self.l1.pk: 100})

    def test_negativo_vira_ausencia(self):
        self._salvar(**{'rej_%s' % self.l1.pk: '-5'})
        self.assertEqual(self._rascunho().rejections, {})

    def test_pk_de_outra_ordem_nao_entra(self):
        outra = self._ordem(3)
        self._salvar(**{'rej_%s' % outra._linhas[0].pk: '9',
                        'rej_%s' % self.l1.pk: '4'})
        self.assertEqual(self._rascunho().rejections, {str(self.l1.pk): 4})

    def test_zero_nao_ocupa_espaco_no_mapa(self):
        """Campo em branco vale zero — guardar `{pk: 0}` seria guardar a
        ausência, e o mapa cresceria com o que ele NÃO fez."""
        self._salvar(**{'rej_%s' % self.l1.pk: '0'})
        self.assertEqual(self._rascunho().rejections, {})


class LeituraSujaTests(_Base):
    """O JSON é o único campo que o banco não valida — a leitura filtra de
    novo. Uma tela que quebra por causa de um rascunho é pior do que um
    rascunho perdido."""

    def _plantar(self, mapa):
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            d = SettlementDraft(order=so, rejections=mapa)
            d.save()

    def test_lixo_no_json_nao_derruba_a_tela(self):
        self._plantar({'nao-e-numero': 5, str(self.l1.pk): 'x',
                       '999999': 3, str(self.l2.pk): 7})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.draft_rejections(so), {self.l2.pk: 7})
        self.assertEqual(self.client.get(
            reverse('compras:detail', args=[self.so.pk])).status_code, 200)

    def test_valor_acima_do_enviado_no_json_e_ignorado_na_leitura(self):
        self._plantar({str(self.l1.pk): 500})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertEqual(services.draft_rejections(so), {})


class ElesVoltamTests(_Base):
    """A garantia nº 2 — o pedido, na sua forma mais curta."""

    def test_o_numero_volta_para_o_campo(self):
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        html = self._ficha()
        self.assertIn('name="rej_%s"' % self.l1.pk, html)
        self.assertIn('value="23"', html)

    def test_a_observacao_volta_para_o_campo(self):
        self._salvar(notes='pino oxidado na bandeja 2')
        self.assertIn('pino oxidado na bandeja 2', self._ficha())

    def test_o_aprovado_e_o_resultado_da_linha_acompanham(self):
        """Não basta o campo voltar preenchido: a linha inteira tem de ler o
        rascunho, senão ele vê 23 recusados e 100 aprovados na mesma linha."""
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            linha = next(l for g in services.result_rows(so, com_rascunho=True)
                         for l in g['lines'] if l['pk'] == self.l1.pk)
        self.assertEqual(linha['rejected'], 23)
        self.assertEqual(linha['accepted'], 77)

    def test_salvar_os_numeros_nao_apaga_a_observacao(self):
        """O autosave dos campos manda o formulário inteiro, mas um POST que
        NÃO traga `notes` não pode zerar o texto — senão a observação some
        pela porta dos fundos."""
        self._salvar(notes='lacre rompido')
        self._salvar(**{'rej_%s' % self.l1.pk: '4'})     # sem `notes`
        self.assertEqual(self._rascunho().notes, 'lacre rompido')

    def test_salvar_de_novo_substitui_e_nao_acumula(self):
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        self._salvar(**{'rej_%s' % self.l2.pk: '4'})
        self.assertEqual(self._rascunho().rejections, {str(self.l2.pk): 4})

    def test_limpar_tudo_limpa_mesmo(self):
        """O "Limpar recusas" salva junto. Sem isso ele apaga na tela, sai e
        volta com as recusas de volta — o oposto do que o botão prometeu."""
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        self._salvar()
        self.assertEqual(self._rascunho().rejections, {})


class NaoVazaParaOClienteTests(_Base):
    """A garantia nº 1, e a que custa uma negociação se quebrar.

    Decisão do dono, 2026-09-07: o cliente vê a recusa quando o resultado
    FECHA — ou no PDF parcial, que o comprador manda quando QUER começar a
    conversa. Recusa pela metade na tela do cliente lê como acusação.
    """

    def test_result_rows_ignora_o_rascunho_por_PADRAO(self):
        """O padrão é o lado seguro: quem quer o rascunho pede."""
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            linha = next(l for g in services.result_rows(so)
                         for l in g['lines'] if l['pk'] == self.l1.pk)
        self.assertEqual(linha['rejected'], 0)
        self.assertEqual(linha['accepted'], 100)

    def test_a_tela_do_cliente_nao_pede_o_rascunho(self):
        """A trava contra o erro de uma linha: basta alguém acrescentar o
        sinalizador na `vendas/views.py` para o cliente passar a ver a
        conferência ao vivo, sem que nada mais quebre."""
        import inspect
        from vendas import views
        fonte = inspect.getsource(views)
        self.assertIn('services.result_rows(so)', fonte)
        self.assertNotIn('com_rascunho', fonte)

    def test_o_pdf_do_resultado_parcial_nao_le_o_rascunho(self):
        """Ele lê o POST — o que está na tela AGORA. O rascunho é a mesma
        coisa por outro caminho, e dois caminhos divergem: o comprador
        mandaria um papel com o número de ontem."""
        self._salvar(**{'rej_%s' % self.l1.pk: '90'})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            doc = services.result_preview(so, {})
        self.assertEqual(doc['rejected'], 0)


class SomeAoFecharTests(_Base):
    """A garantia nº 3."""

    def test_fechar_o_resultado_apaga_o_rascunho(self):
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        self.assertIsNotNone(self._rascunho())
        self._fechar({self.l1.pk: (23, None)})
        self.assertIsNone(self._rascunho())

    def test_depois_de_fechado_a_linha_le_o_ACERTO(self):
        """A prova de que não sobrou fonte dupla: fecho com um número
        DIFERENTE do que estava no rascunho e a tela mostra o do acerto."""
        self._salvar(**{'rej_%s' % self.l1.pk: '23'})
        self._fechar({self.l1.pk: (9, None)})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            linha = next(l for g in services.result_rows(so, com_rascunho=True)
                         for l in g['lines'] if l['pk'] == self.l1.pk)
        self.assertEqual(linha['rejected'], 9)

    def test_o_rascunho_nao_emite_fatura_nem_move_a_etapa(self):
        """Salvar dez vezes deixa o banco onde estava — só o rascunho muda."""
        for n in range(10):
            self._salvar(**{'rej_%s' % self.l1.pk: str(n + 1)})
        with company_scope(self.emp.id):
            so = SalesOrder.objects.get(pk=self.so.pk)
            self.assertFalse(Invoice.all_companies.filter(order=so).exists())
            self.assertEqual(services.order_stage(so),
                             services.STAGE_CONFERENCIA)
            self.assertTrue(services.can_settle(so))


class TelaTests(_Base):
    """O que a página precisa entregar para o autosave existir."""

    def test_a_ficha_traz_o_endereco_do_autosave(self):
        html = self._ficha()
        self.assertIn('data-rascunho="%s"'
                      % reverse('compras:rascunho', args=[self.so.pk]), html)

    def test_o_selo_existe_e_traz_a_hora_do_ultimo_salvamento(self):
        self.assertIn('id="rasc"', self._ficha())
        self.assertNotIn('data-em=', self._ficha())     # ainda não salvou
        self._salvar(**{'rej_%s' % self.l1.pk: '3'})
        self.assertIn('data-em=', self._ficha())

    def test_fora_da_conferencia_a_ficha_nao_arma_o_autosave(self):
        """Sem `data-rascunho` o bloco de JS sai pela porta e nada tenta
        salvar — a tela do resultado fechado não fica batendo numa rota que
        responde 409."""
        self._fechar()
        self.assertNotIn('data-rascunho=', self._ficha())
