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
