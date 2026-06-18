"""
Testes do gateway de triagem do estoque (Fase 1).

Rodar sempre com o settings de teste (SQLite em memória, Gemini off):

    python manage.py test estoque --settings=core.settings_test

Dois blocos:
  - GatewayDestinationTests: _compute_gateway como função pura (dicts sintéticos),
    sem banco — prova a ordem identificação → fonte → rentabilidade e a regra
    conservadora (INDETERMINADO → aprovado).
  - AddChipHardBlockTests: integra a view add_chip com classify() mockado, para
    isolar a lógica de roteamento (estoque / fila / reprovado / desconhecido) do
    engine de classificação.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chips.engine import is_dead_by_generation
from chips.models import UnknownChip

from .models import InventoryEntry, Lot, PendingEntry, RejectedEntry
from .views import _compute_gateway


def _result(**over):
    """Dict de classificação mínimo, sobrescrevível por teste."""
    base = {
        'chip_type': '', 'subtype': '', 'brand': '',
        'capacity': '', 'emcp_ram': '', 'emcp_nand': '', 'is_emcp': False,
        'interface': '', 'dram_density': '',
        'classification_source': '', 'confidence': '', 'fuzzy_suggestions': [],
    }
    base.update(over)
    return base


class GatewayDestinationTests(TestCase):
    """_compute_gateway: destino correto + estados das 3 etapas.

    TestCase (não SimpleTestCase): assess_profitability / is_dead_by_generation
    leem ProfitabilityConfig do banco (get_config cria o singleton default)."""

    def test_confirmado_rentavel_aprovado(self):
        r = _result(chip_type='eMMC', capacity='16GB',
                    classification_source='banco de dados', confidence='confirmed')
        g = _compute_gateway(r, has_cap=True)
        self.assertEqual(g['destination'], 'aprovado')
        self.assertEqual(g['profitable'], 'RENTÁVEL')
        self.assertEqual(g['profitable_key'], 'rentavel')
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'pass', 'pass'])

    def test_confirmado_nao_rentavel_reprovado(self):
        r = _result(chip_type='eMMC', capacity='2GB',  # < 4GB (default) → NÃO RENTÁVEL
                    classification_source='banco de dados', confidence='confirmed')
        g = _compute_gateway(r, has_cap=True)
        self.assertEqual(g['destination'], 'reprovado')
        self.assertEqual(g['profitable'], 'NÃO RENTÁVEL')
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'pass', 'fail'])

    def test_confirmado_indeterminado_aprovado(self):
        # NOR flash não tem regra de rentabilidade → INDETERMINADO → aprovado.
        r = _result(chip_type='NOR', capacity='8GB', confidence='manual')
        g = _compute_gateway(r, has_cap=True)
        self.assertEqual(g['destination'], 'aprovado')
        self.assertEqual(g['profitable'], 'INDETERMINADO')
        self.assertEqual(g['profitable_key'], 'indeterminado')
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'pass', 'pass'])

    def test_nao_confirmado_vai_para_fila(self):
        # Mesmo sendo eMMC 16GB (rentável), a fonte falha antes da rentabilidade.
        r = _result(chip_type='eMMC', capacity='16GB',
                    classification_source='gramática', confidence='estimated')
        g = _compute_gateway(r, has_cap=True)
        self.assertEqual(g['destination'], 'fila')
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'fail', 'skip'])
        self.assertEqual(g['profitable'], '')  # rentabilidade nem avaliada

    def test_sem_specs_desconhecido(self):
        g = _compute_gateway(_result(), has_cap=False)
        self.assertEqual(g['destination'], 'desconhecido')
        self.assertEqual([s['status'] for s in g['steps']], ['fail', 'skip', 'skip'])

    def test_typo_e_paralelo_ao_destino(self):
        # Sugestões fuzzy aparecem independentemente do destino (rede de segurança).
        r = _result(fuzzy_suggestions=['KLMAG1JETD', 'KLMAG1JET4'])
        g = _compute_gateway(r, has_cap=False)
        self.assertEqual(g['destination'], 'desconhecido')
        self.assertTrue(g['typo']['has'])
        self.assertEqual(len(g['typo']['suggestions']), 2)

    def test_sem_typo(self):
        g = _compute_gateway(_result(chip_type='eMMC', capacity='16GB',
                                     confidence='confirmed'), has_cap=True)
        self.assertFalse(g['typo']['has'])

    # ── Morto por geração (DERIVADO da rentabilidade) ───────────────────────
    def test_is_dead_by_generation(self):
        # Geração morta — independe da capacidade (eMCP exige RAM e NAND, como no real).
        self.assertTrue(is_dead_by_generation(_result(
            chip_type='eMCP', is_emcp=True,
            emcp_ram='LPDDR2 ⚠ cap. não mapeada', emcp_nand='eMMC ⚠ cap. não mapeada')))
        self.assertTrue(is_dead_by_generation(_result(chip_type='DDR', subtype='DDR2')))
        self.assertTrue(is_dead_by_generation(_result(chip_type='MCP')))
        # Geração viva
        self.assertFalse(is_dead_by_generation(_result(
            chip_type='eMCP', is_emcp=True, emcp_ram='LPDDR4 2GB', emcp_nand='eMMC 16GB')))
        # Não-rentável por CAPACIDADE NÃO conta como morto por geração
        self.assertFalse(is_dead_by_generation(_result(chip_type='eMMC', capacity='2GB')))
        self.assertFalse(is_dead_by_generation(_result(
            chip_type='eMCP', is_emcp=True, emcp_ram='LPDDR3 0.5GB', emcp_nand='eMMC 16GB')))

    def test_gen_dead_nao_confirmado_vai_reprovado(self):
        # KMN5W000ZM-like: eMCP LPDDR2 por gramática, capacidade não mapeada (has_cap
        # False). Antes caía em DESCONHECIDO; agora vai direto pra REPROVADO por geração.
        r = _result(chip_type='eMCP', is_emcp=True, subtype='LPDDR2 + eMMC',
                    emcp_ram='LPDDR2 ⚠ cap. não mapeada', emcp_nand='eMMC ⚠ cap. não mapeada',
                    classification_source='gramática', confidence='estimated')
        g = _compute_gateway(r, has_cap=False)
        self.assertEqual(g['destination'], 'reprovado')
        self.assertTrue(g['reject_by_generation'])
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'fail', 'fail'])

    def test_gen_dead_confirmado_segue_fluxo_normal(self):
        # eMCP LPDDR2 CONFIRMADO → reprovado normal (sem rótulo de geração).
        r = _result(chip_type='eMCP', is_emcp=True, subtype='LPDDR2 + eMMC',
                    emcp_ram='LPDDR2 1GB', emcp_nand='eMMC 8GB',
                    classification_source='banco de dados', confidence='confirmed')
        g = _compute_gateway(r, has_cap=True)
        self.assertEqual(g['destination'], 'reprovado')
        self.assertFalse(g['reject_by_generation'])
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'pass', 'fail'])

    # ── Caixa física: DRAM = geração(LITERAL)+densidade; NAND por capacidade GB ──
    def test_caixa_dram_geracao_mais_densidade(self):
        from estoque.views import _compute_destination
        # Geração aparece EXATA (DDR3L, não 'D3'); densidade do dram_density.
        # capacity (256MB) é IGNORADA — caixa é por densidade impressa no chip.
        self.assertEqual(_compute_destination(_result(
            chip_type='RAM', subtype='DDR3', interface='DDR3L',
            capacity='256MB', dram_density='2Gb = por die [✓]')), ('DDR3L+2G', 'lpddr'))
        # Samsung DDR4 (sem confundir Gb com GB)
        self.assertEqual(_compute_destination(_result(
            chip_type='DDR4', interface='DDR4',
            dram_density='4Gb = 512MB por die [✓]')), ('DDR4+4G', 'lpddr'))
        # LPDDR4 sem interface → cai no subtype, literal
        self.assertEqual(_compute_destination(_result(
            chip_type='LPDDR4', subtype='LPDDR4',
            dram_density='8Gb = 1GB por die [✓]')), ('LPDDR4+8G', 'lpddr'))
        # NAND continua por capacidade em GB (não afetado)
        self.assertEqual(_compute_destination(_result(
            chip_type='eMMC', capacity='16GB')), ('EMMC16GB', 'emmc'))


class AddChipHardBlockTests(TestCase):
    """add_chip: roteamento estoque / fila / reprovado / desconhecido."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='op', password='x')
        self.client.login(username='op', password='x')
        self.lot = Lot.objects.create(number=0, operator=self.user)
        self.url = reverse('estoque:add', args=[self.lot.pk])

    @patch('estoque.views.classify')
    def test_confirmado_nao_rentavel_vira_rejected(self, mock_classify):
        mock_classify.return_value = _result(
            chip_type='eMMC', capacity='2GB',  # < 4GB → NÃO RENTÁVEL por capacidade
            classification_source='banco de dados', confidence='confirmed')
        self.client.post(self.url, {'pn': 'TESTREJECT01', 'qty': '2', 'has_cap': 'true'})
        self.assertEqual(
            RejectedEntry.objects.filter(lot=self.lot, part_number='TESTREJECT01').count(), 1)
        self.assertFalse(
            InventoryEntry.objects.filter(lot=self.lot, part_number='TESTREJECT01').exists())

    @patch('estoque.views.classify')
    def test_reprovado_nao_emcp_com_none_nao_quebra(self, mock_classify):
        # Chip não-eMCP (LPDDR2): classify devolve emcp_ram/emcp_nand = None.
        # Antes do fix, o insert no RejectedEntry dava NotNullViolation (500).
        mock_classify.return_value = _result(
            chip_type='LPDDR2', capacity='1GB', interface='LPDDR2',
            emcp_ram=None, emcp_nand=None,
            classification_source='banco de dados', confidence='confirmed')
        resp = self.client.post(self.url, {'pn': 'K4P8G304EQ', 'qty': '1', 'has_cap': 'true'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            RejectedEntry.objects.filter(lot=self.lot, part_number='K4P8G304EQ').count(), 1)

    @patch('estoque.views.classify')
    def test_confirmado_rentavel_entra_no_estoque(self, mock_classify):
        mock_classify.return_value = _result(
            chip_type='eMMC', capacity='16GB',
            classification_source='banco de dados', confidence='confirmed')
        self.client.post(self.url, {
            'pn': 'TESTOK16', 'qty': '1', 'has_cap': 'true',
            'chip_type': 'eMMC', 'capacity': '16GB',
            'classification_source': 'banco de dados'})
        self.assertTrue(
            InventoryEntry.objects.filter(lot=self.lot, part_number='TESTOK16').exists())
        self.assertFalse(RejectedEntry.objects.filter(part_number='TESTOK16').exists())

    @patch('estoque.views.classify')
    def test_nao_confirmado_vai_para_pending(self, mock_classify):
        mock_classify.return_value = _result(
            chip_type='eMMC', capacity='16GB',
            classification_source='gramática', confidence='estimated')
        self.client.post(self.url, {'pn': 'TESTGRAM01', 'qty': '1', 'has_cap': 'true'})
        self.assertTrue(
            PendingEntry.objects.filter(lot=self.lot, part_number='TESTGRAM01').exists())
        self.assertFalse(InventoryEntry.objects.filter(part_number='TESTGRAM01').exists())
        self.assertFalse(RejectedEntry.objects.filter(part_number='TESTGRAM01').exists())

    def test_has_cap_false_vai_para_unknown(self):
        # has_cap=false e chip não-reconhecido → UnknownChip (classify roda, mas
        # não é morto por geração nem confirmado).
        self.client.post(self.url, {'pn': 'TESTUNK01', 'qty': '1', 'has_cap': 'false'})
        self.assertTrue(UnknownChip.objects.filter(part_number='TESTUNK01').exists())

    @patch('estoque.views.classify')
    def test_gen_dead_nao_confirmado_vira_rejected_geracao(self, mock_classify):
        # eMCP LPDDR2 por gramática, capacidade não mapeada, has_cap=false:
        # antes ia pra UnknownChip; agora vai direto pra reprovado POR GERAÇÃO.
        mock_classify.return_value = _result(
            chip_type='eMCP', is_emcp=True, subtype='LPDDR2 + eMMC',
            emcp_ram='LPDDR2 ⚠ cap. não mapeada', emcp_nand='eMMC ⚠ cap. não mapeada',
            classification_source='gramática', confidence='estimated')
        self.client.post(self.url, {'pn': 'KMN5W000ZM', 'qty': '1', 'has_cap': 'false'})
        rej = RejectedEntry.objects.filter(lot=self.lot, part_number='KMN5W000ZM')
        self.assertEqual(rej.count(), 1)
        self.assertEqual(rej.first().rejection_reason, 'NÃO RENTÁVEL (geração)')
        self.assertFalse(UnknownChip.objects.filter(part_number='KMN5W000ZM').exists())
