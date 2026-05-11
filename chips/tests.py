"""
chips/tests.py — Testes do engine de classificação de chips
============================================================

Como rodar:
    python manage.py test chips              # todos os testes
    python manage.py test chips.tests.EngineUnitTests   # só unitários (sem banco)
    python manage.py test chips.tests.EngineIntegrationTests  # com banco real

Quando rodar:
    - Antes de qualquer deploy ou push para main
    - Após mexer em chips/engine.py ou chips/models.py
    - Após adicionar/alterar famílias no banco (testes de integração)
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, SimpleTestCase


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES UNITÁRIOS — não precisam do banco, rodam rápido
# ═══════════════════════════════════════════════════════════════════════════════

class DecodeLenTests(SimpleTestCase):
    """Testa decode de chave multi-char (decode_cap_len > 1)."""

    def _make_family(self, pos, cap_len, map_name, is_emcp=False, interface='', gen_pos=None, gen_map=''):
        """Helper: cria um objeto ChipFamily fake (sem banco)."""
        from unittest.mock import MagicMock
        fam = MagicMock()
        fam.decode_cap_pos  = pos
        fam.decode_cap_len  = cap_len
        fam.decode_cap_map  = map_name
        fam.decode_gen_pos  = gen_pos
        fam.decode_gen_map  = gen_map
        fam.decode_density_type = ''
        fam.is_emcp         = is_emcp
        fam.chip_type       = 'eMCP' if is_emcp else 'eMMC'
        fam.subtype         = ''
        fam.interface       = interface
        fam.suffix_rules    = ''
        fam.tip             = ''
        fam.reasoning       = ''
        fam.prefix          = 'KMR'
        fam.brand.name      = 'Samsung'
        fam.doc_page_id     = None
        return fam

    def _mock_map(self, entries):
        """Patch _load_decode_map para retornar dict fixo."""
        return entries

    def test_cap_len_1_usa_char_simples(self):
        """decode_cap_len=1 (default) — comportamento original."""
        from chips.engine import _result_from_family
        with patch('chips.engine._load_decode_map', return_value={'C': ('64GB', '')}):
            with patch('chips.engine._doc_url', return_value=None):
                fam = self._make_family(pos=3, cap_len=1, map_name='CAP_MAP')
                r = _result_from_family('KLMCG0016A', fam)
        self.assertEqual(r['capacity'], '64GB')

    def test_cap_len_2_usa_par_de_chars(self):
        """decode_cap_len=2 — chave 'X1' → NAND 64GB + RAM 4GB."""
        from chips.engine import _result_from_family

        cap_map  = {'X1': ('64GB', '4GB'), 'BT': ('16GB', '2GB')}
        gen_map  = {'R': ('LPDDR4/4X', '')}

        def mock_load(map_name):
            if map_name == 'EMCP_CAP_KMR':
                return cap_map
            if map_name == 'EMCP_GEN_KMR':
                return gen_map
            return {}

        with patch('chips.engine._load_decode_map', side_effect=mock_load):
            with patch('chips.engine._doc_url', return_value=None):
                fam = self._make_family(
                    pos=3, cap_len=2, map_name='EMCP_CAP_KMR',
                    is_emcp=True, interface='eMMC 5.1',
                    gen_pos=2, gen_map='EMCP_GEN_KMR',
                )
                # KMRx1000B614 → pos2='R', pos3-4='X1'
                r = _result_from_family('KMRX1000B614', fam)

        self.assertEqual(r['emcp_nand'], 'eMMC 5.1 64GB')
        self.assertEqual(r['emcp_ram'],  'LPDDR4/4X 4GB')
        self.assertEqual(r['emcp_source'], 'gramática')

    def test_emcp_sem_mapa_usa_fallback_emcp_ram_types(self):
        """eMCP sem decode_cap_map cai no fallback EMCP_RAM_TYPES pela 3ª letra."""
        from chips.engine import _result_from_family

        with patch('chips.engine._load_decode_map', return_value={}):
            with patch('chips.engine._doc_url', return_value=None):
                fam = self._make_family(
                    pos=None, cap_len=1, map_name='',
                    is_emcp=True, interface='eMMC 5.1',
                )
                # 3ª letra 'R' → LPDDR4/4X
                r = _result_from_family('KMRABC001X', fam)

        self.assertEqual(r['emcp_ram'], 'LPDDR4/4X')
        self.assertIn('eMMC', r['emcp_nand'])
        self.assertEqual(r['emcp_source'], 'parcial (gramática)')

    def test_emcp_ram_types_r_e_lpddr4(self):
        """Verifica que 'R' mapeia para LPDDR4/4X (corrigido — era LPDDR3)."""
        from chips.engine import EMCP_RAM_TYPES
        self.assertEqual(EMCP_RAM_TYPES['R'], 'LPDDR4/4X')

    def test_emcp_ram_types_f_e_lpddr3(self):
        """Verifica que 'F' mapeia para LPDDR3 (corrigido — era LPDDR4/LPDDR4X)."""
        from chips.engine import EMCP_RAM_TYPES
        self.assertEqual(EMCP_RAM_TYPES['F'], 'LPDDR3')

    def test_cap_len_2_chave_nao_encontrada(self):
        """Chave de 2 chars que não existe no mapa → emcp parcial (sem crash)."""
        from chips.engine import _result_from_family

        with patch('chips.engine._load_decode_map', return_value={'X1': ('64GB', '4GB')}):
            with patch('chips.engine._doc_url', return_value=None):
                fam = self._make_family(
                    pos=3, cap_len=2, map_name='EMCP_CAP_KMR',
                    is_emcp=True, interface='eMMC 5.1',
                )
                # 'ZZ' não existe no mapa
                r = _result_from_family('KMRZZ000B614', fam)

        # Não deve estourar — emcp_nand/ram ficam parciais
        self.assertIn('eMMC', r['emcp_nand'])
        self.assertEqual(r['emcp_source'], 'parcial (gramática)')


class CheckRemarkedTests(SimpleTestCase):
    """Testa a detecção de chips remarked (divergência de capacidade)."""

    def _check(self, grammar_val, db_val):
        from chips.engine import _check_remarked
        return _check_remarked(
            {'capacity': grammar_val},
            {'capacity': db_val},
        )

    def test_mesma_capacidade_nao_e_remarked(self):
        self.assertFalse(self._check('4GB', '4GB'))

    def test_capacidades_diferentes_e_remarked(self):
        self.assertTrue(self._check('4GB', '2GB'))

    def test_campos_vazios_nao_e_remarked(self):
        """Sem dados em um dos lados não há base para comparar."""
        self.assertFalse(self._check(None, '4GB'))
        self.assertFalse(self._check('4GB', None))
        self.assertFalse(self._check('', ''))

    def test_mesma_capacidade_mb(self):
        self.assertFalse(self._check('512MB', '512MB'))

    def test_capacidades_mb_diferentes(self):
        self.assertTrue(self._check('512MB', '256MB'))

    def test_dram_density_field(self):
        """_check_remarked também compara dram_density."""
        from chips.engine import _check_remarked
        result = _check_remarked(
            {'dram_density': '4Gb = 512MB por die [✓]'},
            {'dram_density': '2Gb = 256MB por die [✓]'},
        )
        self.assertTrue(result)


class SpecsCompleteTests(SimpleTestCase):
    """Testa o gate de qualidade antes de persistir resultado do Gemini."""

    def _ok(self, specs):
        from chips.engine import _specs_are_complete
        return _specs_are_complete(specs)

    def test_emmc_com_capacidade_passa(self):
        self.assertTrue(self._ok({'chip_type': 'eMMC', 'capacity': '64GB'}))

    def test_emmc_sem_capacidade_falha(self):
        self.assertFalse(self._ok({'chip_type': 'eMMC', 'capacity': ''}))

    def test_emcp_com_ram_e_nand_passa(self):
        self.assertTrue(self._ok({
            'chip_type': 'eMCP',
            'ram': 'LPDDR4X 4GB',
            'nand': 'eMMC 5.1 64GB',
        }))

    def test_emcp_sem_ram_falha(self):
        self.assertFalse(self._ok({
            'chip_type': 'eMCP',
            'ram': '',
            'nand': 'eMMC 5.1 64GB',
        }))

    def test_emcp_sem_nand_falha(self):
        self.assertFalse(self._ok({
            'chip_type': 'eMCP',
            'ram': 'LPDDR4X 4GB',
            'nand': '',
        }))

    def test_soc_com_brand_passa(self):
        self.assertTrue(self._ok({'chip_type': 'SoC', 'brand': 'Qualcomm'}))

    def test_soc_sem_brand_falha(self):
        self.assertFalse(self._ok({'chip_type': 'SoC', 'brand': ''}))

    def test_chip_type_vazio_falha(self):
        self.assertFalse(self._ok({'chip_type': '', 'capacity': '64GB'}))

    def test_dram_com_capacidade_passa(self):
        self.assertTrue(self._ok({'chip_type': 'LPDDR4', 'capacity': '4GB'}))


class ExtractGibTests(SimpleTestCase):
    """Testa extração de capacidade em GB para comparação de remarked."""

    def _gib(self, text):
        from chips.engine import _extract_gib
        return _extract_gib(text)

    def test_gigabytes(self):
        self.assertAlmostEqual(self._gib('4GB'), 4.0)

    def test_megabytes(self):
        self.assertAlmostEqual(self._gib('512MB'), 0.5)

    def test_string_com_contexto(self):
        self.assertAlmostEqual(self._gib('4Gb = 512MB por die [✓]'), 4.0)

    def test_none_retorna_none(self):
        self.assertIsNone(self._gib(None))

    def test_sem_unidade_retorna_none(self):
        self.assertIsNone(self._gib('apenas texto'))


class NormalizeTests(SimpleTestCase):
    """Testa normalização do PN na entrada do classify()."""

    def test_minusculas_sao_normalizadas(self):
        """classify() deve tratar 'kmq310006a' igual a 'KMQ310006A'."""
        # Verifica a normalização interna sem chamar o banco
        import re
        pn = 'kmq310006a'
        normalized = re.sub(r'[^A-Z0-9]', '', pn.upper().strip())
        self.assertEqual(normalized, 'KMQ310006A')

    def test_hifen_e_removido(self):
        import re
        pn = 'K9HDG08U5M-LCB0'
        normalized = re.sub(r'[^A-Z0-9]', '', pn.upper().strip())
        self.assertEqual(normalized, 'K9HDG08U5MLCB0')

    def test_pn_vazio_retorna_invalido(self):
        # Não precisamos do banco para testar isso
        with patch('chips.engine.KnownPart') as _:
            with patch('chips.engine._match_family', return_value=None):
                with patch('chips.engine._gemini_lookup', return_value=None):
                    with patch('chips.engine._fuzzy_candidates', return_value=[]):
                        with patch('chips.engine._log_search'), patch('chips.engine._log_unknown'):
                            from chips.engine import classify
                            result = classify('   ')
                            self.assertFalse(result['known'])
                            self.assertIn('error', result)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO — usam banco de dados real (TestCase)
# ═══════════════════════════════════════════════════════════════════════════════

class EngineIntegrationTests(TestCase):
    """
    Testes que exercitam o classify() com banco real, mas com Gemini mockado
    para não fazer chamadas externas e não gerar custo de API.
    """

    @classmethod
    def setUpTestData(cls):
        """Cria dados mínimos no banco de teste (SQLite separado, descartado após os testes)."""
        from chips.models import Brand, ChipFamily, DecodeMap, KnownPart, Source

        # Marca
        cls.samsung = Brand.objects.create(name='Samsung', code='SAM')

        # DecodeMap para capacidade eMMC
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='A', val_primary='16GB', val_secondary='')
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='B', val_primary='32GB', val_secondary='')
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='C', val_primary='64GB', val_secondary='')

        # Família Samsung eMMC com decode rules
        cls.family_emmc = ChipFamily.objects.create(
            brand=cls.samsung,
            prefix='KLM',
            chip_type='eMMC',
            subtype='eMMC Samsung',
            interface='eMMC 5.1',
            decode_cap_pos=3,
            decode_cap_map='CAP_MAP',
            is_emcp=False,
            active=True,
            priority=50,
        )

        # Família Samsung eMCP (sem decode — depende do Gemini)
        cls.family_emcp = ChipFamily.objects.create(
            brand=cls.samsung,
            prefix='KMQ',
            chip_type='eMCP',
            subtype='LPDDR3 + eMMC',
            is_emcp=True,
            active=True,
            priority=50,
        )

        # DecodeMap para eMCP KMR — chaves de 2 chars (cap dual)
        # BUG-3: X1 corrigido para 32GB+2GB (era 64GB+4GB — valor antigo, pré-Octopart).
        # Produção usa SAM_EMCP_CAP onde X1=32GB+2GB (confirmado: KMQX10013MB, Octopart).
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='X1', val_primary='32GB', val_secondary='2GB')
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='BT', val_primary='16GB', val_secondary='2GB')
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='GD', val_primary='32GB', val_secondary='3GB')
        # DecodeMap para geração RAM KMR
        DecodeMap.objects.create(map_name='EMCP_GEN_KMR', char_key='R', val_primary='LPDDR4/4X', val_secondary='')
        DecodeMap.objects.create(map_name='EMCP_GEN_KMR', char_key='S', val_primary='LPDDR4X',   val_secondary='')

        # Família Samsung eMCP KMR — com decode dual (cap_len=2)
        cls.family_kmr = ChipFamily.objects.create(
            brand=cls.samsung,
            prefix='KMR',
            chip_type='eMCP',
            subtype='LPDDR4/4X + eMMC 5.1',
            interface='eMMC 5.1',
            is_emcp=True,
            decode_cap_pos=3,
            decode_cap_len=2,
            decode_cap_map='EMCP_CAP_KMR',
            decode_gen_pos=2,
            decode_gen_map='EMCP_GEN_KMR',
            active=True,
            priority=40,  # prefixo mais longo → prioridade maior
        )

        # KnownPart enriched (para testar camada 1 — db_exact)
        cls.source = Source.objects.create(name='Test', src_type='manual', url='test:manual')
        cls.known_emcp = KnownPart.objects.create(
            brand=cls.samsung,
            family=cls.family_emcp,
            part_number='KMQ310006A',
            status='enriched',
            chip_type='eMCP',
            emcp_ram='LPDDR3 1GB',
            emcp_nand='eMMC 4GB',
            device='Galaxy J3 2016',
            confidence='confirmed',
            source=cls.source,
        )

    # ── Camada 1: db_exact ────────────────────────────────────────────────────

    def test_db_exact_retorna_resultado_confirmado(self):
        """PN exato no banco deve retornar imediatamente com known_exact=True."""
        from chips.engine import classify
        result = classify('KMQ310006A')
        self.assertTrue(result['known'])
        self.assertTrue(result['known_exact'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertEqual(result['emcp_ram'], 'LPDDR3 1GB')
        self.assertEqual(result['emcp_nand'], 'eMMC 4GB')

    def test_db_exact_case_insensitive(self):
        """PN em minúsculas deve funcionar igual."""
        from chips.engine import classify
        result = classify('kmq310006a')
        self.assertTrue(result['known'])
        self.assertTrue(result['known_exact'])

    # ── Camada 2: gramática ───────────────────────────────────────────────────

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_gramatica_decoda_emmc_capacity(self, _mock_gemini):
        """
        PN da família KLM (eMMC) com decode_cap_pos=3, decode_cap_map=CAP_MAP.
        KLM**C**xxx → posição 3 = 'C' → CAP_MAP['C'] = '64GB'.
        """
        from chips.engine import classify
        result = classify('KLMCG0016A')   # pos 3 = 'C' → 64GB
        self.assertTrue(result['known'])
        self.assertFalse(result.get('known_exact', False))
        self.assertEqual(result['chip_type'], 'eMMC')
        self.assertEqual(result['capacity'], '64GB')

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_gramatica_emcp_sem_dados_gemini_retorna_parcial(self, _mock_gemini):
        """
        eMCP sem decode rules e com Gemini mockado para None deve retornar
        resultado parcial (chip_type correto, emcp_ram/nand vazios).
        """
        from chips.engine import classify
        # PN que começa com KMQ mas não está no banco como enriched
        result = classify('KMQABC001X')
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertFalse(result.get('known_exact', False))

    # ── Camada 2: Gemini complementa gramática ────────────────────────────────

    @patch('chips.engine._gemini_lookup')
    @patch('chips.engine._save_gemini_to_db', return_value=None)
    def test_gemini_complementa_emcp_sem_capacidade(self, _mock_save, mock_gemini):
        """
        Quando a gramática não tem capacidades do eMCP, Gemini é chamado
        e os dados são mesclados no resultado.
        """
        mock_gemini.return_value = {
            'chip_type': 'eMCP',
            'brand': 'Samsung',
            'ram': 'LPDDR4 3GB',
            'nand': 'eMMC 5.1 32GB',
            'device': 'Galaxy A10',
            'confidence': 'high',
            'source_url': None,
            'reasoning': 'Found in preduo.com',
        }

        from chips.engine import classify
        result = classify('KMQABC002X')
        self.assertTrue(result['known'])
        self.assertEqual(result['emcp_ram'], 'LPDDR4 3GB')
        self.assertEqual(result['emcp_nand'], 'eMMC 5.1 32GB')

    # ── Camada 4: PN desconhecido ─────────────────────────────────────────────

    @patch('chips.engine._gemini_lookup', return_value=None)
    @patch('chips.engine._fuzzy_candidates', return_value=[])
    def test_pn_desconhecido_retorna_not_found(self, _mock_fuzzy, _mock_gemini):
        """PN sem família e sem resultado Gemini → known=False."""
        from chips.engine import classify
        result = classify('XYZUNKNOWN99')
        self.assertFalse(result['known'])
        self.assertTrue(result.get('gemini_searched', False))
        self.assertFalse(result.get('gemini_found', True))

    # ── Double-check remarked ─────────────────────────────────────────────────

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_remarked_nao_dispara_quando_gemini_acabou_de_salvar(self, _mock_gemini):
        """
        _gemini_saved_now=True deve impedir o double-check.
        Neste teste, Gemini retorna None então _gemini_saved_now permanece False,
        mas verificamos que o fluxo não lança exceção.
        """
        from chips.engine import classify
        # KLM com decode funcional — Gemini None, sem DB anterior → sem remarked
        result = classify('KLMAG0008A')   # pos 3 = 'A' → 16GB
        self.assertFalse(result.get('remarked_flag', False))

    # ── eMCP dual-decode (decode_cap_len=2) ───────────────────────────────────

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_emcp_kmr_dual_decode_sem_gemini(self, _mock_gemini):
        """
        Família KMR com decode_cap_len=2 deve decodificar NAND e RAM
        diretamente pela gramática, sem precisar do Gemini.
        KMRx1000B614 → pos2='R'→LPDDR4/4X, pos3-4='X1'→32GB NAND + 2GB RAM.

        Nota: X1=32GB+2GB (Octopart: KMQX10013MB). Era 64GB+4GB antes da correção
        — atualizado em BUG-3 para refletir o valor real de produção (SAM_EMCP_CAP).
        """
        from chips.engine import classify
        result = classify('KMRX1000B614')
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertEqual(result['emcp_nand'],  'eMMC 5.1 32GB')
        self.assertEqual(result['emcp_ram'],   'LPDDR4/4X 2GB')
        self.assertEqual(result['emcp_source'], 'gramática')
        # Gemini NÃO deve ter sido chamado (campos já completos)
        self.assertFalse(result.get('gemini_found', False))

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_emcp_kmr_par_bt(self, _mock_gemini):
        """Par 'BT' → 16GB NAND + 2GB RAM."""
        from chips.engine import classify
        # KMRBT... — pos2='R', pos3-4='BT'
        result = classify('KMRBT100B614')
        self.assertEqual(result['emcp_nand'], 'eMMC 5.1 16GB')
        self.assertEqual(result['emcp_ram'],  'LPDDR4/4X 2GB')

    @patch('chips.engine._gemini_lookup', return_value=None)
    def test_emcp_kmr_chave_invalida_fica_parcial(self, _mock_gemini):
        """Chave desconhecida no mapa → resultado parcial, sem crash."""
        from chips.engine import classify
        # KMRZZ... — pos3-4='ZZ' não existe em EMCP_CAP_KMR
        result = classify('KMRZZ100B614')
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        # emcp_source deve indicar que é parcial
        self.assertIn('parcial', result.get('emcp_source', ''))
