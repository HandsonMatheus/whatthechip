"""
chips/tests.py — Testes do engine de classificação de chips
============================================================

Cobertura após a remoção do Gemini e do campo KnownPart.status (jun/2026):

  • Gate de confiança: só confidence ∈ (confirmed, manual) é AUTORITATIVO —
    vence a gramática e retorna na camada 1 (db_exact). Registros distributor/
    estimated NÃO são autoritativos: o engine cai na gramática (sem poluir o
    resultado com dados de baixa confiança).
  • Sem fila de revisão: buscar um PN não cria mais KnownPart "raw".
  • Rentabilidade (assess_profitability / is_dead_by_generation) intacta — ela
    depende só do `result` dict, nunca do status.
  • Fuzzy de digitação intacto.
  • Nenhum símbolo Gemini nem campo status sobrou no código.

Como rodar:
    python manage.py test chips --settings=core.settings_test
    python manage.py test chips.tests.EngineIntegrationTests --settings=core.settings_test
"""

from unittest.mock import patch
from django.test import TestCase, SimpleTestCase


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES UNITÁRIOS — não precisam do banco, rodam rápido
# ═══════════════════════════════════════════════════════════════════════════════

class DecodeLenTests(SimpleTestCase):
    """Testa decode de chave multi-char (decode_cap_len > 1)."""

    def _make_family(self, pos, cap_len, map_name, is_emcp=False, interface='', gen_pos=None, gen_map='', gen_len=1):
        """Helper: cria um objeto ChipFamily fake (sem banco)."""
        from unittest.mock import MagicMock
        fam = MagicMock()
        fam.decode_cap_pos  = pos
        fam.decode_cap_len  = cap_len
        fam.decode_cap_map  = map_name
        fam.decode_gen_pos  = gen_pos
        fam.decode_gen_map  = gen_map
        fam.decode_gen_len  = gen_len   # precisa ser int: o engine faz pos+gen_len (senão MagicMock vaza)
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

        # o engine anexa "⚠ cap. não mapeada" quando não há capacidade decodificada;
        # o que importa neste teste é o tipo RAM vindo do fallback EMCP_RAM_TYPES ('R' → LPDDR4/4X)
        self.assertTrue(r['emcp_ram'].startswith('LPDDR4/4X'))
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
        # Não precisamos do banco para testar isso (sem família, sem fuzzy)
        with patch('chips.engine._match_family', return_value=None):
            with patch('chips.engine._combined_suggestions', return_value=[]):
                with patch('chips.engine._log_search'), patch('chips.engine._log_unknown'):
                    from chips.engine import classify
                    result = classify('   ')
                    self.assertFalse(result['known'])
                    self.assertIn('error', result)


class NoGeminiNoStatusTests(SimpleTestCase):
    """
    Prova de remoção: Gemini e o campo status sumiram de verdade.
    Falha se alguém reintroduzir qualquer símbolo Gemini, o campo status,
    ou os níveis de confiança de IA.
    """

    def test_engine_sem_simbolos_gemini(self):
        import chips.engine as eng
        for sym in (
            "_get_api_key", "_gemini_api_call", "_gemini_lookup",
            "_gemini_emcp_followup", "_save_gemini_to_db", "_build_result_from_gemini",
            "_specs_are_complete", "_persist_grammar_result",
            "GEMINI_PROMPT", "GEMINI_EMCP_FOLLOWUP", "GEMINI_MODELS_FALLBACK",
        ):
            self.assertFalse(hasattr(eng, sym), f"{sym} ainda existe em chips.engine")

    def test_settings_sem_flags_gemini(self):
        from django.conf import settings
        self.assertFalse(hasattr(settings, "GEMINI_ENABLED"))
        self.assertFalse(hasattr(settings, "GEMINI_API_KEY"))

    def test_knownpart_sem_campo_status(self):
        from django.core.exceptions import FieldDoesNotExist
        from chips.models import KnownPart
        with self.assertRaises(FieldDoesNotExist):
            KnownPart._meta.get_field("status")
        self.assertFalse(hasattr(KnownPart, "is_enriched"))
        self.assertFalse(hasattr(KnownPart, "STATUS_CHOICES"))

    def test_confidence_sem_niveis_de_ia(self):
        from chips.models import KnownPart, Source
        conf_keys = dict(KnownPart.CONFIDENCE_CHOICES).keys()
        for ai in ("ai_high", "ai_medium", "ai_low"):
            self.assertNotIn(ai, conf_keys)
        # Source também não tem mais o tipo "ai"
        self.assertNotIn("ai", dict(Source.SOURCE_TYPES).keys())


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO — usam banco de dados real (TestCase)
# ═══════════════════════════════════════════════════════════════════════════════

class EngineIntegrationTests(TestCase):
    """
    Exercita classify() com banco real. Sem Gemini, sem status: o engine usa
    apenas banco confirmado (confidence ∈ confirmed/manual) + gramática.
    """

    @classmethod
    def setUpTestData(cls):
        from chips.models import Brand, ChipFamily, DecodeMap, KnownPart, Source

        cls.samsung = Brand.objects.create(name='Samsung', code='SAM')

        # DecodeMap para capacidade eMMC
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='A', val_primary='16GB', val_secondary='')
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='B', val_primary='32GB', val_secondary='')
        DecodeMap.objects.create(map_name='CAP_MAP', char_key='C', val_primary='64GB', val_secondary='')

        # Família Samsung eMMC com decode rules
        cls.family_emmc = ChipFamily.objects.create(
            brand=cls.samsung, prefix='KLM', chip_type='eMMC',
            subtype='eMMC Samsung', interface='eMMC 5.1',
            decode_cap_pos=3, decode_cap_map='CAP_MAP',
            is_emcp=False, active=True, priority=50,
        )

        # Família Samsung eMCP (sem decode — resultado parcial pela gramática)
        cls.family_emcp = ChipFamily.objects.create(
            brand=cls.samsung, prefix='KMQ', chip_type='eMCP',
            subtype='LPDDR3 + eMMC', is_emcp=True, active=True, priority=50,
        )

        # DecodeMap para eMCP KMR — chaves de 2 chars (cap dual)
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='X1', val_primary='32GB', val_secondary='2GB')
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='BT', val_primary='16GB', val_secondary='2GB')
        DecodeMap.objects.create(map_name='EMCP_CAP_KMR', char_key='GD', val_primary='32GB', val_secondary='3GB')
        DecodeMap.objects.create(map_name='EMCP_GEN_KMR', char_key='R', val_primary='LPDDR4/4X', val_secondary='')
        DecodeMap.objects.create(map_name='EMCP_GEN_KMR', char_key='S', val_primary='LPDDR4X',   val_secondary='')

        cls.family_kmr = ChipFamily.objects.create(
            brand=cls.samsung, prefix='KMR', chip_type='eMCP',
            subtype='LPDDR4/4X + eMMC 5.1', interface='eMMC 5.1', is_emcp=True,
            decode_cap_pos=3, decode_cap_len=2, decode_cap_map='EMCP_CAP_KMR',
            decode_gen_pos=2, decode_gen_map='EMCP_GEN_KMR',
            active=True, priority=40,  # prefixo mais longo → prioridade maior
        )

        # KnownPart CONFIRMADO (autoridade): testa camada 1 (db_exact). Sem status.
        cls.source = Source.objects.create(name='Test', src_type='manual', url='test:manual')
        cls.known_emcp = KnownPart.objects.create(
            brand=cls.samsung, family=cls.family_emcp,
            part_number='KMQ310006A',
            chip_type='eMCP', emcp_ram='LPDDR3 1GB', emcp_nand='eMMC 4GB',
            device='Galaxy J3 2016', confidence='confirmed', source=cls.source,
        )

    # ── Camada 1: db_exact (só confirmados são autoridade) ────────────────────

    def test_db_exact_confirmado_retorna_imediato(self):
        """PN confirmado no banco retorna na camada 1 com known_exact=True."""
        from chips.engine import classify
        result = classify('KMQ310006A')
        self.assertTrue(result['known'])
        self.assertTrue(result['known_exact'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertEqual(result['emcp_ram'], 'LPDDR3 1GB')
        self.assertEqual(result['emcp_nand'], 'eMMC 4GB')

    def test_db_exact_case_insensitive(self):
        from chips.engine import classify
        result = classify('kmq310006a')
        self.assertTrue(result['known'])
        self.assertTrue(result['known_exact'])

    # ── Gate de confiança: o coração da mudança ───────────────────────────────

    def test_distribuidor_com_specs_reconhecido_mas_gramatica_vence(self):
        """
        Gate fiel ao antigo status="enriched": um KnownPart distributor COM specs
        VOLTA a ser reconhecido na camada 1 (known_exact=True). Mas continua SEM
        vencer a gramática completa — quem sobrepõe o decode é só confirmed/manual.
        (Regressão corrigida: antes o gate confidence-only escondia esses registros.)
        """
        from chips.models import KnownPart
        # 'KLMCG0016A': a gramática decoda capacity=64GB (pos3='C'). O registro
        # distributor diz 128GB — é reconhecido, mas a gramática completa prevalece.
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emmc,
            part_number='KLMCG0016A', chip_type='eMMC',
            capacity='128GB', confidence='distributor',
        )
        from chips.engine import classify
        result = classify('KLMCG0016A')
        self.assertTrue(result['known_exact'])               # reconhecido (visível)
        self.assertEqual(result['capacity'], '64GB')          # gramática vence (não 128GB)
        self.assertEqual(result['confidence'], 'distributor')

    def test_estimated_com_specs_reconhecido(self):
        """estimated COM specs também é reconhecido (gate = tem dados reais);
        a gramática completa ainda vence o valor."""
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emmc,
            part_number='KLMBG0008A', chip_type='eMMC',
            capacity='999GB', confidence='estimated',
        )
        from chips.engine import classify
        result = classify('KLMBG0008A')   # pos3='B' → gramática 32GB
        self.assertTrue(result['known_exact'])
        self.assertEqual(result['capacity'], '32GB')

    def test_registro_vazio_sem_specs_nao_e_reconhecido(self):
        """Placeholder vazio (chip_type, mas SEM capacidade — a antiga fila raw)
        NÃO é reconhecido: cai na gramática. É o que o gate _USABLE exclui."""
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emmc,
            part_number='KLMAG0007A', chip_type='eMMC',
            capacity='', emcp_ram='', emcp_nand='', density_gbit='',
            confidence='estimated',
        )
        from chips.engine import classify
        result = classify('KLMAG0007A')   # pos3='A' → gramática 16GB
        self.assertFalse(result.get('known_exact', False))
        self.assertEqual(result['capacity'], '16GB')
        self.assertTrue(result.get('pn_not_in_db'))

    def test_confirmado_sobrepoe_gramatica(self):
        """Registro confirmed com capacidade própria VENCE a gramática completa."""
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emmc,
            part_number='KLMAG0008A', chip_type='eMMC',
            capacity='99GB', confidence='confirmed',   # gramática diria 16GB (pos3='A')
        )
        from chips.engine import classify
        result = classify('KLMAG0008A')
        self.assertTrue(result['known_exact'])
        self.assertEqual(result['capacity'], '99GB')   # banco confirmado venceu

    def test_manual_tambem_e_autoritativo(self):
        """confidence='manual' conta como confirmado (autoridade)."""
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emmc,
            part_number='KLMAG0009A', chip_type='eMMC',
            capacity='8GB', confidence='manual',
        )
        from chips.engine import classify
        result = classify('KLMAG0009A')
        self.assertTrue(result['known_exact'])
        self.assertEqual(result['capacity'], '8GB')

    # ── Sem fila de revisão: buscar PN não cria KnownPart raw ──────────────────

    def test_busca_de_pn_nao_cria_knownpart(self):
        """Buscar um PN decodificável pela gramática NÃO cria registro (a antiga
        fila raw foi removida)."""
        from chips.models import KnownPart
        from chips.engine import classify
        before = KnownPart.objects.count()
        classify('KLMCG0016A')          # gramática reconhece, mas não está no banco
        self.assertEqual(KnownPart.objects.count(), before)

    # ── Camada 2: gramática ───────────────────────────────────────────────────

    def test_gramatica_decoda_emmc_capacity(self):
        """KLM**C**xxx → pos 3 = 'C' → CAP_MAP['C'] = '64GB'."""
        from chips.engine import classify
        result = classify('KLMCG0016A')
        self.assertTrue(result['known'])
        self.assertFalse(result.get('known_exact', False))
        self.assertEqual(result['chip_type'], 'eMMC')
        self.assertEqual(result['capacity'], '64GB')

    def test_gramatica_emcp_sem_dados_retorna_parcial(self):
        """eMCP sem decode rules → resultado parcial (chip_type correto, sem cap)."""
        from chips.engine import classify
        result = classify('KMQABC001X')   # KMQ, não está no banco
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertFalse(result.get('known_exact', False))

    # ── Camada 3: PN desconhecido + fuzzy ─────────────────────────────────────

    def test_pn_desconhecido_retorna_not_found(self):
        """PN sem família → known=False, sem chaves Gemini."""
        from chips.engine import classify
        result = classify('XYZUNKNOWN99')
        self.assertFalse(result['known'])
        self.assertIn('fuzzy_suggestions', result)
        self.assertNotIn('gemini_searched', result)
        self.assertNotIn('gemini_found', result)

    def test_fuzzy_sugere_pn_confirmado(self):
        """Digitação errada de um PN confirmado → sugerido via fuzzy."""
        from chips.engine import classify
        # KMQ310006A é confirmado; busca a variação KMQ310006B (1 char de diferença).
        result = classify('KMQ310006B')
        self.assertIn('KMQ310006A', result.get('fuzzy_suggestions', []))

    # ── eMCP dual-decode (decode_cap_len=2) ───────────────────────────────────

    def test_emcp_kmr_dual_decode(self):
        """KMRx1000B614 → pos2='R'→LPDDR4/4X, pos3-4='X1'→32GB NAND + 2GB RAM."""
        from chips.engine import classify
        result = classify('KMRX1000B614')
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertEqual(result['emcp_nand'],  'eMMC 5.1 32GB')
        self.assertEqual(result['emcp_ram'],   'LPDDR4/4X 2GB')
        self.assertEqual(result['emcp_source'], 'gramática')

    def test_emcp_kmr_par_bt(self):
        """Par 'BT' → 16GB NAND + 2GB RAM."""
        from chips.engine import classify
        result = classify('KMRBT100B614')
        self.assertEqual(result['emcp_nand'], 'eMMC 5.1 16GB')
        self.assertEqual(result['emcp_ram'],  'LPDDR4/4X 2GB')

    def test_emcp_kmr_chave_invalida_fica_parcial(self):
        """Chave desconhecida no mapa → resultado parcial, sem crash."""
        from chips.engine import classify
        result = classify('KMRZZ100B614')
        self.assertTrue(result['known'])
        self.assertEqual(result['chip_type'], 'eMCP')
        self.assertIn('parcial', result.get('emcp_source', ''))


# ═══════════════════════════════════════════════════════════════════════════════
# RENTABILIDADE — prova de que assess_profitability/is_dead_by_generation NÃO
# foram afetados pela remoção (dependem só do `result` dict, nunca do status).
# Usa TestCase porque assess_profitability lê ProfitabilityConfig (singleton DB).
# ═══════════════════════════════════════════════════════════════════════════════

class ProfitabilityTests(TestCase):

    def _assess(self, result):
        from chips.engine import assess_profitability
        return assess_profitability(result)

    def _dead(self, result):
        from chips.engine import is_dead_by_generation
        return is_dead_by_generation(result)

    # ── assess_profitability ──────────────────────────────────────────────────

    def test_emcp_moderno_rentavel(self):
        self.assertEqual(self._assess({
            'is_emcp': True, 'chip_type': 'eMCP',
            'emcp_ram': 'LPDDR4 3GB', 'emcp_nand': 'eMMC 5.1 32GB',
        }), 'RENTÁVEL')

    def test_emcp_lpddr2_nao_rentavel_por_geracao(self):
        self.assertEqual(self._assess({
            'is_emcp': True, 'chip_type': 'eMCP',
            'emcp_ram': 'LPDDR2 1GB', 'emcp_nand': 'eMMC 16GB',
        }), 'NÃO RENTÁVEL')

    def test_emmc_pequeno_nao_rentavel(self):
        self.assertEqual(self._assess({'chip_type': 'eMMC', 'capacity': '2GB'}), 'NÃO RENTÁVEL')

    def test_emmc_grande_rentavel(self):
        self.assertEqual(self._assess({'chip_type': 'eMMC', 'capacity': '16GB'}), 'RENTÁVEL')

    def test_epop_sempre_nao_rentavel(self):
        self.assertEqual(self._assess({
            'chip_type': 'ePoP', 'is_emcp': True, 'emcp_ram': '', 'emcp_nand': '',
        }), 'NÃO RENTÁVEL')

    def test_gddr2_nao_rentavel(self):
        self.assertEqual(self._assess({'chip_type': 'GDDR2'}), 'NÃO RENTÁVEL')

    def test_ddr3_baixa_densidade_nao_rentavel(self):
        self.assertEqual(self._assess({
            'chip_type': 'RAM', 'subtype': 'DDR3',
            'dram_density': '1Gb = 128MB por die [✓]',
        }), 'NÃO RENTÁVEL')

    def test_nand_flash_raw_nao_rentavel(self):
        self.assertEqual(self._assess({'chip_type': 'NAND Flash', 'capacity': '512MB'}), 'NÃO RENTÁVEL')

    # ── is_dead_by_generation (derivado da rentabilidade) ─────────────────────

    def test_dead_lpddr2_independe_da_capacidade(self):
        """LPDDR2 é morto por GERAÇÃO → True mesmo removendo os números."""
        self.assertTrue(self._dead({
            'is_emcp': True, 'chip_type': 'eMCP',
            'emcp_ram': 'LPDDR2 1GB', 'emcp_nand': 'eMMC 16GB',
        }))

    def test_dead_falso_quando_rejeicao_e_por_capacidade(self):
        """eMMC pequeno é rejeitado por CAPACIDADE, não por geração → not dead."""
        self.assertFalse(self._dead({'chip_type': 'eMMC', 'capacity': '2GB'}))

    def test_dead_falso_para_chip_moderno(self):
        self.assertFalse(self._dead({
            'is_emcp': True, 'chip_type': 'eMCP',
            'emcp_ram': 'LPDDR4 3GB', 'emcp_nand': 'eMMC 5.1 32GB',
        }))
