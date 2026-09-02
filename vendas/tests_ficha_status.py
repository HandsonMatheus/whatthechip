# -*- coding: utf-8 -*-
"""
O ESTADO DA COMPRA NA FICHA — três nomes para o mesmo fato (dono, 2026-09-02).

Ele abriu uma ordem e encontrou a mesma compra chamada de três jeitos na
mesma tela:

  · a lista dizia            EM TRÂNSITO
  · o selo ao lado do código dizia   RECEBIMENTO
  · o trilho de etapas dizia         RECEBIDO

E "RECEBIDO" era o pior, porque a caixa **não tinha sido recebida** — o passo
estava só corrente. O trilho nomeava a etapa como se ela já tivesse
acontecido, e o cinza do passo dizia o contrário logo ao lado.

Duas correções, e elas são de naturezas diferentes:

  (A) o selo do topo SAIU. Não por ser feio: ele era uma SEGUNDA FONTE para o
      mesmo fato. O trilho anda por data real de cada etapa (`order_steps`);
      o selo andava por uma cascata de `if` sobre fatura e preço. Duas contas
      independentes para a mesma pergunta divergem — é só questão de quando.

  (B) o passo `recebido` só se CHAMA "Recebido" depois de recebido. Antes
      disso o que está acontecendo é o trânsito, e é isso que ele diz.

⚠ A chave `recebido` continua canônica. O que mudou foi o rótulo.
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
from vendas.models import DocSequence, SEQ_SO, SalesOrder

User = get_user_model()

FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')
LISTA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compras.html')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


class _Ficha(TestCase):

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
                company=self.emp, number=1, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1400'), total_rmb=D('1000.00'),
                total_usd=D('140.00'), shipped_at=date(2026, 8, 27),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()

    def _html(self):
        self.client.force_login(self.parceiro)
        r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def _trilho(self, html):
        """Só o bloco do trilho — o resto da ficha também fala em recebimento
        (o campo "Recebimento em", o botão "Marcar como recebido"), e um
        assertIn na página inteira passaria por acidente."""
        m = re.search(r'<div id="stat".*?</div>\s*</div>', html, re.S)
        self.assertIsNotNone(m, 'o trilho de etapas sumiu da ficha')
        return m.group(0)

    def _topo(self, html):
        m = re.search(r'<div class="rhead__idl">(.*?)</div>', html, re.S)
        self.assertIsNotNone(m, 'o cabeçalho da ficha sumiu')
        return m.group(1)


# ═══════════════════════════════════════════════════════════════════════════
# (A) O SELO DO TOPO
# ═══════════════════════════════════════════════════════════════════════════
class SeloDoTopoTests(_Ficha):

    def test_o_topo_nao_tem_mais_selo_de_estado(self):
        """Sobra o código do lote e nada mais. Se um selo voltar aqui, volta
        junto a divergência — a lista, o trilho e ele responderiam à mesma
        pergunta por caminhos diferentes."""
        topo = self._topo(self._html())
        self.assertIn('rhead__code', topo)
        self.assertNotIn('class="tag', topo)

    def test_o_topo_nao_diz_mais_recebimento(self):
        """"Recebimento" era o ramo `{% else %}` do selo. Ele descrevia a
        compra pela AUSÊNCIA de fatura, o que é quase sempre verdade e quase
        nunca informativo."""
        self.assertNotIn('Recebimento', self._topo(self._html()))

    def test_o_trilho_continua_no_lugar(self):
        """A remoção do selo não pode levar o trilho junto: ele é a fonte que
        FICOU, e sem ele a ficha não diz mais em que pé está a compra."""
        trilho = self._trilho(self._html())
        for passo in ('Fechado', 'Enviado', 'Resultado', 'Pagamento'):
            self.assertIn(passo, trilho)


# ═══════════════════════════════════════════════════════════════════════════
# (B) O PASSO "RECEBIDO"
# ═══════════════════════════════════════════════════════════════════════════
class PassoRecebidoTests(_Ficha):

    def test_enquanto_nao_recebeu_o_passo_diz_em_transito(self):
        """Dono: "ele só se torna RECEBIDO, quando o comprador marca como
        recebido". Enviada e ainda não marcada: o que está acontecendo é o
        trânsito."""
        self.assertIsNone(self.so.received_at)
        trilho = self._trilho(self._html())
        self.assertIn('Em trânsito', trilho)
        self.assertNotIn('Recebido', trilho)

    def test_ao_marcar_como_recebido_o_passo_vira_recebido(self):
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        trilho = self._trilho(self._html())
        self.assertIn('Recebido', trilho)
        self.assertNotIn('Em trânsito', trilho)

    def test_o_estado_do_passo_acompanha_o_rotulo(self):
        """O rótulo e o estado visual têm de contar a MESMA história. Era essa
        a incoerência: `is-now` (cinza, "ainda não") com a palavra "Recebido"
        (passado) em cima."""
        passos = {p['key']: p for p in services.order_steps(self.so)}
        self.assertEqual(passos[services.STEP_RECEBIDO]['state'], 'current')
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        passos = {p['key']: p for p in services.order_steps(self.so)}
        self.assertEqual(passos[services.STEP_RECEBIDO]['state'], 'done')

    def test_a_chave_do_passo_continua_canonica(self):
        """Trocamos o RÓTULO. A chave é o que o `order_steps` devolve e o que
        o template compara — mexer nela quebraria os cinco passos de uma vez,
        silenciosamente, porque `{% elif %}` que não casa não dá erro: só
        deixa de escrever o nome."""
        self.assertEqual(services.STEP_RECEBIDO, 'recebido')
        self.assertIn("p.key == 'recebido'", _ler(FICHA))


# ═══════════════════════════════════════════════════════════════════════════
# A BORDA QUE A REGRA DO DONO NÃO COBRE
# ═══════════════════════════════════════════════════════════════════════════
class PassoPuladoTests(TestCase):
    """`pulado`: o passo não tem data, mas um POSTERIOR tem — o resultado
    fechou e ninguém marcou o recebimento. A caixa chegou; faltou o registro.

    Pela letra da regra do dono ("só vira Recebido quando o comprador marca"),
    esse passo diria "Em trânsito" ao lado de um resultado já fechado — que é
    exatamente a mentira que o `order_steps` foi escrito para evitar (leia o
    docstring dele). Por isso `pulado` fica com "Recebido".

    ⚠ Este teste prova que a GUARDA existe no template, não que ela desenha
      certo: montar o estado `pulado` de verdade exige fatura com acerto
      fechado, e isso vive nos testes de resultado. O olho está no
      TESTES_TELA1_CELULAR.md.
    """

    def test_o_template_trata_o_passo_pulado(self):
        ficha = _ler(FICHA)
        self.assertIn("p.state == 'pulado'", ficha,
                      'sem esta guarda, um resultado fechado sem recebimento '
                      'registrado mostra "Em trânsito" — a tela mentindo')

    def test_pulado_e_mesmo_um_estado_possivel(self):
        """Se o `order_steps` deixar de emitir `pulado`, a guarda acima vira
        código morto e este teste avisa antes de alguém "limpar" o template."""
        import inspect
        self.assertIn("'pulado'", inspect.getsource(services.order_steps))


# ═══════════════════════════════════════════════════════════════════════════
# AS DUAS TELAS FALAM A MESMA LÍNGUA
# ═══════════════════════════════════════════════════════════════════════════
class VocabularioTests(TestCase):

    def test_nenhuma_das_duas_telas_diz_mais_a_conferir(self):
        """Era o nome antigo do estágio. Ficou em nenhuma das duas — a lista e
        a ficha descrevem a mesma condição com a mesma palavra."""
        for p in (FICHA, LISTA):
            self.assertNotIn('{% trans "A conferir" %}', _ler(p),
                             '%s ainda diz "A conferir"' % os.path.basename(p))

    def test_em_transito_e_a_palavra_das_duas(self):
        for p in (FICHA, LISTA):
            self.assertIn('Em trânsito', _ler(p),
                          '%s não usa a palavra nova' % os.path.basename(p))
