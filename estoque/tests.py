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

import threading
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from chips.engine import is_dead_by_generation
from chips.models import UnknownChip
from tenancy.models import Company, Membership
from tenancy.scope import (CompanyScopedManager, CompanyScopeMissing,
                           company_scope, set_current_company)

from .models import InventoryEntry, Lot, PendingEntry, RejectedEntry
from .views import _compute_gateway


def _grant(user, role=Membership.ROLE_OPERATOR):
    """Vincula o usuário de teste a uma empresa com papel (T1: as views do
    estoque exigem Membership ativo — tenancy.access.role_required)."""
    company, _ = Company.objects.get_or_create(
        name='eMiner', defaults={'slug': 'eminer'})
    Membership.objects.update_or_create(
        user=user, company=company, defaults={'role': role, 'active': True})
    return company


def _scope(testcase, company):
    """Escopo AMBIENTE de empresa para o corpo do teste (T3: os managers do
    estoque são fail-closed — asserts diretos no ORM precisam de escopo, como
    um comando precisaria). Cleanup força None (comandos chamados no meio do
    teste também setam o contextvar; o reset por token não se aplica)."""
    set_current_company(getattr(company, 'pk', company))
    testcase.addCleanup(set_current_company, None)


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
        self.assertEqual(g['destination'], 'aprovado')       # entra no estoque (conservador)
        self.assertEqual(g['profitable'], 'INDETERMINADO')
        self.assertEqual(g['profitable_key'], 'indeterminado')
        # F1b: o 3º passo NÃO é 'pass' (verde "sim") — é 'warn' (âmbar "indeterminado").
        # Antes mostrava "Rentável: sim" mentiroso num chip não avaliado.
        self.assertEqual([s['status'] for s in g['steps']], ['pass', 'pass', 'warn'])

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
        self.company = _grant(self.user)       # T1: operador precisa de vínculo
        _scope(self, self.company)             # T3: asserts diretos no ORM
        self.lot = Lot.objects.create(number=0, operator=self.user,
                                      company=self.company)
        self.client.login(username='op', password='x')
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
        self.company = _grant(self.user)
        _scope(self, self.company)
        self.lot = Lot.objects.create(number=77, operator=self.user,
                                      company=self.company)

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
        self.company = _grant(self.user)       # T1: operador precisa de vínculo
        _scope(self, self.company)             # T3
        self.client.force_login(self.user)
        self.lot = Lot.objects.create(number=88, operator=self.user,
                                      company=self.company)

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


# ═══════════════════════════════════════════════════════════════════════════
# T1 (PLANO_MULTITENANT.md) — matriz PAPEL × VIEW (prova do objetivo O1)
# ═══════════════════════════════════════════════════════════════════════════

class RoleMatrixTests(TestCase):
    """§8 do plano vira parametrização: cada view sensível × cada papel →
    status esperado. Esconder botão NUNCA é a única barreira — o gate é a view.

    operador → busca/preview/adicionar/lista/detalhe (403 no resto)
    gerente+ → abrir/fechar/reabrir/exportar
    sem vínculo (logado) → 403 em tudo do estoque
    anônimo → redirect ao login
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.company = Company.objects.create(name='eMiner', slug='eminer')
        cls.users = {}
        for username, role in [('mx_op', Membership.ROLE_OPERATOR),
                               ('mx_mgr', Membership.ROLE_MANAGER),
                               ('mx_adm', Membership.ROLE_ADMIN)]:
            u = User.objects.create_user(username=username, password='x')
            Membership.objects.create(user=u, company=cls.company, role=role)
            cls.users[role] = u
        # Logado mas SEM vínculo com empresa (ex.: conta órfã) → 403 em tudo.
        cls.users['none'] = User.objects.create_user(username='mx_orfao', password='x')
        # Lote aberto por um GERENTE — o operador trabalha nele (lote é da empresa).
        cls.lot = Lot.all_companies.create(number=900, operator=cls.users['manager'],
                                           company=cls.company)

    def setUp(self):
        _scope(self, self.company)   # T3: asserts diretos no ORM do teste

    def _as(self, who):
        self.client.logout()
        if who is not None:
            self.client.force_login(self.users[who])

    # ── A matriz em si ───────────────────────────────────────────────────────
    def test_matriz_papel_view(self):
        lot_pk = self.lot.pk
        # (nome, método, url, dados, {papel: status esperado})
        # 200 = ok · 302 = redirect pós-ação (ok) · 403 = barrado
        matrix = [
            ('painel', 'get', reverse('painel'), {},
             {'operator': 200, 'manager': 200, 'admin': 200, 'none': 403}),
            ('lot_list', 'get', reverse('estoque:index'), {},
             {'operator': 200, 'manager': 200, 'admin': 200, 'none': 403}),
            ('lot_detail', 'get', reverse('estoque:lot_detail', args=[lot_pk]), {},
             {'operator': 200, 'manager': 200, 'admin': 200, 'none': 403}),
            ('preview', 'get', reverse('estoque:preview', args=[lot_pk]), {'pn': 'KM'},
             {'operator': 200, 'manager': 200, 'admin': 200, 'none': 403}),
            ('export', 'get', reverse('estoque:export', args=[lot_pk]), {},
             {'operator': 403, 'manager': 200, 'admin': 200, 'none': 403}),
            ('lot_close', 'post', reverse('estoque:lot_close', args=[lot_pk]), {},
             {'operator': 403, 'manager': 302, 'admin': 302, 'none': 403}),
            ('lot_reopen', 'post', reverse('estoque:lot_reopen', args=[lot_pk]), {},
             {'operator': 403, 'manager': 302, 'admin': 302, 'none': 403}),
            ('lot_create', 'post', reverse('estoque:lot_create'), {'description': 't'},
             {'operator': 403, 'manager': 302, 'admin': 302, 'none': 403}),
        ]
        for name, method, url, data, expected in matrix:
            for who, status in expected.items():
                with self.subTest(view=name, papel=who):
                    self._as(who)
                    resp = getattr(self.client, method)(url, data)
                    self.assertEqual(resp.status_code, status)
            # Estado do lote pode ter mudado (close/reopen) — restaura.
            Lot.objects.filter(pk=lot_pk).update(
                status=Lot.STATUS_OPEN, closed_at=None)

    def test_anonimo_redireciona_ao_login(self):
        self._as(None)
        resp = self.client.get(reverse('estoque:index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    @patch('estoque.views.classify')
    def test_operador_adiciona_chip_em_lote_aberto(self, mock_classify):
        """O trabalho do operador continua intacto (O2): adicionar a lote aberto
        — inclusive lote aberto pelo GERENTE (lote é ativo da empresa)."""
        mock_classify.return_value = _result(
            chip_type='eMMC', capacity='16GB',
            classification_source='banco de dados', confidence='confirmed')
        self._as('operator')
        resp = self.client.post(reverse('estoque:add', args=[self.lot.pk]),
                                {'pn': 'MATRIXOK16', 'qty': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(InventoryEntry.objects.filter(
            lot=self.lot, part_number='MATRIXOK16').exists())

    @patch('estoque.views.classify')
    def test_operador_remove_so_de_lote_aberto(self, mock_classify):
        """Remoção: p/ operador é correção de lançamento (só lote ABERTO);
        gerente também mexe em lote fechado (comportamento de hoje preservado)."""
        mock_classify.return_value = _result(   # p/ o on-read do render da tabela
            chip_type='eMMC', capacity='16GB',
            classification_source='banco de dados', confidence='confirmed')
        entry = InventoryEntry.objects.create(
            lot=self.lot, part_number='MATRIXRM1', quantity=5)
        url = reverse('estoque:remove', args=[self.lot.pk, entry.pk])

        self._as('operator')
        self.assertEqual(self.client.post(url, {'qty': '1'}).status_code, 200)

        Lot.objects.filter(pk=self.lot.pk).update(status=Lot.STATUS_CLOSED)
        self.assertEqual(self.client.post(url, {'qty': '1'}).status_code, 403)

        self._as('manager')
        self.assertEqual(self.client.post(url, {'qty': '1'}).status_code, 200)
        Lot.objects.filter(pk=self.lot.pk).update(status=Lot.STATUS_OPEN)

    def test_template_esconde_acoes_de_gerente_do_operador(self):
        """Navegação por papel (§9): operador não vê 'Novo Lote' nem Fechar/
        Exportar; gerente vê. (UX — a barreira real é a matriz acima.)"""
        self._as('operator')
        body = self.client.get(reverse('estoque:index')).content.decode()
        self.assertNotIn('Novo Lote', body)
        detail = self.client.get(
            reverse('estoque:lot_detail', args=[self.lot.pk])).content.decode()
        self.assertNotIn('Fechar Lote', detail)
        self.assertNotIn('Exportar', detail)

        self._as('manager')
        body = self.client.get(reverse('estoque:index')).content.decode()
        self.assertIn('Novo Lote', body)
        detail = self.client.get(
            reverse('estoque:lot_detail', args=[self.lot.pk])).content.decode()
        self.assertIn('Fechar Lote', detail)
        self.assertIn('Exportar', detail)

    def test_operador_ve_lote_de_outro_usuario(self):
        """Lote é ativo da EMPRESA (não do usuário): o operador enxerga e
        trabalha no lote que o gerente abriu — mudança intencional da T1
        (antes cada usuário só via os próprios lotes; ver _get_lot)."""
        self._as('operator')
        resp = self.client.get(reverse('estoque:index'))
        self.assertContains(resp, '#900')


class PainelTests(TestCase):
    """/painel/ (lançadeira pós-login): hero = lote aberto → 1 clique para a
    bancada; empty-state orienta por papel; stats do dia como contexto."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.company = Company.objects.create(name='eMiner', slug='eminer')
        cls.op = User.objects.create_user('pn_op', password='x')
        cls.mgr = User.objects.create_user('pn_mgr', password='x')
        Membership.objects.create(user=cls.op, company=cls.company,
                                  role=Membership.ROLE_OPERATOR)
        Membership.objects.create(user=cls.mgr, company=cls.company,
                                  role=Membership.ROLE_MANAGER)

    def setUp(self):
        _scope(self, self.company)   # T3

    def test_hero_mostra_lote_aberto_com_cta(self):
        lot = Lot.objects.create(number=500, operator=self.mgr,
                                 company=self.company,
                                 description='Compra Jul/26')
        self.client.force_login(self.op)
        resp = self.client.get(reverse('painel'))
        self.assertContains(resp, '#500')
        self.assertContains(resp, 'Continuar triagem')
        self.assertContains(resp, reverse('estoque:lot_detail', args=[lot.pk]))

    def test_lote_fechado_nao_vira_hero(self):
        Lot.objects.create(number=501, operator=self.mgr, company=self.company,
                           status=Lot.STATUS_CLOSED)
        self.client.force_login(self.op)
        resp = self.client.get(reverse('painel'))
        self.assertContains(resp, 'Nenhum lote aberto')
        self.assertNotContains(resp, 'Continuar triagem')

    def test_empty_state_orienta_por_papel(self):
        """Sem lote aberto: gerente ganha CTA de abrir; operador, a instrução
        de pedir ao gerente (ele não pode abrir — matriz §8)."""
        self.client.force_login(self.mgr)
        resp = self.client.get(reverse('painel'))
        self.assertContains(resp, 'Abrir um lote')

        self.client.force_login(self.op)
        resp = self.client.get(reverse('painel'))
        self.assertNotContains(resp, 'Abrir um lote')
        self.assertContains(resp, 'Peça ao gerente')

    def test_stats_do_dia(self):
        lot = Lot.objects.create(number=502, operator=self.mgr,
                                 company=self.company)
        InventoryEntry.objects.create(lot=lot, part_number='PNHOJE1')
        PendingEntry.objects.create(lot=lot, part_number='PNFILA1',
                                    operator=self.op)
        self.client.force_login(self.op)
        resp = self.client.get(reverse('painel'))
        self.assertContains(resp, 'Tipos lançados hoje')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# T2 (PLANO_MULTITENANT.md §7) — numeração de lote atômica (prova do O3)
# ═══════════════════════════════════════════════════════════════════════════

class LotNumberSequenceTests(TestCase):
    """open_for_company em série: contador incrementa, herda seed, auto-cura
    drift (lote criado por fora do contador). Roda em qualquer banco."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('seq_user')
        self.company = Company.objects.create(name='SeqCo', slug='seqco')

    def test_empresa_nova_comeca_no_lote_1(self):
        lot = Lot.open_for_company(self.company, self.user, 'primeiro')
        self.assertEqual(lot.number, 1)          # "Lote #001" (§5.2 do plano)
        self.assertEqual(Lot.open_for_company(self.company, self.user).number, 2)

    def test_herda_seed_do_bootstrap(self):
        Company.objects.filter(pk=self.company.pk).update(last_lot_number=40)
        self.company.refresh_from_db()
        self.assertEqual(Lot.open_for_company(self.company, self.user).number, 41)

    def test_auto_cura_drift_do_contador(self):
        """Lote criado POR FORA do contador (legado/manual) não gera colisão:
        o guard max(contador, Max(number)) pula para depois dele."""
        Lot.all_companies.create(number=77, operator=self.user,
                                 company=self.company)      # fora do contador
        lot = Lot.open_for_company(self.company, self.user)
        self.assertEqual(lot.number, 78)
        self.company.refresh_from_db()
        self.assertEqual(self.company.last_lot_number, 78)  # contador curado


class LotNumberRaceTests(TransactionTestCase):
    """O3 (§7 do plano): N threads abrindo lote JUNTAS → números sequenciais sem
    buraco, zero IntegrityError.

    ⚠ Postgres-only: select_for_update é NO-OP no SQLite e o settings_test usa
    SQLite em memória — aqui a prova passaria sem provar nada. Rodar de verdade:

        python manage.py test estoque.tests.LotNumberRaceTests
        # (settings default → seu Postgres local)
    """

    N_THREADS = 8

    @skipUnless(connection.vendor == 'postgresql',
                'select_for_update é no-op no SQLite — rodar contra Postgres')
    def test_corrida_de_numeracao(self):
        user = get_user_model().objects.create_user('race_user')
        company = Company.objects.create(name='RaceCo', slug='raceco')

        barrier = threading.Barrier(self.N_THREADS)   # todas partem juntas
        numbers, errors = [], []

        def worker():
            try:
                barrier.wait()
                lot = Lot.open_for_company(company, user)
                numbers.append(lot.number)
            except Exception as exc:                  # IntegrityError incluso
                errors.append(exc)
            finally:
                connection.close()                    # conexão da thread

        threads = [threading.Thread(target=worker) for _ in range(self.N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])                             # zero quebra
        self.assertEqual(sorted(numbers),
                         list(range(1, self.N_THREADS + 1)))     # sem buraco
        company.refresh_from_db()
        self.assertEqual(company.last_lot_number, self.N_THREADS)


# ═══════════════════════════════════════════════════════════════════════════
# T3 (PLANO_MULTITENANT.md §12.1) — HANDSHAKE DE TENANCY (prova do O4)
# A fronteira comercial absoluta: a empresa A JAMAIS vê lote/estoque/fila da B.
# ═══════════════════════════════════════════════════════════════════════════

class TenancyHandshakeTests(TestCase):
    """Permanente na suíte (no espírito do golden/handshake de rentabilidade):
    cria empresas A e B com dados e prova que A não lê/edita/deleta/exporta
    NADA de B — via manager padrão (Camada A) e via views. A camada B (RLS,
    SQL cru) entra na T4 com o teste próprio."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.a = Company.objects.create(name='eMiner', slug='eminer')
        cls.b = Company.objects.create(name='Brasil Reciclagem', slug='brasil')
        cls.mgr_a = User.objects.create_user('hs_mgr_a', password='x')
        cls.mgr_b = User.objects.create_user('hs_mgr_b', password='x')
        Membership.objects.create(user=cls.mgr_a, company=cls.a,
                                  role=Membership.ROLE_MANAGER)
        Membership.objects.create(user=cls.mgr_b, company=cls.b,
                                  role=Membership.ROLE_MANAGER)
        cls.lot_a = Lot.open_for_company(cls.a, cls.mgr_a, 'lote da eMiner')
        cls.lot_b = Lot.open_for_company(cls.b, cls.mgr_b, 'lote da Brasil')
        # company dos filhos herda do lote no save() (CompanyBoundByLot).
        cls.entry_a = InventoryEntry.all_companies.create(
            lot=cls.lot_a, part_number='PN_DA_EMINER', quantity=3)
        cls.entry_b = InventoryEntry.all_companies.create(
            lot=cls.lot_b, part_number='PN_DA_BRASIL', quantity=5)
        PendingEntry.all_companies.create(
            lot=cls.lot_b, part_number='PEND_DA_BRASIL', operator=cls.mgr_b)
        RejectedEntry.all_companies.create(
            lot=cls.lot_b, part_number='REJ_DA_BRASIL', operator=cls.mgr_b)

    # ── Numeração por empresa ────────────────────────────────────────────────
    def test_cada_empresa_tem_sua_sequencia(self):
        self.assertEqual(self.lot_a.number, 1)
        self.assertEqual(self.lot_b.number, 1)   # mesmo nº, empresas diferentes
        self.assertEqual(self.entry_b.company_id, self.b.pk)  # denormalizado

    # ── Fail-closed (Camada A) ───────────────────────────────────────────────
    def test_sem_escopo_explode_nunca_vaza_todos(self):
        for Model in (Lot, InventoryEntry, PendingEntry, RejectedEntry):
            with self.subTest(model=Model.__name__):
                with self.assertRaises(CompanyScopeMissing):
                    list(Model.objects.all())

    # ── ORM escopado: leitura e escrita ──────────────────────────────────────
    def test_orm_da_a_nao_le_nem_edita_a_b(self):
        with company_scope(self.a):
            self.assertEqual(
                list(Lot.objects.values_list('description', flat=True)),
                ['lote da eMiner'])
            self.assertFalse(
                InventoryEntry.objects.filter(part_number='PN_DA_BRASIL').exists())
            self.assertEqual(PendingEntry.objects.count(), 0)
            self.assertEqual(RejectedEntry.objects.count(), 0)
            # Escrita cross-company pelo manager padrão = 0 linhas afetadas.
            self.assertEqual(
                InventoryEntry.objects.filter(pk=self.entry_b.pk).update(quantity=99), 0)
            self.assertEqual(Lot.objects.filter(pk=self.lot_b.pk).delete()[0], 0)
        with company_scope(self.b):
            self.entry_b.refresh_from_db()
            self.assertEqual(self.entry_b.quantity, 5)         # intacta
            self.assertTrue(Lot.objects.filter(pk=self.lot_b.pk).exists())

    # ── Views: gerente da B tentando o lote da A ─────────────────────────────
    def test_views_da_a_devolvem_404_para_a_b(self):
        self.client.force_login(self.mgr_b)
        casos = [
            ('detail', 'get', reverse('estoque:lot_detail', args=[self.lot_a.pk]), {}),
            ('export', 'get', reverse('estoque:export', args=[self.lot_a.pk]), {}),
            ('preview', 'get', reverse('estoque:preview', args=[self.lot_a.pk]),
             {'pn': 'KMQX10013M'}),
            ('add', 'post', reverse('estoque:add', args=[self.lot_a.pk]),
             {'pn': 'KMQX10013M', 'qty': '1'}),
            ('close', 'post', reverse('estoque:lot_close', args=[self.lot_a.pk]), {}),
            ('remove', 'post',
             reverse('estoque:remove', args=[self.lot_a.pk, self.entry_a.pk]),
             {'qty': '1'}),
        ]
        for nome, metodo, url, data in casos:
            with self.subTest(view=nome):
                resp = getattr(self.client, metodo)(url, data)
                self.assertEqual(resp.status_code, 404)   # nem existe para a B

    def test_lista_e_painel_mostram_so_a_propria_empresa(self):
        self.client.force_login(self.mgr_b)
        body = self.client.get(reverse('estoque:index')).content.decode()
        self.assertIn('lote da Brasil', body)
        self.assertNotIn('lote da eMiner', body)
        painel = self.client.get(reverse('painel')).content.decode()
        self.assertNotIn('lote da eMiner', painel)


class TenancyDeclarationTests(TestCase):
    """§12.1: "tabela sem decisão de tenancy = suíte vermelha". Todo modelo dos
    apps do projeto ou está na lista GLOBAL declarada (PRECIFICACAO §10), ou é
    escopado (campo company + CompanyScopedManager como manager padrão).
    Criou modelo novo e este teste quebrou? Decida o tenancy dele AQUI."""

    GLOBAL_DECLARADOS = {
        # Catálogo/produto — o "Google dos chips" é um cérebro só (§10).
        'chips.Brand', 'chips.ChipFamily', 'chips.DecodeMap', 'chips.KnownPart',
        'chips.Source', 'chips.SearchLog', 'chips.UnknownChip',
        'chips.CorrectionRequest', 'chips.ChipSubmission',
        'chips.ProfitabilityConfig', 'chips.CatalogVersion',
        # CMS de documentação.
        'pages.Page',
        # O próprio tecido do tenancy.
        'tenancy.Company', 'tenancy.Branch', 'tenancy.Membership',
    }
    APPS_DO_PROJETO = {'chips', 'estoque', 'pages', 'tenancy'}

    def test_toda_tabela_declara_tenancy(self):
        from django.apps import apps as django_apps
        faltando = []
        for model in django_apps.get_models():
            if model._meta.app_label not in self.APPS_DO_PROJETO:
                continue    # django/pghistory internos
            if hasattr(model, 'pgh_tracked_model'):
                continue    # tabela de evento pghistory (espelha a rastreada;
                            # ganha policy própria na T4)
            label = f'{model._meta.app_label}.{model.__name__}'
            if label in self.GLOBAL_DECLARADOS:
                continue
            has_company = any(f.name == 'company' for f in model._meta.fields)
            scoped = isinstance(model._default_manager, CompanyScopedManager)
            if not (has_company and scoped):
                faltando.append(label)
        self.assertEqual(
            faltando, [],
            'Modelo(s) SEM decisão de tenancy: ou adicione à lista '
            'GLOBAL_DECLARADOS (com justificativa no PR), ou dê a ele campo '
            'company + CompanyScopedManager + caso no TenancyHandshakeTests: '
            f'{faltando}')
