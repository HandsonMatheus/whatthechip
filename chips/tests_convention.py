"""
chips/tests_convention.py — Contrato da convenção (chip_types.py).

Camada "registro" do contrato (§3.2 do plano): testa a FONTE ÚNICA pura, sem
banco. Deve ficar VERDE já na Fase 2 (não depende do refactor dos consumidores).

    python manage.py test chips.tests_convention --settings=core.settings_test
"""
from django.test import SimpleTestCase

from chips.chip_types import (
    CHIP_TYPES, CANONICAL_TYPES, GENERIC_TYPES, DEAD_TYPES,
    canonical_chip_type, profit_family, label_kind, is_commercial,
    is_generic, is_known, is_dead, spec_for,
)

_CATEGORIES = {
    "managed_nand", "managed_mcp", "nand_raw", "dram_pc", "dram_mobile",
    "dram_gpu", "dram_legacy", "dram_unknown", "catalog",
}
_LABEL_KINDS = {"emmc", "ufs", "emcp", "umcp", "nand", "ddr", "lpddr", "gddr",
                "sdram", "rdram", "none"}
_PROFIT_FAMILIES = {"emcp", "emmc", "ufs", "ddr", "lpddr", "gddr", "dead",
                    "indeterminado"}


class RegistryWellFormedTests(SimpleTestCase):
    """O registro é internamente consistente."""

    def test_specs_use_valid_enums(self):
        for tok, s in CHIP_TYPES.items():
            self.assertIn(s.category, _CATEGORIES, tok)
            self.assertIn(s.label_kind, _LABEL_KINDS, tok)
            self.assertIn(s.profit_family, _PROFIT_FAMILIES, tok)

    def test_canonical_tokens_are_idempotent(self):
        # canonical_chip_type de um token canônico específico devolve ele mesmo.
        for tok in CANONICAL_TYPES:
            self.assertEqual(canonical_chip_type(tok), tok, tok)

    def test_generic_and_canonical_disjoint(self):
        self.assertTrue(GENERIC_TYPES.isdisjoint(CANONICAL_TYPES))

    def test_emcp_umcp_flagged(self):
        self.assertTrue(spec_for("eMCP").is_emcp)
        self.assertTrue(spec_for("uMCP").is_emcp)

    def test_dram_discrete_carries_generation(self):
        for tok in ("DDR3", "DDR4", "LPDDR4X", "LPDDR5", "GDDR5"):
            self.assertTrue(spec_for(tok).carries_generation, tok)


class CanonicalChipTypeTests(SimpleTestCase):
    """Resolução de chip_type cru → token canônico (casos reais do banco)."""

    def test_generic_resolves_via_subtype(self):
        self.assertEqual(canonical_chip_type("RAM", "DDR3 SDRAM"), "DDR3")
        self.assertEqual(canonical_chip_type("RAM", "LPDDR4X Mobile"), "LPDDR4X")
        self.assertEqual(canonical_chip_type("LPDDR", "LPDDR4X Multi-Channel"), "LPDDR4X")
        self.assertEqual(canonical_chip_type("DDR", "DDR1"), "DDR1")
        self.assertEqual(canonical_chip_type("RAM", "GDDR3"), "GDDR3")

    def test_generic_without_signal_stays_generic(self):
        # Sem subtype que revele a geração → permanece genérico (validador sinaliza).
        self.assertEqual(canonical_chip_type("RAM", ""), "RAM")
        self.assertEqual(canonical_chip_type("LPDDR", ""), "LPDDR")
        self.assertEqual(canonical_chip_type("DDR", ""), "DDR")

    def test_junk_sdram_suffix_maps_to_generation(self):
        # "DDR4 SDRAM" → DDR4 (a geração ganha do sufixo SDRAM).
        self.assertEqual(canonical_chip_type("DDR4 SDRAM", ""), "DDR4")

    def test_case_and_alias(self):
        self.assertEqual(canonical_chip_type("emmc"), "eMMC")
        self.assertEqual(canonical_chip_type("EMCP"), "eMCP")
        self.assertEqual(canonical_chip_type("nand flash"), "NAND Flash")
        self.assertEqual(canonical_chip_type("nor"), "NOR Flash")

    def test_specific_tokens_passthrough(self):
        for tok in ("eMMC", "UFS", "uMCP", "DDR3L", "LPDDR3", "GDDR6", "SDRAM", "RDRAM"):
            self.assertEqual(canonical_chip_type(tok), tok, tok)

    def test_subtype_sdram_on_ddr_does_not_demote(self):
        # chip_type já específico (DDR3) com subtype "DDR3 SDRAM" → continua DDR3.
        self.assertEqual(canonical_chip_type("DDR3", "DDR3 SDRAM"), "DDR3")

    def test_unknown_fail_open(self):
        self.assertEqual(canonical_chip_type("QuantumRAM 9000"), "QuantumRAM 9000")
        self.assertEqual(canonical_chip_type(""), "")


class ProfitFamilyTests(SimpleTestCase):
    """Rentabilidade por tipo — inclui a decisão SDRAM/RDRAM/EDO = dead."""

    def test_legacy_dram_is_dead(self):
        for tok in ("SDRAM", "RDRAM", "EDO DRAM"):
            self.assertEqual(profit_family(tok), "dead", tok)
            self.assertTrue(is_dead(tok), tok)

    def test_raw_nand_and_catalog_dead(self):
        for tok in ("NAND Flash", "NOR Flash", "MCP", "ePoP"):
            self.assertTrue(is_dead(tok), tok)
        # OneNAND fica INDETERMINADO (preserva o comportamento antigo — não estava
        # no conjunto "dead"). Candidato a "dead" como o EDO, se o usuário decidir.
        self.assertEqual(profit_family("OneNAND"), "indeterminado")

    def test_dram_families(self):
        self.assertEqual(profit_family("DDR3"), "ddr")
        self.assertEqual(profit_family("DDR3L"), "ddr")
        self.assertEqual(profit_family("LPDDR4X"), "lpddr")
        self.assertEqual(profit_family("GDDR5"), "gddr")

    def test_managed_families(self):
        self.assertEqual(profit_family("eMCP"), "emcp")
        self.assertEqual(profit_family("uMCP"), "emcp")  # uMCP usa regras de eMCP
        self.assertEqual(profit_family("eMMC"), "emmc")
        self.assertEqual(profit_family("UFS"), "ufs")

    def test_soc_indeterminado(self):
        self.assertEqual(profit_family("SoC"), "indeterminado")


class LabelAndCommercialTests(SimpleTestCase):

    def test_label_kind(self):
        self.assertEqual(label_kind("DDR3"), "ddr")
        self.assertEqual(label_kind("LPDDR4X"), "lpddr")
        self.assertEqual(label_kind("GDDR5"), "gddr")
        self.assertEqual(label_kind("eMMC"), "emmc")
        self.assertEqual(label_kind("UFS"), "ufs")
        self.assertEqual(label_kind("eMCP"), "emcp")
        self.assertEqual(label_kind("uMCP"), "umcp")
        self.assertEqual(label_kind("NAND Flash"), "nand")

    def test_commercial_flags(self):
        self.assertTrue(is_commercial("eMMC"))
        self.assertTrue(is_commercial("DDR3"))
        self.assertTrue(is_commercial("NAND Flash"))
        self.assertFalse(is_commercial("NOR Flash"))
        self.assertFalse(is_commercial("RDRAM"))
        self.assertFalse(is_commercial("SoC"))

    def test_generic_known(self):
        self.assertTrue(is_generic("RAM"))
        self.assertTrue(is_generic("LPDDR"))
        self.assertFalse(is_generic("LPDDR4X"))
        self.assertTrue(is_known("eMMC"))
        self.assertTrue(is_known("emmc"))
        self.assertFalse(is_known("QuantumRAM 9000"))
