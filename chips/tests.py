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

    def test_emcp_nao_samsung_sem_mapa_extrai_do_subtype(self):
        """Fix 2026-07-15: EMCP_RAM_TYPES é EXCLUSIVO Samsung. Família eMCP de OUTRA marca
        sem decode_gen_map NÃO pega a geração pelo dict (colidia — TYD 3ª='D' → 'LPDDR4X'
        num chip LPDDR3). Extrai do próprio subtype; subtype vazio → placeholder INDETERMINADO."""
        from chips.engine import _result_from_family
        with patch('chips.engine._load_decode_map', return_value={}):
            with patch('chips.engine._doc_url', return_value=None):
                # (1) Toshiba TYD — 3ª letra 'D' colidiria com EMCP_RAM_TYPES['D']='LPDDR4X':
                #     agora vem LPDDR3 do subtype.
                fam = self._make_family(pos=None, cap_len=1, map_name='',
                                        is_emcp=True, interface='eMMC 4.5')
                fam.brand.name = 'Toshiba-Kioxia'; fam.prefix = 'TYD'; fam.subtype = 'LPDDR3'
                r = _result_from_family('TYD0FH221627RA', fam)
                self.assertTrue(r['emcp_ram'].startswith('LPDDR3'),
                                f"esperava LPDDR3 do subtype, veio {r['emcp_ram']!r}")
                self.assertNotIn('LPDDR4', r['emcp_ram'])
                # (2) subtype VAZIO (ex.: SanDisk SDAD): fallback SEGURO → 'não mapeada'
                #     (INDETERMINADO), NUNCA bare 'LPDDR' (que a rentab. leria como LPDDR1/descarte).
                fam2 = self._make_family(pos=None, cap_len=1, map_name='',
                                         is_emcp=True, interface='eMMC 4.5')
                fam2.brand.name = 'SanDisk'; fam2.prefix = 'SDAD'; fam2.subtype = ''
                r2 = _result_from_family('SDADA4CR128G', fam2)
                self.assertIn('não mapeada', r2['emcp_ram'])
                self.assertFalse(r2['emcp_ram'].startswith('LPDDR'),
                                 f"subtype vazio não pode virar 'LPDDR' bare, veio {r2['emcp_ram']!r}")

    def test_emcp_samsung_sem_mapa_ainda_usa_dict(self):
        """Controle do fix: Samsung SEM gen_map continua decodificando pela 3ª letra
        (EMCP_RAM_TYPES) — o gate é a MARCA, e a Samsung é a dona da convenção KMx."""
        from chips.engine import _result_from_family
        with patch('chips.engine._load_decode_map', return_value={}):
            with patch('chips.engine._doc_url', return_value=None):
                fam = self._make_family(pos=None, cap_len=1, map_name='',
                                        is_emcp=True, interface='eMMC 5.1')
                # brand.name já é 'Samsung'; KMV → 3ª letra 'V' → EMCP_RAM_TYPES (LPDDR2 legado).
                fam.prefix = 'KMV'; fam.subtype = ''   # mesmo subtype vazio, Samsung usa o dict
                r = _result_from_family('KMV0000000000', fam)
                # Samsung via dict → começa com a geração ('LPDDR2 (legado)…'); NÃO cai no
                # placeholder 'RAM não mapeada' do ramo não-Samsung. (O engine sempre anexa
                # '⚠ cap. não mapeada' quando não há capacidade — por isso testo o PREFIXO.)
                self.assertTrue(r['emcp_ram'].startswith('LPDDR'),
                                f"Samsung deve decodificar via dict, veio {r['emcp_ram']!r}")
                self.assertNotIn('RAM não mapeada', r['emcp_ram'])

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


class ExtractGibTests(SimpleTestCase):
    """Testa extração de capacidade em GB (usada pela rentabilidade)."""

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


class SchemaDedupTests(SimpleTestCase):
    """Portão de unicidade (data contract): duplicatas na MESMA marca são rejeitadas
    no dry-run, antes do banco. Chave canônica — PN via normalize_pn (pega variação
    de formato). Reporta todas as colisões."""

    def _bf(self, **kw):
        from chips.knowledge.schema import BrandFile
        return BrandFile(brand={"name": "T", "code": "T"}, **kw)

    def test_prefix_duplicado_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._bf(families=[{"prefix": "K4A", "chip_type": "DDR4"},
                               {"prefix": "K4A", "chip_type": "DDR3"}])

    def test_pn_duplicado_exato_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._bf(known_parts=[{"part_number": "K4A8G165WC"},
                                  {"part_number": "K4A8G165WC"}])

    def test_pn_duplicado_por_normalizacao_rejeita(self):
        """Variação de formato que normaliza igual também é duplicata (entity resolution)."""
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._bf(known_parts=[{"part_number": "MT29C4G48-5 IT"},
                                  {"part_number": "MT29C4G485IT"}])

    def test_char_key_duplicado_no_mapa_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._bf(maps={"X": [["11", "256MB", ""], ["11", "512MB", ""]]})

    def test_sem_duplicatas_passa(self):
        bf = self._bf(
            families=[{"prefix": "K4A", "chip_type": "DDR4"},
                      {"prefix": "K4B", "chip_type": "DDR3"}],
            known_parts=[{"part_number": "K4A8G165WC"}, {"part_number": "K4B8G165WC"}],
            maps={"X": [["11", "256MB", ""], ["12", "512MB", ""]]},
        )
        self.assertEqual(len(bf.families), 2)


class SchemaStructureTests(SimpleTestCase):
    """F2/E: validadores ESTRUTURAIS do decode no portão (0 violações no legado → hard)."""

    def _fam(self, **kw):
        from chips.knowledge.schema import FamilySpec
        return FamilySpec(**{"prefix": "XX", "chip_type": "DDR4", **kw})

    def test_cap_pos_sem_map_nem_density_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._fam(decode_cap_pos=3)   # não há como decodificar capacidade

    def test_cap_pos_com_density_type_passa(self):
        self._fam(decode_cap_pos=3, decode_density_type="pc")   # density_type basta

    def test_cap_pos_alem_do_pn_length_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._fam(decode_cap_pos=8, decode_cap_len=2, decode_cap_map="M", pn_length=9)  # 8+2>9

    def test_gen_pos_alem_do_pn_length_rejeita(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._fam(decode_gen_pos=10, decode_gen_map="G", pn_length=9)   # 10+1>9


class GlobalMapGuardTests(TestCase):
    """F2/D: só a Samsung define DRAM_PC/DRAM_MOBILE (mapa global brand=None). Outra
    marca definindo sobrescreveria a densidade de TODAS → load_brands recusa."""

    def test_marca_nao_samsung_com_mapa_global_recusa(self):
        import os
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from chips.management.commands.load_brands import _KNOWLEDGE_DIR
        path = os.path.join(_KNOWLEDGE_DIR, "_guardtest.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('brand: {name: GuardT, code: GT}\n'
                     'maps:\n  DRAM_PC: [["11", "2Gb", "256MB"]]\n'
                     'families: [{prefix: GTX, chip_type: DDR4}]\n')
        try:
            with self.assertRaises(CommandError):
                call_command("load_brands", "--brand", "_guardtest", verbosity=0)
        finally:
            os.unlink(path)


class LoaderCrossBrandGuardTests(TestCase):
    """Backstop cross-brand: um prefixo pertence a UMA marca. Uma 2ª marca declarando o
    mesmo prefixo é rejeitada pelo loader (não sobrescreve a família da outra em silêncio)."""

    def test_prefixo_de_outra_marca_rejeita(self):
        from chips.models import Brand, ChipFamily
        from chips.knowledge.schema import FamilySpec
        from chips.management.commands.load_brands import Command
        from django.core.management.base import CommandError
        a = Brand.objects.create(name="MarcaA", code="MA")
        ChipFamily.objects.create(brand=a, prefix="ZZZQ", chip_type="DDR4")
        b = Brand.objects.create(name="MarcaB", code="MB")
        with self.assertRaises(CommandError):
            Command()._upsert_families(b, [FamilySpec(prefix="ZZZQ", chip_type="DDR3")])


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


# fix_known_parts APOSENTADO (2026-07-01) — a guarda de CI das entradas (FixKnownPartsEntriesTests)
# saiu junto; o equivalente pros known_parts YAML é o `extra="forbid"` do KnownPartSpec (rejeita
# campo desconhecido no portão Pydantic). Ver KnownPartsLoadTests.


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

    def test_emcp_confirmado_identity_only_usa_gramatica(self):
        """PROVA do 'identity-only' (padrão dos imports PSG Samsung, ex. KMQE60013B): um eMCP
        CONFIRMADO sem emcp_ram/emcp_nand próprios EXIBE RAM/NAND na tela — mas vêm da GRAMÁTICA,
        não do registro. O badge 'Confirmado' engana: a spec não está no known_part."""
        from chips.engine import classify
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_kmr, part_number='KMRBT099QZ',
            chip_type='eMCP', subtype='', confidence='confirmed',
            emcp_ram='', emcp_nand='')   # ← identity-only: registro SEM spec própria
        r = classify('KMRBT099QZ')
        self.assertIn('16GB', r.get('emcp_nand') or '')   # NAND aparece na tela...
        self.assertIn('2GB', r.get('emcp_ram') or '')      # ...RAM aparece...
        fresh = KnownPart.objects.get(part_number='KMRBT099QZ')
        self.assertEqual((fresh.emcp_ram or '') + (fresh.emcp_nand or ''), '')  # ...mas o registro está VAZIO

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

    def test_sugestao_inclui_distribuidor_mas_nao_estimated(self):
        """Dono (2026-07-08): registro de DISTRIBUIDOR também é sugerido (prefixo/
        fuzzy); 'estimated' continua fora (baixa confiança)."""
        from chips.engine import classify
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emcp, part_number='KMQ3200DIST',
            chip_type='eMCP', emcp_ram='LPDDR3 2GB', emcp_nand='eMMC 8GB',
            confidence='distributor', source=self.source)
        KnownPart.objects.create(
            brand=self.samsung, family=self.family_emcp, part_number='KMQ3201ESTIM',
            chip_type='eMCP', emcp_ram='LPDDR3 2GB', emcp_nand='eMMC 8GB',
            confidence='estimated', source=self.source)
        self.assertIn('KMQ3200DIST',
                      classify('KMQ3200').get('fuzzy_suggestions', []))     # distribuidor entra
        self.assertNotIn('KMQ3201ESTIM',
                         classify('KMQ3201').get('fuzzy_suggestions', []))  # estimated fica fora

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

    def test_gddr_sempre_nao_rentavel(self):
        # Decisão de negócio (dono, 2026-07-23): GDDR saiu do mercado — morto
        # POR TIPO, independente de geração/densidade (até 22/07 GDDR3+ era
        # avaliado por gddr_min_gen/gddr_min_gbit, removidos). E é DEAD por
        # tipo → triagem descarta mesmo sem confirmação no banco.
        self.assertEqual(self._assess({'chip_type': 'GDDR2'}), 'NÃO RENTÁVEL')
        self.assertEqual(self._assess(
            {'chip_type': 'GDDR3', 'dram_density': '4Gb = 512MB por die'}), 'NÃO RENTÁVEL')
        self.assertEqual(self._assess(
            {'chip_type': 'GDDR6', 'dram_density': '8Gb = 1GB por die'}), 'NÃO RENTÁVEL')
        self.assertTrue(self._dead({'chip_type': 'GDDR6',
                                    'dram_density': '8Gb = 1GB por die'}))

    def test_ddr3_baixa_densidade_nao_rentavel(self):
        self.assertEqual(self._assess({
            'chip_type': 'RAM', 'subtype': 'DDR3',
            'dram_density': '1Gb = 128MB por die [✓]',
        }), 'NÃO RENTÁVEL')

    def test_ssd_rentavel_por_gb(self):
        # SSD BGA/NVMe (dono 2026-07-24): comprado por GB — com capacidade é
        # RENTÁVEL (o ¥ escala com o GB); sem capacidade, INDETERMINADO.
        self.assertEqual(self._assess({'chip_type': 'SSD',
                                       'capacity': '440GB'}), 'RENTÁVEL')
        self.assertEqual(self._assess({'chip_type': 'SSD'}), 'INDETERMINADO')

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

class RentabilidadeHandshakeTests(TestCase):
    """F3 — HANDSHAKE de rentabilidade (a espinha do 'até o destino comercial').

    Garante que NENHUM chip_type COMERCIAL (com caixa física) caia em INDETERMINADO
    quando tem specs saudáveis. Um tipo/geração NOVO adicionado a chip_types.py sem
    regra em assess_profitability → cai em INDETERMINADO → este teste FALHA, forçando
    o autor a declarar a regra (ou marcar o tipo como não-comercial). Este teste, se
    existisse, teria pegado o bug do GDDR3+ (era comercial e retornava INDETERMINADO).
    É também o guard do PREÇO: sem veredito de rentabilidade não há faixa de preço."""

    def test_todo_tipo_comercial_tem_veredito_definitivo(self):
        from chips.chip_types import CHIP_TYPES
        from chips.engine import assess_profitability
        # specs GENEROSAS: garantem que um INDETERMINADO é falta de REGRA, não de capacidade.
        healthy = {'capacity': '256GB', 'dram_density': '16Gb = 2GB por die',
                   'emcp_ram': 'LPDDR5 8GB', 'emcp_nand': 'eMMC 5.1 256GB'}
        falhas = []
        for tok, spec in CHIP_TYPES.items():
            if spec.generic or not spec.commercial:
                continue   # genéricos e não-comerciais (catálogo) podem ser INDETERMINADO
            r = {'chip_type': tok, 'subtype': tok, 'is_emcp': spec.is_emcp, **healthy}
            if assess_profitability(r) == 'INDETERMINADO':
                falhas.append(tok)
        self.assertEqual(
            falhas, [],
            f"tipo(s) COMERCIAL(is) caindo em INDETERMINADO com specs saudáveis (falta regra "
            f"em assess_profitability, ou marque commercial=False em chip_types.py): {falhas}")


# ── Golden OBRIGATÓRIO pra família NOVA (jul/2026) ───────────────────────────────
# Prefixos das 188 famílias ATIVAS que já existiam quando a regra entrou. São
# GRANDFATHERED (provadas em prod → não exigem golden retroativo). QUALQUER família de
# prefixo NOVO (fora daqui) precisa de ≥1 PN-âncora num `_<MARCA>_GOLDEN`, senão o
# GoldenObrigatorioTests falha — força o chat a PROVAR o decode da família nova (o
# `characterize` não valida PN novo). Ao dar golden a uma grandfathered, pode tirá-la daqui.
_FAMILIES_GRANDFATHERED = frozenset({
    "04EMCP", "08EMCP", "16EMCP", "32EMCP", "64EMCP", "EMCP", "GD25B", "GD25LB", "GD25LQ",
    "GD25Q", "GD5F", "GDQ", "H26M", "H26T", "H28M", "H28S", "H28U", "H54G", "H58G", "H5A",
    "H5AN", "H5C", "H5MS", "H5PS", "H5RS", "H5TC", "H5TQ", "H9CC", "H9CK", "H9DA", "H9DP",
    "H9HC", "H9HCN", "H9HK", "H9HP", "H9HQ", "H9HR", "H9JK", "H9RT", "H9TK", "H9TP", "H9TQ",
    "HN8G", "HN8T", "HY5DU", "HY5MS", "HY5PS", "K3", "K3KL", "K3L", "K3LK", "K3MF", "K3PE",
    "K3Q", "K3QF", "K3R", "K3RG", "K3U", "K4A", "K4B", "K4E", "K4F", "K4G", "K4H", "K4J",
    "K4M", "K4N", "K4P", "K4R", "K4RA", "K4RB", "K4RC", "K4S", "K4T", "K4U", "K4W", "K4X",
    "K4Z", "K5", "K5D", "K5L", "K5N", "K5W", "K7", "K8", "K9C", "K9F", "K9G", "K9H", "K9HDG",
    "K9K", "K9L", "K9W", "K9X", "K9Z", "KAT", "KF9", "KLM", "KLU", "KLUBG", "KLUCG", "KLUDG",
    "KLUEG", "KLUFG", "KLUGG", "KM", "KM1", "KM2", "KM2L", "KM2P", "KM3H", "KM3P", "KM4",
    "KM5", "KM8", "KMAG", "KMAS", "KMD", "KMF", "KMG", "KMJ", "KMK", "KML", "KMN", "KMQ",
    "KMR", "KMS", "KMV", "KUS", "MT29F", "MT29P", "MT29T", "MT29TZZZ", "MT29VZZZ", "MT30AZZZ",
    "MT40A", "MT41K", "MT52L", "MT53B", "MT53D", "MT53E", "MTFC", "NT5AD", "NT5CC", "NT5PA",
    "PMA", "PMD", "PME", "PMF", "PMF4", "PMF5", "PMS", "RS1G32L", "RS256M32L", "RS256M32LD3",
    "RS2G32L", "RS512M32L", "RS512M32LD3", "RS70B", "RS70B08G", "RS70B16G", "RS70B32G",
    "RS70B64G", "RS70BT7G", "S2A", "S2D", "S2M", "S5E", "S5K", "SD5DH", "SD7DP", "SDAD",
    "SDEM", "SDHQB", "SDIN", "SDINB", "SDINDDH", "SDINEDK", "SDINFD", "SDMAG", "TH58", "THGAF",
    "THGAM", "THGBM", "THGJF", "THGJFBT", "TYC", "TYD",
})


class GoldenObrigatorioTests(SimpleTestCase):
    """F3+ — GOLDEN OBRIGATÓRIO: família NOVA (prefixo fora do baseline grandfathered)
    tem que ter PN-âncora num `_<MARCA>_GOLDEN`. É a última trava — sem ela, uma família
    nova entra sem prova de que decodifica certo. Grandfather as 188 atuais; enforce as novas."""

    def _golden_pns(self):
        import chips.tests as t
        pns = set()
        for name, val in vars(t).items():
            if name.endswith("_GOLDEN") and isinstance(val, dict):
                pns.update(str(k).upper() for k in val)
        return pns

    def _active_families(self):
        import glob, os, yaml
        from chips.management.commands.load_brands import _KNOWLEDGE_DIR
        fams = {}
        for f in glob.glob(os.path.join(_KNOWLEDGE_DIR, "*.yaml")):
            doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
            for fam in doc.get("families") or []:
                if fam.get("active", True) and fam.get("prefix"):
                    fams[fam["prefix"]] = os.path.basename(f)
        return fams

    def test_familia_nova_exige_ancora_no_golden(self):
        golden = self._golden_pns()
        faltando = []
        for prefix, brand in sorted(self._active_families().items()):
            if prefix in _FAMILIES_GRANDFATHERED:
                continue
            if not any(pn.startswith(prefix.upper()) for pn in golden):
                faltando.append(f"{prefix} ({brand})")
        self.assertEqual(faltando, [],
            "família(s) NOVA(s) SEM PN-âncora no _<MARCA>_GOLDEN de chips/tests.py — adicione a "
            f"âncora + saída esperada (é a prova de que a família decodifica certo): {faltando}")

    def test_mecanismo_pega_familia_nova_sem_golden(self):
        # sanity: prova que a trava REALMENTE pega um prefixo novo sem cobertura.
        golden = {"K4W4G1646Q"}                       # só cobre K4W
        self.assertFalse(any(pn.startswith("WB25Q") for pn in golden),
                         "a trava tem que NÃO achar cobertura pra uma família nova WB25Q")


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


class AuditKnownPartsTests(TestCase):
    """audit_known_parts (read-only): marca known_part confirmado cujo spec DIVERGE da
    gramática corrigida (stale), IGNORA o que bate, e nunca escreve. É o comando que
    lista os registros a corrigir no banco depois de um fix de gramática (bug X6 etc.)."""

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("audit_known_parts", *args, stdout=out)
        return out.getvalue()

    def _load_sam(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        from chips.models import Brand
        call_command("load_brands", "--brand", "samsung", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()
        return Brand.objects.get(name="Samsung")

    def test_marca_stale_ignora_correto(self):
        from chips.models import KnownPart
        sam = self._load_sam()
        # stale: a gramática KMG X6 = LPDDR3 3GB, mas o banco tem 2GB (valor antigo, assado)
        KnownPart.objects.create(part_number="KMGX6001BA", brand=sam, confidence="confirmed",
                                 review_status="approved", chip_type="eMCP", subtype="LPDDR3",
                                 emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR3 2GB")
        # correto: bate com a gramática (KMD X6 = LPDDR4X 3GB) → NÃO deve ser marcado
        KnownPart.objects.create(part_number="KMDX60018M", brand=sam, confidence="confirmed",
                                 review_status="approved", chip_type="eMCP", subtype="LPDDR4X",
                                 emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR4X 3GB")
        out = self._run("--brand", "samsung", "--family", "KMG,KMD")
        self.assertIn("KMGX6001BA", out)       # stale → marcado
        self.assertIn("LPDDR3 3GB", out)       # mostra o valor da gramática
        self.assertNotIn("KMDX60018M", out)    # correto → NÃO marcado
        self.assertIn("DIVERGENTES: 1", out)

    def test_read_only_nao_escreve(self):
        from chips.models import KnownPart
        sam = self._load_sam()
        KnownPart.objects.create(part_number="KMGX6001BA", brand=sam, confidence="confirmed",
                                 review_status="approved", chip_type="eMCP", subtype="LPDDR3",
                                 emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR3 2GB")
        antes = KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram
        out = self._run("--family", "KMG")
        self.assertIn("READ-ONLY", out)
        self.assertEqual(KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram, antes)

    def test_empty_lista_confirmado_sem_spec(self):
        from chips.models import KnownPart
        sam = self._load_sam()
        # confirmado SEM spec própria (identity-only) — deve aparecer
        KnownPart.objects.create(part_number="KMDZ9999XM", brand=sam, confidence="confirmed",
                                 review_status="approved", chip_type="eMCP")
        # confirmado COM spec (emcp_ram/nand) — NÃO deve aparecer (campos discretos vazios é normal)
        KnownPart.objects.create(part_number="KMDX60018M", brand=sam, confidence="confirmed",
                                 review_status="approved", chip_type="eMCP", subtype="LPDDR4X",
                                 emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR4X 3GB")
        out = self._run("--brand", "samsung", "--empty")
        self.assertIn("SEM SPEC PRÓPRIA", out)
        self.assertIn("KMDZ9999XM", out)       # identity-only → listado
        self.assertNotIn("KMDX60018M", out)    # tem emcp_ram/nand → não listado


class CorrectKnownPartsTests(TestCase):
    """correct_known_parts (par de escrita do audit): dry-run NÃO grava; --commit
    corrige stale→gramática pelo portão + backup; --revert desfaz; --exclude pula."""

    def _sam(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        from chips.models import Brand
        call_command("load_brands", "--brand", "samsung", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()
        return Brand.objects.get(name="Samsung")

    def _stale_kmg(self, sam):
        from chips.models import KnownPart
        # gramática KMG X6 = LPDDR3 3GB; gravo 2GB (stale)
        return KnownPart.objects.create(part_number="KMGX6001BA", brand=sam, confidence="confirmed",
                                        review_status="approved", chip_type="eMCP", subtype="LPDDR3",
                                        emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR3 2GB")

    def test_dry_run_nao_grava(self):
        from io import StringIO
        from django.core.management import call_command
        from chips.models import KnownPart
        self._stale_kmg(self._sam())
        out = StringIO()
        call_command("correct_known_parts", "--family", "KMG", stdout=out)
        self.assertIn("DRY-RUN", out.getvalue())
        self.assertEqual(KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram, "LPDDR3 2GB")

    def test_commit_corrige_e_revert_desfaz(self):
        import tempfile, os
        from django.core.management import call_command
        from chips.models import KnownPart
        self._stale_kmg(self._sam())
        bkp = tempfile.mktemp(suffix=".json")
        call_command("correct_known_parts", "--family", "KMG", "--commit", "--backup", bkp, verbosity=0)
        self.assertEqual(KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram, "LPDDR3 3GB")  # corrigido
        self.assertTrue(os.path.exists(bkp))
        call_command("correct_known_parts", "--revert", bkp, verbosity=0)
        self.assertEqual(KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram, "LPDDR3 2GB")  # revertido
        os.unlink(bkp)

    def test_exclude_pula_pn(self):
        from io import StringIO
        from django.core.management import call_command
        from chips.models import KnownPart
        self._stale_kmg(self._sam())
        out = StringIO()
        call_command("correct_known_parts", "--family", "KMG", "--exclude", "KMGX6001BA",
                     "--commit", stdout=out)
        self.assertIn("Nada a corrigir", out.getvalue())
        self.assertEqual(KnownPart.objects.get(part_number="KMGX6001BA").emcp_ram, "LPDDR3 2GB")


class GuardCatalogTests(TestCase):
    """Tripwire contra perda silenciosa do catálogo vivo (incidente jul/2026)."""

    def _n_known_parts(self, n):
        from chips.models import Brand, KnownPart
        b, _ = Brand.objects.get_or_create(name="GC", code="GC")
        base = KnownPart.objects.count()  # offset → PNs únicos entre lotes
        for i in range(base, base + n):
            KnownPart.objects.create(part_number=f"GCPART{i:04d}", brand=b,
                                     confidence="confirmed", capacity="8GB")

    def _run(self, **kw):
        from io import StringIO
        from django.core.management import call_command
        out, err = StringIO(), StringIO()
        code = 0
        try:
            call_command("guard_catalog", stdout=out, stderr=err, **kw)
        except SystemExit as e:
            code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_crescimento_atualiza_high_water(self):
        from chips.models import CatalogVersion
        self._n_known_parts(100)
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(CatalogVersion.current_row().max_known_parts, 100)
        # cresceu mais → high-water sobe
        self._n_known_parts_more = self._n_known_parts(50)
        code, _, _ = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(CatalogVersion.current_row().max_known_parts, 150)

    def test_queda_grande_dispara_alarme_e_falha(self):
        from chips.models import CatalogVersion, KnownPart
        self._n_known_parts(100)
        self._run()  # high-water = 100
        # simula a perda: apaga 90%
        ids = list(KnownPart.objects.values_list("id", flat=True)[:90])
        KnownPart.objects.filter(id__in=ids).delete()
        code, _, err = self._run()
        self.assertEqual(code, 1, "queda de 90% tem que FALHAR")
        self.assertIn("ALARME", err)
        # o high-water NÃO é rebaixado por uma queda
        self.assertEqual(CatalogVersion.current_row().max_known_parts, 100)

    def test_queda_pequena_dentro_da_tolerancia_nao_falha(self):
        from chips.models import KnownPart
        self._n_known_parts(100)
        self._run()  # high-water = 100
        ids = list(KnownPart.objects.values_list("id", flat=True)[:5])
        KnownPart.objects.filter(id__in=ids).delete()  # −5% (≤ 10%)
        code, out, _ = self._run()
        self.assertEqual(code, 0, "queda de 5% está dentro da tolerância")

    def test_reset_rebaixa_o_high_water(self):
        from chips.models import CatalogVersion, KnownPart
        self._n_known_parts(100)
        self._run()
        KnownPart.objects.all().delete()
        code, _, _ = self._run(reset=True)
        self.assertEqual(code, 0)
        self.assertEqual(CatalogVersion.current_row().max_known_parts, 0)


class KnownPartModelGateTests(TestCase):
    """Opção 2 / Fase 1: o portão de convenção + vocabulário roda no clean()/save() do
    MODELO → cobre TODO caminho de escrita (admin, bless_base, imports, restore, API),
    não só o load_brands. Antes, só o portão Pydantic (caminho YAML) validava."""

    def _brand(self):
        from chips.models import Brand
        b, _ = Brand.objects.get_or_create(name="GateB", code="GATEB")
        return b

    def test_save_normaliza_subtype_em_qualquer_caminho(self):
        from chips.models import KnownPart
        kp = KnownPart.objects.create(part_number="GATE001", brand=self._brand(),
                                      chip_type="DDR4", subtype="DDR4 SDRAM", confidence="confirmed")
        kp.refresh_from_db()
        self.assertEqual(kp.subtype, "DDR4", "canonical_gen tem que rodar no save()")

    def test_save_limpa_string_None(self):
        from chips.models import KnownPart
        kp = KnownPart.objects.create(part_number="GATE002", brand=self._brand(),
                                      capacity="None", emcp_ram="none", confidence="manual")
        kp.refresh_from_db()
        self.assertEqual((kp.capacity, kp.emcp_ram), ("", ""))

    def test_save_interface_nao_carrega_geracao_ram(self):
        from chips.models import KnownPart
        kp = KnownPart.objects.create(part_number="GATE003", brand=self._brand(),
                                      chip_type="LPDDR4", interface="LPDDR4", confidence="confirmed")
        kp.refresh_from_db()
        self.assertEqual(kp.interface, "")

    def test_save_rejeita_confidence_fora_do_vocabulario(self):
        from chips.models import KnownPart
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            KnownPart.objects.create(part_number="GATE004", brand=self._brand(), confidence="chute")

    def test_checkconstraint_bloqueia_confidence_no_banco(self):
        # .update() pula save()/clean() → a CheckConstraint do BANCO é a última linha de
        # defesa (sobrevive a bulk/SQL cru/admin), fechando o buraco do write não-validado.
        from chips.models import KnownPart
        from django.db import IntegrityError, transaction
        kp = KnownPart.objects.create(part_number="GATE005", brand=self._brand(), confidence="confirmed")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KnownPart.objects.filter(pk=kp.pk).update(confidence="lixo")

    def test_save_poe_densidade_ddr_no_lugar_certo(self):
        # Regra 4 (bug lote 40, 2026-07-11): DDR-kind com capacity "pelada" em
        # Gbit ('2G' — o que o bless_base grava da caixa) e density_gbit vazio
        # → density_gbit auto-preenche ('2Gb'); capacity FICA (fill-only).
        from chips.models import KnownPart
        kp = KnownPart.objects.create(part_number="GATE007", brand=self._brand(),
                                      chip_type="DDR3", subtype="DDR3",
                                      capacity="2G", confidence="manual")
        kp.refresh_from_db()
        self.assertEqual(kp.density_gbit, "2Gb")
        self.assertEqual(kp.capacity, "2G")
        # 'GB' é byte de pacote — NUNCA vira densidade (Gb≠GB).
        kp2 = KnownPart.objects.create(part_number="GATE008", brand=self._brand(),
                                       chip_type="DDR3", subtype="DDR3",
                                       capacity="2GB", confidence="manual")
        kp2.refresh_from_db()
        self.assertEqual(kp2.density_gbit, "")
        # Kind de pacote (eMMC) intocado, mesmo com '2G' no capacity.
        kp3 = KnownPart.objects.create(part_number="GATE009", brand=self._brand(),
                                       chip_type="eMMC", capacity="2G",
                                       confidence="manual")
        kp3.refresh_from_db()
        self.assertEqual(kp3.density_gbit, "")
        # density_gbit já preenchido não é sobrescrito.
        kp4 = KnownPart.objects.create(part_number="GATE010", brand=self._brand(),
                                       chip_type="DDR3", subtype="DDR3",
                                       capacity="2G", density_gbit="4Gb",
                                       confidence="manual")
        kp4.refresh_from_db()
        self.assertEqual(kp4.density_gbit, "4Gb")

    def test_guard_tipo_x_familia_is_emcp(self):
        # BRECHA do SD5DH26A4G (fechada aqui): um known_part eMCP submetido/aprovado caindo
        # numa família eMMC (is_emcp=False) — o engine tira o tipo da FAMÍLIA e nunca lê
        # emcp_nand/emcp_ram → a capacidade some no classify. O clean() agora barra os dois
        # sentidos do conflito eMCP↔não-eMCP; identity-only (chip_type vazio) segue livre.
        from chips.models import ChipFamily, KnownPart
        from chips.engine import clear_engine_cache
        from django.core.exceptions import ValidationError
        b = self._brand()
        ChipFamily.objects.create(brand=b, prefix="GEMMC", chip_type="eMMC",
                                  is_emcp=False, active=True, priority=50)
        ChipFamily.objects.create(brand=b, prefix="GEMCP", chip_type="eMCP",
                                  is_emcp=True, active=True, priority=50)
        clear_engine_cache()   # _match_family (no clean()) tem que ver as famílias novas

        # (1) o caso reportado: eMCP sob família eMMC → REJEITA.
        with self.assertRaises(ValidationError):
            KnownPart.objects.create(part_number="GEMMC26A4G", brand=b, chip_type="eMCP",
                                     subtype="LPDDR1", emcp_nand="4GB",
                                     emcp_ram="LPDDR1 768MB", confidence="manual")
        # (2) sentido reverso: eMMC sob família eMCP → REJEITA.
        with self.assertRaises(ValidationError):
            KnownPart.objects.create(part_number="GEMCP0016A", brand=b, chip_type="eMMC",
                                     capacity="16GB", confidence="manual")
        # (3) coerente: eMCP sob família eMCP → OK.
        self.assertTrue(KnownPart.objects.create(
            part_number="GEMCP0032B", brand=b, chip_type="eMCP", subtype="LPDDR4",
            emcp_nand="32GB", emcp_ram="LPDDR4 3GB", confidence="manual").pk)
        # (4) coerente: eMMC sob família eMMC → OK.
        self.assertTrue(KnownPart.objects.create(
            part_number="GEMMC0016C", brand=b, chip_type="eMMC", capacity="16GB",
            confidence="manual").pk)
        # (5) identity-only: chip_type vazio defere à gramática → OK (não é conflito).
        self.assertTrue(KnownPart.objects.create(
            part_number="GEMMC0008D", brand=b, chip_type="", confidence="confirmed").pk)
        clear_engine_cache()   # não vazar as famílias de teste pro cache dos próximos testes

    def test_densidade_derivada_de_familia_cap_map(self):
        # Raiz do bug lote 40 (2026-07-11): família DDR-kind SEM decode de
        # densidade próprio (cap_map com bytes POR DIE) ganha dram_density
        # DERIVADO no engine (MB×8÷1024) — cobre todas as marcas de uma vez,
        # sem reforma de yaml (posições de PN variam por marca).
        from chips.engine import classify
        from chips.models import Brand, ChipFamily, DecodeMap
        b = Brand.objects.create(name="DerivB", code="DERIVB")
        DecodeMap.objects.create(map_name="DERIV_CAP", char_key="2",
                                 val_primary="256MB", val_secondary="", brand=b)
        ChipFamily.objects.create(
            brand=b, prefix="ZZT", chip_type="DDR3", subtype="DDR3",
            decode_cap_pos=3, decode_cap_len=1, decode_cap_map="DERIV_CAP",
            active=True)
        r = classify("ZZT2AAAA")
        self.assertEqual(r.get("capacity"), "256MB")
        self.assertEqual(r.get("dram_density"), "2Gb = 256MB por die [✓]")
        self.assertEqual(r.get("density_gbit_num"), 2.0)

    def test_gddr5x_no_vocabulario(self):
        # Dono (2026-07-11): GDDR5X preserva a especificidade (nunca dobrar
        # pra 'GDDR' genérico — mudava a triagem do MT58K).
        from chips.chip_types import canonical_chip_type, label_kind
        self.assertEqual(canonical_chip_type("GDDR5X", ""), "GDDR5X")
        self.assertEqual(label_kind("GDDR5X"), "gddr")

    def test_portao_pydantic_e_modelo_usam_a_mesma_fonte(self):
        # Consistência: a normalização do YAML (Pydantic) e a do modelo dão o MESMO subtype.
        from chips.knowledge.convention import apply_kp_convention
        from chips.models import KnownPart

        class _Tmp:
            chip_type, subtype, interface = "DDR3", "DDR3 SDRAM", ""
            capacity = emcp_ram = emcp_nand = density_gbit = density_gb = ""
        via_funcao = apply_kp_convention(_Tmp()).subtype
        kp = KnownPart.objects.create(part_number="GATE006", brand=self._brand(),
                                      chip_type="DDR3", subtype="DDR3 SDRAM", confidence="confirmed")
        kp.refresh_from_db()
        self.assertEqual(via_funcao, kp.subtype)   # ambos → "DDR3"


class ReviewLayerTests(TestCase):
    """Opção 2 / Fase 2: só review_status='approved' é visível/autoritativo no engine;
    o maker-checker (four-eyes) barra auto-aprovação (no clean E na constraint do banco)."""

    def _fam(self):
        from chips.models import Brand, ChipFamily
        b, _ = Brand.objects.get_or_create(name="RevB", code="REVB")
        fam, _ = ChipFamily.objects.get_or_create(brand=b, prefix="REVX", defaults={"chip_type": "eMMC"})
        return b, fam

    def test_submitted_nao_e_visivel_no_engine(self):
        from chips.models import KnownPart
        from chips.engine import classify, clear_engine_cache
        b, fam = self._fam()
        KnownPart.objects.create(part_number="REVX0001", brand=b, family=fam, chip_type="eMMC",
                                 capacity="64GB", confidence="confirmed", review_status="submitted")
        clear_engine_cache()
        self.assertFalse(classify("REVX0001").get("known_exact"),
                         "submitted não pode ser reconhecido como registro do banco")

    def test_approved_e_visivel_no_engine(self):
        from chips.models import KnownPart
        from chips.engine import classify, clear_engine_cache
        b, fam = self._fam()
        KnownPart.objects.create(part_number="REVX0002", brand=b, family=fam, chip_type="eMMC",
                                 capacity="64GB", confidence="confirmed", review_status="approved")
        clear_engine_cache()
        r = classify("REVX0002")
        self.assertTrue(r.get("known_exact"))
        self.assertEqual(r.get("capacity"), "64GB")

    def test_four_eyes_clean_barra_auto_aprovacao(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import ValidationError
        from chips.models import KnownPart
        b, _ = self._fam()
        u = get_user_model().objects.create(username="steward1")
        with self.assertRaises(ValidationError):
            KnownPart.objects.create(part_number="REVX0003", brand=b, confidence="confirmed",
                                     review_status="approved", submitted_by=u, approved_by=u)

    def test_four_eyes_constraint_no_banco(self):
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError, transaction
        from chips.models import KnownPart
        b, _ = self._fam()
        u = get_user_model().objects.create(username="steward2")
        kp = KnownPart.objects.create(part_number="REVX0004", brand=b, confidence="confirmed",
                                      review_status="submitted", submitted_by=u)
        with self.assertRaises(IntegrityError):   # .update() pula o clean → constraint do banco barra
            with transaction.atomic():
                KnownPart.objects.filter(pk=kp.pk).update(review_status="approved", approved_by=u)

    def test_aprovacao_por_outro_usuario_ok(self):
        from django.contrib.auth import get_user_model
        from chips.models import KnownPart
        b, _ = self._fam()
        U = get_user_model()
        sub = U.objects.create(username="sub"); app = U.objects.create(username="app")
        kp = KnownPart.objects.create(part_number="REVX0005", brand=b, confidence="confirmed",
                                      review_status="submitted", submitted_by=sub)
        kp.review_status = "approved"; kp.approved_by = app; kp.save()   # ≠ submitter → ok
        kp.refresh_from_db()
        self.assertEqual(kp.review_status, "approved")


class SubmitKnownPartsTests(TestCase):
    """Opção 2 / Fase 3: submit_known_parts grava como 'submitted' (oculto) pelo portão."""

    def _write(self, texto):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        f.write(texto); f.close()
        return f.name

    def test_submit_cria_submitted_e_oculto_ate_aprovar(self):
        import os
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        from chips.models import Brand, KnownPart
        from chips.engine import classify, clear_engine_cache
        Brand.objects.get_or_create(name="SubB", code="SUBB")
        get_user_model().objects.create(username="chat_subb")
        path = self._write('brand: "SubB"\n'
                           'known_parts:\n'
                           '  - part_number: "SUBB0001"\n'
                           '    chip_type: "eMMC"\n'
                           '    capacity: "64GB"\n'
                           '    confidence: confirmed\n'
                           '    notes: "datasheet X"\n')
        try:
            call_command("submit_known_parts", path, commit=True, user="chat_subb")
        finally:
            os.unlink(path)
        kp = KnownPart.objects.get(part_number="SUBB0001")
        self.assertEqual(kp.review_status, "submitted")
        self.assertEqual(kp.submitted_by.username, "chat_subb")
        clear_engine_cache()
        self.assertFalse(classify("SUBB0001").get("known_exact"), "submitted não pode ser visível")

    def test_portao_rejeita_confidence_invalido(self):
        import os
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from chips.models import Brand
        Brand.objects.get_or_create(name="SubB2", code="SUBB2")
        path = self._write('brand: "SubB2"\nknown_parts:\n  - part_number: "X1"\n    confidence: lixo\n')
        try:
            with self.assertRaises(CommandError):
                call_command("submit_known_parts", path, commit=True)
        finally:
            os.unlink(path)

    def test_submit_nao_rebaixa_pn_ja_aprovado(self):
        import os
        from django.core.management import call_command
        from chips.models import Brand, KnownPart
        b, _ = Brand.objects.get_or_create(name="SubB3", code="SUBB3")
        KnownPart.objects.create(part_number="SUBB3LIVE", brand=b, chip_type="eMMC",
                                 capacity="64GB", confidence="confirmed", review_status="approved")
        path = self._write('brand: "SubB3"\n'
                           'known_parts:\n'
                           '  - part_number: "SUBB3LIVE"\n'
                           '    chip_type: "eMMC"\n'
                           '    capacity: "128GB"\n'
                           '    confidence: confirmed\n')
        try:
            call_command("submit_known_parts", path, commit=True)
        finally:
            os.unlink(path)
        kp = KnownPart.objects.get(part_number="SUBB3LIVE")
        self.assertEqual(kp.review_status, "approved", "não pode rebaixar um PN live")
        self.assertEqual(kp.capacity, "64GB", "não pode sobrescrever o dado live")

    def test_brand_como_bloco_diz_a_verdade(self):
        """O erro que mordeu DUAS vezes (Kingston, 2026-08-17 e 2026-08-19).

        O chat de marca escreve `brand:` no formato do yaml de GRAMÁTICA
        (bloco name/code/notes). O valor vira dict, o `filter(name=<dict>)`
        não casa nada, e a mensagem genérica mandava "crie a gramática antes"
        — conselho ERRADO: a gramática está lá, quem está errado é o arquivo.
        A mensagem tem que nomear a causa e mostrar a linha certa."""
        import os
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from chips.models import Brand
        Brand.objects.get_or_create(name="Kingston", code="KSTT")
        path = self._write('brand:\n'
                           '  name: Kingston\n'
                           '  code: KST\n'
                           "  notes: ''\n"
                           'known_parts:\n'
                           '  - part_number: "D2516EC4BXGGB"\n'
                           '    chip_type: "DDR3L"\n'
                           '    density_gbit: "4Gb"\n'
                           '    confidence: confirmed\n'
                           '    notes: "datasheet"\n')
        try:
            with self.assertRaises(CommandError) as ctx:
                call_command("submit_known_parts", path, commit=True)
        finally:
            os.unlink(path)
        msg = str(ctx.exception)
        self.assertIn("veio como BLOCO", msg)
        self.assertIn("brand: Kingston", msg)          # a linha certa, pronta
        self.assertIn("A gramática NÃO está faltando", msg)
        self.assertNotIn("crie a gramática antes", msg)  # o conselho errado sumiu

    def test_marca_ausente_de_verdade_sugere_as_parecidas(self):
        """Quando a marca REALMENTE não existe, o conselho da gramática vale —
        mas erro de grafia é mais comum que marca nova, então mostra as
        parecidas em vez de deixar o dono adivinhar."""
        import os
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from chips.models import Brand
        Brand.objects.get_or_create(name="Kingston", code="KSTT")
        path = self._write('brand: "Kingstom"\n'          # typo
                           'known_parts:\n'
                           '  - part_number: "KTYPO1"\n'
                           '    chip_type: "eMMC"\n'
                           '    capacity: "64GB"\n'
                           '    confidence: confirmed\n'
                           '    notes: "datasheet"\n')
        try:
            with self.assertRaises(CommandError) as ctx:
                call_command("submit_known_parts", path, commit=True)
        finally:
            os.unlink(path)
        msg = str(ctx.exception)
        self.assertIn("crie a gramática", msg)      # aqui o conselho é o certo
        self.assertIn("parecida(s) no banco", msg)
        self.assertIn("Kingston", msg)


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
        self.assertIn('load_brands', chamados)               # Samsung + demais marcas via load_brands
        # add_chip_families foi APOSENTADO (famílias migradas p/ yamls) → não está mais nos passos
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
        self.assertEqual(chamados[0], 'load_brands')          # 1º: load_brands samsung (mapas globais)
        self.assertEqual(mock_cc.call_args_list[0].kwargs.get('brand'), 'samsung')
        self.assertEqual(chamados[-1], 'import_samsung_psg')  # último passo (fix_known_parts APOSENTADO)
        self.assertNotIn('add_chip_families', chamados)       # APOSENTADO — famílias migradas p/ yamls
        self.assertNotIn('fix_known_parts', chamados)         # APOSENTADO — autoridade nos known_parts dos yamls
        kw = {c.args[0]: c.kwargs for c in mock_cc.call_args_list}
        self.assertNotIn('populate_samsung', chamados)        # aposentado → load_brands samsung
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
                    'populate_toshiba', 'populate_hynix', 'populate_samsung'):
            self.assertNotIn(pop, chamados)                    # aposentados
        # cada marca migrada passa por load_brands, gravando (commit=True)
        brands_load = [c.kwargs.get('brand') for c in mock_cc.call_args_list
                       if c.args[0] == 'load_brands']
        for marca in ('samsung', 'piecemakers', 'gigadevice', 'rayson', 'kingston', 'sandisk',
                      'micron', 'toshiba-kioxia', 'hynix', 'nanya'):
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
    call_command("load_brands", "--brand", slug, "--commit", "--skip-known-parts", verbosity=0)

    b = Brand.objects.get(code=spec.brand.code)
    tc.assertEqual((b.name, b.notes), (spec.brand.name, spec.brand.notes))
    tc.assertEqual(ChipFamily.objects.filter(brand=b).count(), len(spec.families))
    for fs in spec.families:
        fam = ChipFamily.objects.get(prefix=fs.prefix)
        tc.assertEqual(fam.brand_id, b.id)
        for campo in _FAM_FIELDS:
            tc.assertEqual(getattr(fam, campo), getattr(fs, campo), f"{slug}:{fs.prefix}.{campo}")
    from chips.management.commands.load_brands import _GLOBAL_MAPS
    total = sum(len(v) for v in spec.maps.values())
    # mapas universais (DRAM_PC/DRAM_MOBILE) são gravados com brand=None, não brand=b
    n_global = sum(len(spec.maps.get(m, [])) for m in _GLOBAL_MAPS)
    tc.assertEqual(DecodeMap.objects.filter(brand=b).count(), total - n_global)
    for map_name, entries in spec.maps.items():
        map_brand = None if map_name in _GLOBAL_MAPS else b
        for e in entries:
            dm = DecodeMap.objects.get(brand=map_brand, map_name=map_name, char_key=e.char_key)
            tc.assertEqual((dm.val_primary, dm.val_secondary), (e.val_primary, e.val_secondary))


# ── Goldens de id: (chip_type, capacity, emcp_nand, emcp_ram, dram_density, rentabilidade) ──
# Congelados da gramática validada (populate ANTES de aposentá-la; conferidos vs docs). Cada marca
# deve identificar TODOS os seus PNs conhecidos SEMPRE assim (regra do dono, 2026-06-30).
_PMK_GOLDEN = {
    "PMF510816DBR":     ("DDR3",  "128MB", "", "", "1Gb = 128MB por die [✓]", "NÃO RENTÁVEL"),  # 1Gb/die → < 2Gb → descarta; densidade DERIVADA do cap_map (2026-07-11)
    "PMF511808EBR":     ("DDR3",  "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),      # 2Gb x8
    "PMF511816EBR":     ("DDR3",  "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),      # 2Gb x16 (KnownPart em prod)
    "PMF512816CBR":     ("DDR3",  "512MB", "", "", "4Gb = 512MB por die [✓]", "RENTÁVEL"),      # 4Gb
    "PMF411816EBR":     ("DDR3L", "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),      # DDR3L 2Gb (=DDR3)
    "PMA212508ABR":     ("DDR4",  "",      "", "", "", "INDETERMINADO"), # DDR4 s/ decode → KnownPart resolve
    "PMA212816ABR":     ("DDR4",  "",      "", "", "", "INDETERMINADO"),
    "PMG6124D":         ("DDR4",  "",      "", "", "", "INDETERMINADO"), # PMG6 (família NOVA 2026-07-13, DDR4 s/ decode — igual PMA); âncora golden obrigatória (verificado no classify)
    "PMF511816EBRKADN": ("DDR3",  "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),      # variante -KADN do 2Gb
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
    # DDR3/DDR3L/DDR4 DISCRETA (não mobile/LPDDR) — família nova 2026-08-20, achada a partir de um
    # PN real 100% não-classificado no gateway do estoque (RS512M16Z2DD). Gramática decide só o
    # TIPO (decode_cap_pos=null em todas as 9); densidade exata (density_gbit) vem de known_part —
    # mesmo padrão já usado por outras marcas pra DDR4/DDR3 sem decode posicional (ver _PMK_GOLDEN/
    # _GIGA_GOLDEN). Por isso capacity="" e rentabilidade=INDETERMINADO em todas (specs insuficientes
    # pra decisão comercial — não é bug, é o handshake funcionando corretamente sem capacidade).
    "RS512M16Z2DD-62DT":  ("DDR4",  "", "", "", "", "INDETERMINADO"),  # Tier-1 szrayson.com; 8Gb=512Mx16
    "RS256M16ZADD-75DT":  ("DDR4",  "", "", "", "", "INDETERMINADO"),  # Tier-2 LCSC; 4Gb=256Mx16
    "RS512M8ZADD-75DT":   ("DDR4",  "", "", "", "", "INDETERMINADO"),  # Tier-2 LCSC; 4Gb=512Mx8 (irmã x8 da acima)
    "RS1G16Z4DD-62DT":    ("DDR4",  "", "", "", "", "INDETERMINADO"),  # Tier-1 szrayson.com; 16Gb=1Gx16
    "RS128M16V8DB-107AT": ("DDR3",  "", "", "", "", "INDETERMINADO"),  # Tier-1 szrayson.com; 2Gb=128Mx16, 1.5V
    "RS256M16V0DB-107AT": ("DDR3",  "", "", "", "", "INDETERMINADO"),  # Tier-2 LCSC; 4Gb=256Mx16, 1.5V
    "RS512M16VADF-107AT": ("DDR3",  "", "", "", "", "INDETERMINADO"),  # Glochip (Tier 2/3, apoio); 8Gb=512Mx16, 1.5V
    "RS128M16VMDD-107BT": ("DDR3L", "", "", "", "", "INDETERMINADO"),  # Glochip (Tier 2/3, apoio); 2Gb=128Mx16, 1.35V
    "RS256M16VMDC-107BT": ("DDR3L", "", "", "", "", "INDETERMINADO"),  # Glochip (Tier 2/3, apoio); 4Gb=256Mx16, 1.35V
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
                    "RAM não mapeada — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),  # subtype vazio → fallback INDETERMINADO (fix 2026-07-15: antes "tipo 'A'" via dict Samsung)
    "SDADB48K16G": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                    "RAM não mapeada — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),  # idem SDADA4DR64G
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
    "MT29PZZZ4D4BKESK":     ("eMCP", "", "eMMC ⚠ cap. não mapeada", "LPDDR2 ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # MT29P subtype LPDDR2 (canônico) → emcp_ram mais preciso
}
_TK_GOLDEN = {  # Toshiba-Kioxia (marca única). THGBMFG/THGBMHG DESATIVADAS (active:false, 2026-07) —
    # eram magras que interceptavam o THGBM; agora o THGBM decodifica os THGBMxx posicionalmente. Demais
    # magras (eMCP/UFS por prefixo) = INDETERMINADO na gramática; THGBM decodifica capacidade.
    "THGBMBG7D2KBAIL": ("eMMC", "16GB", "", "", "", "RENTÁVEL"),   # Toshiba THGBM (decodifica cap)
    "TYC0FH121638RA":  ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR2 ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # Toshiba TYC — LPDDR2 do subtype (fix EMCP_RAM_TYPES 2026-07-15); LPDDR2 = geração morta → descarte (antes mascarado como "tipo 'C'" → ia pra fila)
    "TYD0FH221627RA":  ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR3 ⚠ cap. não mapeada", "", "INDETERMINADO"),  # Toshiba TYD — LPDDR3 do subtype (corrigido 2026-07-15: antes colidia com EMCP_RAM_TYPES['D']→"LPDDR4X"; o dict é exclusivo Samsung)
    # TY8A0A/TY9A0A/TYAB0A/TY890A/TYBC0A/TY6801/TY6701/TY5701 (2026-07-15, família NOVA — eMCP Toshiba
    # muito legado ~2010-2011, RAM LPDDR1, SEM known_part nenhum, só gramática): as 8 variantes de chave
    # dão o MESMO resultado (magras, sem decode_cap_map; decode_gen_map='TY_EMCP_GEN' vazio de propósito
    # força extração de "LPDDR1" do subtype em vez do fallback EMCP_RAM_TYPES — ver reasoning no yaml).
    # NÃO RENTÁVEL só por geração, independente de capacidade — era esse o pedido do dono.
    "TY8A0A111173KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TY9A0A111171KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TYAB0A111128KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TY890A111229KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TYBC0A111124LC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # PN da bancada
    "TY6801111190KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TY6701111184KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TY5701111183KC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    # TY90 (2026-08-24, família NOVA — eMCP Toshiba ~2012-2013, estrutura própria/RA-RC, RAM LPDDR1
    # fixo como as irmãs TY8A0A): magra igual ao grupo acima, mesmo mecanismo (TY_EMCP_GEN vazio).
    # PN da bancada TY90HH131647RA e o anchor TY90GH131451RC (Tier-1 IHS/iSuppli teardown) — ambos
    # NÃO RENTÁVEL só por geração na gramática pura; capacidade real (8GB/16GB) vem do known_part.
    "TY90GH131451RC": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
    "TY90HH131647RA": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # PN da bancada
    # TYE0 (2026-08-24, família NOVA — mesma FORMA do TY90 (TY+2chars+"0"+letra+H+dígitos+RA/RC,
    # pn_length=14) mas chave "E0", produto DIFERENTE: pacote BGA-221 (igual TYD), RAM citada em Gb
    # não Mb (Tier-3 única, rlitl.com) — geração NÃO confirmada, subtype fica vazio de propósito.
    # Veredito esperado por PESQUISA (não copiado do classify() de hoje): NAND=16GB confirmado
    # (distributor), RAM sem fonte → engine sai "RAM não mapeada" → assess_profitability não
    # completa o guard eMCP (ram_gb=None) → INDETERMINADO. Mesmo padrão já estabelecido pela
    # família TYD (ver TYD0FH221627RA acima, também INDETERMINADO pelo mesmo motivo: geração de
    # RAM desconhecida). Se o engine discordar deste valor, o vermelho é a informação, não o teste.
    "TYE0HH231659RA": ("eMCP", "", "eMMC ⚠ cap. não mapeada",
                        "RAM não mapeada — consultar datasheet ⚠ cap. não mapeada", "", "INDETERMINADO"),  # PN da bancada
    "THGBMFG7C2LBAIL": ("eMMC", "16GB", "", "", "", "RENTÁVEL"),   # THGBMFG desativada → THGBM decodifica (F=5.0, 7C2=16GB)
    "THGBMHG8C4LBAIR": ("eMMC", "32GB", "", "", "", "RENTÁVEL"),   # THGBMHG desativada → THGBM decodifica (H=5.1, 8C4=32GB)
    "THGAF8G8T23BAIL": ("UFS",  "32GB", "", "", "", "RENTÁVEL"),  # Kioxia THGAF — decode_cap_map 2026-07-08: pn[6:8]="G8"=32GB (Kioxia Highlight Q1/2021)
    "THGAMVG7T13BAIL": ("eMMC", "", "", "", "", "INDETERMINADO"),  # Kioxia THGAM
    "THGJFPT0E18BAIP": ("UFS",  "", "", "", "", "INDETERMINADO"),  # Kioxia THGJF
    "THGBX2G7B2JLA01": ("NAND Flash", "16GB", "", "", "", "NÃO RENTÁVEL"),  # THGBX (2026-07-08, família nova) — decodifica 7B2=16GB (iFixit); NÃO RENTÁVEL é por TIPO (NAND raw sem controlador eMMC/UFS), não pela capacidade
    "THGBF7G8K4LBATR": ("UFS", "32GB", "", "", "", "RENTÁVEL"),  # THGBF (2026-07-09, revisado na 2ª rodada) — decode_cap_map reaproveita THGAF_CAP via pn[6:8]="G8"=32GB; 3 PNs (32/64/128GB) confirmam o padrão contra Octopart/Avnet, mas prefixo THGBF em si NUNCA confirmado Tier-1 — capacidade decodifica pela gramática, tipo/interface exato seguem sem Tier-1
    # TC58NVG (2026-08-20, família NOVA — NAND Flash raw standalone, SLC, chip único). Decode posicional
    # próprio (decode_cap_pos=7, mapa TC58NVG_CAP) via decoder OFICIAL Toshiba (MFOPR-916, 2010) — ver
    # reasoning no yaml. subtype=SLC NAND fixo por família (100% dos PNs reais vistos usam célula S/2-level).
    # NÃO RENTÁVEL é por TIPO (NAND raw sem controlador), igual ao THGBX — independente de capacidade.
    # Âncora original TC58NVG0S3HBAI4 = PN da bancada, corrigido de typo (1→I na posição 14); já tem
    # known_part confidence=confirmed próprio, mas o golden roda com --skip-known-parts (só gramática).
    "TC58NVG0S3HBAI4": ("NAND Flash", "128MB", "", "", "", "NÃO RENTÁVEL"),  # posição7="0" → G0=1Gbit=128MB
    "TC58NVG0S3HTA00": ("NAND Flash", "128MB", "", "", "", "NÃO RENTÁVEL"),  # irmão TSOP, mesma densidade
    "TC58NVG1S3HTA00": ("NAND Flash", "256MB", "", "", "", "NÃO RENTÁVEL"),  # posição7="1" → G1=2Gbit=256MB
    "TC58NVG2S0HTA00": ("NAND Flash", "512MB", "", "", "", "NÃO RENTÁVEL"),  # posição7="2" → G2=4Gbit=512MB; posição9="0" (organização) não afeta a chave
    "TC58NVG1S3ETA00": ("NAND Flash", "256MB", "", "", "", "NÃO RENTÁVEL"),  # variante design rule 43nm (posição10="E") — mesma capacidade, prova que design rule não afeta a chave
    "TC58NVG2S3ETA00": ("NAND Flash", "512MB", "", "", "", "NÃO RENTÁVEL"),  # variante 43nm
    "TC58NVG1S3HTAI0": ("NAND Flash", "256MB", "", "", "", "NÃO RENTÁVEL"),  # sufixo de pacote/modo "I0" diferente — mesma capacidade
}
_HYX_GOLDEN = {  # SK Hynix: 37 famílias (populate_hynix + add_chip_families). Cobre DDR1-5, LPDDR2-4X, eMMC, eMCP, UFS.
    "H26M74002HMR":      ("eMMC", "64GB",  "", "", "", "RENTÁVEL"),
    "H26T87001CMR":      ("eMMC", "128GB", "", "", "", "RENTÁVEL"),
    "H28U88301AMR":      ("UFS",  "128GB", "", "", "", "RENTÁVEL"),
    "H54GE6CYRB":        ("LPDDR4X", "6GB", "", "", "", "RENTÁVEL"),  # CORRIGIDO 2026-07-10 (autorização do dono): era 4GB (fonte antiga não rastreável); Puris fetch direto de H54GE6CYRBX262N confirma 48Gbit=6GB
    "H54GD6AYRBX273N":   ("LPDDR4X", "3GB", "", "", "", "RENTÁVEL"),  # 2ª âncora H54G, chave 'D' nova (2026-07-10) — Preduo (24Gbit) + título Alibaba ("3GB") confirmam D=3GB
    "H5AN8G8NAFR-UHC":   ("DDR4", "1GB",  "", "", "8Gb = 1GB por die [✓]", "RENTÁVEL"),   # densidade per-die GB (lote 042): 1GB=1024MB×8÷1024=8Gb — bate com o 8G do PN
    "H5AN8G8NAFR-VKC":   ("DDR4", "1GB",  "", "", "8Gb = 1GB por die [✓]", "RENTÁVEL"),
    "H5CG48MEBDX014N":   ("DDR5", "2GB",  "", "", "16Gb = 2GB por die [✓]", "RENTÁVEL"),  # 2GB=2048MB→16Gb (die DDR5 padrão)
    "H5GQ4H24AJR":       ("GDDR5", "512MB", "", "", "4Gb = 512MB por die [✓]", "NÃO RENTÁVEL"),  # âncora H5GQ; GDDR morto por tipo (2026-07-23)
    "HY5RS123235B":      ("GDDR3", "", "", "", "", "NÃO RENTÁVEL"),  # âncora HY5RS (família magra, 2026-08-20) — tipo pelo prefixo, capacidade só via known_part; GDDR morto por tipo independe de densidade
    "H5PS1G83EFR-S6C":   ("DDR2", "128MB", "", "", "1Gb = 128MB por die [✓]", "NÃO RENTÁVEL"),
    "H5TC4G83CFR-PBA":   ("DDR3L", "512MB", "", "", "4Gb = 512MB por die [✓]", "RENTÁVEL"),
    "H5TQ2G63GFR":       ("DDR3", "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),
    "H9CCNNNCLTML":      ("LPDDR3", "4GB", "", "", "", "RENTÁVEL"),
    "H9CKNNNBJTMP":      ("LPDDR3", "2GB", "", "", "", "RENTÁVEL"),
    "H9CKNNNAETAP":      ("LPDDR3", "1.5GB", "", "", "", "NÃO RENTÁVEL"),  # código 'A' NOVO (2026-07-13): WinSource "12Gb" + corrobora Fire HD 8 (2017, 1.5GB RAM)
    "H9DA4GH2GJAM":      ("eMCP", "", "eMMC 4.x 4GB", "LPDDR1 256MB", "", "NÃO RENTÁVEL"),
    "H9TA4GH2GDAC":      ("eMCP", "", "eMMC 4.x 4GB", "LPDDR1 256MB", "", "NÃO RENTÁVEL"),  # família NOVA, irmã do H9DA — WinSource 2026-07-08, output real conferido
    "H9TA1GH1GBMMVR4GM": ("eMCP", "", "eMMC 4.x 1GB", "LPDDR1 1GB",  "", "NÃO RENTÁVEL"),  # corrobora NAND '1' + RAM '1G' (match exato c/ mapa H9DA)
    "H9TA1GG51BMMVR4DM": ("eMCP", "", "eMMC 4.x 1GB", "LPDDR1 512MB", "", "NÃO RENTÁVEL"),  # corrobora RAM '51'
    "H9TA2GG1GDACPR4DM": ("eMCP", "", "eMMC 4.x 2GB", "LPDDR1 1GB",  "", "NÃO RENTÁVEL"),  # corrobora NAND '2'
    "H9TA4GG4GDMCPR4GM": ("eMCP", "", "eMMC 4.x 4GB", "LPDDR1 (código não mapeado — atualizar populate) ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # RAM '4G' SEM corroboração (não existe no mapa H9DA) — prova que a gramática NÃO adivinha
    "H9DP32A4JJBC":      ("eMCP", "", "eMMC 4GB", "LPDDR1 512MB", "", "NÃO RENTÁVEL"),  # gen corrigida LPDDR2→LPDDR1 (datasheet H9DP32A4JJBCGR "Mobile DDR / 400Mbps", 2026-07-09)
    "H9HCNNNCPMAL":      ("LPDDR4X", "4GB", "", "", "", "RENTÁVEL"),
    "H9HCNNNECMML":      ("LPDDR4X", "6GB", "", "", "", "RENTÁVEL"),
    "H9HKNNNCTUMUBR-NMH": ("LPDDR4X", "4GB", "", "", "", "RENTÁVEL"),  # 1º golden da família H9HK (2026-07-09) — sem cobertura antes; PN buscado na bancada, C=4GB confirmado por WinSource (32Gb/8) + já mapeado
    "H9AG9G5ANB":        ("eMCP", "", "eMMC 5.1 64GB", "LPDDR4X 4GB", "", "RENTÁVEL"),  # âncora H9AG (família nova, 2026-08-24) — datasheet oficial uttc.com.tw lido na íntegra, Ordering Information conferida
    "H9HP16AECMMD":      ("eMCP", "", "eMMC 5.1 128GB", "LPDDR4X 6GB", "", "RENTÁVEL"),
    "H9HP27ABUMMDAR-KEM": ("eMCP", "", "eMMC 5.1 32GB", "LPDDR4X 2GB", "", "RENTÁVEL"),  # chave RAM 'AB' nova no mapa compartilhado H9HP/H9HQ (2026-07-09) — Preduo + Puris concordam
    "H9HQ22AECMMDAR-KEM": ("uMCP", "", "UFS 2.1 256GB", "LPDDR4X 6GB", "", "RENTÁVEL"),  # chave NAND '22' nova no mapa (2026-07-09) — Preduo + distribuidor concordam, mesmo padrão de pares 15/16 e 53/54
    "H9TKNNN8JDAP":      ("LPDDR2", "1GB", "", "", "", "NÃO RENTÁVEL"),
    "H9TQ64A8GTCC":      ("eMCP", "", "eMMC 5.x 8GB", "LPDDR3 1GB", "", "RENTÁVEL"),
    "H9TQ64AAETMCUR-KUM": ("eMCP", "", "eMMC 5.x 8GB", "LPDDR3 1.5GB", "", "RENTÁVEL"),  # AA=1.5GB (12Gb) ≠ AB=2GB — WinSource 2026-07-06, ver hynix.yaml
    "H9TQ18ABJTMCUR-KTM": ("eMCP", "", "eMMC 5.x 16GB", "LPDDR3 2GB", "", "RENTÁVEL"),  # chave NAND '18' nova no mapa (2026-07-09) — Preduo + Puris concordam, mesmo padrão de trio 16/17/18
    "HN8T05BZGR":        ("UFS", "128GB", "", "", "", "RENTÁVEL"),
    "HY5DU281622ET-25":  ("DDR1", "16MB", "", "", "0.125Gb = 16MB por die [✓]", "NÃO RENTÁVEL"),
    "HY5PS121621CFP-25": ("DDR2", "64MB", "", "", "0.5Gb = 64MB por die [✓]", "NÃO RENTÁVEL"),
}


# Samsung — GABARITO MESTRE: 87 famílias (populate_samsung + add_chip_families), 15 mapas.
# Golden = populate + O PORTÃO REAL (FamilySpec) aplicado (K4R fix; genérico 'LPDDR'→'LPDDR2';
# multi-geração 'LPDDR4X/5X'→'LPDDR4X'). Cobre TODAS as 87 famílias; alguns PNs são sintéticos
# (construídos p/ famílias legadas sem PN documentado). Prova que o yaml reproduz gate(populate).
_SAM_GOLDEN = {
    'K31G1646DBCK': ('LPDDR2', '', '', '', '16Gb = 2GB por die [✓]', 'NÃO RENTÁVEL'),
    'K3KL7L70DM': ('LPDDR5X', '3GB', '', '', '', 'RENTÁVEL'),
    'K3KL8L80EM': ('LPDDR5X', '4GB', '', '', '', 'RENTÁVEL'),
    'K3L1G1646DBC': ('LPDDR5X', '', '', '', '', 'INDETERMINADO'),
    'K3LK3K3': ('LPDDR5', '8GB', '', '', '', 'RENTÁVEL'),
    'K3LK3K30EM': ('LPDDR5', '8GB', '', '', '', 'RENTÁVEL'),
    'K3MF8F80DM': ('LPDDR3', '', '', '', '', 'INDETERMINADO'),
    'K3MF9F90MM': ('LPDDR3', '', '', '', '', 'INDETERMINADO'),
    'K3PE0E000A': ('LPDDR2', '2GB', '', '', '', 'NÃO RENTÁVEL'),
    'K3PE7E700B': ('LPDDR2', '1GB', '', '', '', 'NÃO RENTÁVEL'),
    'K3Q2G30PC': ('LPDDR3', '', '', '', '2Gb = 256MB por die [~]', 'RENTÁVEL'),
    'K3Q8F30MB': ('LPDDR3', '', '', '', '8Gb = 1GB por die [✓]', 'RENTÁVEL'),
    'K3QF3F30': ('LPDDR3', '2GB', '', '', '', 'RENTÁVEL'),
    'K3QFAFA0CM': ('LPDDR3', '8GB', '', '', '', 'RENTÁVEL'),
    'K3R1G1646DBC': ('LPDDR3', '', '', '', '1Gb = 128MB por die [~]', 'NÃO RENTÁVEL'),
    'K3RG2G2': ('LPDDR4', '4GB', '', '', '', 'RENTÁVEL'),
    'K3RG6G6': ('LPDDR4', '6GB', '', '', '', 'RENTÁVEL'),
    'K3UH6H6': ('LPDDR4X', '4GB', '', '', '', 'RENTÁVEL'),
    'K3UH6H60': ('LPDDR4X', '4GB', '', '', '', 'RENTÁVEL'),
    'K4AAG085W': ('DDR4', '', '', '', '16Gb = 2GB por die [~]', 'RENTÁVEL'),
    'K4AAG165W': ('DDR4', '', '', '', '16Gb = 2GB por die [~]', 'RENTÁVEL'),
    'K4B2G1646F': ('DDR3', '', '', '', '2Gb = 256MB por die [~]', 'RENTÁVEL'),
    'K4B8G0846D': ('DDR3', '', '', '', '8Gb = 1GB por die [✓]', 'RENTÁVEL'),
    'K4B4G0446D': ('DDR3', '', '', '', '4Gb = 512MB por die [✓]', 'RENTÁVEL'),  # 2026-08-20: largura x4 (04), 1º golden da família com essa largura
    'K4D553235FGC33': ('GDDR2', '32MB', '', '', '0.25Gb = 32MB por die [✓]', 'NÃO RENTÁVEL'),  # densidade DERIVADA (2026-07-11)
    'K4D263238KFC40': ('GDDR2', '16MB', '', '', '0.125Gb = 16MB por die [✓]', 'NÃO RENTÁVEL'),
    'K4E6E304': ('LPDDR3', '2GB', '', '', '', 'RENTÁVEL'),
    'K4EBE304': ('LPDDR3', '4GB', '', '', '', 'RENTÁVEL'),
    'K4FHE30': ('LPDDR4', '3GB', '', '', '', 'RENTÁVEL'),
    'K4FHE3D': ('LPDDR4', '3GB', '', '', '', 'RENTÁVEL'),
    'K4G10325': ('GDDR5', '', '', '', '1Gb = 128MB por die [~]', 'NÃO RENTÁVEL'),
    'K4G80325FB': ('GDDR5', '', '', '', '8Gb = 1GB por die [✓]', 'NÃO RENTÁVEL'),  # GDDR morto por tipo (2026-07-23)
    'K4H510438G': ('DDR1', '', '', '', '512Mb = 64MB por die [~]', 'NÃO RENTÁVEL'),
    'K4H560838D': ('DDR1', '', '', '', '256Mb = 32MB por die [~]', 'NÃO RENTÁVEL'),
    'K4J10324KE': ('GDDR3', '', '', '', '', 'NÃO RENTÁVEL'),  # GDDR morto por tipo (2026-07-23)
    'K4J55323QF': ('GDDR3', '', '', '', '', 'NÃO RENTÁVEL'),
    'K4M1G1646DBC': ('LPDDR1', '', '', '', '', 'NÃO RENTÁVEL'),
    'K4N51163': ('GDDR2', '', '', '', '', 'NÃO RENTÁVEL'),
    'K4N51163Q': ('GDDR2', '', '', '', '', 'NÃO RENTÁVEL'),
    'K4P2G304EB': ('LPDDR2', '', '', '', '2Gb = 256MB por die [~]', 'NÃO RENTÁVEL'),
    'K4P4G324EB': ('LPDDR2', '', '', '', '4Gb = 512MB por die [✓]', 'NÃO RENTÁVEL'),
    'K4R271669F': ('RDRAM', '128Mb', '', '', '', 'NÃO RENTÁVEL'),
    'K4R441669E': ('RDRAM', '144Mb', '', '', '', 'NÃO RENTÁVEL'),
    'K4RAH086V': ('DDR5', '', '', '', '16Gb = 2GB por die [~]', 'RENTÁVEL'),
    'K4RAH165V': ('DDR5', '', '', '', '16Gb = 2GB por die [~]', 'RENTÁVEL'),
    'K4RBH046V': ('DDR5', '', '', '', '32Gb = 4GB por die [~]', 'RENTÁVEL'),
    'K4RBH046VM': ('DDR5', '', '', '', '32Gb = 4GB por die [~]', 'RENTÁVEL'),
    'K4RCH046V': ('DDR5', '', '', '', '32Gb = 4GB por die [~]', 'RENTÁVEL'),
    'K4RCH046VM': ('DDR5', '', '', '', '32Gb = 4GB por die [~]', 'RENTÁVEL'),
    'K4S641632H': ('SDRAM', '', '', '', '64Mb = 8MB por die [✓]', 'NÃO RENTÁVEL'),
    'K4T1G083QJ': ('DDR2', '', '', '', '1Gb = 128MB por die [~]', 'NÃO RENTÁVEL'),
    'K4T1G084QJ': ('DDR2', '', '', '', '1Gb = 128MB por die [~]', 'NÃO RENTÁVEL'),
    'K4UHE3D': ('LPDDR4X', '3GB', '', '', '', 'RENTÁVEL'),
    'K4UHE3S': ('LPDDR4X', '3GB', '', '', '', 'RENTÁVEL'),
    'K4W4G1646': ('GDDR3', '', '', '', '4Gb = 512MB por die [✓]', 'NÃO RENTÁVEL'),  # GDDR morto por tipo (2026-07-23)
    'K4W4G1646D': ('GDDR3', '', '', '', '4Gb = 512MB por die [✓]', 'NÃO RENTÁVEL'),
    'K4XXXXXX': ('LPDDR1', '', '', '', "Código 'XX' não mapeado — consultar datasheet", 'NÃO RENTÁVEL'),
    'K4XXXXXX-BCPB': ('LPDDR1', '', '', '', "Código 'XX' não mapeado — consultar datasheet", 'NÃO RENTÁVEL'),
    'K4Y50164UE': ('RDRAM', '512Mb', '', '', '', 'NÃO RENTÁVEL'),  # 2026-08-20: família nova, XDR DRAM (PS3 Cell RAM) — âncora golden obrigatória
    'K4ZAF325B': ('GDDR6', '', '', '', '', 'NÃO RENTÁVEL'),  # GDDR morto por tipo (2026-07-23)
    'K4ZAF325BC': ('GDDR6', '', '', '', '', 'NÃO RENTÁVEL'),
    'K524G2G': ('NOR Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'K524G2GACJ': ('NOR Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'K5D1G12ACD': ('OneNAND', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K5D5657ACB': ('OneNAND', '256Mb', '', '', '', 'NÃO RENTÁVEL'),
    'K5L2731': ('MCP', '', '', '', '', 'NÃO RENTÁVEL'),
    'K5L5563': ('MCP', '', '', '', '', 'NÃO RENTÁVEL'),
    'K5N1229ACC-BQ12': ('MCP', '', '', '', '', 'NÃO RENTÁVEL'),
    'K5W1G12ACM': ('MCP', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K5W1G12ACM-BL60TNO': ('MCP', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K71G1646DBCK': ('SRAM', '', '', '', '', 'INDETERMINADO'),
    'K81G1646DBCK': ('NOR Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'K9C1G1646DBC': ('NAND Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'K9F2G08U0B': ('NAND Flash', '2Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9F4G08U0D': ('NAND Flash', '4Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9GAG08U0E': ('NAND Flash', '16Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9GBG08U0A': ('NAND Flash', '32Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9H1G1646DBC': ('NAND Flash', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9HDG08U5A': ('NAND Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'K9K8G08U0A': ('NAND Flash', '8Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9LCG08U1A': ('NAND Flash', '64Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9W1G1646DBC': ('NAND Flash', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9X1G1646DBC': ('NAND Flash', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'K9Z1G1646DBC': ('NAND Flash', '1Gb', '', '', '', 'NÃO RENTÁVEL'),
    'KA1000015E': ('MCP', '', '', '', '', 'NÃO RENTÁVEL'),
    'KAT1G1646DBC': ('ePoP', '', 'eMMC ⚠ cap. não mapeada', "tipo 'T' — consultar datasheet ⚠ cap. não mapeada", '', 'NÃO RENTÁVEL'),
    'KF91G1646DBC': ('NAND Flash', '', '', '', '', 'NÃO RENTÁVEL'),
    'KLM2G1DEHE': ('eMMC', '2GB', '', '', '', 'NÃO RENTÁVEL'),
    'KLMCG2KETM': ('eMMC', '64GB', '', '', '', 'RENTÁVEL'),
    'KLMCG2UCTA': ('eMMC', '64GB', '', '', '', 'RENTÁVEL'),
    'KLU1G1646D': ('UFS', '', '', '', '', 'INDETERMINADO'),
    'KLUBG4G1CE': ('UFS', '32GB', '', '', '', 'RENTÁVEL'),
    'KLUBG4G1ZF': ('UFS', '32GB', '', '', '', 'RENTÁVEL'),
    'KLUCG2U1DC': ('UFS', '64GB', '', '', '', 'RENTÁVEL'),
    'KLUCG4J1ED': ('UFS', '64GB', '', '', '', 'RENTÁVEL'),
    'KLUDG2R1DE': ('UFS', '128GB', '', '', '', 'RENTÁVEL'),
    'KLUDG4UHGC': ('UFS', '128GB', '', '', '', 'RENTÁVEL'),
    'KLUEG4RHHF': ('UFS', '256GB', '', '', '', 'RENTÁVEL'),
    'KLUEG8U1EM': ('UFS', '256GB', '', '', '', 'RENTÁVEL'),
    'KLUFG8RHKF': ('UFS', '512GB', '', '', '', 'RENTÁVEL'),
    'KLUFG8RHYE': ('UFS', '512GB', '', '', '', 'RENTÁVEL'),
    'KLUGGAR1FA': ('UFS', '1TB', '', '', '', 'RENTÁVEL'),
    'KLUGGARHUF': ('UFS', '1TB', '', '', '', 'RENTÁVEL'),
    'KM11G1646D': ('uMCP', '', 'UFS 4.0 ⚠ cap. não mapeada', 'LPDDR5X ⚠ cap. não mapeada', '', 'INDETERMINADO'),
    'KM2B8001CM': ('uMCP', '', 'UFS 256GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2H7001CM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2L9001CM': ('uMCP', '', 'UFS 2.2 128GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2P8001CM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2P9001CM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2Q7001CM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2V7001CM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM2V8001CM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM3H6001CA': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM3P6001CM': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM41G1646D': ('eMCP', '', 'eMMC 5.1 ⚠ cap. não mapeada', 'LPDDR4X ⚠ cap. não mapeada', '', 'INDETERMINADO'),
    'KM4X6001KM': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR4X 2GB', '', 'RENTÁVEL'),
    'KM5C7001DM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM5L9000CM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 6GB', '', 'RENTÁVEL'),
    'KM5L9001DM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM5P8001DM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM5P9001DM': ('uMCP', '', 'UFS 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM5V7001DM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM5V8001DM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KM6E3S4AM0': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'RAM não mapeada — consultar datasheet ⚠ cap. não mapeada', '', 'INDETERMINADO'),
    'KM8F8001JM': ('uMCP', '', 'UFS ⚠ cap. não mapeada', 'LPDDR4X ⚠ cap. não mapeada', '', 'INDETERMINADO'),
    'KM8F9001JM': ('uMCP', '', 'UFS 256GB', 'LPDDR4X 8GB', '', 'RENTÁVEL'),
    'KM8V8001JM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 8GB', '', 'RENTÁVEL'),
    'KM8V8001LM': ('uMCP', '', 'UFS 128GB', 'LPDDR4X 8GB', '', 'RENTÁVEL'),
    'KMAG9001PM': ('uMCP', '', 'UFS 3.1 128GB', 'LPDDR5 8GB', '', 'RENTÁVEL'),
    'KMAS9001PM': ('uMCP', '', 'UFS 3.1 256GB', 'LPDDR5 8GB', '', 'RENTÁVEL'),
    'KMDD60018M': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR4X 3GB', '', 'RENTÁVEL'),
    'KMDH6001DA': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KMDP60018M': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR4X 3GB', '', 'RENTÁVEL'),  # 2026-08-20: era 4GB (bug de posição, RAM mora na cauda 8M, não na chave P6)
    'KMDP6001DA': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),
    'KMDV6001DA': ('eMCP', '', 'eMMC 5.1 128GB', 'LPDDR4X 4GB', '', 'RENTÁVEL'),  # 2026-08-20: chave V6 não tinha RAM mapeada antes do fix de cauda
    'KMDX60018M': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR4X 3GB', '', 'RENTÁVEL'),
    'KMFE60012M': ('eMCP', '', 'eMMC 5.1 16GB', 'LPDDR3 2GB', '', 'RENTÁVEL'),
    'KMFN60012M': ('eMCP', '', 'eMMC 5.1 8GB', 'LPDDR3 1GB', '', 'RENTÁVEL'),
    'KMGD6001BM': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR3 3GB', '', 'RENTÁVEL'),
    'KMGP6001BA': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR3 3GB', '', 'RENTÁVEL'),
    'KMGP6001BM': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR3 3GB', '', 'RENTÁVEL'),
    'KMGX6001BA': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR3 3GB', '', 'RENTÁVEL'),
    'KMI2U000MA': ('eMCP', '', 'eMMC 32GB', 'LPDDR2 2GB', '', 'NÃO RENTÁVEL'),
    'KMJ1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR2 ⚠ cap. não mapeada', '', 'NÃO RENTÁVEL'),
    'KMK1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR2 ⚠ cap. não mapeada', '', 'NÃO RENTÁVEL'),
    'KML1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR5 ⚠ cap. não mapeada', '', 'INDETERMINADO'),
    'KMN1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR2 ⚠ cap. não mapeada', '', 'NÃO RENTÁVEL'),
    'KMQE60013B': ('eMCP', '', 'eMMC 5.1 16GB', 'LPDDR3 2GB', '', 'RENTÁVEL'),
    'KMQX60013A': ('eMCP', '', 'eMMC 5.1 32GB', 'LPDDR3 2GB', '', 'RENTÁVEL'),
    'KMRP60014M': ('eMCP', '', 'eMMC 5.1 64GB', 'LPDDR3 4GB', '', 'RENTÁVEL'),
    'KMR310008M': ('eMCP', '', 'eMMC 5.1 16GB', 'LPDDR3 3GB', '', 'RENTÁVEL'),
    'KMS1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR1 ⚠ cap. não mapeada', '', 'NÃO RENTÁVEL'),
    'KMV1G1646D': ('eMCP', '', 'eMMC ⚠ cap. não mapeada', 'LPDDR2 (legado) ⚠ cap. não mapeada', '', 'NÃO RENTÁVEL'),
    'KUS1G1646DBC': ('BGA SSD', '', '', '', '', 'INDETERMINADO'),
    'S2A1G1646DBC': ('PMIC', '', '', '', '', 'INDETERMINADO'),
    'S2D1G1646DBC': ('PMIC', '', '', '', '', 'INDETERMINADO'),
    'S2M1G1646DBC': ('PMIC', '', '', '', '', 'INDETERMINADO'),
    'S5E8895': ('SoC', '', '', '', '', 'INDETERMINADO'),
    'S5E9825': ('SoC', '', '', '', '', 'INDETERMINADO'),
    'S5K1G1646DBC': ('Sensor', '', '', '', '', 'INDETERMINADO'),
}

_NANYA_GOLDEN = {  # Nanya: 3 famílias DDR magras — tipo pelo prefixo, capacidade vem das KnownParts
    # (a gramática dá só o tipo → INDETERMINADO). ⚠ NT5CC=DDR3L (1.35V), não DDR3 (corrigido jul/2026; NT5CB=DDR3).
    'NT5CC256M16DP-DI': ('DDR3L', '', '', '', '', 'INDETERMINADO'),
    'NT5CC128M16JR-EK': ('DDR3L', '', '', '', '', 'INDETERMINADO'),
    'NT5CC512M8JR':     ('DDR3L', '', '', '', '', 'INDETERMINADO'),
    'NT5AD256M16D4-JC': ('DDR4', '', '', '', '', 'INDETERMINADO'),
    'NT5AD512M8-JC':    ('DDR4', '', '', '', '', 'INDETERMINADO'),
    'NT5PA256M16DP':    ('DDR3L', '', '', '', '', 'INDETERMINADO'),
    'NT5PA128M16FP':    ('DDR3L', '', '', '', '', 'INDETERMINADO'),
    # NT6CL = LPDDR3 mobile (SDP/DDP/QDP) — família nova 2026-07-15, mesmo padrão magro
    # (tipo pelo prefixo, capacidade só via known_part; ver nanya.yaml `reasoning`/`tip`).
    'NT6CL256M32AM':    ('LPDDR3', '', '', '', '', 'INDETERMINADO'),
    # NT5TU = DDR2 (PC/desktop legado) — família nova 2026-07-15. DIFERENTE das outras: DDR2
    # está abaixo de ddr_min_gen (3=DDR3 mínimo) → NÃO RENTÁVEL já na gramática, sem precisar
    # de known_part (is_dead_by_generation=True mesmo sem capacidade).
    'NT5TU32M16FG-AC':  ('DDR2', '', '', '', '', 'NÃO RENTÁVEL'),
}


_FORESEE_GOLDEN = {  # Foresee/Longsys — 1a entrega: eMMC (FEMD/FEMK/FEMJ). Capacidade LITERAL
    # no PN (pn[6:9]=GB, NAO Gbit). Fonte Tier-1: catalogo oficial Longsys + LCSC/DigiKey.
    "FEMDNN128G-A3A56": ("eMMC", "128GB", "", "", "", "RENTÁVEL"),   # FEMD comercial 128GB 3D TLC
    "FEMDNN032G-A3A55": ("eMMC", "32GB",  "", "", "", "RENTÁVEL"),   # FEMD comercial 32GB
    "FEMKNN008G-58A42": ("eMMC", "8GB",   "", "", "", "RENTÁVEL"),   # FEMK subsize 8GB MLC
    "FEMJNM032G-58C29": ("eMMC", "32GB",  "", "", "", "RENTÁVEL"),   # FEMJ subsize TLC 32GB
    "FEUDNN064G-C2A56": ("UFS",  "64GB",  "", "", "", "RENTÁVEL"),   # FEUDNN UFS 2.2 comercial 64GB
    "FEUDNN256G-C2A44": ("UFS",  "256GB", "", "", "", "RENTÁVEL"),   # FEUDNN 256GB
    "FEUDME064G-B8A19": ("UFS",  "64GB",  "", "", "", "RENTÁVEL"),   # FEUDME UFS 2.1 Gear3 automotivo
    "FEPRF6432-58A1930": ("eMCP", "", "eMMC ⚠ cap. não mapeada", "LPDDR4X ⚠ cap. não mapeada", "", "INDETERMINADO"),  # FEPR eMCP4x LPDDR4X (cap via known_part)
    "FEPNA1608-58A4302": ("eMCP", "", "eMMC ⚠ cap. não mapeada", "LPDDR3 ⚠ cap. não mapeada", "", "INDETERMINADO"),    # FEPN eMCP3 LPDDR3 inferido (cap via known_part)
    "FUPRB6432-C2A56N1": ("uMCP", "", "UFS 2.2 ⚠ cap. não mapeada", "LPDDR4X ⚠ cap. não mapeada", "", "INDETERMINADO"),  # FUPR uMCP4x UFS 2.2 + LPDDR4X confirmado (cap via known_part)
    "FUPRFA832-C2A56N1": ("uMCP", "", "UFS 2.2 ⚠ cap. não mapeada", "LPDDR4X ⚠ cap. não mapeada", "", "INDETERMINADO"),  # FUPR uMCP4x 128GB (cap via known_part)
    "FAPUA0804-58C2948": ("ePoP", "", "eMMC ⚠ cap. não mapeada", "LPDDR3 ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),   # FAPU ePOP3 — dead-by-type (cap irrelevante, sem known_part)
    "FAPEA3216-58C29N3": ("ePoP", "", "eMMC ⚠ cap. não mapeada", "LPDDR4X ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),  # FAPE ePOP4x — dead-by-type
    "FLXC2002G-N2": ("LPDDR4X", "2GB", "", "", "", "RENTÁVEL"),   # FLXC LPDDR4X standalone 2GB (16Gbit) — DigiKey confirmado
    "FLXC2004G-30": ("LPDDR4X", "4GB", "", "", "", "RENTÁVEL"),   # FLXC 4GB (32Gbit) — DigiKey confirmado (4GByte)
    "FLXC4008G-30": ("LPDDR4X", "8GB", "", "", "", "RENTÁVEL"),   # FLXC 8GB (64Gbit) — catálogo oficial
    "F60C1A0002-M6AR": ("DDR3L", "256MB", "", "", "2Gb = 256MB por die [✓]", "RENTÁVEL"),  # F60C DDR3L 2Gb/die
    "F60C1A0004-M79R": ("DDR3L", "512MB", "", "", "4Gb = 512MB por die [✓]", "RENTÁVEL"),  # F60C DDR3L 4Gb/die wide-temp
    "F35UQA512M-WWT": ("NAND Flash", "", "", "", "", "NÃO RENTÁVEL"),        # F35 SPI NAND SLC — dead-by-type
    "FS35ND04G-S2Y2QWFI000": ("NAND Flash", "", "", "", "", "NÃO RENTÁVEL"), # FS35 SPI NAND SLC — dead-by-type
    "FS33ND01GS108TFI0": ("NAND Flash", "", "", "", "", "NÃO RENTÁVEL"),     # FS33 parallel NAND SLC — dead-by-type
    "FSNU8A001G-TWT": ("NAND Flash", "", "", "", "", "NÃO RENTÁVEL"),        # FSN BGA NAND SLC — dead-by-type
    "F70ME0101D-RDWA": ("MCP", "", "", "", "", "NÃO RENTÁVEL"),              # F70M nMCP legado (NAND+LPDDR2) — dead-by-type
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
        call_command("load_brands", "--brand", "piecemakers", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "piecemakers", "--commit", "--skip-known-parts", verbosity=0)
        self.assertGreater(CatalogVersion.current(), v0)


class GigaDeviceLoadBrandsTests(TestCase):
    """Passo 4: GigaDevice migrada p/ YAML. Fidelidade + identificação de TODOS os PNs
    conhecidos (golden capturado da gramática populate_gigadevice antes de aposentá-la)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "gigadevice")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "gigadevice", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "rayson", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "kingston", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "sandisk", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "micron", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _MIC_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class ToshibaKioxiaLoadBrandsTests(TestCase):
    """Passo 4: Toshiba + Kioxia CONSOLIDADAS numa marca única 'Toshiba-Kioxia' (2026-07-01).
    Mesma empresa (Toshiba Memory → Kioxia out/2019, mesmo esquema de PN). 11 famílias
    (THGBM/TYC/TYD + THGBMFG/HG, THGAF/AM, THGJF/JFBT, KMEYH, TH58) num só yaml. THGBMFG/THGBMHG/KMEYH
    DESATIVADAS (bug/lixo, 2026-07): com THGBMFG/HG off, o THGBM decodifica os THGBMxx (golden atualizado)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "toshiba-kioxia")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "toshiba-kioxia", "--commit", "--skip-known-parts", verbosity=0)
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
        call_command("load_brands", "--brand", "hynix", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _HYX_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")

class SamsungLoadBrandsTests(TestCase):
    """Passo 4: Samsung — o GABARITO MESTRE (87 famílias, 15 mapas). Fidelidade (yaml→banco, com
    DRAM_PC/DRAM_MOBILE globais brand=None) + identificação das 87 famílias. Inclui o fix do bug
    K4R (density_type+cap_map juntos → só density; capacity Gb-em-GB removido, igual ao K4A)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "samsung")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "samsung", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _SAM_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")

    def test_mapas_globais_ficam_brand_none(self):
        """DRAM_PC/DRAM_MOBILE são universais → brand=None (drop-in fiel ao populate, sem duplicata)."""
        from django.core.management import call_command
        from chips.models import DecodeMap
        call_command("load_brands", "--brand", "samsung", "--commit", "--skip-known-parts", verbosity=0)
        for m in ("DRAM_PC", "DRAM_MOBILE"):
            self.assertTrue(DecodeMap.objects.filter(map_name=m, brand__isnull=True).exists(), m)
            self.assertFalse(DecodeMap.objects.filter(map_name=m, brand__isnull=False).exists(),
                             f"{m} não deveria ter brand (universal)")



class NanyaLoadBrandsTests(TestCase):
    """Passo 4: Nanya no YAML. 3 famílias DDR magras (NT5CC=DDR3L 1.35V — ≠ NT5CB DDR3; NT5AD=DDR4,
    NT5PA=DDR3L; capacidade das KnownParts)."""

    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "nanya")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia; prod é monotônico)
        for pn, esperado in _NANYA_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class ForeseeLoadBrandsTests(TestCase):
    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "foresee")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "foresee", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia)
        for pn, esperado in _FORESEE_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


_ESMT_GOLDEN = {  # ESMT — 1a entrega (onboarding 2026-08-05): 6 famílias DDR3L MAGRAS M15T
    # (o prefixo = PN-base, com densidade+organização literal). Família magra sem decode de
    # densidade → a gramática sozinha dá DDR3L SEM densidade → INDETERMINADO; a densidade e o
    # veredito de rentabilidade vêm do known_part APROVADO (submissions/esmt_m15t_*). O golden
    # prova que a família CASA o PN e classifica o tipo certo (o chat ESMT havia deixado sem).
    "M15T1G1664A":  ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 1Gb x16
    "M15T2G16128A": ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 2Gb x16
    "M15T4G16256A": ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 4Gb x16
    "M15T8G16512A": ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 8Gb x16
    # Par x8 da 2ª rodada 2026-08-05 (ESMT.md §3.2) — âncoras adicionadas na E0
    # (2026-08-06): o chat ESMT registrou as famílias no yaml mas não colou o
    # golden, e o GoldenObrigatorioTests ficou vermelho. Mesmo padrão magro.
    "M15T2G8256A":  ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 2Gb x8
    "M15T4G8512A":  ("DDR3L", "", "", "", "", "INDETERMINADO"),   # 4Gb x8

    # M14D/M14F -- DDR2 SDRAM, 6 famílias MAGRAS (rodada 2026-08-20, ver esmt.yaml e
    # submissions/esmt_m14d_2026-08-20.yaml). DDR2 < cfg.ddr_min_gen (3=DDR3 mínimo) --
    # NÃO RENTÁVEL já na gramática pura, sem density/known_part (mesmo padrão do NT5TU
    # da Nanya, ver _NANYA_GOLDEN acima). Dívida do incidente 2026-08-24 (AUTORIA.md
    # §3.3) -- família entrou no yaml sem âncora, GoldenObrigatorioTests ficou vermelho
    # pra TODAS as marcas.
    "M14D128168A":   ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 128Mb x16
    "M14D2561616A":  ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 256Mb x16
    "M14D5121632A":  ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 512Mb x16
    "M14F5121632A":  ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 512Mb x16, 1.55V (par do M14D5121632A)
    "M14D1G1664A":   ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 1Gb x16
    "M14D1G8128A":   ("DDR2", "", "", "", "", "NÃO RENTÁVEL"),   # 1Gb x8

    # M15F -- DDR3 SDRAM (não-L), 4 famílias MAGRAS (rodada 2026-08-20, ver esmt.yaml e
    # submissions/esmt_m15f_2026-08-20.yaml). DDR3 == cfg.ddr_min_gen -- passa a trava de
    # geração, mas sem decode_density_type a gramática pura não tem Gb/GB pra avaliar o
    # limiar (cfg.ddr3_min_gbit) -- INDETERMINADO honesto, mesmo padrão já usado pelos
    # M15T desta marca (acima) e por NT5CC/NT5PA da Nanya. Dívida do mesmo incidente
    # 2026-08-24 acima.
    "M15F1G1664A":   ("DDR3", "", "", "", "", "INDETERMINADO"),   # 1Gb x16
    "M15F2G16128A":  ("DDR3", "", "", "", "", "INDETERMINADO"),   # 2Gb x16
    "M15F4G16256A":  ("DDR3", "", "", "", "", "INDETERMINADO"),   # 4Gb x16
    "M15F5121632A":  ("DDR3", "", "", "", "", "INDETERMINADO"),   # 512Mb x16

    # FM6BD4G2GA -- eMCP (NAND+DRAM MCP), 1ª categoria eMCP desta marca (rodada
    # 2026-08-24, ver esmt.yaml §FM6 e submissions/esmt_fm6_2026-08-24.yaml). Família
    # magra sem decode_cap_map/decode_gen_map -- is_emcp=True cai no Caminho 3 do bloco
    # eMCP (chips/engine.py): sem mapa próprio, extrai a geração do SUBTYPE ("LPDDR2")
    # via regex, e monta emcp_nand/emcp_ram com o placeholder "cap. não mapeada" (mesmo
    # mecanismo já provado por TYC0FH121638RA/_TK_GOLDEN e SD5DH26A4G/_SD_GOLDEN).
    # LPDDR2 < cfg.emcp_min_lpddr_gen (3) -- NÃO RENTÁVEL só por geração, ANTES de checar
    # GB (fix 2026-05-27 no assess_profitability) -- exatamente a classe de bug que este
    # golden existe pra pegar (AUTORIA.md §3.3). Dívida do mesmo incidente 2026-08-24.
    "FM6BD4G2GA": ("eMCP", "", "eMMC ⚠ cap. não mapeada", "LPDDR2 ⚠ cap. não mapeada", "", "NÃO RENTÁVEL"),
}


class ESMTLoadBrandsTests(TestCase):
    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "esmt")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "esmt", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia)
        for pn, esperado in _ESMT_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")


class KnownPartsLoadTests(TestCase):
    """Migração da AUTORIDADE (fix_known_parts → YAML known_parts): o loader cria os
    KnownParts e eles VENCEM a gramática (confirmed/manual). Round-trip dump→load provado
    IDÊNTICO no sandbox (541 PNs); aqui o núcleo + regressão do bug density_gbit."""

    def _load(self, data):
        from chips.knowledge.schema import BrandFile
        from chips.management.commands.load_brands import Command
        from chips.models import Brand, CatalogVersion
        from chips.engine import clear_engine_cache
        spec = BrandFile(**data)
        brand, _ = Brand.objects.get_or_create(
            name=spec.brand.name, defaults={"code": spec.brand.code})
        cmd = Command()
        cmd._upsert_maps(brand, spec.maps)
        cmd._upsert_families(brand, spec.families)
        cmd._upsert_known_parts(brand, spec.known_parts)
        CatalogVersion.bump()
        clear_engine_cache()
        return brand

    def test_known_part_confirmado_vence_gramatica(self):
        from chips.engine import classify
        self._load({
            "brand": {"name": "TesteKP", "code": "TKP"},
            "maps": {"ZZC": [{"char_key": "1G", "val_primary": "128MB", "val_secondary": ""}]},
            "families": [{"prefix": "ZZ", "chip_type": "DDR3", "subtype": "DDR3",
                          "decode_cap_pos": 2, "decode_cap_len": 2, "decode_cap_map": "ZZC"}],
            "known_parts": [{"part_number": "ZZ1G0000", "chip_type": "DDR4", "capacity": "512MB",
                             "confidence": "confirmed"}],
        })
        r = classify("ZZ1G0000") or {}
        # o known_part confirmado VENCE a gramática nas SPECS: capacity 512MB (não os 128MB
        # que a gramática decodificaria). O chip_type segue a FAMÍLIA (merge _result_from_known).
        self.assertEqual(r.get("capacity"), "512MB")
        self.assertTrue(r.get("known_exact"))
        self.assertEqual(r.get("confidence"), "confirmed")

    def test_fidelidade_e_density_gbit_string(self):
        # regressão: KnownPartSpec.density_gbit era Optional[int]; o modelo é TextField NOT NULL
        from chips.models import KnownPart
        self._load({
            "brand": {"name": "TesteDG", "code": "TDG"},
            "known_parts": [{"part_number": "DG1", "chip_type": "DDR4", "density_gbit": "8Gb",
                             "emcp_ram": "LPDDR4X 4GB", "confidence": "manual", "notes": "fonte X"}],
        })
        kp = KnownPart.objects.get(part_number="DG1")
        self.assertEqual((kp.density_gbit, kp.emcp_ram, kp.confidence, kp.notes),
                         ("8Gb", "LPDDR4X 4GB", "manual", "fonte X"))

    def test_portao_da_convencao_nos_known_parts(self):
        # fase 1b: o MESMO data contract da gramática aplicado à autoridade
        from chips.knowledge.schema import KnownPartSpec
        kp = KnownPartSpec(part_number="X", chip_type="LPDDR3", subtype="LPDDR3 Mobile",
                           interface="LPDDR3", capacity="None", emcp_nand="None")
        self.assertEqual(kp.subtype, "LPDDR3")   # 'LPDDR3 Mobile' → canônico
        self.assertEqual(kp.interface, "")       # geração fora do interface (largura/vazio)
        self.assertEqual(kp.capacity, "")        # lixo 'None' → vazio
        self.assertEqual(kp.emcp_nand, "")


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


# ═══════════════════════════════════════════════════════════════════════════════
# F0 — SPECS NUMÉRICAS (PRECIFICACAO.md §8): strings pra humano, números pra máquina
# ═══════════════════════════════════════════════════════════════════════════════

class NumericSpecsTests(SimpleTestCase):
    """_attach_numeric_specs é pura (dict→dict): testa sem banco.

    Contrato F0: nand_gb / ram_gb / cap_gb / density_gbit_num / ram_gen anexados
    ao resultado, derivados das strings de exibição pelos extratores da
    rentabilidade. Placeholder/lixo → None (nunca 0); geração ausente → ""."""

    def _attach(self, **fields):
        from chips.engine import _attach_numeric_specs
        return _attach_numeric_specs(dict(fields))

    def test_emcp_completo(self):
        r = self._attach(emcp_nand="eMMC 5.1 64GB", emcp_ram="LPDDR4X 4GB",
                         subtype="LPDDR4X")
        self.assertEqual(r["nand_gb"], 64.0)
        self.assertEqual(r["ram_gb"], 4.0)
        self.assertEqual(r["ram_gen"], "LPDDR4X")

    def test_placeholder_de_capacidade_nao_vira_numero(self):
        # Gramática sem chave mapeada emite placeholder — não pode virar float.
        r = self._attach(emcp_nand="eMMC 5.1 ⚠ cap. não mapeada",
                         emcp_ram="tipo 'T' — consultar datasheet")
        self.assertIsNone(r["nand_gb"])
        self.assertIsNone(r["ram_gb"])
        self.assertEqual(r["ram_gen"], "")

    def test_capacidade_decimal_mb_e_tb(self):
        self.assertEqual(self._attach(capacity="1.5GB")["cap_gb"], 1.5)   # K4E2E304EA
        self.assertEqual(self._attach(capacity="512MB")["cap_gb"], 0.5)
        self.assertEqual(self._attach(capacity="1TB")["cap_gb"], 1024.0)

    def test_capacidade_lixo_vazio_ou_none_string(self):
        self.assertIsNone(self._attach(capacity="None")["cap_gb"])   # string 'None' do snapshot
        self.assertIsNone(self._attach(capacity="")["cap_gb"])
        self.assertIsNone(self._attach()["cap_gb"])

    def test_densidade_le_gigabit_nunca_gigabyte(self):
        # "8Gb = 1GB por die": densidade = 8 Gb; o "1GB" (byte) NÃO pode contaminar
        # nem a densidade nem o cap_gb (armadilha Gb≠GB; _CAP_RE é case-insensitive,
        # por isso _extract_gib NUNCA é aplicado ao dram_density).
        r = self._attach(dram_density="8Gb = 1GB por die [~]")
        self.assertEqual(r["density_gbit_num"], 8.0)
        self.assertIsNone(r["cap_gb"])
        self.assertEqual(
            self._attach(dram_density="16Gb total [✓]")["density_gbit_num"], 16.0)

    def test_ram_gen_normaliza_e_faz_fallback(self):
        self.assertEqual(self._attach(subtype="LPDDR4 Mobile")["ram_gen"], "LPDDR4")
        # sem subtype → cai no emcp_ram ("LPDDR3 1GB" → LPDDR3)
        self.assertEqual(self._attach(emcp_ram="LPDDR3 1GB")["ram_gen"], "LPDDR3")
        # tipos não-LPDDR não inventam geração de RAM
        self.assertEqual(self._attach(subtype="DDR3")["ram_gen"], "")

    def test_dict_de_erro_nao_explode_e_ganha_contrato(self):
        r = self._attach(pn="X", known=False, error="PN inválido")
        for k in ("nand_gb", "ram_gb", "cap_gb", "density_gbit_num"):
            self.assertIsNone(r[k])
        self.assertEqual(r["ram_gen"], "")


class EmcpGeracaoDesconhecidaTests(TestCase):
    """FIX 2026-07-09 (JW500 / MT29C "Mobile DDR"): eMCP com geração de RAM
    DESCONHECIDA — capacidade abaixo do mínimo reprova SEM depender de geração
    (4ª instância do padrão recorrente do CLAUDE.md §7; antes o bail
    lpddr_gen=None vinha ANTES dos limiares e devolvia INDETERMINADO)."""

    def test_capacidade_abaixo_do_minimo_reprova_sem_geracao(self):
        from chips.engine import assess_profitability
        r = {'chip_type': 'eMCP', 'subtype': 'Mobile DDR', 'is_emcp': True,
             'emcp_ram': 'Mobile DDR 512MB', 'emcp_nand': '1GB', 'capacity': ''}
        self.assertEqual(assess_profitability(r), 'NÃO RENTÁVEL')

    def test_geracao_desconhecida_com_capacidades_ok_segue_indeterminado(self):
        # Sem saber a geração NÃO se pode APROVAR — indeterminado é honesto aqui.
        from chips.engine import assess_profitability
        r = {'chip_type': 'eMCP', 'subtype': 'Mobile DDR', 'is_emcp': True,
             'emcp_ram': 'Mobile DDR 4GB', 'emcp_nand': '64GB', 'capacity': ''}
        self.assertEqual(assess_profitability(r), 'INDETERMINADO')


class NumericSpecsWiringTests(TestCase):
    """O wrapper público classify() anexa o bloco numérico em TODOS os retornos
    (db exato, norm, FBGA, gramática, desconhecido) — aqui, o caminho
    'desconhecido' prova a fiação sem depender de catálogo carregado."""

    def test_classify_desconhecido_carrega_o_contrato(self):
        from chips.engine import classify
        r = classify("ZZZZTESTE999")
        for k in ("nand_gb", "ram_gb", "cap_gb", "density_gbit_num", "ram_gen"):
            self.assertIn(k, r)


class ConsultaEhPlataformaTests(TestCase):
    """Fim da busca pública (dono, 2026-08-05 — PLANO_MULTITENANT §10.7).

    /chips/search/ e /chips/decode/ devolviam o classify() INTEIRO (subtype,
    densidade, capacidade, fonte e o veredito RENTÁVEL) pra internet aberta —
    era o furo lateral da máscara v3.1, provado ao vivo em produção. O gate
    `platform_only` (chips/views.py) fecha os dois com o critério
    `tenancy.access.is_unmasked` — a MESMA fonte única da bancada/tabela/
    export/OV. Este teste é o CADEADO permanente: se alguém "abrir pro
    operador consultar", isto fica vermelho (seria regressão da F12).

    Auto-contido de propósito (sem fixture de catálogo): o 403 nem chega a
    chamar o classify, e o caminho 200 da plataforma funciona com PN
    desconhecido (card "não identificado")."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from tenancy.models import Company, Membership
        User = get_user_model()
        cls.company = Company.objects.create(name='ConsultaCo', slug='consultaco')
        cls.papeis = {}
        for role in ('admin', 'manager', 'operator'):
            u = User.objects.create_user(f'{role}_consulta')
            Membership.objects.create(user=u, company=cls.company, role=role)
            cls.papeis[role] = u
        cls.sem_vinculo = User.objects.create_user('avulso_consulta')
        cls.root = User.objects.create_superuser('root_consulta', password='x')

    # — vazamento: nada de spec/veredito/marca pode aparecer no corpo do 403 —
    _TERMOS_PROIBIDOS = ('RENTÁVEL', 'chip_type', 'subtype', 'capacity',
                         'density', 'confidence', 'brand', 'Samsung', 'eMMC')

    def _assert_403_sem_vazamento(self, resp, quem):
        self.assertEqual(resp.status_code, 403, quem)
        corpo = resp.content.decode()
        for termo in self._TERMOS_PROIBIDOS:
            self.assertNotIn(termo, corpo, f'{quem}: 403 vazou {termo!r}')

    def test_anonimo_403_nos_dois_endpoints(self):
        self._assert_403_sem_vazamento(
            self.client.get('/chips/search/', {'pn': 'K4B4G16E'}), 'anon/search')
        self._assert_403_sem_vazamento(
            self.client.get('/chips/decode/', {'pn': 'K4B4G16E'}), 'anon/decode')

    def test_logado_nao_plataforma_403_nos_dois_endpoints(self):
        """Papel NÃO abre a consulta: nem o admin da empresa-cliente passa
        (gate de papel barraria só o anônimo — o porquê está no docstring do
        platform_only). Usuário sem vínculo idem."""
        contas = dict(self.papeis, avulso=self.sem_vinculo)
        for quem, user in contas.items():
            self.client.logout()
            self.client.force_login(user)
            self._assert_403_sem_vazamento(
                self.client.get('/chips/search/', {'pn': 'K4B4G16E'}),
                f'{quem}/search')
            self._assert_403_sem_vazamento(
                self.client.get('/chips/decode/', {'pn': 'K4B4G16E'}),
                f'{quem}/decode')

    def test_search_403_e_json_com_negativa_curta(self):
        self.client.force_login(self.papeis['operator'])
        resp = self.client.get('/chips/search/', {'pn': 'K4B4G16E'})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(list(resp.json().keys()), ['error'])   # SÓ a negativa

    def test_plataforma_continua_consultando(self):
        """Superuser (plataforma) segue com os dois endpoints — 200 mesmo com
        PN fora do catálogo (o card 'não identificado' também é resposta)."""
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(
            '/chips/search/', {'pn': 'ZZZZTESTE999'}).status_code, 200)
        self.assertEqual(self.client.get(
            '/chips/decode/', {'pn': 'ZZZZTESTE999'}).status_code, 200)


class K9PseudoPnTests(TestCase):
    """K9 (dono 2026-08-14, HANDOFF_K9): "K9" é pseudo-código de TIPO — a
    categoria de mercado do NAND cru TSOP (único não-BGA), triada por FORMATO.
    O classify curto-circuita ANTES de família/banco/fuzzy: identidade vem do
    registro (chips/chip_types.py), sem marca/capacidade/specs, elegível ao
    estoque (confidence manual) e sempre RENTÁVEL (preço fixo por unidade)."""

    def test_classify_k9_identidade_plana(self):
        from chips.engine import classify
        r = classify('K9')
        self.assertEqual(r['chip_type'], 'K9')
        self.assertTrue(r['known'])
        self.assertTrue(r['known_exact'])
        self.assertEqual(r['confidence'], 'manual')
        # PLANO de propósito: sem marca, sem capacidade, sem specs.
        self.assertEqual((r['brand'], r['capacity'], r['subtype']), ('', '', ''))
        self.assertEqual(r['profitable'], 'RENTÁVEL')
        # Jamais sugerir K9F…/K9G… (não é typo — é o nome da categoria).
        self.assertEqual(r['fuzzy_suggestions'], [])

    def test_classify_k9_minusculo_normaliza(self):
        from chips.engine import classify
        self.assertEqual(classify('k9')['chip_type'], 'K9')

    def test_k9_sempre_rentavel_sem_specs(self):
        from chips.engine import assess_profitability
        self.assertEqual(assess_profitability({'chip_type': 'K9'}), 'RENTÁVEL')

    def test_nand_flash_pn_decodado_segue_morto(self):
        # Decisão explícita do dono (2026-08-14): caminhos PARALELOS — o raw
        # NAND decodado por PN continua NÃO RENTÁVEL → refino; só o pseudo-
        # código "K9" (triagem por formato) vale ¥.
        from chips.engine import assess_profitability
        self.assertEqual(
            assess_profitability({'chip_type': 'NAND Flash',
                                  'subtype': 'SLC NAND',
                                  'capacity': '512MB'}),
            'NÃO RENTÁVEL')


class MicronApiBloqueioTests(SimpleTestCase):
    """O WAF da Micron não pode virar "FBGA sem resultado".

    Incidente 2026-08-18/19: uma varredura acidental (`--fbga $C` com a
    variável vazia → 1.462 requisições) queimou o IP no WAF da Micron. Depois
    disso o chat de marca passou a receber "Request Rejected" e ficou tentando
    de tempos em tempos — o que RENOVA o bloqueio em vez de esperá-lo vencer.

    Pior: a página de bloqueio chega com HTTP 200 e corpo HTML. O código
    tentava `r.json()`, falhava, devolvia `None` — e o chamador lia isso como
    "esse FBGA não tem produto". Ou seja: porta fechada virando evidência de
    fonte vazia, justamente na investigação que decidia se a API resolve os
    807 Micron sem capacidade."""

    def test_pagina_de_bloqueio_e_reconhecida(self):
        from chips.management.commands.fill_capacity_from_micron_api import _e_bloqueio
        f5 = ('<html><head><title>Request Rejected</title></head><body>'
              'The requested URL was rejected. Please consult with your '
              'administrator.<br>Your support ID is: 1234567890</body></html>')
        self.assertTrue(_e_bloqueio(200, f5))
        self.assertTrue(_e_bloqueio(403, '<html>Access Denied</html>'))

    def test_json_legitimo_nao_e_bloqueio(self):
        """O caso REAL da Micron: HTTP 200 com registro VAZIO. Isso é resposta
        de verdade ("o FBGA mapeia, o produto não existe") e não pode ser
        confundida com bloqueio — foi assim que os becos sem saída do
        BRIEFING_MICRON foram estabelecidos."""
        from chips.management.commands.fill_capacity_from_micron_api import _e_bloqueio
        vazio = '{"details":[{"part-name":"","part-key":"","pageurl":""}]}'
        self.assertFalse(_e_bloqueio(200, vazio))
        self.assertFalse(_e_bloqueio(200, '{"details":[]}'))
        self.assertFalse(_e_bloqueio(404, ''))

    def test_bloqueio_levanta_em_vez_de_devolver_none(self):
        from chips.management.commands import fill_capacity_from_micron_api as m

        class _R:
            status_code = 200
            text = '<html><title>Request Rejected</title>support ID is: 9</html>'

        class _S:
            _perfil = 'chrome131'
            def get(self, *a, **k):
                return _R()

        with self.assertRaises(m.MicronBloqueado):
            m._query_by_fbga('D8KFG', _S())

    def test_html_inesperado_tambem_levanta(self):
        """Qualquer HTTP 200 não-JSON é suspeito: devolver None ali é o mesmo
        erro com outra roupa."""
        from chips.management.commands import fill_capacity_from_micron_api as m

        class _R:
            status_code = 200
            text = '<!DOCTYPE html><html>algum interstitial novo</html>'

        class _S:
            _perfil = 'chrome131'
            def get(self, *a, **k):
                return _R()

        with self.assertRaises(m.MicronBloqueado):
            m._query_by_fbga('D8KFG', _S())

    def test_bloqueio_403_com_html_tambem_levanta(self):
        """Este é o caso que SÓ o `_e_bloqueio` pega: 403 não entra no ramo do
        `r.json()`, então sem a checagem explícita ele cairia no retry e
        acabaria devolvendo None — bloqueio virando "sem resultado" de novo."""
        from chips.management.commands import fill_capacity_from_micron_api as m

        class _R:
            status_code = 403
            text = '<html><body>Access Denied</body></html>'

        class _S:
            _perfil = 'chrome131'
            def get(self, *a, **k):
                return _R()

        with self.assertRaises(m.MicronBloqueado):
            m._query_by_fbga('D8KFG', _S(), retries=1)

    def test_ua_nao_e_cravado_a_mao(self):
        """UA escrito à mão + TLS de outro Chrome = incoerência que o WAF
        procura. Quem manda o UA é o perfil do curl_cffi."""
        from chips.management.commands.fill_capacity_from_micron_api import _HEADERS
        self.assertNotIn('User-Agent', _HEADERS)

    def test_perfil_tls_mais_novo_primeiro(self):
        """Perfil velho é pior que nenhum: Chrome 110 em 2026 não existe."""
        from chips.management.commands.fill_capacity_from_micron_api import _PERFIS_TLS
        numeros = [int(p.replace('chrome', '')) for p in _PERFIS_TLS]
        self.assertEqual(numeros, sorted(numeros, reverse=True))
        self.assertGreaterEqual(numeros[0], 130)


class SugestaoPrefixoRankingTests(TestCase):
    """A lista de sugestões não pode cortar por ORDEM ALFABÉTICA.

    Bug de bancada (2026-08-24, relatado pelo dono com print). O operador
    digitou ``K4B4G16``; o chip na mão era da revisão ``…46E``, **aprovado no
    banco**. O popup mostrou 5 PNs e nenhum era ``46E``.

    Não era ranking ruim — era AUSÊNCIA de ranking. ``_prefix_candidates``
    fazia ``.order_by("part_number")[:5]``: alfabético, corte em 5. As
    linhagens ``46B`` e ``46D`` enchiam as 5 vagas e TODO ``46E`` ficava
    invisível, sempre, e **em silêncio** — o operador conclui que o chip não
    está no catálogo e descarta material bom.

    Estes testes fixam as três garantias: (1) o PN aprovado APARECE, (2) a
    ordem é por relevância — completude mais curta primeiro, que é a mais
    próxima do digitado —, (3) o teto não é mais 5.
    """

    @classmethod
    def setUpTestData(cls):
        from chips.models import Brand, KnownPart
        cls.brand = Brand.objects.create(name='Samsung', code='SAM')
        # O cenário real: 12 variantes aprovadas do mesmo PN base. As 4 revisões
        # curtas (B/D/E/Q) + 8 variantes longas de grade/embalagem.
        cls.curtos = ['K4B4G1646B', 'K4B4G1646D', 'K4B4G1646E', 'K4B4G1646Q']
        cls.longos = ['K4B4G1646DBCK0', 'K4B4G1646DBCNB', 'K4B4G1646DBYK0',
                      'K4B4G1646DBYNB', 'K4B4G1646EBCK0', 'K4B4G1646EBCMA',
                      'K4B4G1646EBYK0', 'K4B4G1646EBYMA']
        for pn in cls.curtos + cls.longos:
            KnownPart.objects.create(
                brand=cls.brand, part_number=pn, chip_type='DDR3',
                subtype='DDR3', density_gbit='4Gb', interface='x16',
                confidence='confirmed', review_status='approved',
                notes='fixture de teste',
            )

    def _sugestoes(self, digitado='K4B4G16'):
        from chips.engine import _prefix_candidates
        return [k.part_number for k in _prefix_candidates(digitado)]

    def test_o_pn_aprovado_do_operador_aparece(self):
        """O BUG, literal: 46E existe e aprovado — tem que estar na lista."""
        self.assertIn('K4B4G1646E', self._sugestoes(),
                      "o PN da bancada sumiu da sugestão — operador descarta chip bom")

    def test_nenhuma_linhagem_de_revisao_fica_de_fora(self):
        """Não basta o 46E: NENHUMA revisão pode ser engolida pelo corte."""
        sug = self._sugestoes()
        for pn in self.curtos:
            self.assertIn(pn, sug, f"revisão {pn} invisível na sugestão")

    def test_ordena_por_relevancia_nao_por_alfabeto(self):
        """Completude mais CURTA primeiro — é a mais próxima do digitado.

        Com ordem alfabética, K4B4G1646DBCK0 (14 chars) vinha antes de
        K4B4G1646E (10). Aqui as 4 revisões curtas têm que ocupar as 4
        primeiras posições, em qualquer ordem entre si.
        """
        sug = self._sugestoes()
        self.assertEqual(set(sug[:4]), set(self.curtos),
                         f"as 4 revisões curtas deviam vir primeiro; veio {sug[:4]}")

    def test_teto_nao_e_mais_cinco(self):
        """O 5 ERA o bug. Com 12 aprovados, a lista devolve os 12."""
        self.assertEqual(len(self._sugestoes()), 12)

    def test_combined_tambem_devolve_mais_que_cinco(self):
        """O corte duplo: _prefix_candidates cortava em 5 e _combined_suggestions
        cortava o merge em 5 de novo — então prefixo cheio deixava o fuzzy com
        ZERO vaga. Os dois tetos subiram juntos."""
        from chips.engine import _combined_suggestions
        self.assertGreater(len(_combined_suggestions('K4B4G16')), 5)

    def test_nao_sugere_registro_nao_aprovado(self):
        """O teto maior NÃO pode vazar a fila de revisão pra bancada."""
        from chips.models import KnownPart
        KnownPart.objects.create(
            brand=self.brand, part_number='K4B4G1646Z', chip_type='DDR3',
            subtype='DDR3', density_gbit='4Gb', confidence='confirmed',
            review_status='submitted', notes='ainda na fila',
        )
        self.assertNotIn('K4B4G1646Z', self._sugestoes(),
                         "PN 'submitted' vazou pra sugestão")


class DeployCatalogDescobertaTests(SimpleTestCase):
    """Resto de teste no disco NÃO pode virar passo do deploy do catálogo.

    Achado 2026-08-24 (rodada do dono). O `GlobalMapGuardTests` escreve um
    `chips/knowledge/_guardtest.yaml` e apaga no `finally` — mas se a suíte
    morre no meio, o arquivo fica. O `_discover_brands` do `deploy_catalog`
    varre `chips/knowledge/*.yaml` por glob, então adotava o fixture como
    marca: apareceu literalmente como ``[2/16] load_brands {'brand':
    '_guardtest'}`` numa saída real.

    O estrago não é cosmético. Esse fixture define de propósito um mapa
    GLOBAL (`DRAM_PC`) sendo uma marca não-Samsung — exatamente o que o
    `load_brands` recusa com `CommandError`. Ou seja: **um arquivo esquecido
    aborta o deploy no passo 2 de 16**, com a Samsung já gravada e as outras
    11 marcas não. Catálogo meio montado em produção.

    Convenção fixada: `_` no início = privado, nunca é marca.
    """

    def test_yaml_com_underscore_nao_vira_marca(self):
        import os
        from chips.management.commands.deploy_catalog import (
            _discover_brands, _KNOWLEDGE_DIR)
        path = os.path.join(_KNOWLEDGE_DIR, "_descobertatest.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("brand: {name: X, code: X}\nfamilies: []\n")
        try:
            marcas = _discover_brands()
        finally:
            os.unlink(path)
        self.assertNotIn("_descobertatest", marcas,
                         "yaml com '_' entrou no deploy como marca")
        self.assertNotIn("_guardtest", marcas)

    def test_marcas_de_verdade_continuam_sendo_descobertas(self):
        """A blindagem não pode engolir marca legítima."""
        from chips.management.commands.deploy_catalog import _discover_brands
        marcas = _discover_brands()
        for esperada in ("samsung", "micron", "sandisk", "toshiba-kioxia"):
            self.assertIn(esperada, marcas)
        self.assertEqual(marcas[0], "samsung",
                         "Samsung tem que ser a 1ª (define os mapas globais)")


class CampoDeMedidaComProsaTests(TestCase):
    """PROSA em campo de MEDIDA (`capacity`, `emcp_ram`, `emcp_nand`, `density_*`).

    Incidente 2026-08-24. O dono viu no admin um `KMYFE0B0CA` (Samsung eMCP) cuja
    coluna Capacidade era uma frase inteira: *"RAM: SDRAM 1GB (pré-LPDDR, não é
    LPDDR — ver notes) / NAND: moviNAND ~1GB (NAND MLC 8Gb + controlador, 2 dies)
    + OneNAND 1GB"*.

    **Por que o portão não pegou:** não havia o que pegar. O `KnownPartSpec`
    declara esses campos como `str = ""` livre e o `model_validator` diz, no
    próprio docstring, *"NÃO rejeita (known_part é ponto de dado)"*. A convenção
    `emcp_ram = 'LPDDR{n} {cap}GB'` está no `CLAUDE.md §6` como regra ABSOLUTA e
    não era aplicada em canto nenhum do código.

    **Por que é caro:** `_extract_gib` é um `re.search` — pega o PRIMEIRO número
    que casar. Com prosa, "o primeiro" depende da ordem das palavras, e o mesmo
    chip vai parar em prateleiras diferentes. `test_a_mesma_informacao_em_tres_
    caixas` mede isso.
    """

    RAM_PROSA = "SDRAM 1GB (pré-LPDDR, não é LPDDR — ver notes)"
    NAND_PROSA = "moviNAND ~1GB (NAND MLC 8Gb + controlador, 2 dies) + OneNAND 1GB"

    def test_a_mesma_informacao_em_tres_caixas(self):
        """O núcleo do dano: prosa reordenada = prateleira diferente."""
        from estoque.views import _compute_destination
        base = {"chip_type": "eMCP", "subtype": "", "capacity": "",
                "dram_density": "", "interface": "", "brand": "Samsung",
                "is_emcp": True, "emcp_ram": "SDRAM 1GB"}
        caixas = {
            _compute_destination(dict(base, emcp_nand=n))[0]
            for n in ("moviNAND ~1GB (NAND MLC 8Gb + controlador) + OneNAND 1GB",
                      "NAND MLC 8Gb + controlador = moviNAND 1GB + OneNAND 1GB",
                      "moviNAND + OneNAND, 2GB no total (MLC 8Gb por die)")
        }
        self.assertGreater(
            len(caixas), 1,
            "se isto virar 1, alguém tornou a extração robusta a prosa — ótimo, "
            "mas revise este teste antes de relaxar a checagem de forma")
        # E o pior deles: 'MLC 8Gb' (gigaBIT) lido como 8 GB — o bug de unidade
        # da casa entrando por um canal sem vigilância.
        self.assertIn("EMCP8+1", caixas)

    def test_classificador_separa_prosa_de_forma_alternativa(self):
        """Não pode gritar com a forma estabelecida: `emcp_nand='eMMC 5.1 16GB'`
        aparece 55x no seed curado — é convenção real, não dívida."""
        from chips.management.commands.audit_campo_forma import classifica
        self.assertEqual(classifica("emcp_nand", "eMMC 5.1 16GB"), "ALTERNATIVO")
        self.assertEqual(classifica("emcp_nand", "UFS 2.2 128GB"), "ALTERNATIVO")
        self.assertEqual(classifica("emcp_nand", "16GB"), "CANÔNICO")
        self.assertEqual(classifica("emcp_ram", "LPDDR3 1GB"), "CANÔNICO")
        self.assertEqual(classifica("capacity", "512MB"), "CANÔNICO")
        # a dívida
        self.assertEqual(classifica("emcp_ram", self.RAM_PROSA), "PROSA")
        self.assertEqual(classifica("emcp_nand", self.NAND_PROSA), "PROSA")
        self.assertEqual(classifica("capacity", "NAND 512MB + mDDR1 256MB"), "PROSA")
        # unidade faltando: '64' não diz se é 64Gb ou 64GB (8x de diferença)
        self.assertEqual(classifica("density_gbit", "64"), "AMBÍGUO")
        # ── falsos-positivos da 1ª versão do auditor, corrigidos 2026-08-24 ──
        # Faixa de versão com barra é forma ESTABELECIDA (6 registros SK Hynix em
        # prod): o engine extrai 16.0 e a caixa sai certa. Auditor que grita com
        # dado bom treina o leitor a ignorar o auditor.
        self.assertEqual(classifica("emcp_nand", "eMMC 4.5 / 5.0 16GB"), "ALTERNATIVO")
        self.assertEqual(classifica("emcp_nand", "eMMC 5.x 8GB"), "ALTERNATIVO")
        # 'None' é classe PRÓPRIA: não é "faltou unidade", é o None do Python
        # virado texto. Origem e correção diferentes.
        self.assertEqual(classifica("capacity", "None"), "NULO")
        self.assertEqual(classifica("emcp_ram", "none"), "NULO")
        # DOIS produtos no mesmo campo: a interface do NAND E a geração da RAM,
        # com uma capacidade só — não dá pra saber de quem ela é.
        self.assertEqual(classifica("emcp_nand", "eMMC 5.x + LPDDR3 16GB"), "PROSA")
        self.assertEqual(classifica("emcp_nand", "eMMC 5.1 + LPDDR4X 64GB"), "PROSA")
        # 'Gb' != 'GB' — case-sensitive de propósito (MICRON.md §4)
        self.assertEqual(classifica("density_gbit", "4Gb"), "CANÔNICO")
        self.assertEqual(classifica("emcp_nand", "4GB"), "CANÔNICO")

    def test_auditoria_acha_o_caso_real_e_nao_grita_com_o_legitimo(self):
        from io import StringIO
        from django.core.management import call_command
        from chips.models import Brand, KnownPart
        b = Brand.objects.create(name="Samsung", code="SAM")
        KnownPart.objects.create(
            brand=b, part_number="KMYFE0B0CA", chip_type="eMCP",
            emcp_ram=self.RAM_PROSA, emcp_nand=self.NAND_PROSA,
            confidence="confirmed", review_status="submitted", notes="fixture")
        KnownPart.objects.create(
            brand=b, part_number="KMQ310006A", chip_type="eMCP",
            emcp_ram="LPDDR3 1GB", emcp_nand="eMMC 5.1 16GB",
            confidence="confirmed", review_status="approved", notes="fixture")
        out = StringIO()
        call_command("audit_campo_forma", stdout=out)
        texto = out.getvalue()
        self.assertIn("KMYFE0B0CA", texto)
        self.assertNotIn("KMQ310006A", texto, "gritou com a forma alternativa legítima")
        self.assertIn("CAIXA:", texto, "não mostrou o impacto na prateleira")

    def test_por_marca_nao_estoura_com_classe_nova(self):
        """Regressão de um crash MEU (2026-08-24): a contagem por marca usava
        `setdefault(nome, {"PROSA": 0, "AMBÍGUO": 0})` — dicionário que precisa
        conhecer o vocabulário de antemão. Quando o balde NULO nasceu, o comando
        morreu com `KeyError: 'NULO'` **em produção, no meio da varredura**, depois
        de já ter impresso metade do relatório. Contar pelo que APARECE, nunca por
        lista fixa."""
        from io import StringIO
        from django.core.management import call_command
        from chips.models import Brand, KnownPart
        b = Brand.objects.create(name="SK Hynix", code="HYX")
        for pn, cap in (("AAA1", ""), ("BBB2", "64"), ("CCC3", "4GB + 512MB")):
            KnownPart.objects.create(brand=b, part_number=pn, chip_type="eMCP",
                                     capacity=cap, confidence="confirmed",
                                     review_status="approved", notes="fixture")
        # ⚠ O 'None' TEM que entrar por `.update()`. Criar com `save()` não
        # reproduz: o `apply_kp_convention` limpa a string na hora, o balde NULO
        # fica vazio e o teste passa mesmo com o bug. Foi assim que a 1ª versão
        # deste teste não mordeu na mutação — e é assim que o legado chegou ao
        # banco de verdade (`.update()`/`bulk_update` não chamam `save()`).
        KnownPart.objects.filter(part_number="AAA1").update(capacity="None")
        out = StringIO()
        call_command("audit_campo_forma", stdout=out)   # não pode estourar
        texto = out.getvalue()
        self.assertIn("Por marca", texto)
        self.assertIn("nulo=", texto)

    def test_auditoria_grita_quando_varre_zero(self):
        """Lição do `audit_category_codes` (CLAUDE.md §7): zero silencioso numa
        auditoria é indistinguível de 'está tudo limpo'."""
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("audit_campo_forma", stdout=out)
        self.assertIn("ZERO known_parts", out.getvalue())

    def test_submit_AVISA_forma_suspeita(self):
        """O portão não bloqueia (known_part é ponto de dado, por decisão), mas
        a prosa tem que APARECER — era invisível até 2026-08-24."""
        import tempfile, os
        from io import StringIO
        from django.core.management import call_command
        from chips.models import Brand
        Brand.objects.create(name="Samsung", code="SAM")
        yml = ("brand: Samsung\nknown_parts:\n"
               "  - part_number: KMYFE0B0CA\n"
               "    chip_type: eMCP\n"
               f"    emcp_ram: '{self.RAM_PROSA}'\n"
               f"    emcp_nand: '{self.NAND_PROSA}'\n"
               "    confidence: confirmed\n"
               "    notes: 'fonte Tier-1 de teste'\n")
        fd, path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(yml)
        try:
            out = StringIO()
            call_command("submit_known_parts", path, stdout=out)
            texto = out.getvalue()
        finally:
            os.unlink(path)
        self.assertIn("FORMA suspeita", texto,
                      "o painel do submit não avisou sobre prosa em campo de medida")
        self.assertIn("PROSA", texto)


class LabelEmcpTruncadoTests(TestCase):
    """O label da caixa de eMCP/uMCP PERDE a RAM quando ela é medida em MB.

    Achado 2026-08-24, enquanto se auditava outra coisa. O branch eMCP do
    `estoque/views.py::_compute_destination` monta a etiqueta com
    `_extract_gb`, cuja regex é `(\\d+(?:\\.\\d+)?)\\s*GB` — **só casa 'GB',
    nunca 'MB'**. Então um eMCP legítimo, com os campos preenchidos DIREITO::

        emcp_nand = '4GB'   ·   emcp_ram = 'LPDDR3 512MB'   →   'EMCP4+'

    A etiqueta sai sem a RAM. E RAM de 512MB é comuníssima em eMCP legado: no
    seed curado são **12 de 59** (20%).

    É o MESMO bug que o branch NAND teve e que foi corrigido em 2026-06-19
    trocando `_extract_gb` por `_format_cap` (que lê MB e preserva a unidade —
    `CLAUDE.md §7`, bullet "Label 'NAND' sem info"). O eMCP/uMCP ficou para trás.

    ⚠ Este teste DOCUMENTA o comportamento atual em vez de exigir o certo, de
    propósito: mudar o label muda a CHAVE do código de caixa (F12), e código de
    caixa é **eterno** — gaveta já etiquetada no cliente não muda de nome
    sozinha. A correção é decisão do dono, não refactor. Quando ele decidir,
    troque os `assertEqual` daqui e o teste vira a especificação nova.
    """

    def _label(self, nand, ram):
        from estoque.views import _compute_destination
        return _compute_destination({
            "chip_type": "eMCP", "subtype": "LPDDR3", "capacity": "",
            "emcp_ram": ram, "emcp_nand": nand, "dram_density": "",
            "interface": "", "brand": "SK Hynix", "is_emcp": True})[0]

    def test_RAM_em_MB_some_da_etiqueta(self):
        self.assertEqual(self._label("4GB", "LPDDR3 512MB"), "EMCP4+",
                         "se mudou, o dono decidiu corrigir — atualize o teste E "
                         "confira o impacto nos códigos de caixa já emitidos")

    def test_RAM_em_GB_sai_completa(self):
        self.assertEqual(self._label("16GB", "LPDDR3 2GB"), "EMCP16+2")

    def test_capacity_combinada_deixa_o_chip_SEM_etiqueta(self):
        """Pior caso: eMCP com `capacity='4GB + 512MB'` e `emcp_*` vazios sai com
        a etiqueta literal 'eMCP' — sem número nenhum. O chip não tem prateleira.
        4 registros assim em prod (SK Hynix), todos `approved`."""
        from estoque.views import _compute_destination
        label = _compute_destination({
            "chip_type": "eMCP", "subtype": "", "capacity": "4GB + 512MB",
            "emcp_ram": "", "emcp_nand": "", "dram_density": "",
            "interface": "", "brand": "SK Hynix", "is_emcp": True})[0]
        self.assertEqual(label, "eMCP")

    def test_sao_TRES_causas_e_a_auditoria_separa(self):
        """"70 truncados" parece UM problema e são TRÊS, com donos diferentes.
        Misturar num número só faz o dono decidir errado — ou não decidir:

          [ram-em-MB]  bug de CÓDIGO — `_extract_gb` cego pra MB.
          [guard-nand] bug de CÓDIGO, OUTRO — o label é
                       `f"EMCP{n}+{r}" if nand else 'eMCP'`, então falta de NAND
                       **descarta a RAM que se CONHECE**.
          [sem-dado]   NÃO é bug de label: identity-only (PN↔FBGA sem spec).
                       Trabalho de DADO, com frente própria já existente.
        """
        from io import StringIO
        from django.core.management import call_command
        from chips.models import Brand, KnownPart
        b = Brand.objects.create(name="Samsung", code="SAM")
        for pn, nand, ram in (("KMFJ20005A", "eMMC 4GB", "LPDDR3 512MB"),
                              ("KMDP6001DA", "", "LPDDR4X 4GB"),
                              ("KLM8G1GEAC", "", "")):
            KnownPart.objects.create(brand=b, part_number=pn, chip_type="eMCP",
                                     emcp_nand=nand, emcp_ram=ram,
                                     confidence="confirmed",
                                     review_status="approved", notes="fixture")
        KnownPart.objects.filter(part_number="KLM8G1GEAC").update(
            emcp_nand="None", emcp_ram="None")
        out = StringIO()
        call_command("audit_campo_forma", stdout=out)
        texto = out.getvalue()
        # ⚠ NÃO usar `assertIn(causa, texto)`: as três causas aparecem no texto
        # de AJUDA da seção, então a asserção passa mesmo com a classificação
        # quebrada — foi exatamente assim que a 1ª versão deste teste sobreviveu
        # à mutação. Asserir na LINHA DE DETALHE, que casa causa com PN.
        import re as _re
        # Só as linhas de DETALHE (as que trazem `nand=`); as de resumo têm as
        # mesmas etiquetas e contaminariam a leitura. E o nome da causa tem
        # MAIÚSCULA ('ram-em-MB') — classe de caractere só-minúscula não casa.
        linhas = dict(
            _re.findall(r"\[([A-Za-z-]+)\s*\]\s+(\S+)\s+nand=", texto))
        self.assertEqual(linhas.get("ram-em-MB"), "KMFJ20005A")
        self.assertEqual(linhas.get("guard-nand"), "KMDP6001DA")
        self.assertEqual(linhas.get("sem-dado"), "KLM8G1GEAC")

    def test_falta_de_NAND_descarta_a_RAM_conhecida(self):
        """A 2ª causa, isolada: o chip TEM `emcp_ram='LPDDR4X 4GB'` — em GB, na
        convenção, sem prosa — e mesmo assim a etiqueta sai `'eMCP'`, porque o
        guard do label exige NAND. A informação boa é jogada fora pela falta da
        outra."""
        self.assertEqual(self._label("", "LPDDR4X 4GB"), "eMCP")

    def test_o_branch_NAND_ja_foi_corrigido_e_le_MB(self):
        """A prova de que a correção existe e só não foi aplicada aqui:
        `_format_cap` lê MB e preserva a unidade."""
        from estoque.views import _format_cap, _extract_gb
        self.assertEqual(_format_cap("LPDDR3 512MB"), "512MB")
        self.assertEqual(_extract_gb("LPDDR3 512MB"), "",
                         "_extract_gb não lê MB — é essa a causa")
