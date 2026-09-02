# -*- coding: utf-8 -*-
"""
A LISTA DE COMPRAS NO TELEFONE — seis achados do dono no iPhone (2026-09-02).

Ele abriu `compras:list` no celular e listou, em ordem: a origem sumida, a
barra de filtros rachada em faixas cinza, só ¥ e nenhum US$, o status "A
conferir" pouco claro, a paginação quebrada e a falta do par esperado ×
resultado.

Cinco dos seis são de CSS, e é por isso que metade destes testes lê a folha em
vez de renderizar HTML. Não é preguiça de teste de interface: o que quebrou
foi sempre uma regra vencendo a outra por especificidade — nenhuma delas
aparece no HTML, e um `assertContains` passaria com a tela em branco. O que dá
para provar em Python é que a REGRA existe e mora na faixa certa; o resto está
no roteiro de conferência (TESTES_TELA1_CELULAR.md), que é olho no aparelho.

⚠ Cada teste aqui nasceu de um jeito específico de a regra sumir. Se um deles
  estiver "óbvio demais", releia o comentário: ele guarda a mutação que já
  aconteceu uma vez.
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
from django.utils import translation

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import services
from vendas.models import DocSequence, SEQ_SO, SalesOrder
from vendas.views_partner import _stage_labels

User = get_user_model()

CSS = os.path.join(settings.BASE_DIR, 'static', 'wtc', 'components.css')
TPL = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                   'partner_compras.html')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════════════════
# O QUE A TELA ESCREVE
# ═══════════════════════════════════════════════════════════════════════════
class ListaNoTelefoneTests(TestCase):

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
                fx_usd_rate=D('0.1400'), total_rmb=D('203237.00'),
                total_usd=D('28453.18'), shipped_at=date(2026, 8, 27),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()

    def _html(self):
        self.client.force_login(self.parceiro)
        return self.client.get(reverse('compras:list')).content.decode()

    # ── (4) o status ──────────────────────────────────────────────────────
    def test_o_estagio_se_chama_em_transito(self):
        """Dono, 2026-09-02: "mude o status que se chama A CONFERIR para EM
        TRANSITO, vai ficar mais claro assim"."""
        with translation.override('pt-br'):
            self.assertEqual(str(_stage_labels()[services.STAGE_A_CONFERIR]),
                             'Em trânsito')

    def test_a_chave_canonica_continua_a_conferir(self):
        """O rótulo mudou; a CHAVE não pode mudar junto. Ela vive na query
        string (`?status=a_conferir`), nos counts e nos testes antigos — um
        link de filtro que o comprador salvou no telefone continua valendo.
        Este teste é o freio de quem for "padronizar" os dois."""
        self.assertEqual(services.STAGE_A_CONFERIR, 'a_conferir')
        self.assertIn('a_conferir', self._html())

    def test_a_lista_nao_diz_mais_a_conferir(self):
        html = self._html()
        self.assertIn('Em trânsito', html)
        self.assertNotIn('>A conferir<', html)

    def test_em_transito_traduz_nos_quatro_idiomas(self):
        """A entrada foi acrescentada à mão nos três catálogos (o Mac do dono
        não tem gettext). Se alguém rodar `makemessages` e o `.mo` não for
        recompilado, en/es/zh voltam a ler o msgid em português."""
        esperado = {'en': 'In transit', 'es': 'En tránsito',
                    'zh-hans': '运输中', 'pt-br': 'Em trânsito'}
        for lng, texto in esperado.items():
            with translation.override(lng):
                self.assertEqual(
                    str(_stage_labels()[services.STAGE_A_CONFERIR]), texto,
                    '%s não traduz "Em trânsito"' % lng)

    # ── (3) e (6) o par esperado × resultado ──────────────────────────────
    def test_o_cartao_mostra_us_junto_do_yuan(self):
        """Dono: "só aparece o RMB, deve aparecer USD tambem". O acompanhante
        vive DENTRO da célula do ¥ — a coluna Total US$ some abaixo de 1100px
        e não tem como voltar sozinha."""
        html = self._html()
        self.assertIn('cusd', html)
        celula = re.search(r'<td class="v key"[^>]*>(.*?)</td>', html, re.S)
        self.assertIsNotNone(celula, 'a célula .key sumiu da lista')
        self.assertIn('28453', celula.group(1),
                      'o US$ não está dentro da célula do ¥')

    def test_esperado_e_resultado_sao_rotulados(self):
        """Dois valores em DINHEIRO no mesmo cartão. A regra do cartão é "sem
        rótulo — a forma diz o que é", e ela funciona com um número só; com
        dois da mesma espécie, forma nenhuma distingue. Sem `data-lbl` o
        comprador lê dois montantes e não sabe qual é qual."""
        html = self._html()
        self.assertIn("data-lbl=\"Esperado\"", html)
        self.assertIn("data-lbl=\"Resultado\"", html)


# ═══════════════════════════════════════════════════════════════════════════
# O QUE A FOLHA DE ESTILO GARANTE
# ═══════════════════════════════════════════════════════════════════════════
class RegrasDeCelularTests(TestCase):
    """Cinco dos seis achados são regra de CSS vencendo regra de CSS. Nenhum
    deles aparece no HTML — por isso a folha é lida como texto."""

    def setUp(self):
        self.css = _ler(CSS)
        self.tpl = _ler(TPL)

    # ── (1) a origem ──────────────────────────────────────────────────────
    def test_a_celula_de_origem_nao_pode_ser_classe_c(self):
        """O ACHADO. `.dtab .c .otag{display:none}` apaga qualquer selo dentro
        de uma célula `.c` — a regra existe porque, no protótipo, o selo morava
        colado ao código e fazia a 1ª linha do cartão ter altura variável.
        Quando a origem virou coluna própria ela herdou o `class="c"` do
        vizinho e herdou o apagamento junto: sumiu do telefone sem sumir do
        desktop, que é por que passou despercebido."""
        self.assertIn('<td class="orig">', self.tpl)
        self.assertNotIn('<td class="c"><span class="otag', self.tpl)
        self.assertIn('.dtab .c .otag{display:none}', self.css,
                      'a regra do protótipo sumiu — então a origem voltaria a '
                      'poder morar dentro do .c, e o próximo a mexer não teria '
                      'nada que o impedisse')

    # ── (3) o acompanhante em US$ ────────────────────────────────────────
    def test_o_us_acende_exatamente_onde_a_coluna_apaga(self):
        """Faixa certa é 1100px, e não 600px. A coluna Total US$ leva
        `hide-lg` (some em 1100). Se o acompanhante acendesse só no bloco de
        telefone, o tablet — entre 600 e 1100 — ficaria sem nenhum dos dois.
        E ele tem de nascer apagado: acima de 1100 a coluna já mostra o mesmo
        número, e os dois juntos seriam o valor escrito duas vezes na linha."""
        self.assertIn('.dtab .v.key .cusd{display:none}', self.css)
        for faixa in ('@media(max-width:1100px)',
                      '@container vp (max-width:1100px)'):
            bloco = [l for l in self.css.splitlines() if l.startswith(faixa)]
            self.assertTrue(bloco, 'sumiu o bloco %s' % faixa)
            self.assertTrue(
                any('.dtab .v.key .cusd{display:block}' in l for l in bloco),
                'o US$ não acende em %s' % faixa)

    def test_a_especificidade_do_seletor_do_us_e_maior_que_a_do_span(self):
        """`.dtab .v span:not(.wtc-pop)` vale 0,3,1 e força `display:block` em
        todo span dentro de uma célula `.v`. Um `.dtab .key .cusd` (0,3,0)
        PERDE dessa regra e o acompanhante reaparece no desktop, ao lado da
        coluna que já escreve o mesmo número. É por isso que o seletor é
        `.v.key` — e não `.key`."""
        self.assertNotIn('.dtab .key .cusd{', self.css)
        self.assertIn('.dtab .v.key .cusd{', self.css)

    # ── (6) o resultado ──────────────────────────────────────────────────
    def test_o_resultado_nao_leva_mais_hide_sm(self):
        """Decisão do dono contra o guia §7.2. Vem com preço: o rótulo. Se
        alguém remover o `data-lbl` "para seguir o guia" sem remover a coluna,
        o cartão volta a ter dois montantes indistinguíveis."""
        self.assertNotIn('<td class="v hide-sm">', self.tpl)
        self.assertIn("data-lbl=\"{% trans 'Resultado' %}\"", self.tpl)
        self.assertIn("data-lbl=\"{% trans 'Esperado' %}\"", self.tpl)

    def test_o_rotulo_do_cartao_so_existe_no_telefone(self):
        """`data-lbl` é a exceção à regra "nenhum rótulo impresso". Ela vale no
        cartão e em lugar nenhum mais — no desktop o cabeçalho da tabela já diz
        o nome da coluna, e o rótulo seria a mesma palavra duas vezes."""
        regra = '.dtab tbody td[data-lbl]::before'
        self.assertEqual(self.css.count(regra), 2,
                         'o rótulo tem de existir nos DOIS espelhos do bloco '
                         'de telefone (@media e @container) e em nenhum outro')

    # ── (2) a barra de filtros ───────────────────────────────────────────
    def test_cada_controle_da_barra_ocupa_a_linha_inteira(self):
        """As faixas cinza. `.tbar` é `flex-wrap` com `gap:1px` sobre
        `background:var(--line)`: o fundo É o fio separador, e o que sobra numa
        linha incompleta não é espaço vazio — é fio esticado. Com três
        controles de largura livre em 390px, duas das três linhas ficavam pela
        metade e a barra aparecia rachada."""
        self.assertEqual(self.css.count('.tbar__sel,.drange{flex:1 1 100%}'), 2)
        self.assertEqual(self.css.count('.tbar__ico{flex:0 0 47px}'), 2)

    # ── (5) a paginação ──────────────────────────────────────────────────
    def test_o_rodape_pode_quebrar_em_duas_faixas(self):
        """Três regras discordavam. `parceiro.css` dá `width:100%` ao
        `.tfoot__sum` abaixo de 760px; o pacote dá `flex:1 1 100%` ao `.pgn`;
        e este bloco dizia `flex-wrap:nowrap`. Com `nowrap` nenhum dos dois
        consegue a própria linha e os dois ficam espremidos lado a lado — a
        paginação saía cortada pela borda."""
        self.assertNotIn('.tfoot{flex-wrap:nowrap', self.css)
        self.assertEqual(
            self.css.count('.tfoot{flex-wrap:wrap;padding:0;min-height:52px}'),
            2, 'o rodapé tem de poder quebrar nos DOIS espelhos')
        self.assertIn('.pgn{margin-left:0;flex:1 1 100%', self.css,
                      'se o .pgn perder a base de 100%, deixar o .tfoot '
                      'quebrar não resolve nada')

    # ── a trava dos espelhos ─────────────────────────────────────────────
    def test_todo_bloco_de_telefone_tem_os_dois_espelhos(self):
        """A folha mantém `@media` e `@container vp` em par: a página solta no
        aparelho lê a janela, a enquadrada pelo viewport.js lê o frame. Uma
        regra escrita em só um dos dois funciona no aparelho do dono e falha no
        protótipo — ou o contrário, que é pior, porque passa na revisão."""
        for regra in ('.tbar__sel,.drange{flex:1 1 100%}',
                      '.dtab tbody td[data-lbl]::before',
                      '.tfoot{flex-wrap:wrap;padding:0;min-height:52px}'):
            self.assertEqual(self.css.count(regra), 2,
                             '%s não está nos dois espelhos' % regra)
