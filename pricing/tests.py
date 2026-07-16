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
                     STATUS_NO_BUY, STATUS_NOT_MADE, STATUS_QUOTED,
                     STATUS_UNQUOTED)


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
        # PREÇO FIXO (decisão 2026-07-07): FAIXA é rejeitada pelo portão.
        with self.assertRaises(ValidationError):
            self._price(kind='emcp', gen='LPDDR4X', tier_value=Decimal('64'),
                        price_min=Decimal('13.50'), price_max=Decimal('16.50'))

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


class ImportPriceXlsxTests(TestCase):
    """F4 — o import da planilha do comprador: dry-run, colapso eMCP,
    3 estados, normalização de marca, idempotência e conflito.
    F10 (RMB canônico): o ¥ da coluna F é gravado DIRETO — a antiga conversão
    × B2 morreu (era ela que gerava os USD "nascidos a 0.15")."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='ImpCo', slug='imp-f4')
        Brand.objects.create(name='Samsung', code='SAM4')
        Brand.objects.create(name='Toshiba-Kioxia', code='TXK4')
        Brand.objects.create(name='Rayson', code='RSN4')

    def _make_xlsx(self, conflict=False, unknown_brand=False):
        import openpyxl
        import tempfile
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        def sheet(name, rows):
            ws = wb.create_sheet(name)
            ws['A1'] = f'{name} — chip sell price (per unit)'
            ws['A2'], ws['B2'] = 'Exchange rate  1 RMB =', 0.15
            ws.append(['Brand', 'Type', 'Subtype', 'Capacity', 'Price (USD)',
                       '★Price (RMB)', '★Quote date', 'Source', 'Notes'])
            for r in rows:
                ws.append(r)

        sheet('Samsung', [
            ['Samsung', 'eMMC', '—', '64GB', None, 40, '2026-06-29 06:57:36', 'mercado', ''],
            ['Samsung', 'eMCP', 'LPDDR4X', '64+4', None, '90-110', None, '', ''],
            ['Samsung', 'eMCP', 'LPDDR4X', '64+3', None,
             '100-120' if conflict else '90-110', None, '', ''],
            # combo VAZIO na mesma faixa: cotado vence célula-por-preencher
            # (caso real da aba SK Hynix — NÃO é conflito):
            ['Samsung', 'eMCP', 'LPDDR4X', '64+6', None, None, None, '', ''],
            ['Samsung', 'GDDR', 'GDDR5', '8Gb', None, 'NO', None, '', ''],
            ['Samsung', 'UFS', '—', '256GB', None, None, None, '', ''],
            ['Samsung', 'DDR', 'DDR3', '2GB', None, 3, None, '', ''],  # unidade ERRADA → pulada
        ])
        sheet('Toshiba Kioxia', [
            ['Toshiba/Kioxia', 'eMMC', '—', '16GB', None, 15, None, '', ''],
        ])
        sheet('Other Brands', [
            ['', 'LPDDR', 'LPDDR4', '2GB', None, 13, None, '', ''],
            ['Rayson', 'eMMC', '—', '8GB', None, 10, None, '', ''],
        ])
        if unknown_brand:
            sheet('Marswell', [['Marswell', 'eMMC', '—', '8GB', None, 10, None, '', '']])
        ws = wb.create_sheet('Instructions')
        ws['A1'] = 'regras'

        f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        wb.save(f.name)
        return f.name

    def _run(self, path, commit=False):
        from io import StringIO
        from django.core.management import call_command
        from tenancy.scope import set_current_company
        out = StringIO()
        try:
            call_command('import_price_xlsx', path, buyer='wuquan',
                         commit=commit, stdout=out)
        finally:
            # scope_command_to_company seta o contextvar do PROCESSO (em uso
            # real o comando termina e o processo morre); no runner de testes
            # ele vazaria para o teste seguinte — reset explícito.
            set_current_company(None)
        return out.getvalue()

    def test_dry_run_nao_grava_nada(self):
        out = self._run(self._make_xlsx())
        self.assertIn('DRY-RUN', out)
        self.assertIn('pulada', out)                       # DDR com GB (unidade errada)
        self.assertEqual(Buyer.all_companies.count(), 0)
        self.assertEqual(Price.all_companies.count(), 0)

    def test_commit_grava_converte_e_colapsa(self):
        out = self._run(self._make_xlsx(), commit=True)
        self.assertIn('COMMIT', out)
        buyer = Buyer.all_companies.get(slug='wuquan')
        self.assertEqual(buyer.company, self.company)

        P = Price.all_companies
        emmc = P.get(kind='emmc', tier_value=Decimal('64'))
        self.assertEqual((emmc.price_min, emmc.price_max),
                         (Decimal('40.00'), Decimal('40.00')))  # ¥40 DIRETO (F10)
        self.assertEqual(str(emmc.quote_date), '2026-06-29')
        emcp = P.get(kind='emcp')                              # 64+4 e 64+3 → UMA linha
        # faixa "90-110" RMB → ponto médio ¥100 (preço FIXO; sem × câmbio)
        self.assertEqual((emcp.price_min, emcp.price_max),
                         (Decimal('100.00'), Decimal('100.00')))
        self.assertEqual(P.get(kind='gddr').status, STATUS_NO_BUY)
        self.assertEqual(P.get(kind='ufs').status, STATUS_UNQUOTED)
        # Normalização de marca: Toshiba/Kioxia → Toshiba-Kioxia.
        toshiba = P.get(kind='emmc', tier_value=Decimal('16'))
        self.assertEqual(toshiba.price_list.brand.name, 'Toshiba-Kioxia')
        # Other Brands: TUDO vira linha da GENÉRICA (coluna A é decorativa —
        # decisão 2026-07-07: nada de lista-fantasma pra Rayson & cia).
        generica = P.get(kind='lpddr')
        self.assertIsNone(generica.price_list.brand)
        self.assertEqual(generica.price_min, Decimal('13.00'))  # ¥13 direto
        outras8 = P.get(kind='emmc', tier_value=Decimal('8'))
        self.assertIsNone(outras8.price_list.brand)            # NÃO é lista Rayson
        self.assertEqual(outras8.price_min, Decimal('10.00'))
        self.assertFalse(PriceList.all_companies.filter(
            brand__name='Rayson').exists())
        # A linha DDR de unidade errada não entrou:
        self.assertEqual(P.filter(kind='ddr').count(), 0)

    def test_idempotente_re_rodar_nao_duplica(self):
        path = self._make_xlsx()
        self._run(path, commit=True)
        antes = Price.all_companies.count()
        out = self._run(path, commit=True)
        self.assertEqual(Price.all_companies.count(), antes)
        self.assertIn('criados: 0', out)

    def test_conflito_emcp_aborta_sem_gravar(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run(self._make_xlsx(conflict=True), commit=True)
        self.assertEqual(Price.all_companies.count(), 0)

    def test_marca_desconhecida_aborta(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run(self._make_xlsx(unknown_brand=True), commit=True)
        self.assertEqual(Price.all_companies.count(), 0)


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

    F10 (RMB canônico, §12.18): o fixture agora guarda os **¥ ORIGINAIS** da
    planilha (a coluna RMB — ¥40, ¥90, ¥25…) e as asserções esperam o **USD
    DERIVADO** pela taxa contratual default 0.14 (¥90 → US$ 12.60; era 13.50
    quando os USD nasceram a 0.15 — a queda de ~6,7% é o contrato atual).

    Provam: chave por kind, derivação ¥→US$, LPDDR4≠4X, RAM fora da chave,
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

        # Samsung — os ¥ da PLANILHA (coluna RMB; faixa "90-110" achatada no
        # ponto médio ¥100→ aqui usamos ¥90, o golden do plano §12.18 — preço
        # FIXO, decisão 2026-07-07). USD derivado @0.14 nas asserções:
        row(cls.l_samsung, 'emmc', '', 64, 'GB', '40', '40', qd=hoje)          # → 5.60
        row(cls.l_samsung, 'emcp', 'LPDDR4X', 64, 'GB', '90', '90')  # sem data → ≈; → 12.60
        row(cls.l_samsung, 'lpddr', 'LPDDR4', 4, 'GB', '25', '25', qd=hoje)    # → 3.50
        row(cls.l_samsung, 'lpddr', 'LPDDR4X', 4, 'GB', '17', '17', qd=hoje)   # → 2.38
        row(cls.l_samsung, 'ddr', 'DDR3L', 4, 'Gb', '4', '4', qd=hoje)         # → 0.56
        row(cls.l_samsung, 'ddr', 'DDR4', 8, 'Gb', '13', '13', qd=velho)       # → 1.82
        row(cls.l_samsung, 'gddr', 'GDDR5', 8, 'Gb', status=STATUS_NO_BUY)
        row(cls.l_samsung, 'ufs', '', 256, 'GB', status=STATUS_UNQUOTED)
        # Nanya (o "curinga" DRAM, agora como dado):
        row(cls.l_nanya, 'ddr', 'DDR3', 2, 'Gb', '3', '3', qd=hoje)            # → 0.42
        row(cls.l_nanya, 'lpddr', 'LPDDR4', 2, 'GB', '13', '13', qd=hoje)      # → 1.82
        # Genérica: linha PRÓPRIA sobrepõe a herdada da Nanya (override):
        row(cls.l_generic, 'ddr', 'DDR3', 4, 'Gb', '5', '5', qd=hoje)          # → 0.70
        # Rayson (da aba Other Brands): só o override dele:
        row(cls.l_rayson, 'emmc', '', 8, 'GB', '10', '10', qd=hoje)            # → 1.40

    def _price(self, **kw):
        from .engine import price
        return price(_r(**kw), self.buyer)

    def test_emmc_samsung_64gb_preco_exato(self):
        q = self._price(chip_type='eMMC', brand='Samsung', cap_gb=64.0)
        self.assertEqual(q.status, 'PRICED')
        # ¥ armazenado + USD derivado (¥40 × 0.14 = 5.60):
        self.assertEqual((q.rmb_min, q.rmb_max), (Decimal('40'), Decimal('40')))
        self.assertEqual((q.price_min, q.price_max),
                         (Decimal('5.60'), Decimal('5.60')))
        self.assertFalse(q.is_range)
        self.assertFalse(q.is_stale)
        self.assertEqual(q.via, 'marca')

    def test_emcp_preco_fixo_e_ram_fora_da_chave(self):
        # O golden do plano §12.18: ¥90 → US$ 12.60 (taxa contratual 0.14).
        q = self._price(chip_type='eMCP', subtype='LPDDR4X', brand='Samsung',
                        nand_gb=64.0, ram_gb=4.0, ram_gen='LPDDR4X')
        self.assertEqual(q.status, 'PRICED')
        self.assertFalse(q.is_range)                     # preço FIXO (2026-07-07)
        self.assertTrue(q.is_stale)                      # linha sem quote_date → ≈
        self.assertEqual(q.value(), Decimal('12.60'))
        self.assertEqual(q.rmb, Decimal('90'))           # o ¥ digitado, intacto
        self.assertEqual(q.mid_rmb, Decimal('90.00'))
        self.assertEqual(q.rmb_display, '90')            # card dual: "¥ 90 · US$ 12.60"
        # RAM 3GB vs 4GB: MESMA faixa de NAND, MESMO preço (regra do comprador).
        q3 = self._price(chip_type='eMCP', subtype='LPDDR4X', brand='Samsung',
                         nand_gb=64.0, ram_gb=3.0, ram_gen='LPDDR4X')
        self.assertEqual(q3.price_min, q.price_min)

    def test_taxa_nova_muda_usd_e_preserva_o_yuan(self):
        # F10: mudar a taxa contratual NUNCA toca os ¥ — só o USD derivado.
        self.buyer.fx_usd_rate = Decimal('0.15')
        self.buyer.save()
        q = self._price(chip_type='eMCP', subtype='LPDDR4X', brand='Samsung',
                        nand_gb=64.0, ram_gb=4.0, ram_gen='LPDDR4X')
        self.assertEqual(q.rmb, Decimal('90'))            # ¥ intacto
        self.assertEqual(q.price_min, Decimal('13.50'))   # USD acompanha a taxa
        # e o banco continua guardando o ¥ cru:
        row = Price.all_companies.get(price_list=self.l_samsung, kind='emcp')
        self.assertEqual(row.price_min, Decimal('90'))

    def test_lpddr4_e_4x_tem_precos_diferentes(self):
        q4 = self._price(chip_type='LPDDR4', brand='Samsung', cap_gb=4.0,
                         ram_gen='LPDDR4')
        q4x = self._price(chip_type='LPDDR4X', brand='Samsung', cap_gb=4.0,
                          ram_gen='LPDDR4X')
        self.assertEqual(q4.price_min, Decimal('3.50'))    # ¥25 × 0.14
        self.assertEqual(q4x.price_min, Decimal('2.38'))   # ¥17 × 0.14 — subtype é bug de preço

    def test_ddr3l_dobra_para_ddr3_na_chave(self):
        # POLÍTICA NOVA (dono, 2026-07-11): "DDR3L e DDR3 são a mesma coisa em
        # termos de preço" — variante de TENSÃO dobra para a geração-base na
        # chave. (Até 10/07 o golden afirmava o oposto — atualizado junto com
        # a decisão; a linha DDR3L 0.60 do fixture fica inalcançável de
        # propósito: grade real não tem linhas DDR3L.)
        q = self._price(chip_type='DDR3L', brand='Samsung', density_gbit_num=4.0)
        self.assertEqual(q.status, 'PRICED')
        self.assertEqual(q.price_min, Decimal('0.70'))   # DDR3 4Gb da genérica (¥5)
        self.assertEqual(q.via, 'genérica')
        # DDR3 puro segue idêntico — mesma chave, mesmo preço.
        q2 = self._price(chip_type='DDR3', brand='Samsung', density_gbit_num=4.0)
        self.assertEqual(q2.price_min, Decimal('0.70'))
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
        self.assertEqual(sk.price_min, Decimal('5.60'))            # ¥40 @0.14
        self.assertEqual(sk.via, 'herança da marca')
        # Rayson: linha própria vence tudo:
        ray = self._price(chip_type='eMMC', brand='Rayson', cap_gb=8.0)
        self.assertEqual((ray.price_min, ray.via), (Decimal('1.40'), 'marca'))
        # Rayson LPDDR4 2GB: não tem → genérica não tem → Nanya (herança da genérica):
        ray2 = self._price(chip_type='LPDDR4', brand='Rayson', cap_gb=2.0,
                           ram_gen='LPDDR4')
        self.assertEqual((ray2.price_min, ray2.via),
                         (Decimal('1.82'), 'herança da genérica'))  # ¥13 @0.14
        # Marca DESCONHECIDA (sem lista): cai direto na genérica→Nanya:
        esmt = self._price(chip_type='DDR3', brand='ESMT', density_gbit_num=2.0)
        self.assertEqual((esmt.price_min, esmt.via),
                         (Decimal('0.42'), 'herança da genérica'))  # ¥3 @0.14

    def test_staleness_por_data(self):
        velho = self._price(chip_type='DDR4', brand='Samsung', density_gbit_num=8.0)
        self.assertEqual(velho.status, 'PRICED')
        self.assertTrue(velho.is_stale)                # cotado há 200 dias > 90
        fresco = self._price(chip_type='DDR3L', brand='Samsung', density_gbit_num=4.0)
        self.assertFalse(fresco.is_stale)

    def test_not_made_e_negativa_autoritativa(self):
        # Linha "não fabricado" responde NOT_MADE e BLOQUEIA o fallback
        # (é a negativa explícita do grid unificado, decisão 2026-07-07).
        Price.all_companies.create(
            price_list=self.l_samsung, kind='ddr', gen='DDR5',
            tier_value=Decimal('16'), tier_unit='Gb', status='not_made')
        q = self._price(chip_type='DDR5', brand='Samsung', density_gbit_num=16.0)
        self.assertEqual(q.status, 'NOT_MADE')
        self.assertIn('não fabricado', q.reason)

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
            price_min=Decimal('40'), price_max=Decimal('40'))   # ¥40 → US$ 5.60

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
        # Valoração SEGUE em USD (F10): 10 × US$ 5.60 (¥40 derivado @0.14).
        self.assertEqual(report.totals['mid'], Decimal('56.00'))
        self.assertEqual(report.coverage_units, 100.0 * 10 / 15)
        (pn, qty, status, reason), = report.unpriced
        self.assertEqual((pn, qty, status), ('PNSEM', 5, 'NO_ROW'))


class PriceCardGateTests(TestCase):
    """F5 — o preço no card de busca é SÓ para papel ADMIN da empresa.
    Operador, gerente e anônimo recebem o card SEM o bloco (gate na view —
    price_quotes chega vazio; esconder no template nunca é a única barreira)."""

    @classmethod
    def setUpTestData(cls):
        from tenancy.models import Membership
        cls.company = Company.objects.create(name='CardCo', slug='card-f5')
        buyer = Buyer.all_companies.create(company=cls.company, name='Wuquan C',
                                           slug='wuquan-card')
        samsung = Brand.objects.create(name='Samsung', code='SAMF5')
        lista = PriceList.all_companies.create(buyer=buyer, brand=samsung)
        Price.all_companies.create(
            price_list=lista, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('40'), price_max=Decimal('40'))   # ¥40 → US$ 5.60

        User = get_user_model()
        cls.users = {}
        for role in ('admin', 'manager', 'operator'):
            u = User.objects.create_user(f'{role}_f5')
            Membership.objects.create(user=u, company=cls.company, role=role)
            cls.users[role] = u

    def _decode(self, user=None):
        from unittest.mock import patch
        if user is not None:
            self.client.force_login(user)
        # Forma COMPLETA do classify() (o card acessa muitos campos):
        fake = dict(
            pn='KLMCG8GEAC', known=True, known_exact=True, chip_type='eMMC',
            subtype='', brand='Samsung', capacity='64GB', dram_density=None,
            emcp_ram=None, emcp_nand=None, device='', confidence='confirmed',
            source_url='', is_emcp=False, tip='', reasoning=[], from_web=False,
            doc_url=None, fuzzy_suggestions=[], interface='', family_prefix='KLM',
            family_undocumented=False, suffix_note=None,
            classification_source='banco de dados', grammar_complete=True,
            in_review_queue=False, pn_not_in_db=False, pn_incomplete=False,
            profitable='RENTÁVEL',
            nand_gb=None, ram_gb=None, cap_gb=64.0, density_gbit_num=None,
            ram_gen='')
        with patch('chips.views.classify', return_value=fake):
            return self.client.get('/chips/decode/', {'pn': 'KLMCG8GEAC'})

    def test_admin_ve_o_preco(self):
        resp = self._decode(self.users['admin'])
        # F10.5: exibição DUAL "¥ 40 · US$ 5.60" — o bloco usa {% localize
        # off %}, então o decimal vem com PONTO em qualquer idioma da UI.
        self.assertContains(resp, '¥ 40')
        self.assertContains(resp, 'US$ 5.60')
        self.assertContains(resp, 'Wuquan C')
        self.assertContains(resp, 'dc2-price-block')

    def test_gerente_operador_e_anonimo_nao_veem(self):
        for who in (self.users['manager'], self.users['operator'], None):
            self.client.logout()
            resp = self._decode(who)
            self.assertEqual(resp.status_code, 200)
            self.assertNotContains(resp, 'US$ 5.60')
            self.assertNotContains(resp, '¥ 40')
            self.assertNotContains(resp, 'dc2-price-block')


class BenchAndLotPricingTests(TestCase):
    """F8 — preço na bancada (admin-only), valoração do lote e congelamento
    no fechamento. + F5-bis: o JSON do /chips/search/ só carrega prices p/ admin."""

    @classmethod
    def setUpTestData(cls):
        from tenancy.models import Membership
        cls.company = Company.objects.create(name='F8Co', slug='f8co')
        cls.buyer = Buyer.all_companies.create(company=cls.company,
                                               name='Wuquan F8', slug='wuquan-f8')
        samsung = Brand.objects.create(name='Samsung', code='SAMF8')
        lista = PriceList.all_companies.create(buyer=cls.buyer, brand=samsung)
        Price.all_companies.create(
            price_list=lista, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('40'), price_max=Decimal('40'))   # ¥40 → US$ 5.60

        User = get_user_model()
        cls.users = {}
        for role in ('admin', 'manager', 'operator'):
            u = User.objects.create_user(f'{role}_f8')
            Membership.objects.create(user=u, company=cls.company, role=role)
            cls.users[role] = u

    def _fake_result(self):
        return dict(
            pn='KLMCG8GEAC', known=True, known_exact=True, chip_type='eMMC',
            subtype='', brand='Samsung', capacity='64GB', dram_density=None,
            emcp_ram=None, emcp_nand=None, device='', confidence='confirmed',
            source_url='', is_emcp=False, tip='', reasoning=[], from_web=False,
            doc_url=None, fuzzy_suggestions=[], interface='', family_prefix='KLM',
            family_undocumented=False, suffix_note=None,
            classification_source='banco de dados', grammar_complete=True,
            in_review_queue=False, pn_not_in_db=False, pn_incomplete=False,
            profitable='RENTÁVEL',
            nand_gb=None, ram_gb=None, cap_gb=64.0, density_gbit_num=None,
            ram_gen='')

    def _lot(self, qty=10):
        from estoque.models import InventoryEntry, Lot
        with company_scope(self.company):
            lot = Lot.open_for_company(self.company, self.users['manager'], 'F8')
            InventoryEntry.objects.create(lot=lot, part_number='KLMCG8GEAC',
                                          quantity=qty)
        return lot

    def test_search_api_json_so_tem_prices_para_admin(self):
        # ⚠ side_effect (dict NOVO por chamada): o search_api MUTA o result
        # ("prices") — return_value compartilhado vazaria o preço do admin
        # para a chamada seguinte do operador (em produção o classify cria
        # um dict novo por chamada; o teste tem que imitar isso).
        from unittest.mock import patch
        with patch('chips.views.classify',
                   side_effect=lambda pn: self._fake_result()):
            self.client.force_login(self.users['admin'])
            d = self.client.get('/chips/search/', {'pn': 'KLMCG8GEAC'}).json()
            self.assertIn('prices', d)
            # F10: as DUAS moedas no JSON — USD derivado + ¥ armazenado.
            self.assertEqual(d['prices'][0]['min'], '5.60')     # string, não float
            self.assertEqual(d['prices'][0]['rmb'], '40')       # ¥ de exibição
            self.assertEqual(d['prices'][0]['mid_rmb'], '40.00')
            self.client.logout()
            self.client.force_login(self.users['operator'])
            d2 = self.client.get('/chips/search/', {'pn': 'KLMCG8GEAC'}).json()
            self.assertNotIn('prices', d2)
            self.client.logout()
            d3 = self.client.get('/chips/search/', {'pn': 'KLMCG8GEAC'}).json()
            self.assertNotIn('prices', d3)                      # anônimo idem

    def test_bancada_preview_mostra_preco_so_para_admin(self):
        from unittest.mock import patch
        lot = self._lot()
        with patch('estoque.views.classify', return_value=self._fake_result()):
            self.client.force_login(self.users['admin'])
            resp = self.client.get(f'/estoque/lote/{lot.pk}/preview/',
                                   {'pn': 'KLMCG8GEAC'})
            self.assertContains(resp, 'dc2-price-block')
            self.assertContains(resp, '¥ 40')            # dual (F10.5)
            self.assertContains(resp, 'US$ 5.60')
            self.client.logout()
            self.client.force_login(self.users['operator'])
            resp2 = self.client.get(f'/estoque/lote/{lot.pk}/preview/',
                                    {'pn': 'KLMCG8GEAC'})
            self.assertEqual(resp2.status_code, 200)
            self.assertNotContains(resp2, 'dc2-price-block')

    def test_fechar_lote_congela_valoracao_e_painel_mostra(self):
        from unittest.mock import patch
        from pricing.models import LotPricing
        lot = self._lot(qty=10)
        with patch('chips.engine.classify', return_value=self._fake_result()):
            # gerente fecha (é o papel dele) → snapshot nasce no servidor
            self.client.force_login(self.users['manager'])
            self.client.post(f'/estoque/lote/{lot.pk}/fechar/')
            lp = LotPricing.all_companies.get(lot=lot)
            # Congelado SEGUE em USD (F10): 10 × US$ 5.60 (¥40 @0.14) — e as
            # linhas de auditoria também (nunca ¥ no snapshot).
            self.assertEqual(lp.total_mid, Decimal('56.00'))
            self.assertEqual(lp.priced_units, 10)
            self.assertEqual(lp.company_id, self.company.pk)
            self.assertEqual(lp.lines[0]['pn'], 'KLMCG8GEAC')
            self.assertEqual(lp.lines[0]['min'], '5.60')        # USD, não ¥
            # gerente NÃO vê o painel de valoração
            resp_m = self.client.get(f'/estoque/lote/{lot.pk}/')
            self.assertNotContains(resp_m, 'Valoração do lote')
            # admin vê o CONGELADO
            self.client.logout()
            self.client.force_login(self.users['admin'])
            resp_a = self.client.get(f'/estoque/lote/{lot.pk}/')
            self.assertContains(resp_a, 'Valoração do lote')
            self.assertContains(resp_a, 'congelada no fechamento')
            self.assertContains(resp_a, 'US$ 56')               # 10 × US$ 5.60

    def test_lote_aberto_mostra_estimativa_ao_vivo_para_admin(self):
        from unittest.mock import patch
        lot = self._lot(qty=5)
        with patch('chips.engine.classify', return_value=self._fake_result()):
            self.client.force_login(self.users['admin'])
            resp = self.client.get(f'/estoque/lote/{lot.pk}/')
            self.assertContains(resp, 'estimativa ao vivo')
            self.assertContains(resp, 'US$ 28')                 # 5 × US$ 5.60


class SeedPriceGridTests(TestCase):
    """seed_price_grid: grid UNIFICADO — marca ganha faltantes como 'não
    fabricado'; Outras marcas como 'não cotado'; idempotente."""

    def _run(self, commit=False):
        from io import StringIO
        from django.core.management import call_command
        from tenancy.scope import set_current_company
        out = StringIO()
        try:
            call_command('seed_price_grid', buyer='wuquan-seed',
                         commit=commit, stdout=out)
        finally:
            set_current_company(None)
        return out.getvalue()

    def test_semeia_uniao_e_e_idempotente(self):
        company = Company.objects.create(name='SeedCo', slug='seed-co')
        buyer = Buyer.all_companies.create(company=company, name='Wuquan S',
                                           slug='wuquan-seed')
        marca = Brand.objects.create(name='Samsung S', code='SAMSE')
        l_marca = PriceList.all_companies.create(buyer=buyer, brand=marca)
        l_gen = PriceList.all_companies.create(buyer=buyer, brand=None)
        Price.all_companies.create(price_list=l_marca, kind='emmc', gen='',
                                   tier_value=Decimal('64'), tier_unit='GB',
                                   status=STATUS_QUOTED,
                                   price_min=Decimal('6.00'),
                                   price_max=Decimal('6.00'))
        Price.all_companies.create(price_list=l_gen, kind='ufs', gen='',
                                   tier_value=Decimal('256'), tier_unit='GB',
                                   status=STATUS_UNQUOTED)

        self._run(commit=False)                              # dry-run: nada
        self.assertEqual(Price.all_companies.count(), 2)

        self._run(commit=True)
        # marca ganhou a UFS 256 como NÃO FABRICADO:
        nova = Price.all_companies.get(price_list=l_marca, kind='ufs')
        self.assertEqual(nova.status, 'not_made')
        # genérica ganhou a eMMC 64 como NÃO COTADO (ela oferece tudo):
        gen_nova = Price.all_companies.get(price_list=l_gen, kind='emmc')
        self.assertEqual(gen_nova.status, STATUS_UNQUOTED)
        # linha existente intocada + idempotência:
        self.assertEqual(Price.all_companies.get(
            price_list=l_marca, kind='emmc').price_min, Decimal('6.00'))
        antes = Price.all_companies.count()
        self._run(commit=True)
        self.assertEqual(Price.all_companies.count(), antes)


class AddPriceRowTests(TestCase):
    """add_price_row: faixa nova entra no grid inteiro — made-by → não cotado;
    demais marcas → não fabricado; Outras marcas sempre não cotado."""

    def _run(self, commit=False, **extra):
        from io import StringIO
        from django.core.management import call_command
        from tenancy.scope import set_current_company
        out = StringIO()
        base = dict(buyer='wuquan-row', kind='lpddr', gen='LPDDR4X',
                    tier='1', unit='GB', made_by='Samsung R', commit=commit)
        base.update(extra)
        try:
            call_command('add_price_row', stdout=out, **base)
        finally:
            set_current_company(None)
        return out.getvalue()

    def test_faixa_nova_no_grid_inteiro(self):
        from django.core.management.base import CommandError
        company = Company.objects.create(name='RowCo', slug='row-co')
        buyer = Buyer.all_companies.create(company=company, name='Wuquan R',
                                           slug='wuquan-row')
        faz = Brand.objects.create(name='Samsung R', code='SAMRW')
        nao_faz = Brand.objects.create(name='Kingston R', code='KGTRW')
        l_faz = PriceList.all_companies.create(buyer=buyer, brand=faz)
        l_nao = PriceList.all_companies.create(buyer=buyer, brand=nao_faz)
        l_gen = PriceList.all_companies.create(buyer=buyer, brand=None)

        self._run(commit=False)                              # dry-run: nada
        self.assertEqual(Price.all_companies.count(), 0)

        self._run(commit=True)
        self.assertEqual(Price.all_companies.get(
            price_list=l_faz, kind='lpddr').status, STATUS_UNQUOTED)
        self.assertEqual(Price.all_companies.get(
            price_list=l_gen, kind='lpddr').status, STATUS_UNQUOTED)
        self.assertEqual(Price.all_companies.get(
            price_list=l_nao, kind='lpddr').status, 'not_made')

        self._run(commit=True)                               # idempotente
        self.assertEqual(Price.all_companies.count(), 3)

        with self.assertRaises(CommandError):                # gen inválida
            self._run(commit=True, gen='DDR3')
        with self.assertRaises(CommandError):                # marca desconhecida
            self._run(commit=True, made_by='Marswell')


class PartnerDashboardTests(TestCase):
    """F6 — /partner/: gate do parceiro, lançadeira, herdados, save e isolamento.
    Auditoria (updated_by/last_updated) GRAVADA mas NUNCA exibida (§7)."""

    @classmethod
    def setUpTestData(cls):
        from tenancy.models import Membership
        cls.company = Company.objects.create(name='P6Co', slug='p6co')
        cls.buyer = Buyer.all_companies.create(company=cls.company,
                                               name='Wuquan P6', slug='wuquan-p6')
        samsung = Brand.objects.create(name='Samsung P6', code='SAMP6')
        sk = Brand.objects.create(name='SK Hynix P6', code='SKP6')
        cls.l_samsung = PriceList.all_companies.create(buyer=cls.buyer, brand=samsung)
        cls.l_sk = PriceList.all_companies.create(buyer=cls.buyer, brand=sk,
                                                  inherits_from=cls.l_samsung)
        Price.all_companies.create(
            price_list=cls.l_samsung, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('6.00'), price_max=Decimal('6.00'))
        Price.all_companies.create(
            price_list=cls.l_samsung, kind='ufs', gen='', tier_value=Decimal('256'),
            tier_unit='GB', status=STATUS_UNQUOTED)

        User = get_user_model()
        cls.partner = User.objects.create_user('parceiro_p6')
        cls.buyer.users.add(cls.partner)
        cls.operator = User.objects.create_user('operador_p6')
        Membership.objects.create(user=cls.operator, company=cls.company,
                                  role='operator')
        # Comprador de OUTRA empresa (isolamento):
        other_co = Company.objects.create(name='P6Outra', slug='p6outra')
        cls.other_buyer = Buyer.all_companies.create(
            company=other_co, name='Outro P6', slug='outro-p6')
        cls.other_partner = User.objects.create_user('parceiro_outro_p6')
        cls.other_buyer.users.add(cls.other_partner)

    def test_gate_parceiro_membro_e_anonimo(self):
        resp = self.client.get('/partner/')
        self.assertEqual(resp.status_code, 302)              # anônimo → login
        self.assertIn('/login/', resp['Location'])
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/partner/').status_code, 403)
        self.client.logout()
        self.client.force_login(self.partner)
        resp = self.client.get('/partner/')
        self.assertContains(resp, 'Wuquan P6')
        self.assertContains(resp, 'Chips sem cotação')
        self.assertContains(resp, 'Bem-vindo')

    def test_como_funciona(self):
        # F6.2: guia curto do comprador — acessível só ao parceiro, com FAQ.
        # F10: a página foi REESCRITA em ¥ (RMB) — nada de "preço em USD".
        self.client.force_login(self.partner)
        resp = self.client.get('/partner/how/')
        self.assertContains(resp, 'Como funciona')
        self.assertContains(resp, 'Perguntas frequentes')
        self.assertContains(resp, 'RMB')
        self.assertContains(resp, 'taxa do')             # taxa do contrato
        self.assertNotContains(resp, 'preço em USD')
        self.client.logout()
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/partner/how/').status_code, 403)

    def test_header_mostra_taxa_contratual(self):
        # F10.3: o header troca a cotação viva pela taxa do CONTRATO
        # (Buyer.fx_usd_rate, default 0.14) — e o script de API morreu.
        self.client.force_login(self.partner)
        resp = self.client.get('/partner/')
        self.assertContains(resp, '1 ¥ = US$ 0.14')
        self.assertNotContains(resp, 'er-api.com')       # cotação viva removida

    def test_catalogo_pdf(self):
        # F9: catálogo em PDF — matriz (colunas=listas, seções=kind) + seletor
        # de idioma do DOCUMENTO (?lang=, independe da sessão).
        # F10.6: seletor de MOEDA (?currency=rmb|usd; default usd = derivado).
        from pricing.pdf import catalog_data
        columns, sections = catalog_data(self.buyer)                 # default: usd
        # Ordem = a da sidebar (sort Python por nome, ASCII): 'SK' < 'Sa'.
        self.assertEqual(columns, ['SK Hynix P6', 'Samsung P6'])
        self.assertEqual([s['title'] for s in sections], ['eMMC', 'UFS'])
        emmc = sections[0]['rows'][0]
        self.assertEqual(emmc['label'], '64GB')
        # USD DERIVADO: ¥6 × 0.14 = 0.84 (o fixture guarda ¥ 6.00).
        self.assertEqual(emmc['cells'][1], ('quoted', '0.84'))
        self.assertEqual(emmc['cells'][0], ('unquoted', None))   # SK sem linha
        # Moeda RMB: o ¥ armazenado cru, sem zeros à direita.
        _cols, sections_rmb = catalog_data(self.buyer, currency='rmb')
        self.assertEqual(sections_rmb[0]['rows'][0]['cells'][1], ('quoted', '6'))

        self.client.force_login(self.partner)
        resp = self.client.get('/partner/catalog.pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        self.assertIn('wuquan-p6-prices-usd-', resp['Content-Disposition'])
        resp_rmb = self.client.get('/partner/catalog.pdf?currency=rmb')
        self.assertTrue(resp_rmb.content.startswith(b'%PDF'))
        self.assertIn('wuquan-p6-prices-rmb-', resp_rmb['Content-Disposition'])
        resp_zh = self.client.get('/partner/catalog.pdf?lang=zh-hans&currency=rmb')
        self.assertTrue(resp_zh.content.startswith(b'%PDF'))     # fonte CJK + ¥
        self.assertContains(self.client.get('/partner/'), 'catalog.pdf')
        self.client.logout()
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/partner/catalog.pdf').status_code, 403)

    def test_lancadeira_redireciona_parceiro_para_o_partner(self):
        self.client.force_login(self.partner)
        resp = self.client.get('/painel/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/partner/')

    def test_lista_mostra_so_linhas_proprias_sem_auditoria(self):
        # GRID UNIFICADO (2026-07-07): a página mostra SÓ as linhas da própria
        # lista — herança não aparece na UI (fica no engine, p/ marcas sem lista).
        self.client.force_login(self.partner)
        resp = self.client.get(f'/partner/lists/{self.l_samsung.pk}/')
        self.assertContains(resp, '6.00')                    # value unlocalized
        self.assertContains(resp, 'Não fabricado')           # opção do select
        self.assertNotContains(resp, 'herdado')
        self.assertNotContains(resp, 'Atualizado')           # auditoria invisível
        self.assertNotContains(resp, 'parceiro_p6')
        # SK (sem linhas próprias antes do seed_price_grid) vem vazia:
        resp_sk = self.client.get(f'/partner/lists/{self.l_sk.pk}/')
        self.assertNotContains(resp_sk, '6.00')

    def test_filtros_por_tipo_e_estado(self):
        self.client.force_login(self.partner)
        url = f'/partner/lists/{self.l_samsung.pk}/'
        resp = self.client.get(url, {'kind': 'ufs'})
        self.assertNotContains(resp, 'value="6.00"')         # linha eMMC filtrada
        self.assertContains(resp, 'UFS')
        resp2 = self.client.get(url, {'state': 'quoted'})
        self.assertContains(resp2, 'value="6.00"')
        self.assertNotContains(resp2, '>256GB')              # a UFS 256 é unquoted

    def test_save_cota_no_buy_e_volta_a_aguardando(self):
        self.client.force_login(self.partner)
        # F6.1 MODERAÇÃO: o save do parceiro NÃO muda o Price — cria um pedido
        # pendente; só a aprovação do admin aplica.
        from pricing.models import PriceChangeRequest
        url = f'/partner/save/{self.l_samsung.pk}/'
        key = dict(kind='emmc', gen='', tier_value='64', tier_unit='GB')
        row = Price.all_companies.get(price_list=self.l_samsung, kind='emmc')

        # 1) pede cotação nova → Price INTACTO + pedido pendente
        self.client.post(url, {**key, 'state': 'quoted', 'price': '5.50'})
        row.refresh_from_db()
        self.assertEqual(row.price_min, Decimal('6.00'))     # nada mudou ainda
        req = PriceChangeRequest.all_companies.get(price=row)
        self.assertEqual(req.review_status, 'pending')
        self.assertEqual((req.new_price, req.old_price),
                         (Decimal('5.50'), Decimal('6.00')))
        self.assertEqual(req.requested_by, self.partner)

        # o grid mostra o aviso "em revisão":
        resp = self.client.get(f'/partner/lists/{self.l_samsung.pk}/')
        self.assertContains(resp, 'em revisão')

        # 2) editar de novo ATUALIZA o pedido pendente (não empilha)
        self.client.post(url, {**key, 'state': 'quoted', 'price': '5.75'})
        self.assertEqual(
            PriceChangeRequest.all_companies.filter(price=row).count(), 1)
        req.refresh_from_db()
        self.assertEqual(req.new_price, Decimal('5.75'))

        # 3) APROVAR aplica no Price (data = dia da aprovação; autor = parceiro)
        User = get_user_model()
        dono = User.objects.create_superuser('dono_p6', password='x')
        req.approve(dono)
        row.refresh_from_db()
        self.assertEqual(row.price_min, Decimal('5.75'))
        self.assertEqual(row.status, STATUS_QUOTED)
        self.assertEqual(row.quote_date, date.today())
        self.assertEqual(row.updated_by, self.partner)
        req.refresh_from_db()
        self.assertEqual((req.review_status, req.reviewed_by),
                         ('approved', dono))

        # 4) REJEITAR não toca no Price
        self.client.post(url, {**key, 'state': 'no_buy'})
        req2 = PriceChangeRequest.all_companies.get(price=row,
                                                    review_status='pending')
        req2.reject(dono)
        row.refresh_from_db()
        self.assertEqual(row.status, STATUS_QUOTED)          # segue cotado 5.75
        self.assertEqual(row.price_min, Decimal('5.75'))

        # 5) no-op não gera pedido fantasma
        self.client.post(url, {**key, 'state': 'quoted', 'price': '5.75'})
        self.assertFalse(PriceChangeRequest.all_companies.filter(
            price=row, review_status='pending').exists())

        # 6) 🔔 NOTIFICAÇÕES: as 2 decisões (aprovada + rejeitada) viram badge…
        resp = self.client.get('/partner/')
        self.assertContains(resp, 'Notificações')
        self.assertEqual(resp.wsgi_request.partner_unseen, 2)
        # …a página lista as decisões e ZERA o badge ao abrir:
        resp = self.client.get('/partner/notifications/')
        self.assertContains(resp, '✔ Aprovado')
        self.assertContains(resp, '✘ Rejeitado')
        self.assertContains(resp, '¥ 5.75')              # F10: pedido em ¥
        resp = self.client.get('/partner/')
        self.assertEqual(resp.wsgi_request.partner_unseen, 0)

    def test_save_invalido_nao_grava(self):
        self.client.force_login(self.partner)
        url = f'/partner/save/{self.l_samsung.pk}/'
        antes = Price.all_companies.get(price_list=self.l_samsung, kind='emmc')
        resp = self.client.post(url, dict(kind='emmc', gen='', tier_value='64',
                                          tier_unit='GB', state='quoted',
                                          price='abc'), follow=True)
        self.assertContains(resp, 'Preço ilegível')
        resp2 = self.client.post(url, dict(kind='emmc', gen='', tier_value='64',
                                           tier_unit='GB', state='quoted'),
                                 follow=True)
        self.assertContains(resp2, 'exige o preço')          # Cotado sem USD
        depois = Price.all_companies.get(price_list=self.l_samsung, kind='emmc')
        self.assertEqual(depois.price_min, antes.price_min)  # intacto

    def test_isolamento_entre_compradores(self):
        self.client.force_login(self.other_partner)
        self.assertEqual(
            self.client.get(f'/partner/lists/{self.l_samsung.pk}/').status_code, 404)
        resp = self.client.post(f'/partner/save/{self.l_samsung.pk}/',
                                dict(kind='emmc', gen='', tier_value='64',
                                     tier_unit='GB', state='quoted',
                                     price='1.00'))
        self.assertEqual(resp.status_code, 404)
        row = Price.all_companies.get(price_list=self.l_samsung, kind='emmc')
        self.assertEqual(row.price_min, Decimal('6.00'))     # intocado


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


class PartnerSelfAccessRLSTests(TransactionTestCase):
    """Regressão do bug de PRODUÇÃO 2026-07-09: o parceiro (sem Membership →
    sem ``app.company_id``) precisa enxergar o PRÓPRIO Buyer sob RLS+FORCE —
    senão o gate do /partner/ lê zero linhas e devolve 403. É a policy da
    pricing/0010 (auto-acesso via ``app.user_id``, que o TenancyMiddleware
    agora emite para todo autenticado). Postgres-only; no dev conectado como
    superuser o RLS nem morde (§6.2.1) — troca para o role de sondagem.

        python manage.py test pricing.tests.PartnerSelfAccessRLSTests
    """

    @skipUnless(connection.vendor == 'postgresql', 'RLS é Postgres-only')
    def test_parceiro_ve_o_proprio_buyer_e_nada_mais(self):
        from estoque.tests import enter_non_superuser
        User = get_user_model()
        a = Company.objects.create(name='SelfA', slug='selfa')
        b = Company.objects.create(name='SelfB', slug='selfb')
        wuquan = User.objects.create_user('rls_wuquan')
        buyer_dele = Buyer.all_companies.create(company=a, name='Wu Quan',
                                                slug='rls-wuquan')
        buyer_dele.users.add(wuquan)
        Buyer.all_companies.create(company=b, name='Outro Comprador',
                                   slug='rls-outro')

        def _clear():
            with connection.cursor() as c:
                for guc in ('app.company_id', 'app.platform', 'app.user_id'):
                    c.execute("SELECT set_config(%s, '', false)", [guc])
        self.addCleanup(_clear)
        _clear()

        with connection.cursor() as cur:
            enter_non_superuser(self, cur)

            # Sem NENHUM GUC (o estado do bug): zero linhas → era o 403.
            cur.execute('SELECT count(*) FROM pricing_buyer')
            self.assertEqual(cur.fetchone()[0], 0)

            # Com app.user_id (o que o middleware emite p/ autenticado):
            # o parceiro vê O PRÓPRIO buyer — e SÓ ele.
            cur.execute("SELECT set_config('app.user_id', %s, false)",
                        [str(wuquan.pk)])
            cur.execute('SELECT slug FROM pricing_buyer')
            self.assertEqual([r[0] for r in cur.fetchall()], ['rls-wuquan'])

            # E o mesmo caminho que o GATE usa (ORM), sob o role de sondagem:
            self.assertTrue(
                Buyer.all_companies.filter(users=wuquan, active=True).exists())

            # As tabelas SENSÍVEIS continuam fechadas sem escopo de empresa.
            cur.execute('SELECT count(*) FROM pricing_pricelist')
            self.assertEqual(cur.fetchone()[0], 0)


class DdrDensityFallbackTests(TestCase):
    """Bug do lote 40 (2026-07-11): DDR de SK Hynix/Nanya saía NO_KEY
    ("densidade indisponível") apesar da linha cotada no grid — a gramática
    dessas famílias põe os bytes POR DIE no `capacity` ('256MB') sem
    `dram_density`, e os confirmados via bless_base carregam a convenção da
    caixa ('2G' = Gbit) com `density_gbit` vazio. O `derive_price_key` agora
    despe a densidade do `capacity` (fallback SÓ para ddr/gddr)."""

    def test_fallback_de_densidade_no_capacity(self):
        from .engine import NO_KEY as NK, derive_price_key
        base = {'chip_type': 'DDR3', 'subtype': 'DDR3'}

        # Gramática SK Hynix/Nanya: bytes por die ('256MB' → 2Gb).
        err, key = derive_price_key({**base, 'capacity': '256MB'})
        self.assertIsNone(err)
        self.assertEqual(key, ('ddr', 'DDR3', Decimal('2'), 'Gb'))

        # bless_base / convenção da caixa: '4G' = 4 Gbit.
        err, key = derive_price_key({**base, 'capacity': '4G'})
        self.assertIsNone(err)
        self.assertEqual(key, ('ddr', 'DDR3', Decimal('4'), 'Gb'))

        # 'GB' é BYTE de pacote — NUNCA vira densidade (Gb≠GB, regra da casa).
        err, key = derive_price_key({**base, 'capacity': '2GB'})
        self.assertIsNone(key)
        self.assertEqual(err.status, NK)

        # F0 (density_gbit_num) continua tendo prioridade sobre o fallback.
        err, key = derive_price_key(
            {**base, 'capacity': '256MB', 'density_gbit_num': 8.0})
        self.assertEqual(key[2], Decimal('8'))

        # Fallback NÃO vale para kinds de pacote (eMMC '2G' seguiria sem chave).
        err, key = derive_price_key({'chip_type': 'eMMC', 'capacity': '2G'})
        self.assertIsNone(key)
        self.assertEqual(err.status, NK)

    def test_ddr3l_precifica_como_ddr3(self):
        # Dono (2026-07-11): variante de tensão = mesmo preço da geração-base.
        from .engine import derive_price_key
        err, key = derive_price_key(
            {'chip_type': 'DDR3L', 'subtype': 'DDR3L', 'capacity': '4G'})
        self.assertIsNone(err)
        self.assertEqual(key, ('ddr', 'DDR3', Decimal('4'), 'Gb'))
        # GDDR5X NÃO dobra para GDDR5 (mercado distinto, não é tensão) — e tem
        # vocabulário próprio desde 2026-07-11 (antes caía pra 'GDDR' genérico
        # e mudava a triagem).
        err, key = derive_price_key(
            {'chip_type': 'GDDR5X', 'subtype': 'GDDR5X', 'capacity': '8G'})
        self.assertIsNone(err)
        self.assertEqual(key, ('gddr', 'GDDR5X', Decimal('8'), 'Gb'))


class EnablePriceRowTests(TestCase):
    """enable_price_row (fase 2 do lote 40): flip "não fabricado" → "não
    cotado" para marca que FABRICA de fato, garantindo a genérica junto.
    Cotado/não-compro são intocáveis; faixa fora da grade aponta o
    add_price_row."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='EnbCo', slug='enb-co')
        cls.buyer = Buyer.all_companies.create(company=cls.company,
                                               name='Wuquan E', slug='wuquan-enb')
        sk = Brand.objects.create(name='SK Hynix E', code='SKENB')
        cls.l_sk = PriceList.all_companies.create(buyer=cls.buyer, brand=sk)
        cls.l_gen = PriceList.all_companies.create(buyer=cls.buyer, brand=None)
        for pl, status in ((cls.l_sk, STATUS_NOT_MADE),
                           (cls.l_gen, STATUS_NOT_MADE)):
            Price.all_companies.create(
                price_list=pl, kind='emcp', gen='LPDDR3',
                tier_value=Decimal('8'), tier_unit='GB', status=status)
        # linha COTADA (guarda: nunca rebaixar) — grid unificado: a
        # genérica também tem a linha (não cotada).
        Price.all_companies.create(
            price_list=cls.l_sk, kind='emmc', gen='', tier_value=Decimal('32'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('4.00'), price_max=Decimal('4.00'))
        Price.all_companies.create(
            price_list=cls.l_gen, kind='emmc', gen='', tier_value=Decimal('32'),
            tier_unit='GB', status=STATUS_UNQUOTED)

    def _run(self, commit=False, **extra):
        from io import StringIO
        from django.core.management import call_command
        from tenancy.scope import set_current_company
        out = StringIO()
        base = dict(buyer='wuquan-enb', brand='SK Hynix E', kind='emcp',
                    gen='LPDDR3', tier='8', unit='GB', commit=commit)
        base.update(extra)
        try:
            call_command('enable_price_row', stdout=out, **base)
        finally:
            set_current_company(None)
        return out.getvalue()

    def _status(self, pl, **key):
        return Price.all_companies.get(price_list=pl, **key).status

    def test_flip_com_generica_e_idempotencia(self):
        key = dict(kind='emcp', gen='LPDDR3', tier_value=Decimal('8'),
                   tier_unit='GB')
        out = self._run(commit=False)                      # dry-run: nada muda
        self.assertIn('não fabricado → não cotado', out)
        self.assertEqual(self._status(self.l_sk, **key), STATUS_NOT_MADE)

        self._run(commit=True)                             # flipa marca+genérica
        self.assertEqual(self._status(self.l_sk, **key), STATUS_UNQUOTED)
        self.assertEqual(self._status(self.l_gen, **key), STATUS_UNQUOTED)

        out = self._run(commit=True)                       # idempotente
        self.assertIn('já está "não cotado"', out)

    def test_cotada_e_fora_da_grade_sao_protegidas(self):
        from django.core.management.base import CommandError
        # Linha cotada NUNCA é rebaixada (nem com commit).
        out = self._run(commit=True, kind='emmc', gen='', tier='32')
        self.assertIn('já COTADA', out)
        self.assertEqual(
            self._status(self.l_sk, kind='emmc', gen='',
                         tier_value=Decimal('32'), tier_unit='GB'),
            STATUS_QUOTED)
        # Fora da grade → erro apontando o add_price_row.
        with self.assertRaises(CommandError):
            self._run(commit=True, tier='128')


class MigratePricesToRmbTests(TestCase):
    """F10.1: a migração DIVIDE pela taxa em que os USD nasceram (0.15),
    recuperando os ¥ originais (13.50 → ¥90); reporta ¥ não-redondo; reverte."""

    def test_converte_e_reverte(self):
        from io import StringIO
        from django.core.management import call_command
        from tenancy.scope import set_current_company
        co = Company.objects.create(name='RmbCo', slug='rmb-co')
        buyer = Buyer.all_companies.create(company=co, name='Wu R', slug='wu-rmb')
        b = Brand.objects.create(name='Sam RMB', code='SAMRMB')
        pl = PriceList.all_companies.create(buyer=buyer, brand=b)
        p = Price.all_companies.create(
            price_list=pl, kind='emmc', gen='', tier_value=Decimal('64'),
            tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('13.50'), price_max=Decimal('13.50'))
        try:
            out = StringIO()
            call_command('migrate_prices_to_rmb', buyer='wu-rmb',
                         rate_used='0.15', stdout=out)          # dry-run
            p.refresh_from_db()
            self.assertEqual(p.price_min, Decimal('13.50'))     # nada mudou
            call_command('migrate_prices_to_rmb', buyer='wu-rmb',
                         rate_used='0.15', commit=True, stdout=out)
            p.refresh_from_db()
            self.assertEqual(p.price_min, Decimal('90.00'))     # ¥ original
            self.assertEqual(p.price_max, Decimal('90.00'))
            call_command('migrate_prices_to_rmb', buyer='wu-rmb',
                         rate_used='0.15',
                         revert='migrate_prices_to_rmb_revert.json', stdout=out)
            p.refresh_from_db()
            self.assertEqual(p.price_min, Decimal('13.50'))     # desfeito
            # taxa vigente é OUTRO número (0.14) e vive no Buyer:
            self.assertEqual(buyer.fx_usd_rate, Decimal('0.14'))
        finally:
            set_current_company(None)
            import os
            if os.path.exists('migrate_prices_to_rmb_revert.json'):
                os.unlink('migrate_prices_to_rmb_revert.json')
