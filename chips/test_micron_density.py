"""
Teste do decode de densidade Micron no engine (decode_density_type='micron').

Prova a regra central: o sufixo D{N} (dies/canais) NÃO multiplica a capacidade —
profundidade × largura já é a densidade total do dispositivo. Esse era o bug que
fazia MT53E768M32D4 (D9WRQ) virar 12GB em vez de 3GB.

Rodar:
    python manage.py test chips.test_micron_density --settings=core.settings_test
"""

from django.test import TestCase

from chips.models import Brand, ChipFamily
from chips.engine import _result_from_family


class MicronDensityDecodeTests(TestCase):
    """decode_density_type='micron' decodifica capacidade pela fórmula depth×width."""

    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name="Micron", code="MIC")
        cls.fam = ChipFamily.objects.create(
            brand=cls.brand, prefix="MT53E", chip_type="RAM",
            subtype="LPDDR4X standalone", interface="LPDDR4X",
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
