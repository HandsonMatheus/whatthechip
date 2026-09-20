"""
A LARGURA no lado do ESTOQUE (2026-09, PLANO_BUS_WIDTH F2).

Três garantias, e a terceira é a que protege o trabalho inteiro:

1. **O snapshot grava a largura** e `interface` nunca mais recebe 'x16' — nem
   na janela em que alguma família ainda trouxer largura pelo caminho antigo.
2. **O card mostra a linha "Largura"**, traduzida, e o card MASCARADO não —
   a máscara é sobre o que o chip É (CLAUDE.md §7, 2026-09-09).
3. **A largura NUNCA sobe da bancada para o catálogo.** O lote pode carregar
   largura vinda da GRAMÁTICA (deduzida do PN) ou, na Parte 2, da revisão por
   foto. Se qualquer um desses caminhos gravasse `KnownPart.bus_width`, o
   coletor passaria a cruzar a regra posicional contra um dado que a própria
   regra produziu — errado com aparência de verificado (HANDOFF §3). Os dois
   canais que promovem lote a catálogo são o `bless_base` e a aprovação de
   `PendingEntry` no admin; os dois estão travados aqui.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from estoque.models import InventoryEntry, Lot, PendingEntry
from estoque.tests import _grant, _result, _scope
from estoque.views import _clean_interface, _snapshot


class SnapshotBusWidthTests(TestCase):
    """O que o lançamento GRAVA."""

    def test_clean_interface_tira_a_largura(self):
        self.assertEqual(_clean_interface({'interface': 'x16'}), '')
        self.assertEqual(_clean_interface({'interface': 'x16 @ 800MHz'}), '')
        self.assertEqual(_clean_interface({'interface': '@ 1866MHz'}), '')

    def test_clean_interface_preserva_PROTOCOLO(self):
        """O engine DEPENDE do protocolo para montar `emcp_nand` e decidir
        UFS×eMMC — limpar demais quebraria o outro lado."""
        for ok in ('eMMC 5.1', 'UFS 3.1', 'Async/ONFI'):
            self.assertEqual(_clean_interface({'interface': ok}), ok)

    def test_clean_interface_continua_tirando_a_GERACAO(self):
        """Regressão da regra antiga: 'DDR3' no interface é geração espelhada."""
        self.assertEqual(_clean_interface({'interface': 'DDR3'}), '')
        self.assertEqual(_clean_interface({'interface': 'LPDDR4X'}), '')

    def test_snapshot_grava_os_tres_campos(self):
        s = _snapshot(_result(chip_type='DDR3', bus_width='x8',
                              bus_width_source='banco'))
        self.assertEqual(s['bus_width'], 'x8')
        self.assertEqual(s['bus_width_source'], 'banco')
        self.assertEqual(s['width_class'], 'narrow')      # x8 → 78 bolas

    def test_snapshot_deriva_a_CLASSE_da_largura(self):
        self.assertEqual(_snapshot(_result(bus_width='x16'))['width_class'], 'wide')
        self.assertEqual(_snapshot(_result(bus_width='x4'))['width_class'], 'narrow')
        # desconhecida fica VAZIA — e vazio ≠ 'wide', distinção que o preço da
        # Parte 2 vai depender.
        self.assertEqual(_snapshot(_result())['width_class'], '')

    def test_snapshot_com_largura_no_interface_legado_NAO_vaza(self):
        """Cinto e suspensório: mesmo que um resultado chegue com 'x16' no
        interface (família ainda não migrada), o campo gravado sai limpo."""
        s = _snapshot(_result(chip_type='DDR3', interface='x16'))
        self.assertEqual(s['interface'], '')


class LancamentoGravaLarguraTests(TestCase):
    """Pela VIEW de verdade — testar `_snapshot` isolado não prova o caminho."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='op_bw', password='x')
        self.company = _grant(self.user)
        _scope(self, self.company)
        self.lot = Lot.objects.create(number=0, origin='pcb', operator=self.user,
                                      company=self.company)
        self.client.login(username='op_bw', password='x')
        self.url = reverse('estoque:add', args=[self.lot.pk])

    @patch('estoque.views.classify')
    def test_ddr3_com_largura_entra_no_lote_com_os_tres_campos(self, mock_classify):
        mock_classify.return_value = _result(
            chip_type='DDR3', capacity='512MB', dram_density='4Gb = 512MB por die',
            bus_width='x8', bus_width_source='banco', interface='x16',
            classification_source='banco de dados', confidence='confirmed')
        self.client.post(self.url, {'pn': 'BWLOTE0001', 'qty': '3', 'has_cap': 'true'})
        e = InventoryEntry.objects.get(lot=self.lot, part_number='BWLOTE0001')
        self.assertEqual(e.bus_width, 'x8')
        self.assertEqual(e.width_class, 'narrow')
        self.assertEqual(e.bus_width_source, 'banco')
        self.assertEqual(e.interface, '', 'a largura vazou para o interface')


class CardLarguraTests(TestCase):
    """A linha na TELA — e em dois idiomas, como manda o MULTILANGUAGE §7."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='op_card', password='x',
                                             is_superuser=True, is_staff=True)
        self.company = _grant(self.user)
        _scope(self, self.company)
        self.lot = Lot.objects.create(number=0, origin='pcb', operator=self.user,
                                      company=self.company)
        self.client.login(username='op_card', password='x')
        self.url = reverse('estoque:preview', args=[self.lot.pk])

    @patch('estoque.views.classify')
    def _render(self, mock_classify, idioma='pt-br', **over):
        """⚠ `translation.override` NÃO funciona aqui: a resposta passa pelo
        middleware, que RE-RESOLVE o idioma pela cadeia do projeto
        (UserLanguage > cookie > Accept-Language > pt-br) e desfaz o override.
        O padrão da casa é mandar o cabeçalho — mesmo do
        `vendas/tests_origem_do_lote.py`."""
        mock_classify.return_value = _result(**over)
        return self.client.get(self.url, {'pn': 'BWCARD0001'},
                               HTTP_ACCEPT_LANGUAGE=idioma)

    def test_ddr3_mostra_a_largura(self):
        r = self._render(chip_type='DDR3', capacity='512MB', bus_width='x8',
                         dram_density='4Gb = 512MB por die',
                         classification_source='banco de dados',
                         confidence='confirmed')
        html = r.content.decode()
        self.assertIn('Largura', html)
        self.assertIn('x8', html)

    def test_emcp_NAO_mostra_a_linha(self):
        """Gerenciado tem DOIS barramentos — o campo é vazio por regra, e uma
        linha vazia na bancada é ruído que ensina o operador a ignorar a tela."""
        r = self._render(chip_type='eMCP', is_emcp=True, emcp_nand='16GB',
                         emcp_ram='LPDDR3 1GB',
                         classification_source='banco de dados',
                         confidence='confirmed')
        # o ramo eMCP do card não tem a linha; o rótulo não aparece
        self.assertNotIn('Largura', r.content.decode())

    def test_rotulo_traduz_mas_o_VALOR_nao(self):
        """`x8` é valor canônico universal, como o part number — nunca traduz.
        Só o rótulo. (I18N.md: lógica compara CHAVE, usuário vê RÓTULO.)"""
        r = self._render(idioma='zh-hans',
                         chip_type='DDR3', capacity='512MB', bus_width='x8',
                         dram_density='4Gb = 512MB por die',
                         classification_source='banco de dados',
                         confidence='confirmed')
        html = r.content.decode()
        self.assertIn('位宽', html, 'o rótulo não traduziu')
        self.assertIn('x8', html, 'o VALOR foi traduzido — não pode')


class LarguraNuncaSobeAoCatalogoTests(TestCase):
    """⚠ A TRAVA MAIS IMPORTANTE desta fase.

    A regra posicional só vale porque é cruzada contra uma fonte INDEPENDENTE.
    Se a largura que a bancada observou (ou que a gramática deduziu do próprio
    PN) subisse para o `KnownPart`, o cruzamento viraria a regra concordando
    com ela mesma: os acordos sobem, a família é promovida, a planilha ganha
    linhas — e nada foi provado.

    São dois os canais que promovem lote → catálogo, e os dois estão aqui.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='op_i4', password='x')
        self.company = _grant(self.user)
        _scope(self, self.company)
        self.lot = Lot.objects.create(number=0, origin='pcb', operator=self.user,
                                      company=self.company)

    def test_aprovacao_de_pendencia_NAO_leva_a_largura(self):
        from chips.models import KnownPart
        from estoque.admin import _confirm_as_knownpart
        pend = PendingEntry.objects.create(
            lot=self.lot, company=self.company, operator=self.user,
            part_number='BWPEND0001', quantity=1, chip_type='DDR3',
            brand='TesteI4', capacity='512MB',
            interface='x16',                      # legado, veio do lote
            bus_width='x8', bus_width_source='gramatica')   # deduzido do PN!
        _confirm_as_knownpart(pend)
        kp = KnownPart.objects.get(part_number='BWPEND0001')
        self.assertEqual(kp.bus_width, '',
                         'a largura da bancada subiu ao catálogo — circularidade')
        self.assertEqual(kp.interface, '',
                         'o interface legado subiu com a largura dentro')

    def test_aprovacao_PRESERVA_o_protocolo(self):
        """O corolário: bloquear a largura não pode jogar fora o protocolo, que
        é dado legítimo ('a versão do eMMC vale dinheiro', 2026-08-27)."""
        from chips.models import KnownPart
        from estoque.admin import _confirm_as_knownpart
        pend = PendingEntry.objects.create(
            lot=self.lot, company=self.company, operator=self.user,
            part_number='BWPEND0002', quantity=1, chip_type='eMMC',
            brand='TesteI4', capacity='16GB', interface='eMMC 5.1')
        _confirm_as_knownpart(pend)
        kp = KnownPart.objects.get(part_number='BWPEND0002')
        self.assertEqual(kp.interface, 'eMMC 5.1')
