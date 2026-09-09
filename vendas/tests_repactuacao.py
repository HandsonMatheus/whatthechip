# -*- coding: utf-8 -*-
"""
O COMPRADOR MUDA O PREÇO (dono, 2026-09-09).

  "vamos deixar ele mudar o preco mesmo e fodase... E se ele subir fica uma
   setinha verde naquela linha, se baixar fica uma vermelha apontando pra
   baixo. Ele é comprador, ele quem diz o preco, se eu achar ruim busco outro
   e cabou... Ele deve ser capaz de mudar o preco dentro da SO, o preco novo
   deve propagar pro cliente na SO dele e no lote tbm."

Contexto: em 07/09 o comprador aplicou uma tabela ~15% menor sobre um lote
que já tinha preço congelado e já tinha saído. A decisão do dono foi aceitar
que o preço é dele e fazer o sistema REGISTRAR — para o dia de "buscar outro"
ser uma decisão com número, e não com sensação.

═══════════════════════════════════════════════════════════════════════════
A REGRA CENTRAL, e ela é a razão de este arquivo existir:

    CONGELADO → alimenta o ESPERADO. NÃO se move nunca.
    APLICADO  → alimenta o RESULTADO. É o congelado, ou o repactuado.

O `result_rows` usava UM `unit` para os dois. Repactuar sem separá-los faria
o ESPERADO andar junto com o RESULTADO — e a diferença entre o combinado e o
conferido, que é a informação inteira e a única defesa do dono na conversa
com o cliente, desapareceria da tela.
═══════════════════════════════════════════════════════════════════════════

⚠ Quase nada aqui foi construído: `SettlementLine.new_unit_rmb`,
  `settlement_totals`, `settle_and_invoice` e o ramo repactuado do PDF já
  existiam desde sempre, e a tela do gerente (`/vendas/<pk>/acerto/`) já
  editava preço. O que faltava era a porta do COMPRADOR e a propagação.
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
FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')


class _Base(TestCase):
    """Duas linhas, preços diferentes — uma vai subir e a outra descer, que é
    o único cenário em que as duas setas aparecem na mesma tela."""

    FX = D('0.1481')
    #: ⚠ ¥3,00 × 0,1481 = 0,4443 → congela em 0,44. O centavo perdido por
    #:   unidade é o que faz a soma congelada divergir de ¥×taxa — é o cenário
    #:   do bug de 07/09, e mantê-lo aqui garante que a repactuação não o
    #:   ressuscite por outro caminho.
    U1, U1_USD, Q1 = D('3.00'), D('0.44'), 10000
    U2, U2_USD, Q2 = D('10.00'), D('1.48'), 500

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
                company=self.emp, number=9, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=self.FX,
                total_rmb=self.U1 * self.Q1 + self.U2 * self.Q2,
                total_usd=self.U1_USD * self.Q1 + self.U2_USD * self.Q2,
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            self.l1 = SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Micron', kind='ddr3',
                gen='', tier_value=D('2'), tier_unit='GB', quantity=self.Q1,
                unit_rmb=self.U1, unit_usd=self.U1_USD)
            self.l2 = SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Nanya', kind='emmc',
                gen='', tier_value=D('8'), tier_unit='GB', quantity=self.Q2,
                unit_rmb=self.U2, unit_usd=self.U2_USD)
        self.client.force_login(self.parceiro)

    def _linhas(self, **kw):
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so, **kw)
        return {l['pk']: l for g in grupos for l in g['lines']}

    def _fechar(self, ajustes):
        with company_scope(self.emp.id):
            return services.settle_and_invoice(self.so, ajustes, self.parceiro)


class OCongeladoNaoSeMoveTests(_Base):
    """A regra central. Se um destes cair, a tela perde a comparação que o
    dono usa para explicar a queda ao cliente."""

    def test_o_ESPERADO_da_linha_ignora_a_repactuacao(self):
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        self.assertEqual(l['total_rmb'], self.U1 * self.Q1)      # ¥30.000
        self.assertEqual(l['congelado_rmb'], self.U1)

    def test_o_RESULTADO_da_linha_usa_o_preço_novo(self):
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        self.assertEqual(l['pago_rmb'], D('2.55') * self.Q1)     # ¥25.500
        self.assertEqual(l['unit_rmb'], D('2.55'))               # o APLICADO

    def test_a_diferenca_fica_VISIVEL_na_mesma_linha(self):
        """O ponto do desenho inteiro: combinado e conferido lado a lado."""
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        self.assertGreater(l['total_rmb'], l['pago_rmb'])
        self.assertEqual(l['total_rmb'] - l['pago_rmb'], D('4500.00'))

    def test_a_OV_confirmada_continua_intacta(self):
        """`so.total_rmb`/`total_usd` são o combinado. Reescrevê-los apagaria
        a única prova documentada de quanto foi repactuado — e quebraria a
        comparação histórica entre lotes."""
        antes = (self.so.total_rmb, self.so.total_usd)
        self._fechar({self.l1.pk: (0, D('2.55'))})
        self.so.refresh_from_db()
        self.assertEqual((self.so.total_rmb, self.so.total_usd), antes)

    def test_sem_repactuacao_nada_muda(self):
        """A trava contra o oposto: uma OV sem preço mexido tem de ler
        exatamente como antes desta feature."""
        self._fechar({self.l1.pk: (12, None)})
        l = self._linhas()[self.l1.pk]
        self.assertIsNone(l['novo_rmb'])
        self.assertEqual(l['unit_rmb'], l['congelado_rmb'])
        self.assertEqual(l['pago_rmb'], self.U1 * (self.Q1 - 12))


class ODolarDaLinhaRepactuadaTests(_Base):
    """O `new_unit_rmb` não tem par em dólar congelado — o US$ dessa linha só
    pode ser derivado. É a única derivação permitida, e ela tem forma."""

    def test_o_usd_deriva_da_taxa_TRAVADA_da_OV(self):
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        # 2.55 × 0.1481 = 0.377655 → 0.38
        self.assertEqual(l['unit_usd'], D('0.38'))

    def test_arredonda_em_CENTAVOS_antes_de_multiplicar(self):
        """0,38 × 10.000 = 3.800,00. Multiplicar primeiro daria
        2,55 × 0,1481 × 10.000 = 3.776,55 — R$ 23 de diferença numa linha só,
        e a tela discordaria da fatura."""
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        self.assertEqual(l['pago_usd'], D('3800.00'))
        self.assertNotEqual(l['pago_usd'],
                            (D('2.55') * self.FX * self.Q1))

    def test_a_tela_e_a_FATURA_dizem_o_mesmo_numero(self):
        """O fecho do arco de 07/09: o que ele lê enquanto confere tem de ser
        o que o `settle_and_invoice` grava."""
        _st, inv = self._fechar({self.l1.pk: (30, D('2.55')),
                                 self.l2.pk: (0, D('11.00'))})
        linhas = self._linhas()
        soma_rmb = sum(l['pago_rmb'] for l in linhas.values())
        soma_usd = sum(l['pago_usd'] for l in linhas.values())
        self.assertEqual(inv.total_rmb, soma_rmb)
        self.assertEqual(inv.total_usd, soma_usd)

    def test_o_ESPERADO_em_usd_tambem_fica_parado(self):
        self._fechar({self.l1.pk: (0, D('2.55'))})
        l = self._linhas()[self.l1.pk]
        self.assertEqual(l['total_usd'], self.U1_USD * self.Q1)
        self.assertEqual(l['congelado_usd'], self.U1_USD)


class AFaixaDaMarcaTests(_Base):
    """Faixa dizendo um número e linhas dizendo outro é o erro que só aparece
    depois de fechado. Vale nas duas colunas: a que congela e a que anda."""

    def test_o_grupo_soma_as_linhas_dele_nas_DUAS_contas(self):
        self._fechar({self.l1.pk: (100, D('2.55'))})
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so)
        for g in grupos:
            self.assertEqual(g['rmb'], sum(l['total_rmb'] for l in g['lines']))
            self.assertEqual(g['pago_rmb'],
                             sum(l['pago_rmb'] for l in g['lines']))
            self.assertEqual(g['usd'], sum(l['total_usd'] for l in g['lines']))
            self.assertEqual(g['pago_usd'],
                             sum(l['pago_usd'] for l in g['lines']))


class ORascunhoGuardaOPrecoTests(_Base):
    """Perder um preço digitado dói mais que perder uma contagem."""

    def test_o_preco_sobrevive_a_sair_da_pagina(self):
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '2.55'})
        self.assertEqual(self._linhas(com_rascunho=True)[self.l1.pk]['novo_rmb'],
                         D('2.55'))

    def test_repactuacao_SEM_recusa_tambem_e_uma_linha(self):
        """O rascunho entrava no mapa pelas RECUSAS. Uma linha com preço novo
        e nenhuma recusa não tinha por onde entrar — e sumia."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l2.pk: '11.00'})
        l = self._linhas(com_rascunho=True)[self.l2.pk]
        self.assertEqual(l['novo_rmb'], D('11.00'))
        self.assertEqual(l['rejected'], 0)

    def test_preco_IGUAL_ao_congelado_nao_e_repactuacao(self):
        """Senão tocar no campo e devolver o mesmo número acenderia a seta e
        gravaria um `SettlementLine` dizendo que houve repactuação."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '3.00'})
        self.assertIsNone(
            self._linhas(com_rascunho=True)[self.l1.pk]['novo_rmb'])

    def test_apagar_o_campo_apaga_a_repactuacao(self):
        """`prices={}` tem de limpar. Se `{}` preservasse (como o `notes`
        faz com `None`), ele apagaria o preço na tela e ele voltaria no F5."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '2.55'})
            services.save_draft(self.so, {}, self.parceiro, prices={})
        self.assertIsNone(
            self._linhas(com_rascunho=True)[self.l1.pk]['novo_rmb'])

    def test_lixo_no_json_nao_derruba_a_tela(self):
        """O JSON é o único campo do sistema que o banco não valida."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: 'abc', 999: '5.00',
                                        self.l2.pk: '-1'})
        linhas = self._linhas(com_rascunho=True)
        self.assertIsNone(linhas[self.l1.pk]['novo_rmb'])
        self.assertIsNone(linhas[self.l2.pk]['novo_rmb'])


class OPostDoCompradorTests(_Base):
    """A porta que faltava: o formulário da conferência."""

    def _post(self, dados):
        return self.client.post(
            reverse('compras:resultado', args=[self.so.pk]), dados)

    def test_o_comprador_fecha_com_preco_novo(self):
        self._post({f'price_{self.l1.pk}': '2.55',
                    f'rej_{self.l2.pk}': '5'})
        with company_scope(self.emp.id):
            self.so.refresh_from_db()
            inv = self.so.invoices.first()
        self.assertIsNotNone(inv, 'a fatura não saiu')
        self.assertEqual(self._linhas()[self.l1.pk]['novo_rmb'], D('2.55'))

    def test_preco_ilegivel_para_o_fechamento(self):
        """Aqui NÃO é autosave: fechar é o ato de valor, e um preço ilegível
        não pode virar fatura em silêncio."""
        r = self._post({f'price_{self.l1.pk}': 'dois e meio'})
        with company_scope(self.emp.id):
            self.assertFalse(self.so.invoices.exists())
        self.assertEqual(r.status_code, 302)

    def test_preco_igual_ao_congelado_nao_grava_repactuacao(self):
        self._post({f'price_{self.l1.pk}': '3.00', f'rej_{self.l1.pk}': '10'})
        l = self._linhas()[self.l1.pk]
        self.assertIsNone(l['novo_rmb'])
        self.assertEqual(l['rejected'], 10)


class ASetaTests(_Base):
    """O pedido literal: ↑ verde subiu, ↓ vermelha baixou, nada se não tocou.

    ⚠ A seta é desenhada DUAS vezes — pelo servidor no carregamento e pelo JS
      a cada tecla. As duas leem a MESMA regra ("existe seta quando existe
      `novo`"), e é por isso que ela não pisca ao carregar uma OV já fechada.
    """

    def _html(self):
        return self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()

    def test_desceu_vira_seta_vermelha_para_baixo(self):
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '2.55'})
        self.assertIn('class="rep rep--down"', self._html())

    def test_subiu_vira_seta_verde_para_cima(self):
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l2.pk: '11.00'})
        self.assertIn('class="rep rep--up"', self._html())

    def test_sem_repactuacao_nao_ha_seta(self):
        """⚠ Procura o ELEMENTO, não a string: `rep--down` aparece também no
        JavaScript da própria página (é ele que reescreve a seta a cada
        tecla), e um `assertNotIn` cru reprovava a tela correta."""
        html = self._html()
        self.assertNotIn('class="rep rep--down"', html)
        self.assertNotIn('class="rep rep--up"', html)

    def test_o_campo_leva_o_CONGELADO_como_base_do_JS(self):
        """⚠ O `data-unit` tem de ser o CONGELADO, não o `unit_rmb` (que é o
        APLICADO desde 09/09). Com o aplicado ali, o JS comparava o preço novo
        com ele mesmo, "mudou?" respondia sempre não, e a seta era apagada no
        carregamento — o `<i>` ficava no HTML, com a direção certa, invisível.
        """
        with io.open(FICHA, encoding='utf-8') as f:
            ficha = f.read()
        self.assertIn('data-unit="{% if l.congelado_rmb %}', ficha)
        self.assertNotIn('data-unit="{% if l.unit_rmb %}', ficha)

    def test_a_seta_e_um_GLIFO_e_nao_mais_um_numero(self):
        """A célula do dinheiro já custou uma correção por carregar um terceiro
        número (a perda, 07/09). A direção vai na seta; o valor está no campo
        ao lado e a diferença, no par ESPERADO × RESULTADO."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '2.55'})
        m = re.search(r'<i class="rep rep--down"[^>]*>([^<]*)</i>',
                      self._html())
        self.assertIsNotNone(m, 'a seta sumiu da célula')
        self.assertEqual(m.group(1).strip(), '↓')


# ── O NAVEGADOR ─────────────────────────────────────────────────────────────
# Reaproveita o harness do `tests_dolar_do_heroi` (jsdom rodando o script da
# própria ficha). Pula sozinho onde não houver node com jsdom.
from vendas.tests_dolar_do_heroi import _NODE, HARNESS       # noqa: E402
import json as _json, shutil as _shutil                      # noqa: E402
import subprocess as _sub, tempfile as _tmp, unittest        # noqa: E402


@unittest.skipIf(_NODE is None, 'node com jsdom não disponível')
class NavegadorTests(_Base):
    """A ficha RODANDO. É o único teste que teria pego o bug do `data-unit`.

    O `<i>` da seta saía do servidor com a direção certa, e o `recalcular()`
    do CARREGAMENTO o apagava — porque a base contra a qual ele compara era o
    preço APLICADO (já repactuado), então "mudou?" respondia sempre não. No
    HTML a seta estava lá; na tela, não. Foi a captura que pegou, e é isto
    que passa a pegar.
    """

    def _rodar(self, recusas=None, precos=None):
        node, node_path = _NODE
        pasta = _tmp.mkdtemp()
        try:
            ficha = os.path.join(pasta, 'f.html')
            with io.open(ficha, 'w', encoding='utf-8') as f:
                f.write(self.client.get(
                    reverse('compras:detail',
                            args=[self.so.pk])).content.decode())
            r = _sub.run([node, HARNESS, ficha, _json.dumps(recusas or {}),
                          _json.dumps(precos or {})],
                         env=dict(os.environ, NODE_PATH=node_path),
                         capture_output=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stderr.decode()[-1500:])
            return _json.loads(r.stdout.decode().strip().split('\n')[-1])
        finally:
            _shutil.rmtree(pasta, ignore_errors=True)

    def test_o_script_roda_sem_estourar(self):
        self.assertEqual(
            self._rodar(precos={str(self.l1.pk): '2.55'})['erros'], [])

    def test_a_seta_ACENDE_ao_digitar(self):
        d = self._rodar(precos={str(self.l1.pk): '2.55',
                                str(self.l2.pk): '11.00'})['depois']
        self.assertEqual(d['setas'][str(self.l1.pk)], '↓|rep rep--down')
        self.assertEqual(d['setas'][str(self.l2.pk)], '↑|rep rep--up')

    def test_a_seta_do_SERVIDOR_sobrevive_ao_carregamento(self):
        """O bug de 09/09, virado teste. A OV chega com repactuação já salva;
        o `recalcular()` roda no load e NÃO pode apagar a seta."""
        with company_scope(self.emp.id):
            services.save_draft(self.so, {}, self.parceiro,
                                prices={self.l1.pk: '2.55'})
        antes = self._rodar()['antes']
        self.assertEqual(antes['setas'][str(self.l1.pk)], '↓|rep rep--down')

    def test_o_dolar_do_heroi_bate_com_a_FATURA_apos_repactuar(self):
        """O fecho: o que ele lê enquanto digita preço é o que a fatura grava.
        Arredondar em centavos por linha é o que faz os dois baterem."""
        rej = 30
        r = self._rodar(recusas={str(self.l1.pk): rej},
                        precos={str(self.l1.pk): '2.55'})
        with company_scope(self.emp.id):
            linhas = list(self.so.lines.all())
            rmb, usd = services.settlement_totals(
                linhas, {self.l1.pk: (rej, D('2.55'))}, self.FX)
        self.assertEqual(D(r['depois']['kUsd'].replace('US$ ', '')), usd)
        self.assertEqual(D(r['depois']['kRmb'].replace('¥ ', '')), rmb)

    def test_recusar_E_repactuar_na_MESMA_linha(self):
        """As duas coisas juntas são legítimas e é onde a conta erra fácil:
        `(enviados − recusados) × preço novo`, e não uma mistura dos dois."""
        r = self._rodar(recusas={str(self.l1.pk): '100'},
                        precos={str(self.l1.pk): '2.55'})
        esperado = D('2.55') * (self.Q1 - 100) + self.U2 * self.Q2
        self.assertEqual(D(r['depois']['kRmb'].replace('¥ ', '')), esperado)

    def test_o_LAPIS_abre_a_edicao_e_o_numero_some(self):
        """Antes do clique o campo não existe para o comprador: o que há é o
        número e um lápis apagado."""
        r = self._rodar(precos={str(self.l1.pk): '2.55'})
        self.assertEqual(r['depois']['setas'][str(self.l1.pk)],
                         '↓|rep rep--down')

    def test_o_PRECO_DIGITADO_DISPARA_O_AUTOSAVE(self):
        """O bug de 09/09, e o motivo de este harness ter deixado de engolir o
        `fetch` calado.

        O `save_draft` gravava, o `result_rows` desenhava, 28 testes passavam
        — e o autosave escutava só os campos de RECUSA. Ninguém nunca agendava
        o envio do preço, então atualizar a página trazia tudo em branco. Um
        dublê que só engole não testa o telefonema; testa que ninguém
        reclamou dele.
        """
        r = self._rodar(precos={str(self.l1.pk): '2.55'})
        self.assertTrue(r['enviados'],
                        'o preço digitado não agendou salvamento nenhum')
        campos = dict(c for e in r['enviados'] for c in e['campos'])
        self.assertEqual(campos.get('price_%d' % self.l1.pk), '2.55',
                         'o preço não foi no corpo do autosave: %s' % campos)

    def test_a_RECUSA_continua_disparando_o_autosave(self):
        """A outra metade: consertar o preço não pode ter quebrado a recusa,
        que é o que o rascunho salvava desde 07/09."""
        r = self._rodar(recusas={str(self.l1.pk): '12'})
        campos = dict(c for e in r['enviados'] for c in e['campos'])
        self.assertEqual(campos.get('rej_%d' % self.l1.pk), '12')
