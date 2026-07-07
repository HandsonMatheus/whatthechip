"""
pricing/tests.py — F2: portão do modelo, herança, escopo por empresa e RLS.

Como rodar:
    python manage.py test pricing --settings=core.settings_test
    python manage.py test pricing.tests.PricingRLSTests          # Postgres-only
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from unittest import skipUnless

from chips.models import Brand
from tenancy.models import Company
from tenancy.scope import CompanyScopeMissing, company_scope

from .models import (Buyer, Price, PriceList, PricingConfig,
                     STATUS_NO_BUY, STATUS_QUOTED, STATUS_UNQUOTED)


def _setup_wuquan(company_name='eMiner F2', slug='eminer-f2'):
    """Empresa + comprador + marca + listas mínimas para os testes."""
    company = Company.objects.create(name=company_name, slug=slug)
    buyer = Buyer.all_companies.create(company=company, name=f'Wuquan {slug}',
                                       slug=f'wuquan-{slug}')
    samsung = Brand.objects.create(name=f'Samsung {slug}',
                                   code=f'S{slug[-4:]}'.upper())
    lista = PriceList.all_companies.create(buyer=buyer, brand=samsung)
    return company, buyer, samsung, lista


class PriceGateTests(TestCase):
    """O portão no MODELO (save→full_clean + constraints) barra estrutura errada."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand, cls.lista = _setup_wuquan()

    def _price(self, **kw):
        base = dict(price_list=self.lista, kind='emmc', gen='',
                    tier_value=Decimal('64'), tier_unit='GB',
                    status=STATUS_QUOTED, price_min=Decimal('6.00'),
                    price_max=Decimal('6.00'), quote_date=date(2026, 6, 29))
        base.update(kw)
        return Price.all_companies.create(**base)

    def test_preco_valido_salva_e_herda_company(self):
        p = self._price()
        self.assertEqual(p.company_id, self.company.pk)   # denormalizada da lista
        self.assertFalse(p.is_range)
        faixa = self._price(kind='emcp', gen='LPDDR4X', tier_value=Decimal('64'),
                            price_min=Decimal('13.50'), price_max=Decimal('16.50'))
        self.assertTrue(faixa.is_range)

    def test_kind_x_unidade_erra_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            self._price(kind='ddr', gen='DDR3', tier_unit='GB')   # die é Gb
        with self.assertRaises(ValidationError):
            self._price(kind='emmc', tier_unit='Gb')              # pacote é GB

    def test_kind_x_gen_erra_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            self._price(kind='emmc', gen='eMMC 5.1')     # eMMC: gen vazio
        with self.assertRaises(ValidationError):
            self._price(kind='emcp', gen='DDR3')         # eMCP: gen é LPDDRx
        with self.assertRaises(ValidationError):
            self._price(kind='lpddr', gen='LPDDR')       # genérico não keia preço

    def test_quoted_sem_valor_e_sem_preco_com_valor_rejeitados(self):
        with self.assertRaises(ValidationError):
            self._price(price_min=None, price_max=None)             # quoted sem USD
        with self.assertRaises(ValidationError):
            self._price(status=STATUS_NO_BUY)                       # no_buy com USD
        # os três estados de sem-preço/preço são distintos e válidos:
        self._price(kind='gddr', gen='GDDR5', tier_unit='Gb', status=STATUS_NO_BUY,
                    price_min=None, price_max=None)                 # "NO"
        self._price(kind='ufs', tier_value=Decimal('256'), status=STATUS_UNQUOTED,
                    price_min=None, price_max=None)                 # célula amarela

    def test_faixa_invertida_rejeitada(self):
        with self.assertRaises(ValidationError):
            self._price(price_min=Decimal('16.50'), price_max=Decimal('13.50'))

    def test_chave_duplicada_rejeitada(self):
        # A unicidade da chave é do BANCO (UniqueConstraint) — o full_clean do
        # portão NÃO consulta unique (o _default_manager escopado explodiria
        # fora de request; ver save()).
        self._price()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._price(price_min=Decimal('7.00'), price_max=Decimal('7.00'))


class PriceListInheritanceTests(TestCase):
    """Herança como DADO: 1 nível, mesmo comprador, sem ciclo, genérica única."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.samsung, cls.lista_samsung = _setup_wuquan(
            'eMiner F2H', 'eminer-f2h')
        cls.sk = Brand.objects.create(name='SK Hynix F2H', code='SKF2H')
        cls.nanya = Brand.objects.create(name='Nanya F2H', code='NYF2H')

    def test_heranca_valida_sk_espelha_samsung(self):
        sk = PriceList.all_companies.create(buyer=self.buyer, brand=self.sk,
                                            inherits_from=self.lista_samsung)
        self.assertEqual(sk.inherits_from, self.lista_samsung)

    def test_generica_herda_da_nanya_e_e_unica(self):
        nanya = PriceList.all_companies.create(buyer=self.buyer, brand=self.nanya)
        PriceList.all_companies.create(buyer=self.buyer, brand=None,
                                       inherits_from=nanya)     # a "UMA PÁGINA"
        # 2ª genérica: barrada pela UniqueConstraint condicional (no banco).
        with self.assertRaises(IntegrityError), transaction.atomic():
            PriceList.all_companies.create(buyer=self.buyer, brand=None)

    def test_heranca_de_outro_comprador_rejeitada(self):
        outro = Buyer.all_companies.create(company=self.company, name='Outro F2H',
                                           slug='outro-f2h')
        with self.assertRaises(ValidationError):
            PriceList.all_companies.create(buyer=outro, brand=self.sk,
                                           inherits_from=self.lista_samsung)

    def test_heranca_em_cadeia_rejeitada_1_nivel(self):
        meio = PriceList.all_companies.create(buyer=self.buyer, brand=self.sk,
                                              inherits_from=self.lista_samsung)
        with self.assertRaises(ValidationError):
            PriceList.all_companies.create(buyer=self.buyer, brand=self.nanya,
                                           inherits_from=meio)   # alvo já herda

    def test_auto_heranca_rejeitada(self):
        lista = PriceList.all_companies.create(buyer=self.buyer, brand=self.sk)
        lista.inherits_from = lista
        with self.assertRaises(ValidationError):
            lista.save()


class PricingScopeTests(TestCase):
    """Camada A no pricing: manager fail-closed + isolamento entre empresas."""

    @classmethod
    def setUpTestData(cls):
        cls.a, cls.buyer_a, _, cls.lista_a = _setup_wuquan('ScopeA', 'scope-a')
        cls.b, cls.buyer_b, _, _ = _setup_wuquan('ScopeB', 'scope-b')

    def test_sem_escopo_explode_fail_closed(self):
        with self.assertRaises(CompanyScopeMissing):
            list(Buyer.objects.all())
        with self.assertRaises(CompanyScopeMissing):
            list(Price.objects.all())

    def test_escopo_da_a_nao_ve_a_b(self):
        with company_scope(self.a):
            self.assertEqual(list(Buyer.objects.all()), [self.buyer_a])
            self.assertEqual(PriceList.objects.count(), 1)
        with company_scope(self.b):
            self.assertEqual(list(Buyer.objects.all()), [self.buyer_b])

    def test_comprador_de_plataforma_null_fica_invisivel(self):
        # Decisão F2 (PRECIFICACAO §12): company=NULL é reservado ao marketplace
        # futuro — o manager escopado NÃO o mostra (fail-closed até existir regra).
        Buyer.all_companies.create(company=None, name='Plataforma', slug='plat-f2')
        with company_scope(self.a):
            self.assertEqual(list(Buyer.objects.all()), [self.buyer_a])


class PricingConfigTests(TestCase):
    def test_singleton_com_defaults(self):
        cfg = PricingConfig.get_config()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(cfg.staleness_days, 90)
        self.assertEqual(cfg.default_scenario, 'mid')
        self.assertEqual(PricingConfig.get_config().pk, cfg.pk)   # idempotente


class PricingPghistoryTests(TestCase):
    """Preço é rastreado: toda mudança vira evento (gatilho Postgres)."""

    @skipUnless(connection.vendor == 'postgresql',
                'pghistory usa gatilhos Postgres (no-op no SQLite)')
    def test_update_de_preco_gera_evento(self):
        from django.apps import apps as django_apps
        _, _, _, lista = _setup_wuquan('PgHist', 'pghist-f2')
        p = Price.all_companies.create(
            price_list=lista, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('6.00'), price_max=Decimal('6.00'))
        p.price_min = p.price_max = Decimal('7.00')
        p.save()
        Ev = django_apps.get_model('pricing', 'PriceEvent')
        self.assertGreaterEqual(Ev.objects.filter(pgh_obj=p.pk).count(), 2)


def _r(**kw):
    """Dict no formato que o classify() emite (com as specs numéricas da F0)."""
    base = dict(chip_type='', subtype='', brand='', capacity=None,
                emcp_ram=None, emcp_nand=None, dram_density=None,
                nand_gb=None, ram_gb=None, cap_gb=None,
                density_gbit_num=None, ram_gen='')
    base.update(kw)
    return base


class PriceGoldenTests(TestCase):
    """F3 — goldens com os NÚMEROS REAIS da planilha do Wuquan (§9 do plano).

    Provam: chave por kind, faixa (cenários), LPDDR4≠4X, RAM fora da chave,
    3 estados de sem-preço, genérico→NO_KEY, fora-da-grade→NO_ROW, e a cadeia
    de herança inteira (marca → herança → genérica → herança da genérica)."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date, timedelta
        cls.company = Company.objects.create(name='GoldenCo', slug='golden-f3')
        cls.buyer = Buyer.all_companies.create(company=cls.company,
                                               name='Wuquan G', slug='wuquan-g')
        cls.samsung = Brand.objects.create(name='Samsung', code='SAMG3')
        cls.sk      = Brand.objects.create(name='SK Hynix', code='SKG3')
        cls.nanya   = Brand.objects.create(name='Nanya', code='NYG3')
        cls.rayson  = Brand.objects.create(name='Rayson', code='RSG3')

        L = PriceList.all_companies
        cls.l_samsung = L.create(buyer=cls.buyer, brand=cls.samsung)
        cls.l_nanya   = L.create(buyer=cls.buyer, brand=cls.nanya)
        cls.l_generic = L.create(buyer=cls.buyer, brand=None,
                                 inherits_from=cls.l_nanya)   # regra 4 do prompt
        cls.l_sk      = L.create(buyer=cls.buyer, brand=cls.sk,
                                 inherits_from=cls.l_samsung) # "SK = Samsung"
        cls.l_rayson  = L.create(buyer=cls.buyer, brand=cls.rayson)

        hoje, velho = date.today(), date.today() - timedelta(days=200)

        def row(lista, kind, gen, tier, unit, mn=None, mx=None,
                status=STATUS_QUOTED, qd=None):
            return Price.all_companies.create(
                price_list=lista, kind=kind, gen=gen,
                tier_value=Decimal(str(tier)), tier_unit=unit, status=status,
                price_min=Decimal(str(mn)) if mn is not None else None,
                price_max=Decimal(str(mx)) if mx is not None else None,
                quote_date=qd)

        # Samsung (valores da planilha real):
        row(cls.l_samsung, 'emmc', '', 64, 'GB', '6.00', '6.00', qd=hoje)
        row(cls.l_samsung, 'emcp', 'LPDDR4X', 64, 'GB', '13.50', '16.50')  # sem data → ≈
        row(cls.l_samsung, 'lpddr', 'LPDDR4', 4, 'GB', '3.75', '3.75', qd=hoje)
        row(cls.l_samsung, 'lpddr', 'LPDDR4X', 4, 'GB', '2.55', '2.55', qd=hoje)
        row(cls.l_samsung, 'ddr', 'DDR3L', 4, 'Gb', '0.60', '0.60', qd=hoje)
        row(cls.l_samsung, 'ddr', 'DDR4', 8, 'Gb', '1.95', '1.95', qd=velho)
        row(cls.l_samsung, 'gddr', 'GDDR5', 8, 'Gb', status=STATUS_NO_BUY)
        row(cls.l_samsung, 'ufs', '', 256, 'GB', status=STATUS_UNQUOTED)
        # Nanya (o "curinga" DRAM, agora como dado):
        row(cls.l_nanya, 'ddr', 'DDR3', 2, 'Gb', '0.45', '0.45', qd=hoje)
        row(cls.l_nanya, 'lpddr', 'LPDDR4', 2, 'GB', '1.95', '1.95', qd=hoje)
        # Genérica: linha PRÓPRIA sobrepõe a herdada da Nanya (override):
        row(cls.l_generic, 'ddr', 'DDR3', 4, 'Gb', '0.50', '0.50', qd=hoje)
        # Rayson (da aba Other Brands): só o override dele:
        row(cls.l_rayson, 'emmc', '', 8, 'GB', '1.50', '1.50', qd=hoje)

    def _price(self, **kw):
        from .engine import price
        return price(_r(**kw), self.buyer)

    def test_emmc_samsung_64gb_preco_exato(self):
        q = self._price(chip_type='eMMC', brand='Samsung', cap_gb=64.0)
        self.assertEqual(q.status, 'PRICED')
        self.assertEqual((q.price_min, q.price_max),
                         (Decimal('6.00'), Decimal('6.00')))
        self.assertFalse(q.is_range)
        self.assertFalse(q.is_stale)
        self.assertEqual(q.via, 'marca')

    def test_emcp_faixa_cenarios_e_ram_fora_da_chave(self):
        q = self._price(chip_type='eMCP', subtype='LPDDR4X', brand='Samsung',
                        nand_gb=64.0, ram_gb=4.0, ram_gen='LPDDR4X')
        self.assertEqual(q.status, 'PRICED')
        self.assertTrue(q.is_range)
        self.assertTrue(q.is_stale)                      # linha sem quote_date → ≈
        self.assertEqual(q.value('low'), Decimal('13.50'))
        self.assertEqual(q.value('mid'), Decimal('15.00'))
        self.assertEqual(q.value('high'), Decimal('16.50'))
        # RAM 3GB vs 4GB: MESMA faixa, MESMO preço (regra do comprador).
        q3 = self._price(chip_type='eMCP', subtype='LPDDR4X', brand='Samsung',
                         nand_gb=64.0, ram_gb=3.0, ram_gen='LPDDR4X')
        self.assertEqual(q3.price_min, q.price_min)

    def test_lpddr4_e_4x_tem_precos_diferentes(self):
        q4 = self._price(chip_type='LPDDR4', brand='Samsung', cap_gb=4.0,
                         ram_gen='LPDDR4')
        q4x = self._price(chip_type='LPDDR4X', brand='Samsung', cap_gb=4.0,
                          ram_gen='LPDDR4X')
        self.assertEqual(q4.price_min, Decimal('3.75'))
        self.assertEqual(q4x.price_min, Decimal('2.55'))   # subtype é bug de preço

    def test_ddr3l_nao_cai_em_ddr3_nem_vice_versa(self):
        q = self._price(chip_type='DDR3L', brand='Samsung', density_gbit_num=4.0)
        self.assertEqual(q.price_min, Decimal('0.60'))
        # DDR3 4Gb na Samsung NÃO existe → NO_ROW (nunca cai no DDR3L "parecido");
        # e a cadeia segue: genérica TEM DDR3 4Gb próprio (0.50) → acha lá.
        q2 = self._price(chip_type='DDR3', brand='Samsung', density_gbit_num=4.0)
        self.assertEqual(q2.status, 'PRICED')
        self.assertEqual(q2.price_min, Decimal('0.50'))
        self.assertEqual(q2.via, 'genérica')

    def test_tres_estados_de_sem_preco(self):
        no_buy = self._price(chip_type='GDDR5', brand='Samsung', density_gbit_num=8.0)
        self.assertEqual(no_buy.status, 'NO_BUY')
        unq = self._price(chip_type='UFS', brand='Samsung', cap_gb=256.0)
        self.assertEqual(unq.status, 'UNQUOTED')
        fora = self._price(chip_type='eMMC', brand='Samsung', cap_gb=24.0)
        self.assertEqual(fora.status, 'NO_ROW')
        self.assertIn('24GB', fora.reason)

    def test_generico_e_sem_capacidade_nao_keiam(self):
        self.assertEqual(self._price(chip_type='DDR', brand='Samsung',
                                     density_gbit_num=4.0).status, 'NO_KEY')
        self.assertEqual(self._price(chip_type='NAND Flash',
                                     brand='Samsung').status, 'NO_KEY')
        self.assertEqual(self._price(chip_type='eMMC', brand='Samsung',
                                     cap_gb=None).status, 'NO_KEY')
        self.assertEqual(self._price(chip_type='eMCP', brand='Samsung',
                                     nand_gb=64.0, ram_gen='').status, 'NO_KEY')

    def test_cadeia_de_heranca_completa(self):
        # SK herda da Samsung ("SK = Samsung" como dado):
        sk = self._price(chip_type='eMMC', brand='SK Hynix', cap_gb=64.0)
        self.assertEqual(sk.price_min, Decimal('6.00'))
        self.assertEqual(sk.via, 'herança da marca')
        # Rayson: linha própria vence tudo:
        ray = self._price(chip_type='eMMC', brand='Rayson', cap_gb=8.0)
        self.assertEqual((ray.price_min, ray.via), (Decimal('1.50'), 'marca'))
        # Rayson LPDDR4 2GB: não tem → genérica não tem → Nanya (herança da genérica):
        ray2 = self._price(chip_type='LPDDR4', brand='Rayson', cap_gb=2.0,
                           ram_gen='LPDDR4')
        self.assertEqual((ray2.price_min, ray2.via),
                         (Decimal('1.95'), 'herança da genérica'))
        # Marca DESCONHECIDA (sem lista): cai direto na genérica→Nanya:
        esmt = self._price(chip_type='DDR3', brand='ESMT', density_gbit_num=2.0)
        self.assertEqual((esmt.price_min, esmt.via),
                         (Decimal('0.45'), 'herança da genérica'))

    def test_staleness_por_data(self):
        velho = self._price(chip_type='DDR4', brand='Samsung', density_gbit_num=8.0)
        self.assertEqual(velho.status, 'PRICED')
        self.assertTrue(velho.is_stale)                # cotado há 200 dias > 90
        fresco = self._price(chip_type='DDR3L', brand='Samsung', density_gbit_num=4.0)
        self.assertFalse(fresco.is_stale)

    def test_comprador_sem_listas(self):
        vazio = Buyer.all_companies.create(company=self.company,
                                           name='Sem Lista', slug='sem-lista-g')
        from .engine import price
        q = price(_r(chip_type='eMMC', brand='Samsung', cap_gb=64.0), vazio)
        self.assertEqual(q.status, 'NO_LIST')


class PriceLotTests(TestCase):
    """price_lot: agrega on-read (re-classifica), cobre e lista o sem-preço."""

    def test_relatorio_do_lote(self):
        from unittest.mock import patch
        from estoque.models import Lot, InventoryEntry

        company = Company.objects.create(name='LotCo', slug='lot-f3')
        buyer = Buyer.all_companies.create(company=company, name='WuquanL',
                                           slug='wuquan-l')
        samsung = Brand.objects.create(name='Samsung L', code='SAML3')
        lista = PriceList.all_companies.create(buyer=buyer, brand=samsung)
        Price.all_companies.create(
            price_list=lista, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('6.00'), price_max=Decimal('6.00'))

        User = get_user_model()
        u = User.objects.create_user('lot_f3')
        with company_scope(company):
            lot = Lot.open_for_company(company, u, 'lote F3')
            InventoryEntry.objects.create(lot=lot, part_number='PNOK', quantity=10)
            InventoryEntry.objects.create(lot=lot, part_number='PNSEM', quantity=5)

            fake = {
                'PNOK':  _r(chip_type='eMMC', brand='Samsung L', cap_gb=64.0),
                'PNSEM': _r(chip_type='eMMC', brand='Samsung L', cap_gb=24.0),
            }
            from pricing import engine as peng
            with patch('chips.engine.classify', side_effect=lambda pn: fake[pn]):
                report = peng.price_lot(lot, buyer)

        self.assertEqual(report.total_lines, 2)
        self.assertEqual(report.priced_lines, 1)
        self.assertEqual(report.total_units, 15)
        self.assertEqual(report.priced_units, 10)
        self.assertEqual(report.totals['mid'], Decimal('60.00'))   # 10 × $6
        self.assertEqual(report.coverage_units, 100.0 * 10 / 15)
        (pn, qty, status, reason), = report.unpriced
        self.assertEqual((pn, qty, status), ('PNSEM', 5, 'NO_ROW'))


class PricingRLSTests(TransactionTestCase):
    """Camada B no pricing (espelho do estoque.RLSHandshakeTests): SQL CRU
    respeita as policies das tabelas de preço — nem query bugada cruza empresa.

    ⚠ Postgres-only; troca para role de sondagem sem-super se o dev conecta
    como SUPERUSER (armadilha §6.2.1 do PLANO_MULTITENANT.md).
    """

    _PROBE_ROLE = 'wtc_rls_probe_pricing'

    def _enter_non_superuser(self, cur):
        cur.execute('SELECT rolsuper FROM pg_roles WHERE rolname = current_user')
        if not cur.fetchone()[0]:
            return
        cur.execute('SELECT current_user')
        original = cur.fetchone()[0]

        def _leave():
            with connection.cursor() as c:
                c.execute('RESET ROLE')
                c.execute(f'DROP ROLE IF EXISTS {self._PROBE_ROLE}')
        self.addCleanup(_leave)

        cur.execute(f'DROP ROLE IF EXISTS {self._PROBE_ROLE}')
        cur.execute(f'CREATE ROLE {self._PROBE_ROLE}')
        cur.execute(f'GRANT "{original}" TO {self._PROBE_ROLE}')
        cur.execute(f'SET ROLE {self._PROBE_ROLE}')

    @skipUnless(connection.vendor == 'postgresql', 'RLS é Postgres-only')
    def test_sql_cru_respeita_o_rls_do_pricing(self):
        a, buyer_a, _, lista_a = _setup_wuquan('RlsPA', 'rls-pa')
        b, buyer_b, _, _ = _setup_wuquan('RlsPB', 'rls-pb')
        Price.all_companies.create(
            price_list=lista_a, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('6.00'), price_max=Decimal('6.00'))

        def _clear_gucs():
            with connection.cursor() as c:
                c.execute("SELECT set_config('app.company_id', '', false)")
                c.execute("SELECT set_config('app.platform', '', false)")
        self.addCleanup(_clear_gucs)
        _clear_gucs()

        with connection.cursor() as cur:
            self._enter_non_superuser(cur)
            # 1) SEM GUC → 0 linhas (fail-closed no banco, mesmo pro dono da tabela).
            for table in ('pricing_buyer', 'pricing_pricelist', 'pricing_price'):
                cur.execute(f'SELECT count(*) FROM {table}')
                self.assertEqual(cur.fetchone()[0], 0, table)

            # 2) GUC da empresa A → só as linhas da A.
            cur.execute("SELECT set_config('app.company_id', %s, false)", [str(a.pk)])
            cur.execute('SELECT company_id FROM pricing_buyer')
            self.assertEqual([r[0] for r in cur.fetchall()], [a.pk])
            cur.execute('SELECT count(*) FROM pricing_buyer WHERE company_id = %s',
                        [b.pk])
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute('SELECT count(*) FROM pricing_price')
            self.assertEqual(cur.fetchone()[0], 1)

            # 3) Escrita cruzada barrada NO BANCO (WITH CHECK implícito da policy).
            from django.db import Error as DBError
            with self.assertRaises(DBError):
                cur.execute(
                    "INSERT INTO pricing_buyer (company_id, name, slug, active, notes, created_at) "
                    "VALUES (%s, 'Invasor', 'invasor-rls', true, '', now())",
                    [b.pk])

            # 4) GUC de plataforma → vê as duas empresas (Django admin).
            with connection.cursor() as c2:
                c2.execute("SELECT set_config('app.platform', '1', false)")
            cur.execute('SELECT count(*) FROM pricing_buyer')
            self.assertEqual(cur.fetchone()[0], 2)
