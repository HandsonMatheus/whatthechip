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


class FixKnownPartsEntriesTests(SimpleTestCase):
    """
    Guarda de CI contra reintrodução de campos removidos nas entradas curadas do
    fix_known_parts. Um `create_defaults` com uma chave que não é campo do modelo
    (ex.: o 'status' removido em jun/2026) faz KnownPart(**defaults) estourar
    TypeError e a criação do chip falhar. Este teste pega isso no CI, antes de ir
    pro ar — para qualquer marca que siga um template antigo.
    """

    def test_create_defaults_sem_campos_invalidos(self):
        from chips.management.commands.fix_known_parts import CORRECTIONS
        from chips.models import KnownPart
        valid = {f.name for f in KnownPart._meta.get_fields()} | {"brand_name"}
        offenders = []
        for e in CORRECTIONS:
            pn = e.get("pn", "?")
            for k in (e.get("create_defaults") or {}):
                if k not in valid:
                    offenders.append(f"{pn}: create_defaults['{k}']")
        self.assertEqual(
            offenders, [],
            f"Campos inválidos em create_defaults (modelo não tem mais esses campos): {offenders}",
        )


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


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 1B — catalog_version + cache por versão (auto-invalidação, sem restart)
# ═══════════════════════════════════════════════════════════════════════════════

class CatalogVersionTests(TestCase):
    """Prova que mudar a gramática sobe o carimbo e o engine recarrega SOZINHO —
    sem `clear_engine_cache()` manual nem reinício (acaba a regra de ouro #3)."""

    def test_criar_familia_sobe_versao_e_recarrega_cache(self):
        from chips.models import Brand, ChipFamily, CatalogVersion
        from chips.engine import _get_all_families, _catalog_version, clear_engine_cache

        clear_engine_cache()
        brand = Brand.objects.create(name="TesteCV", code="TCV")
        v0 = _catalog_version()
        n0 = len(_get_all_families())          # popula o cache na versão v0

        # Criar uma família dispara o sinal post_save → CatalogVersion.bump()
        ChipFamily.objects.create(brand=brand, prefix="ZZZQ", chip_type="eMMC")

        v1 = _catalog_version()
        self.assertGreater(v1, v0, "o sinal deveria ter subido o catalog_version")

        # SEM clear manual: a nova versão é cache-miss → recarrega do banco
        n1 = len(_get_all_families())
        self.assertEqual(n1, n0 + 1, "a família nova deve aparecer sem restart")

    def test_bump_e_current_sao_consistentes(self):
        from chips.models import CatalogVersion
        a = CatalogVersion.current()
        b = CatalogVersion.bump()
        self.assertEqual(b, a + 1)
        self.assertEqual(CatalogVersion.current(), b)


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 1A — normalize_pn + busca por part_number_norm (acaba o PN não-encontrado)
# ═══════════════════════════════════════════════════════════════════════════════

class NormalizePnTests(SimpleTestCase):
    def test_remove_separadores_e_maiuscula(self):
        from chips.normalize import normalize_pn
        self.assertEqual(normalize_pn("mt29c4g48-5 it:a"), "MT29C4G485ITA")
        self.assertEqual(normalize_pn("K4B4G1646D-BYK0"), "K4B4G1646DBYK0")
        self.assertEqual(normalize_pn("MT40A1G16KD-062E ES:D"), "MT40A1G16KD062EESD")
        self.assertEqual(normalize_pn(""), "")
        self.assertEqual(normalize_pn(None), "")


class PartNumberNormLookupTests(TestCase):
    def test_save_preenche_norm(self):
        from chips.models import Brand, KnownPart
        b = Brand.objects.create(name="T", code="T")
        kp = KnownPart.objects.create(brand=b, part_number="ZZ99X-1 IT:A",
                                      chip_type="eMMC", capacity="16GB", confidence="confirmed")
        self.assertEqual(kp.part_number_norm, "ZZ99X1ITA")

    def test_busca_resolve_pn_com_separador(self):
        """Um PN salvo COM separador (`-`/espaço/`:`) é encontrado mesmo digitado
        sem eles — o bug que deixava ~1908 PNs em 'tipo vazio' na bancada."""
        from chips.models import Brand, KnownPart
        from chips.engine import classify, clear_engine_cache
        clear_engine_cache()
        b = Brand.objects.create(name="T", code="T")
        KnownPart.objects.create(brand=b, part_number="ZZ99X-1 IT:A",
                                 chip_type="eMMC", capacity="16GB", confidence="confirmed")
        r = classify("zz99x1ita") or {}
        self.assertTrue(r.get("known"), "PN com separador deveria resolver via part_number_norm")
        self.assertEqual(r.get("chip_type"), "eMMC")

    def test_constraint_bloqueia_norma_duplicada(self):
        """1A-p2: a UniqueConstraint(part_number_norm) impede dois PNs que normalizam igual."""
        from chips.models import Brand, KnownPart
        from django.db import IntegrityError, transaction
        b = Brand.objects.create(name="T", code="T")
        KnownPart.objects.create(brand=b, part_number="AB12-CD", chip_type="eMMC", confidence="confirmed")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KnownPart.objects.create(brand=b, part_number="AB12CD", chip_type="eMMC", confidence="confirmed")

    def test_pick_best_known_escolhe_o_melhor(self):
        """1A: _pick_best_known prefere chip_type preenchido (mesmo com confiança menor)."""
        from chips.models import Brand, KnownPart
        from chips.engine import _pick_best_known
        b = Brand.objects.create(name="T", code="T")
        orfao = KnownPart.objects.create(brand=b, part_number="P1", chip_type="", confidence="confirmed")
        cheio = KnownPart.objects.create(brand=b, part_number="P2", chip_type="eMMC", confidence="distributor")
        self.assertEqual(_pick_best_known([orfao, cheio]).pk, cheio.pk)

    def test_salvar_knownpart_sobe_catalog_version(self):
        """Passo 2: criar/editar um KnownPart sobe o catalog_version (→ estoque defasa)."""
        from chips.models import Brand, KnownPart, CatalogVersion
        b = Brand.objects.create(name="T", code="T")
        v0 = CatalogVersion.current()
        KnownPart.objects.create(brand=b, part_number="VERTEST1", chip_type="eMMC", confidence="confirmed")
        self.assertGreater(CatalogVersion.current(), v0)


class DeployCatalogTests(TestCase):
    """Passo 3: deploy_catalog encadeia os comandos de catálogo (na ordem) e sobe
    o catalog_version no fim. Mocka call_command — não roda os populate_* de verdade."""

    @patch('chips.management.commands.deploy_catalog.call_command')
    def test_dry_run_nao_grava_nem_sobe_versao(self, mock_cc):
        from chips.models import CatalogVersion
        from django.core.management import call_command
        v0 = CatalogVersion.current()
        call_command('deploy_catalog')                       # dry-run (sem --commit)
        chamados = [c.args[0] for c in mock_cc.call_args_list]
        self.assertIn('populate_samsung', chamados)
        # add_chip_families NÃO tem --dry-run → é PULADO no dry-run
        self.assertNotIn('add_chip_families', chamados)
        # todo sub-comando chamado no dry-run recebe dry_run=True
        for c in mock_cc.call_args_list:
            self.assertTrue(c.kwargs.get('dry_run'), f"{c.args[0]} sem dry_run")
        self.assertEqual(CatalogVersion.current(), v0)        # NÃO sobe a versão

    @patch('chips.management.commands.deploy_catalog.call_command')
    def test_commit_roda_tudo_em_ordem_e_sobe_versao(self, mock_cc):
        from chips.models import CatalogVersion
        from django.core.management import call_command
        v0 = CatalogVersion.current()
        call_command('deploy_catalog', commit=True)
        chamados = [c.args[0] for c in mock_cc.call_args_list]
        self.assertEqual(chamados[0], 'populate_samsung')     # ordem canônica
        self.assertEqual(chamados[-1], 'fix_known_parts')
        self.assertIn('add_chip_families', chamados)          # roda no commit
        kw = {c.args[0]: c.kwargs for c in mock_cc.call_args_list}
        self.assertTrue(kw['populate_samsung'].get('overwrite'))
        self.assertTrue(kw['import_samsung_psg'].get('all'))
        self.assertEqual(CatalogVersion.current(), v0 + 1)    # sobe 1x no fim

    @patch('chips.management.commands.deploy_catalog.call_command')
    def test_nao_inclui_import_micron_catalog(self, mock_cc):
        """CSVs *_full-catalog.csv NÃO são versionados → import_micron_catalog
        quebraria no Render; não pode entrar no encadeamento."""
        from django.core.management import call_command
        call_command('deploy_catalog', commit=True)
        chamados = [c.args[0] for c in mock_cc.call_args_list]
        self.assertNotIn('import_micron_catalog', chamados)

    @patch('chips.management.commands.deploy_catalog.call_command')
    def test_marcas_migradas_via_load_brands(self, mock_cc):
        """Marcas migradas p/ YAML (passo 4): o deploy usa load_brands, não os
        populate_* aposentados (PieceMakers, GigaDevice)."""
        from django.core.management import call_command
        call_command('deploy_catalog', commit=True)
        chamados = [c.args[0] for c in mock_cc.call_args_list]
        for pop in ('populate_piecemakers', 'populate_gigadevice', 'populate_rayson',
                    'populate_kingston', 'populate_sandisk', 'populate_micron_mcp',
                    'populate_toshiba', 'populate_hynix'):
            self.assertNotIn(pop, chamados)                    # aposentados
        # cada marca migrada passa por load_brands, gravando (commit=True)
        brands_load = [c.kwargs.get('brand') for c in mock_cc.call_args_list
                       if c.args[0] == 'load_brands']
        for marca in ('piecemakers', 'gigadevice', 'rayson', 'kingston', 'sandisk', 'micron',
                      'toshiba', 'kioxia', 'hynix'):
            self.assertIn(marca, brands_load)
        for c in mock_cc.call_args_list:
            if c.args[0] == 'load_brands':
                self.assertTrue(c.kwargs.get('commit'))        # grava de verdade no --commit


class PghistoryTrackingTests(TestCase):
    """Passo 3b: auditoria do catálogo via django-pghistory. As 4 tabelas de
    catálogo têm modelo de evento; no Postgres o gatilho grava um evento por
    mudança (no SQLite o gatilho é no-op, então esse teste é pulado)."""

    def test_existe_event_model_para_cada_tabela_de_catalogo(self):
        from django.apps import apps
        for nome in ("ChipFamilyEvent", "DecodeMapEvent",
                     "KnownPartEvent", "ProfitabilityConfigEvent"):
            self.assertIsNotNone(apps.get_model("chips", nome),
                                 f"{nome} não foi gerado pelo @pghistory.track()")

    def test_editar_knownpart_gera_evento_no_postgres(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("gatilhos pghistory só existem no Postgres (testes usam SQLite)")
        from django.apps import apps
        from chips.models import Brand, KnownPart
        Event = apps.get_model("chips", "KnownPartEvent")
        b = Brand.objects.create(name="PG", code="PG")
        kp = KnownPart.objects.create(brand=b, part_number="PGEVT1",
                                      chip_type="eMMC", confidence="manual")
        antes = Event.objects.filter(pgh_obj_id=kp.pk).count()
        kp.chip_type = "UFS"
        kp.save()
        self.assertGreater(Event.objects.filter(pgh_obj_id=kp.pk).count(), antes)


_FAM_FIELDS = [
    "chip_type", "subtype", "interface", "is_emcp", "active", "priority", "pn_length",
    "decode_cap_pos", "decode_cap_len", "decode_cap_map", "decode_gen_pos",
    "decode_gen_map", "decode_gen_len", "decode_density_type", "suffix_rules",
    "tip", "reasoning",
]


def _ident(pn):
    """Resumo de identificação de um PN pelo engine: (chip_type, capacity,
    emcp_nand, emcp_ram, dram_density, rentabilidade). É o que o teste de 'TODOS
    os PNs' congela — a marca tem que identificar cada PN sempre igual. Inclui os
    campos de eMCP (NAND+RAM) p/ cobrir marcas como a Kingston."""
    from chips.engine import classify, assess_profitability
    r = classify(pn) or {}
    return (r.get("chip_type") or "", r.get("capacity") or "", r.get("emcp_nand") or "",
            r.get("emcp_ram") or "", r.get("dram_density") or "", assess_profitability(r))


def _carrega_marca_e_confere_fidelidade(tc, slug):
    """Carrega chips/knowledge/<slug>.yaml via load_brands e confere que cada
    família/mapa do YAML virou o registro certo no banco (fidelidade YAML→banco)."""
    import os
    import yaml
    from django.conf import settings
    from django.core.management import call_command
    from chips.knowledge.schema import BrandFile
    from chips.models import Brand, ChipFamily, DecodeMap
    path = os.path.join(settings.BASE_DIR, "chips", "knowledge", f"{slug}.yaml")
    with open(path, encoding="utf-8") as fh:
        spec = BrandFile(**yaml.safe_load(fh))
    call_command("load_brands", "--brand", slug, "--commit", verbosity=0)

    b = Brand.objects.get(code=spec.brand.code)
    tc.assertEqual((b.name, b.notes), (spec.brand.name, spec.brand.notes))
    tc.assertEqual(ChipFamily.objects.filter(brand=b).count(), len(spec.families))
    for fs in spec.families:
        fam = ChipFamily.objects.get(prefix=fs.prefix)
        tc.assertEqual(fam.brand_id, b.id)
        for campo in _FAM_FIELDS:
            tc.assertEqual(getattr(fam, campo), getattr(fs, campo), f"{slug}:{fs.prefix}.{campo}")
    total = sum(len(v) for v in spec.maps.values())
    tc.assertEqual(DecodeMap.objects.filter(brand=b).count(), total)
    for map_name, entries in spec.maps.items():
        for e in entries:
            dm = DecodeMap.objects.get(brand=b, map_name=map_name, char_key=e.char_key)
            tc.assertEqual((dm.val_primary, dm.val_secondary), (e.val_primary, e.val_secondary))


# ── Goldens de id: (chip_type, capacity, emcp_nand, emcp_ram, dram_density, rentabilidade) ──
# Congelados da gramática validada (populate ANTES de aposentá-la; conferidos vs docs). Cada marca
# deve identificar TODOS os seus PNs conhecidos SEMPRE assim (regra do dono, 2026-06-30).
_PMK_GOLDEN = {
    "PMF510816DBR":     ("DDR3",  "128MB", "", "", "", "NÃO RENTÁVEL"),  # 1Gb/die → < 2Gb → descarta
    "PMF511808EBR":     ("DDR3",  "256MB", "", "", "", "RENTÁVEL"),      # 2Gb x8
    "PMF511816EBR":     ("DDR3",  "256MB", "", "", "", "RENTÁVEL"),      # 2Gb x16 (KnownPart em prod)
    "PMF512816CBR":     ("DDR3",  "512MB", "", "", "", "RENTÁVEL"),      # 4Gb
    "PMF411816EBR":     ("DDR3L", "256MB", "", "", "", "RENTÁVEL"),      # DDR3L 2Gb (=DDR3)
    "PMA212508ABR":     ("DDR4",  "",      "", "", "", "INDETERMINADO"), # DDR4 s/ decode → KnownPart resolve
    "PMA212816ABR":     ("DDR4",  "",      "", "", "", "INDETERMINADO"),
    "PMF511816EBRKADN": ("DDR3",  "256MB", "", "", "", "RENTÁVEL"),      # variante -KADN do 2Gb
}
_GIGA_GOLDEN = {
    "GD5F1GQ4UBYIG": ("NAND Flash", "128MB", "", "", "", "NÃO RENTÁVEL"),  # SPI NAND 1Gb
    "GD5F1GQ5UEYIG": ("NAND Flash", "128MB", "", "", "", "NÃO RENTÁVEL"),
    "GD5F2GQ4UBYIG": ("NAND Flash", "256MB", "", "", "", "NÃO RENTÁVEL"),  # 2Gb
    "GD5F2GQ5UEYIG": ("NAND Flash", "256MB", "", "", "", "NÃO RENTÁVEL"),
    "GD5F4GQ4UBYIG": ("NAND Flash", "512MB", "", "", "", "NÃO RENTÁVEL"),  # 4Gb
    "GD5F8GQ4UBYIG": ("NAND Flash", "1GB",   "", "", "", "NÃO RENTÁVEL"),  # 8Gb
    "GDQ26FAA":   ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GDQ2BFAA":   ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GDQ2BFAACE": ("DDR4", "", "", "", "", "INDETERMINADO"),  # KnownParts em prod
    "GDQ2BFAACJ": ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GDQ2BFAACQ": ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GDQ2BFAAWJ": ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GDQ2BFAAWQ": ("DDR4", "", "", "", "", "INDETERMINADO"),
    "GD25Q128":     ("NOR Flash", "", "", "", "", "NÃO RENTÁVEL"),  # SPI NOR (geração morta p/ reciclagem)
    "GD25Q128ESIG": ("NOR Flash", "", "", "", "", "NÃO RENTÁVEL"),
    "GD25Q64CSIG":  ("NOR Flash", "", "", "", "", "NÃO RENTÁVEL"),
}
_RAY_GOLDEN = {
    "RS1G32LF4D2BDS":   ("LPDDR4", "4GB", "", "", "", "RENTÁVEL"),
    "RS1G32LO4D2BDS":   ("LPDDR4", "4GB", "", "", "", "RENTÁVEL"),
    "RS1G32LV4D2BDS":   ("LPDDR4", "4GB", "", "", "", "RENTÁVEL"),
    "RS256M32LD3D1LMZ": ("LPDDR3", "1GB", "", "", "", "NÃO RENTÁVEL"),  # 1GB LPDDR3 < limiar
    "RS256M32LZ4":      ("LPDDR4", "1GB", "", "", "", "RENTÁVEL"),      # 1GB LPDDR4 (geração nova)
    "RS2G32LF4D4BDT":   ("LPDDR4", "8GB", "", "", "", "RENTÁVEL"),
    "RS2G32LV4D4BDT":   ("LPDDR4", "8GB", "", "", "", "RENTÁVEL"),
    "RS512M32LD3D2LMZ": ("LPDDR3", "2GB", "", "", "", "RENTÁVEL"),
    "RS512M32LM4D2BDS": ("LPDDR4", "2GB", "", "", "", "RENTÁVEL"),
    "RS512M32LO4D1BDS": ("LPDDR4", "2GB", "", "", "", "RENTÁVEL"),
    "RS70B08G3S03F":    ("eMMC", "8GB",   "", "", "", "RENTÁVEL"),
    "RS70B08G4S":       ("eMMC", "8GB",   "", "", "", "RENTÁVEL"),
    "RS70B16G4S06F":    ("eMMC", "16GB",  "", "", "", "RENTÁVEL"),
    "RS70B16G4S10F":    ("eMMC", "16GB",  "", "", "", "RENTÁVEL"),
    "RS70B16G4S15G":    ("eMMC", "16GB",  "", "", "", "RENTÁVEL"),
    "RS70B32G4S15G":    ("eMMC", "32GB",  "", "", "", "RENTÁVEL"),
    "RS70B64G4S16G":    ("eMMC", "64GB",  "", "", "", "RENTÁVEL"),
    "RS70BT7G4S16G":    ("eMMC", "128GB", "", "", "", "RENTÁVEL"),
    "RS512M32LO4":      ("LPDDR4", "2GB", "", "", "", "RENTÁVEL"),  # KnownPart em prod
    "RS512M32LZ4":      ("LPDDR4", "2GB", "", "", "", "RENTÁVEL"),  # KnownPart em prod
}
_KST_GOLDEN = {  # eMCP: specs em emcp_nand/emcp_ram; rentab pela RAM (512MB→descarta, 1GB+→rentável)
    "04EMCP04-NL2DM627": ("eMCP", "", "eMMC 5.0 4GB",  "LPDDR3 512MB", "", "NÃO RENTÁVEL"),
    "04EMCP04-NL3DM627": ("eMCP", "", "eMMC 5.0 4GB",  "LPDDR3 512MB", "", "NÃO RENTÁVEL"),
    "08EMCP04-NL2DT227": ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 512MB", "", "NÃO RENTÁVEL"),
    "08EMCP04-NL3DT227": ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 512MB", "", "NÃO RENTÁVEL"),
    "08EMCP08-NL2DT227": ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 1GB",   "", "RENTÁVEL"),
    "08EMCP08-NL3DT227": ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 1GB",   "", "RENTÁVEL"),
    "16EMCP08-NL3DTB28": ("eMCP", "", "eMMC 5.1 16GB", "LPDDR3 1GB",   "", "RENTÁVEL"),
    "16EMCP16-EL3GTB29": ("eMCP", "", "eMMC 5.1 16GB", "LPDDR3 2GB",   "", "RENTÁVEL"),
    "32EMCP16-EL3GTB29": ("eMCP", "", "eMMC 5.1 32GB", "LPDDR3 2GB",   "", "RENTÁVEL"),
    "32EMCP16-NL3DTB29": ("eMCP", "", "eMMC 5.1 32GB", "LPDDR3 2GB",   "", "RENTÁVEL"),
    "32EMCP24-EL3JTB29": ("eMCP", "", "eMMC 5.1 32GB", "LPDDR3 3GB",   "", "RENTÁVEL"),
    "64EMCP24-EL3JTA29": ("eMCP", "", "eMMC 5.1 64GB", "LPDDR3 3GB",   "", "RENTÁVEL"),
    "64EMCP32-EL3HTA29": ("eMCP", "", "eMMC 5.1 64GB", "LPDDR3 4GB",   "", "RENTÁVEL"),
    "08EMCP08NL3DT227":  ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 1GB",   "", "RENTÁVEL"),  # forma normalizada
    "16EMCP08NL3DTB28":  ("eMCP", "", "eMMC 5.1 16GB", "LPDDR3 1GB",   "", "RENTÁVEL"),
}
_SD_GOLDEN = {  # SanDisk: famílias MAGRAS — chip_type por prefixo; capacidade vem das KnownParts,
    # então a gramática sozinha dá INDETERMINADO. O teste congela o TIPO por família.
    "SD5DH24A4G":  ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SD7DP24C4G":  ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDADA4DR64G": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                    "tipo 'A' — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),
    "SDADB48K16G": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                    "tipo 'A' — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),
    "SDIN5C116G":  ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDIN5C14G":   ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDIN5C18G":   ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDINBAG":     ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDINBDG4":    ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDINBEG4":    ("eMMC", "", "", "", "", "INDETERMINADO"),
    "SDINDDH4":    ("UFS", "", "", "", "", "INDETERMINADO"),
    "SDINDDH6":    ("UFS", "", "", "", "", "INDETERMINADO"),
    "SDINEDK":     ("UFS", "", "", "", "", "INDETERMINADO"),
    "SDINFDK4":    ("UFS", "", "", "", "", "INDETERMINADO"),
    "SDINFDO4":    ("UFS", "", "", "", "", "INDETERMINADO"),
    "SDINFDQ6":    ("UFS", "", "", "", "", "INDETERMINADO"),
}
_MIC_GOLDEN = {  # Micron: gramática do populate_micron_mcp (MCP) + add_chip_families (DDR/LPDDR/NAND/eMMC).
    # DDR4/DDR3L são magras (cap vem das KnownParts → INDETERMINADO); LPDDR (MT52L/MT53) decodifica capacidade.
    "MT40A1G16Z42BWC1":     ("DDR4",  "",      "", "", "",               "INDETERMINADO"),
    "MT40A4G4Z42BWC1":      ("DDR4",  "",      "", "", "",               "INDETERMINADO"),
    "MT41K64M16TW-107":     ("DDR3L", "",      "", "", "",               "INDETERMINADO"),
    "MT52L1G32D4PG-107":    ("LPDDR3",  "4GB",   "", "", "32Gb total [✓]", "RENTÁVEL"),
    "MT53B512M64D4TX":      ("LPDDR4",  "4GB",   "", "", "32Gb total [✓]", "RENTÁVEL"),
    "MT53B1024M32D4NQ-062": ("LPDDR4",  "4GB",   "", "", "32Gb total [✓]", "RENTÁVEL"),
    "MT53E128M16D1DS-046":  ("LPDDR4X", "256MB", "", "", "2Gb total [✓]",  "NÃO RENTÁVEL"),  # fix MT53 dies
    "MT53D1024M32D4DT-046": ("LPDDR4",  "4GB",   "", "", "32Gb total [✓]", "RENTÁVEL"),
    "MTFC128GAPALNS-AIT":   ("eMMC",  "",      "", "", "",               "INDETERMINADO"),
    "MT29TZZZ8D5":          ("eMCP", "", "eMMC 5.0 8GB",  "LPDDR3 1GB", "", "RENTÁVEL"),
    "MT29VZZZAD8":          ("eMCP", "", "eMMC 5.1 64GB", "LPDDR4 4GB", "", "RENTÁVEL"),
    "MT30AZZZBD9":          ("uMCP", "", "UFS 3.1 128GB", "LPDDR5 6GB", "", "RENTÁVEL"),
    "MT29PZZZ4D4BKESK":     ("eMCP", "", "eMMC ⚠ cap. não mapeada", "LPDDR ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
}
_TK_GOLDEN = {  # Toshiba + Kioxia carregadas JUNTAS (THGBMFG/THGBMHG=Kioxia são prefixos + longos que
    # THGBM=Toshiba → a classificação depende das duas). Magras (eMMC/eMCP/UFS por prefixo, INDETERMINADO),
    # exceto THGBM (Toshiba) que decodifica capacidade.
    "THGBMBG7D2KBAIL": ("eMMC", "16GB", "", "", "", "RENTÁVEL"),   # Toshiba THGBM (decodifica cap)
    "TYC0FH121638RA":  ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "tipo 'C' — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),  # Toshiba TYC
    "TYD0FH221627RA":  ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR4X ⚠ cap. não mapeada", "", "INDETERMINADO"),  # Toshiba TYD
    "THGBMFG7C2LBAIL": ("eMMC", "", "", "", "", "INDETERMINADO"),  # Kioxia THGBMFG
    "THGBMHG8C4LBAIR": ("eMMC", "", "", "", "", "INDETERMINADO"),  # Kioxia THGBMHG
    "THGAF8G8T23BAIL": ("UFS",  "", "", "", "", "INDETERMINADO"),  # Kioxia THGAF
    "THGAMVG7T13BAIL": ("eMMC", "", "", "", "", "INDETERMINADO"),  # Kioxia THGAM
    "THGJFPT0E18BAIP": ("UFS",  "", "", "", "", "INDETERMINADO"),  # Kioxia THGJF
}
_HYX_GOLDEN = {  # SK Hynix: 36 famílias (populate_hynix + add_chip_families). Cobre DDR1-5, LPDDR2-4X, eMMC, eMCP, UFS.
    "H26M74002HMR":      ("eMMC", "64GB",  "", "", "", "RENTÁVEL"),
    "H26T87001CMR":      ("eMMC", "128GB", "", "", "", "RENTÁVEL"),
    "H28U88301AMR":      ("UFS",  "128GB", "", "", "", "RENTÁVEL"),
    "H54GE6CYRB":        ("LPDDR4X", "4GB", "", "", "", "RENTÁVEL"),
    "H5AN8G8NAFR-UHC":   ("DDR4", "1GB",  "", "", "", "RENTÁVEL"),
    "H5AN8G8NAFR-VKC":   ("DDR4", "1GB",  "", "", "", "RENTÁVEL"),
    "H5CG48MEBDX014N":   ("DDR5", "2GB",  "", "", "", "RENTÁVEL"),
    "H5PS1G83EFR-S6C":   ("DDR2", "128MB", "", "", "", "NÃO RENTÁVEL"),
    "H5TC4G83CFR-PBA":   ("DDR3L", "512MB", "", "", "", "RENTÁVEL"),
    "H5TQ2G63GFR":       ("DDR3", "256MB", "", "", "", "RENTÁVEL"),
    "H9CCNNNCLTML":      ("LPDDR3", "4GB", "", "", "", "RENTÁVEL"),
    "H9CKNNNBJTMP":      ("LPDDR3", "2GB", "", "", "", "RENTÁVEL"),
    "H9DA4GH2GJAM":      ("eMCP", "", "eMMC 4.x 4GB", "LPDDR1 256MB", "", "NÃO RENTÁVEL"),
    "H9DP32A4JJBC":      ("eMCP", "", "eMMC 4GB", "LPDDR2 512MB", "", "NÃO RENTÁVEL"),
    "H9HCNNNCPMAL":      ("LPDDR4X", "4GB", "", "", "", "RENTÁVEL"),
    "H9HCNNNECMML":      ("LPDDR4X", "6GB", "", "", "", "RENTÁVEL"),
    "H9HP16AECMMD":      ("eMCP", "", "eMMC 5.1 128GB", "LPDDR4X 6GB", "", "RENTÁVEL"),
    "H9TKNNN8JDAP":      ("LPDDR2", "1GB", "", "", "", "NÃO RENTÁVEL"),
    "H9TQ64A8GTCC":      ("eMCP", "", "eMMC 5.x 8GB", "LPDDR3 1GB", "", "RENTÁVEL"),
    "HN8T05BZGR":        ("UFS", "128GB", "", "", "", "RENTÁVEL"),
    "HY5DU281622ET-25":  ("DDR1", "16MB", "", "", "", "NÃO RENTÁVEL"),
    "HY5PS121621CFP-25": ("DDR2", "64MB", "", "", "", "NÃO RENTÁVEL"),
}


class LoadBrandsPiecemakersTests(TestCase):
    """Passo 4: PieceMakers carregada de chips/knowledge/piecemakers.yaml. Fidelidade
    (YAML→banco) + identificação de TODOS os PNs conhecidos. (Equivalência ao antigo
    populate_piecemakers já provada em prod: characterize --diff IDÊNTICO nos 6549 PNs.)"""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "piecemakers")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "piecemakers", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _PMK_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")

    def test_dry_run_nao_grava(self):
        from django.core.management import call_command
        from chips.models import Brand
        call_command("load_brands", "--brand", "piecemakers", verbosity=0)  # sem --commit
        self.assertFalse(Brand.objects.filter(code="PMK").exists())

    def test_load_brands_sobe_catalog_version(self):
        from django.core.management import call_command
        from chips.models import CatalogVersion
        v0 = CatalogVersion.current()
        call_command("load_brands", "--brand", "piecemakers", "--commit", verbosity=0)
        self.assertGreater(CatalogVersion.current(), v0)


class GigaDeviceLoadBrandsTests(TestCase):
    """Passo 4: GigaDevice migrada p/ YAML. Fidelidade + identificação de TODOS os PNs
    conhecidos (golden capturado da gramática populate_gigadevice antes de aposentá-la)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "gigadevice")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "gigadevice", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _GIGA_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class RaysonLoadBrandsTests(TestCase):
    """Passo 4: Rayson migrada p/ YAML (LPDDR3/LPDDR4 + eMMC). Fidelidade +
    identificação de TODOS os PNs conhecidos (golden da gramática populate_rayson)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "rayson")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "rayson", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _RAY_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class KingstonLoadBrandsTests(TestCase):
    """Passo 4: Kingston migrada p/ YAML (5 famílias eMCP: 04/08/16/32/64). Fidelidade +
    identificação de TODOS os PNs eMCP conhecidos (golden da gramática populate_kingston;
    NAND+RAM decodificados, rentabilidade pela RAM). O KnownPart NAND KF98G16Q4X fica fora
    (não tem família — é resolvido pelo banco em prod, não pela gramática)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "kingston")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "kingston", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _KST_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class SanDiskLoadBrandsTests(TestCase):
    """Passo 4: SanDisk migrada p/ YAML (11 famílias MAGRAS — eMMC/eMCP/UFS por prefixo,
    sem decode de capacidade; a capacidade vem das KnownParts). Fidelidade + identificação
    do TIPO de todos os PNs conhecidos (golden da gramática populate_sandisk)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "sandisk")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "sandisk", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _SD_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class MicronLoadBrandsTests(TestCase):
    """Passo 4: Micron migrada p/ YAML — 13 famílias (3 MCP do populate_micron_mcp +
    10 do add_chip_families: DDR/LPDDR/NAND/eMMC). Fidelidade + identificação de todos
    os PNs conhecidos (golden da gramática atual: LPDDR/MCP decodificam, DDR magras)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "micron")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "micron", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _MIC_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class ToshibaKioxiaLoadBrandsTests(TestCase):
    """Passo 4: populate_toshiba cria DUAS marcas — Toshiba (THGBM/TYC/TYD) e Kioxia
    (a memória virou Kioxia). Fidelidade de cada YAML + identificação de todos os PNs
    com AS DUAS carregadas (THGBMFG/HG=Kioxia são prefixos + longos que THGBM=Toshiba)."""

    def test_toshiba_yaml_fiel(self):
        _carrega_marca_e_confere_fidelidade(self, "toshiba")

    def test_kioxia_yaml_fiel(self):
        _carrega_marca_e_confere_fidelidade(self, "kioxia")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "toshiba", "--commit", verbosity=0)
        call_command("load_brands", "--brand", "kioxia", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _TK_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class HynixLoadBrandsTests(TestCase):
    """Passo 4: SK Hynix migrada p/ YAML — 36 famílias (populate_hynix + add_chip_families).
    Fidelidade + identificação de todos os PNs conhecidos (golden cobre DDR1-5, LPDDR2-4X,
    eMMC, eMCP, UFS; 14 famílias sem KnownPart ficam provadas só pela fidelidade)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "hynix")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "hynix", "--commit", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _HYX_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class KnowledgeSchemaTests(TestCase):
    """Passo 4: o portão Pydantic — as regras de ouro são validadores executáveis."""

    def test_density_type_e_cap_map_juntos_sao_rejeitados(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import FamilySpec
        with self.assertRaises(ValidationError):
            FamilySpec(prefix="K4F", chip_type="RAM",
                       decode_density_type="pc", decode_cap_map="ALGUM_MAPA")

    def test_familia_km_com_digito_exige_gen_pos_nulo(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import FamilySpec
        with self.assertRaises(ValidationError):
            FamilySpec(prefix="KM4", chip_type="eMCP", decode_gen_pos=3)
        # sem gen_pos passa
        FamilySpec(prefix="KM4", chip_type="eMCP")

    def test_confidence_fora_do_vocabulario_e_rejeitado(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import KnownPartSpec
        with self.assertRaises(ValidationError):
            KnownPartSpec(part_number="X", confidence="ai_guess")
        KnownPartSpec(part_number="X", confidence="confirmed")  # válido

    def test_familia_referenciando_mapa_inexistente_e_rejeitada(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import BrandFile
        with self.assertRaises(ValidationError):
            BrandFile(brand={"name": "X", "code": "X"},
                      maps={},
                      families=[{"prefix": "PX", "chip_type": "DDR3",
                                 "decode_cap_map": "NAO_EXISTE"}])

    def test_campo_desconhecido_e_rejeitado(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import FamilySpec
        with self.assertRaises(ValidationError):
            FamilySpec(prefix="PX", chip_type="DDR3", decode_capp_pos=4)  # typo de propósito

    # ── PORTÃO DA CONVENÇÃO (passo 4): normaliza o mecânico, rejeita o ambíguo ──

    def test_chip_type_generico_com_subtype_vira_geracao(self):
        from chips.knowledge.schema import FamilySpec
        f = FamilySpec(prefix="NT5CC", chip_type="RAM", subtype="DDR3 SDRAM")
        self.assertEqual(f.chip_type, "DDR3")   # 'RAM' + 'DDR3 SDRAM' → 'DDR3'
        self.assertEqual(f.subtype, "DDR3")     # subtype limpo

    def test_subtype_verboso_e_limpo(self):
        from chips.knowledge.schema import FamilySpec
        f = FamilySpec(prefix="H9TQ", chip_type="eMCP", subtype="LPDDR3 + eMMC")
        self.assertEqual(f.subtype, "LPDDR3")   # sem '+ eMMC'
        self.assertEqual(f.chip_type, "eMCP")   # gerenciada: chip_type manda

    def test_interface_com_geracao_e_limpa(self):
        from chips.knowledge.schema import FamilySpec
        f = FamilySpec(prefix="H5AN", chip_type="DDR4", subtype="DDR4", interface="DDR4")
        self.assertEqual(f.interface, "")       # interface não carrega geração
        g = FamilySpec(prefix="K4B", chip_type="DDR3", interface="x16")
        self.assertEqual(g.interface, "x16")    # largura de barramento fica

    def test_ativa_com_tipo_generico_irreducivel_e_rejeitada(self):
        from pydantic import ValidationError
        from chips.knowledge.schema import FamilySpec
        with self.assertRaises(ValidationError):
            FamilySpec(prefix="KVR", chip_type="RAM", subtype="DDR", active=True)  # multi-geração

    def test_inativa_com_tipo_generico_e_permitida(self):
        from chips.knowledge.schema import FamilySpec
        f = FamilySpec(prefix="KVR", chip_type="RAM", subtype="DDR", active=False)  # módulo bogus
        self.assertFalse(f.active)              # soft-delete passa (não classifica)
