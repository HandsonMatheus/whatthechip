"""
vendas/tests.py — F11.2: Cotação → OV (fechamento gera draft; confirmar
congela ¥+taxa+US$; reabrir cancela draft / bloqueia com confirmada; gates).

    python manage.py test vendas --settings=core.settings_test
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from chips.models import Brand
from estoque.models import InventoryEntry, Lot
from pricing.models import (Buyer, Price, PriceList, STATUS_QUOTED,
                            STATUS_UNQUOTED)
from tenancy.models import Company, Membership
from tenancy.scope import company_scope, set_current_company

from . import services
from .models import (DocSequence, SEQ_SO, STATUS_CANCELLED, STATUS_CONFIRMED,
                     STATUS_DRAFT, SalesOrder)


def _setup(slug):
    """Empresa + comprador (¥ no grid) + lote com entradas CHAVEADAS (F11.1)."""
    company = Company.objects.create(name=f'Vd {slug}', slug=slug)
    buyer = Buyer.all_companies.create(company=company, name=f'Wu {slug}',
                                       slug=f'wu-{slug}')
    samsung = Brand.objects.create(name=f'Samsung {slug}',
                                   code=f'V{slug[-3:]}'.upper())
    pl = PriceList.all_companies.create(buyer=buyer, brand=samsung)
    Price.all_companies.create(
        price_list=pl, kind='emmc', gen='', tier_value=Decimal('16'),
        tier_unit='GB', status=STATUS_QUOTED,
        price_min=Decimal('15'), price_max=Decimal('15'))      # ¥15 → US$ 2.10
    Price.all_companies.create(
        price_list=pl, kind='emcp', gen='LPDDR4X', tier_value=Decimal('64'),
        tier_unit='GB', status=STATUS_QUOTED,
        price_min=Decimal('90'), price_max=Decimal('90'))      # ¥90 → US$ 12.60
    return company, buyer, samsung.name


def _entries(lot, brand, com_emcp=True):
    """Entradas já com a CHAVE materializada (como o intake F11.1 grava)."""
    InventoryEntry.all_companies.create(
        lot=lot, part_number='VDEMMC1', quantity=3, brand=brand,
        chip_type='eMMC', company=lot.company,
        price_kind='emmc', price_gen='', price_tier_value=Decimal('16'),
        price_tier_unit='GB')
    InventoryEntry.all_companies.create(
        lot=lot, part_number='VDEMMC2', quantity=2, brand=brand,
        chip_type='eMMC', company=lot.company,
        price_kind='emmc', price_gen='', price_tier_value=Decimal('16'),
        price_tier_unit='GB')                       # MESMA categoria → agrega
    if com_emcp:
        InventoryEntry.all_companies.create(
            lot=lot, part_number='VDEMCP1', quantity=4, brand=brand,
            chip_type='eMCP', company=lot.company,
            price_kind='emcp', price_gen='LPDDR4X',
            price_tier_value=Decimal('64'), price_tier_unit='GB')
    InventoryEntry.all_companies.create(
        lot=lot, part_number='VDSOC1', quantity=7, brand=brand,
        chip_type='SoC', company=lot.company,
        price_key_reason='tipo fora do mercado de preço')      # sem chave


class SalesOrderFlowTests(TestCase):
    """O ciclo inteiro: fechar → draft agregado → confirmar congela → cancelar."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-flow')
        User = get_user_model()
        cls.user = User.objects.create_user('vd_user')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)

    def _lot(self):
        lot = Lot.open_for_company(self.company, self.user, 'lote VD')
        _entries(lot, self.brand)
        return lot

    def test_fechamento_gera_draft_agregado_por_categoria(self):
        lot = self._lot()
        so = services.create_draft_for_lot(lot, self.user)
        self.assertIsNotNone(so)
        self.assertEqual(so.status, STATUS_DRAFT)
        self.assertEqual(so.buyer, self.buyer)
        self.assertEqual(so.unkeyed_units, 7)               # o SoC, transparente
        # 2 PNs eMMC 16GB da MESMA marca → UMA linha com qty 5 (resumo).
        lines = {(l.kind, l.gen, str(l.tier_value)): l.quantity
                 for l in so.lines.all()}
        self.assertEqual(lines[('emmc', '', '16.0')], 5)
        self.assertEqual(lines[('emcp', 'LPDDR4X', '64.0')], 4)
        # Nomenclatura canônica SO/NUM/MM/YY (número perpétuo por empresa):
        self.assertEqual(so.number, 1)
        self.assertTrue(so.code.startswith('SO/001/'))
        # Draft é VIVO: nada congelado ainda.
        self.assertIsNone(so.total_rmb)
        self.assertTrue(all(l.unit_rmb is None for l in so.lines.all()))
        # Re-fechar sem reabrir NÃO duplica:
        self.assertIsNone(services.create_draft_for_lot(lot, self.user))

    def test_confirmar_congela_yuan_taxa_e_usd(self):
        lot = self._lot()
        so = services.create_draft_for_lot(lot, self.user)
        services.confirm(so, self.user)
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CONFIRMED)
        self.assertEqual(so.fx_usd_rate, Decimal('0.14'))   # taxa da confirmação
        # 5 × ¥15 + 4 × ¥90 = ¥435 → US$ 60.90 @0.14:
        self.assertEqual(so.total_rmb, Decimal('435.00'))
        self.assertEqual(so.total_usd, Decimal('60.90'))
        emcp = so.lines.get(kind='emcp')
        self.assertEqual((emcp.unit_rmb, emcp.unit_usd),
                         (Decimal('90'), Decimal('12.60')))
        # Congelado NÃO acompanha o grid: preço muda → OV fica.
        row = Price.all_companies.get(kind='emcp',
                                      price_list__buyer=self.buyer)
        row.price_min = row.price_max = Decimal('100')
        row.save()
        so.refresh_from_db()
        self.assertEqual(so.total_rmb, Decimal('435.00'))   # intacta

    def test_confirmar_bloqueia_com_linha_sem_preco(self):
        lot = self._lot()
        # eMCP some do grid → vira "não cotado" (linha existe, sem valor):
        row = Price.all_companies.get(kind='emcp',
                                      price_list__buyer=self.buyer)
        row.status, row.price_min, row.price_max = STATUS_UNQUOTED, None, None
        row.save()
        so = services.create_draft_for_lot(lot, self.user)
        with self.assertRaises(ValidationError) as cm:
            services.confirm(so, self.user)
        self.assertIn('sem preço', str(cm.exception))
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_DRAFT)           # nada congelou

    def test_numeracao_perpetua_por_empresa(self):
        self.assertEqual(DocSequence.next_number(self.company, SEQ_SO), 1)
        self.assertEqual(DocSequence.next_number(self.company, SEQ_SO), 2)
        outra = Company.objects.create(name='Vd Outra', slug='vd-outra')
        self.assertEqual(DocSequence.next_number(outra, SEQ_SO), 1)


class LotCloseReopenTests(TestCase):
    """Hooks no estoque: fechar cria o draft; reabrir cancela draft e é
    BLOQUEADO com OV confirmada (padrão Odoo — dono, 2026-07-16)."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-hook')
        User = get_user_model()
        cls.mgr = User.objects.create_user('vd_mgr', password='x')
        cls.adm = User.objects.create_user('vd_adm', password='x')
        Membership.objects.create(user=cls.mgr, company=cls.company,
                                  role=Membership.ROLE_MANAGER)
        Membership.objects.create(user=cls.adm, company=cls.company,
                                  role=Membership.ROLE_ADMIN)

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        self.lot = Lot.open_for_company(self.company, self.mgr, 'VD hook')
        _entries(self.lot, self.brand, com_emcp=False)

    def test_fechar_cria_draft_e_reabrir_cancela(self):
        self.client.force_login(self.mgr)
        self.client.post(reverse('estoque:lot_close', args=[self.lot.pk]),
                         {'confirm_code': self.lot.code})
        so = SalesOrder.all_companies.get(lot=self.lot)
        self.assertEqual(so.status, STATUS_DRAFT)
        self.client.post(reverse('estoque:lot_reopen', args=[self.lot.pk]))
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CANCELLED)       # draft cancelado
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.STATUS_OPEN)
        # Re-fechar cria OUTRA (número novo — sequência perpétua):
        self.client.post(reverse('estoque:lot_close', args=[self.lot.pk]),
                         {'confirm_code': self.lot.code})
        so2 = (SalesOrder.all_companies.filter(lot=self.lot)
               .exclude(pk=so.pk).get())
        self.assertGreater(so2.number, so.number)

    def test_admin_fecha_e_cai_na_venda_e_smart_buttons(self):
        """F11.2c: admin fecha → redirect direto pra OV; smart buttons nos
        dois sentidos (lote↔venda); PDF baixa; gerente segue no lote."""
        self.client.force_login(self.adm)
        resp = self.client.post(
            reverse('estoque:lot_close', args=[self.lot.pk]),
            {'confirm_code': self.lot.code})
        so = SalesOrder.all_companies.get(lot=self.lot)
        self.assertEqual(resp['Location'],
                         reverse('vendas:so_detail', args=[so.pk]))
        # Smart button no LOTE aponta pra venda (admin):
        lot_page = self.client.get(
            reverse('estoque:lot_detail', args=[self.lot.pk]))
        self.assertContains(lot_page, so.code)
        # Smart button na VENDA aponta pro lote + botão de PDF:
        so_page = self.client.get(reverse('vendas:so_detail', args=[so.pk]))
        self.assertContains(so_page, self.lot.code)
        self.assertContains(so_page, 'Baixar PDF')
        pdf = self.client.get(reverse('vendas:so_pdf', args=[so.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertIn(so.code.replace('/', '-'), pdf['Content-Disposition'])

    def test_fechar_sem_codigo_correto_nao_fecha(self):
        """F11.2c: type-to-confirm é barreira de VIEW — código errado barra."""
        self.client.force_login(self.mgr)
        resp = self.client.post(
            reverse('estoque:lot_close', args=[self.lot.pk]),
            {'confirm_code': 'LOT/999/01/99'}, follow=True)
        self.assertContains(resp, 'não confere')
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.STATUS_OPEN)   # NÃO fechou
        self.assertFalse(SalesOrder.all_companies.filter(lot=self.lot).exists())

    def test_ov_confirmada_bloqueia_reabertura(self):
        self.client.force_login(self.mgr)
        self.client.post(reverse('estoque:lot_close', args=[self.lot.pk]),
                         {'confirm_code': self.lot.code})
        so = SalesOrder.all_companies.get(lot=self.lot)
        with company_scope(self.company):
            services.confirm(so, self.adm)
        resp = self.client.post(
            reverse('estoque:lot_reopen', args=[self.lot.pk]), follow=True)
        self.assertContains(resp, 'CONFIRMADA')             # aviso ao gerente
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.STATUS_CLOSED)  # NÃO reabriu
        # Cancelando a OV, a reabertura passa:
        with company_scope(self.company):
            services.cancel(so, self.adm)
        self.client.post(reverse('estoque:lot_reopen', args=[self.lot.pk]))
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.STATUS_OPEN)


class BackfillSalesOrdersTests(TestCase):
    """F11.3: lote FECHADO sem OV ganha OV retroativa CONFIRMADA a partir do
    LotPricing congelado — total USD fiel, ¥ = USD ÷ taxa da época (0.15),
    confirmed_at = data do congelamento; linhas só com quantidades."""

    def test_backfill_cria_confirmada_e_e_idempotente(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        from pricing.models import LotPricing

        company, buyer, brand = _setup('vd-back')
        User = get_user_model()
        u = User.objects.create_user('vd_back')
        set_current_company(company.pk)
        self.addCleanup(set_current_company, None)

        lot = Lot.open_for_company(company, u, 'histórico')
        _entries(lot, brand, com_emcp=False)          # 5 un. eMMC + 7 sem chave
        lot.status, lot.closed_at = Lot.STATUS_CLOSED, timezone.now()
        lot.save(update_fields=['status', 'closed_at'])
        lp = LotPricing.all_companies.create(
            lot=lot, buyer=buyer,
            total_low=Decimal('60.90'), total_mid=Decimal('60.90'),
            total_high=Decimal('60.90'), priced_units=5, total_units=12,
            priced_lines=2, total_lines=3,
            lines=[{'pn': 'VDEMMC1', 'qty': 3, 'status': 'PRICED'}])

        out = StringIO()
        call_command('backfill_sales_orders', company='vd-back', stdout=out)
        self.assertFalse(SalesOrder.all_companies.exists())   # dry-run
        call_command('backfill_sales_orders', company='vd-back',
                     commit=True, stdout=out)
        so = SalesOrder.all_companies.get(lot=lot)
        self.assertEqual(so.status, STATUS_CONFIRMED)
        self.assertEqual(so.total_usd, Decimal('60.90'))
        self.assertEqual(so.total_rmb, Decimal('406.00'))     # 60.90 ÷ 0.15
        self.assertEqual(so.fx_usd_rate, Decimal('0.15'))     # taxa da ÉPOCA
        so.refresh_from_db()
        self.assertEqual(so.confirmed_at, lp.created_at)      # cronologia fiel
        line = so.lines.get()
        self.assertEqual((line.kind, line.quantity, line.unit_rmb),
                         ('emmc', 5, None))                   # qty sim, unit não
        self.assertEqual(so.unkeyed_units, 7)
        # Idempotente: re-rodar não duplica.
        call_command('backfill_sales_orders', company='vd-back',
                     commit=True, stdout=out)
        self.assertEqual(SalesOrder.all_companies.filter(lot=lot).count(), 1)


class VendasGateTests(TestCase):
    """Menu Vendas é ADMIN-only: gerente/operador/anônimo não veem valor."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-gate')
        User = get_user_model()
        cls.users = {}
        for role in ('admin', 'manager', 'operator'):
            u = User.objects.create_user(f'vdg_{role}', password='x')
            Membership.objects.create(user=u, company=cls.company, role=role)
            cls.users[role] = u

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)

    def test_admin_ve_e_demais_nao(self):
        lot = Lot.open_for_company(self.company, self.users['manager'], 'g')
        _entries(lot, self.brand, com_emcp=False)
        so = services.create_draft_for_lot(lot, self.users['manager'])

        self.client.force_login(self.users['admin'])
        resp = self.client.get(reverse('vendas:so_list'))
        self.assertContains(resp, so.code)
        detail = self.client.get(reverse('vendas:so_detail', args=[so.pk]))
        self.assertContains(detail, '¥ 15')                  # draft vivo, ¥
        self.assertContains(detail, 'US$')
        for role in ('manager', 'operator'):
            self.client.force_login(self.users[role])
            self.assertEqual(
                self.client.get(reverse('vendas:so_list')).status_code, 403)
        self.client.logout()
        resp = self.client.get(reverse('vendas:so_list'))
        self.assertIn(resp.status_code, (302, 403))          # anônimo → login
