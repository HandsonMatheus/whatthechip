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
        # Tipo de catálogo sem regra de rentabilidade → INDETERMINADO → aprovado
        # (regra conservadora). Antes usava chip_type='NOR'; agora 'NOR' é
        # reconhecido como NOR Flash = sucata (dead) pela fonte única
        # (chips/chip_types.py), então usamos 'SoC', que é genuinamente INDETERMINADO.
        r = _result(chip_type='SoC', capacity='8GB', confidence='manual')
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

    # ── Caixa física: DRAM = geração(subtype, LITERAL)+densidade; NAND por GB ──
    def test_caixa_dram_geracao_mais_densidade(self):
        from estoque.views import _compute_destination
        # Geração vem do subtype, literal — MENOS o ruído "SDRAM" (toda DDR é SDRAM).
        # A variante (DDR3/DDR3L/LPDDR3) é preservada. interface pode ser config de
        # barramento ("x16 @ 800MHz") → NÃO vira rótulo. Densidade do dram_density (Gb).
        # Categoria CSS (split jun/2026): DDR/DDR3L → 'ddr' (marrom); LPDDR* → 'lpddr'
        # (azul). O rótulo (DDR3L+2G) é o mesmo; só a cor da caixa muda.
        self.assertEqual(_compute_destination(_result(
            chip_type='RAM', subtype='DDR3L SDRAM', interface='x16 @ 800MHz',
            capacity='256MB', dram_density='2Gb = por die [✓]')), ('DDR3L+2G', 'ddr'))
        # LPDDR móvel = pacote MULTI-DIE → caixa pela CAPACIDADE do pacote em GB
        # (sufixo "GB", convenção CLAUDE.md §6), não pela densidade do die. H9CC 4GB
        # (4 dies de 8Gb) → "LPDDR3+4GB", NUNCA "LPDDR3+32G" (bug do fallback
        # bytes→Gbit assumindo 1 die).
        self.assertEqual(_compute_destination(_result(
            chip_type='RAM', subtype='LPDDR3', interface='LPDDR3',
            capacity='4GB', dram_density=None)), ('LPDDR3+4GB', 'lpddr'))
        # P/ LPDDR a capacidade VENCE a densidade do die (prova que usa capacity):
        # 6GB de pacote, dram_density de 8Gb por die → "LPDDR4+6GB" (6, não 8).
        self.assertEqual(_compute_destination(_result(
            chip_type='LPDDR4', subtype='LPDDR4',
            capacity='6GB', dram_density='8Gb = 1GB por die [✓]')), ('LPDDR4+6GB', 'lpddr'))
        # SK Hynix H5TQ confirmado: dram_density VAZIO + subtype "DDR3 SDRAM".
        # Strip de SDRAM + fallback bytes→Gb (256MB→2G) → 'DDR3+2G'.
        self.assertEqual(_compute_destination(_result(
            chip_type='RAM', subtype='DDR3 SDRAM', interface='DDR3',
            capacity='256MB', dram_density=None)), ('DDR3+2G', 'ddr'))
        # 1GB por chip → 8G (teto físico DDR3)
        self.assertEqual(_compute_destination(_result(
            chip_type='RAM', subtype='DDR3 SDRAM',
            capacity='1GB', dram_density=None)), ('DDR3+8G', 'ddr'))
        # NAND continua por capacidade em GB (não afetado pelo fallback de densidade)
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
    def test_intake_carimba_snapshot_catalog_version(self, mock_classify):
        """Passo 2: a entrada no estoque carimba a edição ATUAL do catálogo (data de atualização)."""
        from chips.models import CatalogVersion
        mock_classify.return_value = _result(
            chip_type='eMMC', capacity='16GB',
            classification_source='banco de dados', confidence='confirmed')
        self.client.post(self.url, {
            'pn': 'TESTVER01', 'qty': '1', 'has_cap': 'true',
            'chip_type': 'eMMC', 'capacity': '16GB',
            'classification_source': 'banco de dados'})
        entry = InventoryEntry.objects.get(lot=self.lot, part_number='TESTVER01')
        self.assertEqual(entry.snapshot_catalog_version, CatalogVersion.current())
        self.assertGreaterEqual(entry.snapshot_catalog_version, 1)

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


class ResnapshotLoteTests(TestCase):
    """Passo 2: o resnapshot_lote revalua as entradas DEFASADAS (catálogo melhorou)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='op2', password='x')
        self.lot = Lot.objects.create(number=77, operator=self.user)

    @patch('chips.engine.classify')
    def test_revalua_entrada_defasada(self, mock_classify):
        from chips.models import CatalogVersion
        from django.core.management import call_command
        v0 = CatalogVersion.current()
        e = InventoryEntry.objects.create(
            lot=self.lot, part_number='MTSTALE1', chip_type='RAM', capacity='48GB',
            snapshot_catalog_version=v0)
        CatalogVersion.bump()                       # catálogo melhora → versão sobe
        cur = CatalogVersion.current()
        self.assertGreater(cur, v0)
        mock_classify.return_value = {
            'chip_type': 'LPDDR4', 'capacity': '6GB',
            'classification_source': 'banco de dados'}
        call_command('resnapshot_lote', '--lot', '77', '--commit')
        e.refresh_from_db()
        self.assertEqual(e.snapshot_catalog_version, cur)   # saiu da defasagem
        self.assertEqual(e.capacity, '6GB')                 # 48GB → 6GB
        self.assertEqual(e.chip_type, 'LPDDR4')

    @patch('chips.engine.classify')
    def test_nao_apaga_source_de_confirmado_sem_familia(self, mock_classify):
        """JZ###: confirmado SEM família casada → classify não devolve Source, mas o
        resnapshot deriva 'banco de dados' (não apaga o rótulo)."""
        from chips.models import CatalogVersion
        from django.core.management import call_command
        v0 = CatalogVersion.current()
        e = InventoryEntry.objects.create(
            lot=self.lot, part_number='JZ109', chip_type='eMMC',
            classification_source='banco de dados', snapshot_catalog_version=v0)
        CatalogVersion.bump()
        mock_classify.return_value = {
            'chip_type': 'eMMC', 'confidence': 'confirmed', 'classification_source': ''}
        call_command('resnapshot_lote', '--lot', '77', '--commit')
        e.refresh_from_db()
        self.assertEqual(e.classification_source, 'banco de dados')  # NÃO apagou

    @patch('chips.engine.classify')
    def test_dry_run_explicito_nao_grava(self, mock_classify):
        """`--dry-run` (explícito) NÃO grava — mesmo com uma entrada defasada."""
        from chips.models import CatalogVersion
        from django.core.management import call_command
        v0 = CatalogVersion.current()
        e = InventoryEntry.objects.create(
            lot=self.lot, part_number='MTDRY1', chip_type='RAM', capacity='48GB',
            snapshot_catalog_version=v0)
        CatalogVersion.bump()
        mock_classify.return_value = {'chip_type': 'LPDDR4', 'capacity': '6GB'}
        call_command('resnapshot_lote', '--lot', '77', '--dry-run')  # NÃO deve gravar
        e.refresh_from_db()
        self.assertEqual(e.capacity, '48GB')                  # intacto
        self.assertEqual(e.snapshot_catalog_version, v0)      # ainda defasado


class OnReadDisplayTests(TestCase):
    """Passo 2: a TELA do estoque mostra o valor ATUAL (cálculo na leitura/on-read)
    das entradas defasadas — sem gravar — e exibe a data de última atualização."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='op3', password='x')
        self.client.force_login(self.user)
        self.lot = Lot.objects.create(number=88, operator=self.user)

    def _get_table(self):
        resp = self.client.get(reverse('estoque:lot_detail', args=[self.lot.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    @patch('estoque.views.classify')
    def test_onread_mostra_valor_atual_de_entrada_defasada(self, mock_classify):
        """Catálogo melhorou desde o intake → a tela mostra o valor ATUAL, não o
        snapshot velho — e NÃO persiste (quem grava é o resnapshot_lote)."""
        from chips.models import CatalogVersion
        v0 = CatalogVersion.current()
        e = InventoryEntry.objects.create(
            lot=self.lot, part_number='MTSTALE9', chip_type='RAM', capacity='48GB',
            snapshot_catalog_version=v0)
        CatalogVersion.bump()                       # catálogo melhora → entrada defasa
        mock_classify.return_value = _result(
            chip_type='LPDDR4', capacity='6GB', classification_source='banco de dados')

        body = self._get_table()
        self.assertIn('6GB', body)                  # valor ATUAL na tela
        self.assertNotIn('48GB', body)              # o defasado não aparece

        e.refresh_from_db()                         # banco INTACTO (on-read não grava)
        self.assertEqual(e.capacity, '48GB')
        self.assertEqual(e.snapshot_catalog_version, v0)

    @patch('estoque.views.classify')
    def test_onread_nao_recalcula_entrada_em_dia(self, mock_classify):
        """Entrada já na versão atual do catálogo → nem chama o classify."""
        from chips.models import CatalogVersion
        InventoryEntry.objects.create(
            lot=self.lot, part_number='MTFRESH9', chip_type='eMMC', capacity='16GB',
            snapshot_catalog_version=CatalogVersion.current())
        body = self._get_table()
        mock_classify.assert_not_called()
        self.assertIn('16GB', body)

    def test_tabela_mostra_data_de_ultima_atualizacao(self):
        from chips.models import CatalogVersion
        InventoryEntry.objects.create(
            lot=self.lot, part_number='MTDATE9', chip_type='eMMC', capacity='16GB',
            snapshot_catalog_version=CatalogVersion.current())
        self.assertIn('atualizado', self._get_table())
