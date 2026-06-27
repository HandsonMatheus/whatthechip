"""
Teste do decode de densidade Micron no engine (decode_density_type='micron').

Prova a regra central: o sufixo D{N} (dies/canais) NÃO multiplica a capacidade —
profundidade × largura já é a densidade total do dispositivo. Esse era o bug que
fazia MT53E768M32D4 (D9WRQ) virar 12GB em vez de 3GB.

Rodar:
    python manage.py test chips.test_micron_density --settings=core.settings_test
"""

from django.test import TestCase
from django.core.management import call_command

from chips.models import Brand, ChipFamily, KnownPart
from chips.engine import _result_from_family


class MicronDensityDecodeTests(TestCase):
    """decode_density_type='micron' decodifica capacidade pela fórmula depth×width."""

    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name="Micron", code="MIC")
        cls.fam = ChipFamily.objects.create(
            brand=cls.brand, prefix="MT53E", chip_type="LPDDR4X",
            subtype="LPDDR4X", interface="LPDDR4X",
            is_emcp=False, decode_density_type="micron",
        )

    def test_d9wrq_3gb_nao_12gb(self):
        # MT53E768M32D4DT (FBGA D9WRQ): 768M×32 = 24Gb = 3GB. Bug dava 12GB (×4 dies).
        r = _result_from_family("MT53E768M32D4DT", self.fam)
        self.assertEqual(r["capacity"], "3GB")

    def test_unidade_G_4gb(self):
        # MT53E1G32D4NQ: 1G×32 = 32Gb = 4GB (MICRON.md). Bug daria 16GB.
        r = _result_from_family("MT53E1G32D4NQ", self.fam)
        self.assertEqual(r["capacity"], "4GB")

    def test_d2_nao_multiplica(self):
        # MT53E512M32D2: 512M×32 = 16Gb = 2GB (não 4GB).
        r = _result_from_family("MT53E512M32D2XX", self.fam)
        self.assertEqual(r["capacity"], "2GB")

    def test_sub_gb_em_mb(self):
        # MT53E128M32: 128M×32 = 4Gb = 512MB.
        r = _result_from_family("MT53E128M32D1XX", self.fam)
        self.assertEqual(r["capacity"], "512MB")


class FixMicronLpddrSpecsCommandTests(TestCase):
    """O bulk command recalcula specs congeladas (bug de dies) mantendo o ouro
    (confidence/PN/fbga intactos)."""

    def test_corrige_specs_bugadas_mantendo_confirmed(self):
        brand = Brand.objects.create(name="Micron", code="MIC")
        kp = KnownPart.objects.create(
            brand=brand,
            part_number="MT53E1G32D4NQ-046 WT:E",   # D9WLQ → 1G×32÷8 = 4GB
            fbga_code="D9WLQ",
            chip_type="RAM",          # errado (genérico)
            subtype="LPDDR4X standalone",
            capacity="16 GB",         # errado (bug de dies: ×4)
            density_gbit="128",       # lixo do bug
            confidence="confirmed",
        )
        call_command("fix_micron_lpddr_specs")
        kp.refresh_from_db()
        # campos derivados corrigidos
        self.assertEqual(kp.capacity, "4 GB")
        self.assertEqual(kp.chip_type, "LPDDR4X")
        self.assertEqual(kp.subtype, "LPDDR4X")
        self.assertEqual(kp.density_gbit, "")
        # ouro intacto
        self.assertEqual(kp.confidence, "confirmed")
        self.assertEqual(kp.part_number, "MT53E1G32D4NQ-046 WT:E")
        self.assertEqual(kp.fbga_code, "D9WLQ")

    def test_idempotente_nao_toca_estimated(self):
        brand = Brand.objects.create(name="Micron", code="MIC")
        kp = KnownPart.objects.create(
            brand=brand, part_number="MT53E1G32D4NQ-046 WT:E", fbga_code="ZZZZZ",
            chip_type="RAM", capacity="16 GB", confidence="estimated",
        )
        call_command("fix_micron_lpddr_specs")   # default: só confirmed/manual
        kp.refresh_from_db()
        self.assertEqual(kp.capacity, "16 GB")   # estimated não é tocado por padrão

    def test_mt52l_e_lpddr3_nao_lpddr4(self):
        # Nomenclatura Micron: "52" = LPDDR3 (tier-1). MT52L NÃO pode virar LPDDR4.
        brand = Brand.objects.create(name="Micron", code="MIC")
        kp = KnownPart.objects.create(
            brand=brand, part_number="MT52L512M32D2PF-107 WT:B", fbga_code="AAAAA",
            chip_type="LPDDR", subtype="LPDDR4", capacity="2 GB", confidence="confirmed",
        )
        call_command("fix_micron_lpddr_specs")
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "LPDDR3")
        self.assertEqual(kp.subtype, "LPDDR3")

    def test_guard_emcp_real_nao_e_tocado(self):
        # eMCP DE VERDADE (tem nand/ram) com prefixo MT53 NÃO pode ser reclassificado.
        brand = Brand.objects.create(name="Micron", code="MIC")
        kp = KnownPart.objects.create(
            brand=brand, part_number="MT53D512M64D8HR-046 WT:B", fbga_code="BBBBB",
            chip_type="eMCP", emcp_nand="eMMC 5.1 32GB", emcp_ram="LPDDR4 4GB",
            confidence="confirmed",
        )
        call_command("fix_micron_lpddr_specs")
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "eMCP")        # real eMCP → intacto
        self.assertEqual(kp.emcp_nand, "eMMC 5.1 32GB")
