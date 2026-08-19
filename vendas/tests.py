"""
vendas/tests.py — F11.2: Cotação → OV (fechamento gera draft; confirmar
congela ¥+taxa+US$; reabrir cancela draft / bloqueia com confirmada; gates).

    python manage.py test vendas --settings=core.settings_test
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chips.models import Brand
from estoque.models import InventoryEntry, Lot
from pricing.models import (Buyer, Price, PriceList, STATUS_QUOTED,
                            STATUS_UNQUOTED)
from tenancy.models import Company, Membership
from tenancy.scope import company_scope, set_current_company

from . import services
from .models import (DocSequence, Invoice, SEQ_SO, STATUS_CANCELLED,
                     STATUS_CONFIRMED, STATUS_DRAFT, SalesOrder)


def _setup(slug):
    """Empresa + comprador (¥ no grid) + lote com entradas CHAVEADAS (F11.1)."""
    company = Company.objects.create(name=f'Vd {slug}', slug=slug)
    buyer = Buyer.all_companies.create(company=company, name=f'Wu {slug}',
                                       slug=f'wu-{slug}')
    samsung = Brand.objects.create(name=f'Samsung {slug}',
                                   code=f'V{slug[-3:]}'.upper())
    pl = PriceList.all_companies.create(buyer=buyer, brand=samsung)
    generica = PriceList.all_companies.create(buyer=buyer, brand=None)
    # correção 2026-08-01: eMMC é UNIFICADO — linha na GENÉRICA
    Price.all_companies.create(
        price_list=generica, kind='emmc', gen='', origin='phone', tier_value=Decimal('16'),
        tier_unit='GB', status=STATUS_QUOTED,
        price_min=Decimal('15'), price_max=Decimal('15'))      # ¥15 → US$ 2.10
    # ESTRUTURAL 2026-07-27: eMCP é UNIFICADO — linha SÓ na genérica.
    Price.all_companies.create(
        price_list=generica, kind='emcp', gen='', tier_value=Decimal('64'),
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


def _streams_do_pdf(pdf: bytes):
    """Os streams de TEXTO do PDF, um a um (compressão desligada).

    Duas exclusões que a suíte aprendeu na marra (2026-08-18):
    · stream de IMAGEM (logo) — pelo ``/Filter`` do dicionário; sem isso o
      blob ASCII85 entra na busca e um `assertNotIn(b'US$')` falha por
      coincidência de bytes;
    · stream de FONTE (o CMap da TTF chinesa) — por não conter ``Tj``. E é
      preciso rodar o regex de texto DENTRO de cada stream, nunca no
      conjunto concatenado: um ``(`` solto no CMap casava com o ``) Tj`` do
      stream seguinte e devolvia meio PDF como se fosse "um texto".
    """
    import re
    fora = []
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', pdf, re.S):
        if b'/Filter' in pdf[max(0, m.start() - 400):m.start()]:
            continue
        if b' Tj' not in m.group(1):
            continue
        fora.append(m.group(1))
    return fora


def _conteudo_do_pdf(pdf: bytes) -> bytes:
    """Os streams de texto concatenados — para asserção sobre a ORDEM em que
    as coisas são desenhadas (ex.: qual fonte vale em cada código)."""
    return b'\n'.join(_streams_do_pdf(pdf))


def _textos_do_pdf(pdf: bytes):
    """Os textos DESENHADOS no PDF (operadores ``(…) Tj``), já sem os números
    de coordenada do stream. Asserção sobre coordenada é armadilha: procurar
    '12.60' cru acha o 512.6047 de uma posição de tabela."""
    import re
    return [t for fluxo in _streams_do_pdf(pdf)
            for t in re.findall(rb'\((.*?)\) Tj', fluxo, re.S)]


def _sem_compressao(test):
    """Desliga a compressão de stream do reportlab SÓ no teste — sem isto o
    texto do PDF vira binário e nenhuma asserção de conteúdo é possível."""
    from reportlab import rl_config
    antes, rl_config.pageCompression = rl_config.pageCompression, 0
    test.addCleanup(setattr, rl_config, 'pageCompression', antes)


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
        lot = Lot.open_for_company(self.company, self.user, 'lote VD', origin='phone')
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
        # v3.1: combo keia SÓ pelo NAND — gen vazio na linha.
        self.assertEqual(lines[('emcp', '', '64.0')], 4)
        # Nomenclatura canônica SO/EMPRESA/NUM/MM/YY (número perpétuo por
        # empresa; o código da empresa entrou no prefixo em 2026-08-18):
        self.assertEqual(so.number, 1)
        self.assertTrue(so.code.startswith(f'SO/{so.company.code}/001/'))
        # Draft é VIVO: nada congelado ainda.
        self.assertIsNone(so.total_rmb)
        self.assertTrue(all(l.unit_rmb is None for l in so.lines.all()))
        # Re-fechar sem reabrir NÃO duplica:
        self.assertIsNone(services.create_draft_for_lot(lot, self.user))

    def test_draft_funde_lpddr4_e_4x_na_mesma_linha(self):
        # Fold (dono 2026-07-21): "LPDDR4X e LPDDR4 são a mesma coisa, uma só
        # caixa" — entradas com chave gravada PRÉ-fold (gen 'LPDDR4X') fundem
        # com as 'LPDDR4' na MESMA linha da OV (agregação dobra o gen).
        from decimal import Decimal as D
        from chips.models import CatalogVersion
        lot = Lot.open_for_company(self.company, self.user, 'lote fold', origin='phone')
        for pn, gen, qty in (('LPFOLD4', 'LPDDR4', 2), ('LPFOLD4X', 'LPDDR4X', 3)):
            InventoryEntry.all_companies.create(
                lot=lot, part_number=pn, quantity=qty, brand='Samsung VD',
                chip_type='LPDDR4', company=self.company,
                snapshot_catalog_version=CatalogVersion.current(),
                price_kind='lpddr', price_gen=gen,
                price_tier_value=D('4'), price_tier_unit='GB')
        so = services.create_draft_for_lot(lot, self.user)
        linhas = list(so.lines.filter(kind='lpddr'))
        self.assertEqual(len(linhas), 1)                    # UMA linha/caixa
        self.assertEqual(linhas[0].gen, 'LPDDR4')           # grafada na base
        self.assertEqual(linhas[0].quantity, 5)             # 2 + 3

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
        # PLANO_FX C (2026-08-01): REABRIR virou exclusivo do superuser —
        # o gerente da fixture agora é superuser pra exercitar o fluxo
        # completo fechar→reabrir (o gate em si é provado no
        # estoque.FxLockOnCloseTests).
        cls.mgr = User.objects.create_superuser('vd_mgr', password='x')
        cls.adm = User.objects.create_user('vd_adm', password='x')
        Membership.objects.create(user=cls.mgr, company=cls.company,
                                  role=Membership.ROLE_MANAGER)
        Membership.objects.create(user=cls.adm, company=cls.company,
                                  role=Membership.ROLE_ADMIN)

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        self.lot = Lot.open_for_company(self.company, self.mgr, 'VD hook', origin='phone')
        _entries(self.lot, self.brand, com_emcp=False)

    def test_fechar_cria_ov_em_RASCUNHO(self):
        """RE-ESPECIFICADO de novo (dono, 2026-08-18, tarde): quem congela é o
        DESPACHO. Fechar o lote é ato de bancada — a venda só existe quando a
        caixa sai, e até lá o preço segue vivo."""
        self.client.force_login(self.mgr)
        self.client.post(reverse('estoque:lot_close', args=[self.lot.pk]),
                         {'confirm_code': self.lot.code})
        so = SalesOrder.all_companies.get(lot=self.lot)
        self.assertEqual(so.status, STATUS_DRAFT)
        self.assertIsNone(so.shipped_at)
        self.assertIsNone(so.total_rmb)

    def test_lote_sem_preco_nasce_rascunho_e_reabrir_cancela(self):
        """O único caminho que ainda nasce VIVO: categoria fora do grid do
        comprador. Aí o rascunho é cancelado ao reabrir, como sempre foi."""
        self.client.force_login(self.mgr)
        InventoryEntry.all_companies.create(       # sem linha no grid
            lot=self.lot, part_number='HOOKSEMPRECO', quantity=3,
            brand=self.brand, chip_type='UFS', company=self.company,
            price_kind='ufs', price_gen='',
            price_tier_value=Decimal('512'), price_tier_unit='GB')
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
        # RE-ESPECIFICADO 2× (dono, 2026-08-18): quem congela é o DESPACHO.
        # A regra provada aqui é a mesma — OV confirmada barra a reabertura —,
        # só que agora o gatilho é registrar que a caixa saiu. Faz até mais
        # sentido: depois do embarque não há o que reabrir.
        with company_scope(self.company):
            services.mark_shipped(so, 'DHL', 'JD1', None, self.mgr)
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CONFIRMED)
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


class SettlementInvoicePaymentTests(TestCase):
    """F11.4: resultado do comprador (mortos+repreço) → fatura com valor
    final (OV INTACTA — padrão Odoo) → pagamentos US$ parciais → paga."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-set')
        User = get_user_model()
        cls.adm = User.objects.create_user('vd_set_adm', password='x')
        Membership.objects.create(user=cls.adm, company=cls.company,
                                  role=Membership.ROLE_ADMIN)

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        lot = Lot.open_for_company(self.company, self.adm, 'set', origin='phone')
        _entries(lot, self.brand)                 # 5 eMMC16 + 4 eMCP64 + SoC
        self.so = services.create_draft_for_lot(lot, self.adm)
        services.confirm(self.so, self.adm)       # ¥435 · US$ 60.90

    def test_acerto_fatura_pagamentos(self):
        from datetime import date
        from vendas.models import Invoice
        emcp = self.so.lines.get(kind='emcp')     # 4 × ¥90
        emmc = self.so.lines.get(kind='emmc')     # 5 × ¥15
        # Resultado: 1 eMCP morto + eMMC repreciado ¥15→¥12.
        st, inv = services.settle_and_invoice(
            self.so, {emcp.pk: (1, None), emmc.pk: (0, Decimal('12'))},
            self.adm, notes='resultado jul')
        # Fatura: 3×¥90 + 5×¥12 = ¥330 → US$ 46.20 @0.14 (soma por linha).
        self.assertEqual(inv.total_rmb, Decimal('330.00'))
        self.assertEqual(inv.total_usd, Decimal('46.20'))
        self.assertEqual(inv.fx_usd_rate, Decimal('0.14'))
        self.assertTrue(inv.code.startswith(f'INV/{inv.company.code}/001/'))
        # OV INTACTA (padrão Odoo): nada mudou na ordem.
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_rmb, Decimal('435.00'))
        emcp.refresh_from_db()
        self.assertEqual((emcp.quantity, emcp.unit_rmb), (4, Decimal('90')))
        # 2ª fatura na mesma OV: barrada.
        with self.assertRaises(ValidationError):
            services.settle_and_invoice(self.so, {}, self.adm)
        # Rejeitar mais que a quantidade: barrado (nova OV seria preciso —
        # aqui só valida a mensagem via fatura ativa cancelada antes):
        services.cancel_invoice(inv, self.adm)
        with self.assertRaises(ValidationError) as cm:
            services.settle_and_invoice(self.so, {emcp.pk: (99, None)},
                                        self.adm)
        self.assertIn('rejeitadas', str(cm.exception).lower())
        # Re-acerto pós-cancelamento: nova fatura, número novo.
        _st2, inv2 = services.settle_and_invoice(self.so, {}, self.adm)
        self.assertGreater(inv2.number, inv.number)
        self.assertEqual(inv2.total_usd, Decimal('60.90'))   # sem ajustes
        # Pagamentos parciais em US$ → saldo → paga.
        services.register_payment(inv2, Decimal('40.00'),
                                  date(2026, 7, 20), self.adm, 'wire 1')
        self.assertEqual(inv2.balance_usd, Decimal('20.90'))
        self.assertEqual(inv2.status, 'open')
        with self.assertRaises(ValidationError):              # acima do saldo
            services.register_payment(inv2, Decimal('21.00'),
                                      date(2026, 7, 21), self.adm)
        services.register_payment(inv2, Decimal('20.90'),
                                  date(2026, 7, 22), self.adm, 'wire 2')
        inv2.refresh_from_db()
        self.assertEqual(inv2.status, 'paid')
        self.assertEqual(inv2.balance_usd, Decimal('0.00'))
        # Fatura com pagamento não cancela.
        with self.assertRaises(ValidationError):
            services.cancel_invoice(inv2, self.adm)

    def test_telas_do_fluxo(self):
        from vendas.models import Invoice
        self.client.force_login(self.adm)
        # ⚠ O CTA saiu da tela da empresa em 2026-08-18 (quem registra o
        # resultado é o COMPRADOR); a ROTA segue viva para o admin.
        resp = self.client.get(reverse('vendas:so_detail', args=[self.so.pk]))
        self.assertNotContains(resp, 'Registrar resultado e faturar')
        # Form do acerto → POST cria fatura e redireciona pra ela:
        emcp = self.so.lines.get(kind='emcp')
        resp = self.client.post(
            reverse('vendas:settlement_new', args=[self.so.pk]),
            {f'rej_{emcp.pk}': '1'})
        inv = Invoice.all_companies.get(order=self.so)
        self.assertEqual(resp['Location'],
                         reverse('vendas:invoice_detail', args=[inv.pk]))
        # Detalhe da fatura: totais + smart buttons OV/lote + form pagamento.
        detail = self.client.get(reverse('vendas:invoice_detail',
                                         args=[inv.pk]))
        self.assertContains(detail, inv.code)
        self.assertContains(detail, self.so.code)
        self.assertContains(detail, 'Registrar pagamento')
        # Smart button FATURA na OV:
        so_page = self.client.get(reverse('vendas:so_detail',
                                          args=[self.so.pk]))
        self.assertContains(so_page, inv.code)
        # Pagamento via POST:
        self.client.post(reverse('vendas:invoice_pay', args=[inv.pk]),
                         {'amount': str(inv.total_usd),
                          'paid_at': '2026-07-20', 'reference': 'wire'})
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'paid')


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

        lot = Lot.open_for_company(company, u, 'histórico', origin='phone')
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


class CongelaNoDespachoTests(TestCase):
    """O ¥ para de andar no DESPACHO, não no fechamento (dono, 2026-08-18).

    ⚠ REVERSÃO do F11.6/F1, que congelava no fechamento do lote. Fechar o lote
    é ato de BANCADA — a venda só existe de verdade quando a caixa SAI. Até
    lá a ordem é rascunho, o preço segue vivo e o comprador nem a enxerga.

    O que motivava congelar no fechamento — "o papel imprime preço" — vale só
    para a via do ADMIN; a do gerente, que viaja com a caixa, não tem coluna
    de dinheiro. E ela é impressa DEPOIS do despacho, com o valor já parado.

    ⚠ `confirm()` é tudo-ou-nada, e categoria sem preço no grid do comprador
    **não pode travar o despacho**: a caixa saiu, o fato é físico. A ordem
    fica em rascunho DESPACHADO, aparece para o comprador assim mesmo (é ele
    quem completa a tabela) e congela quando o preço entrar.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-frz')
        User = get_user_model()
        cls.gerente = User.objects.create_user('vd_frz_mgr', password='x')
        Membership.objects.create(user=cls.gerente, company=cls.company,
                                  role='manager')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        from pricing.models import FxRate
        from datetime import date
        FxRate.objects.get_or_create(date=date.today(),
                                     defaults={'rate': Decimal('0.1400'),
                                               'source': 'teste'})
        self.client.force_login(self.gerente)

    def _fechar(self, lot):
        return self.client.post(reverse('estoque:lot_close', args=[lot.pk]),
                                {'confirm_code': lot.code}, follow=True)

    def test_fechar_o_lote_deixa_a_ov_em_RASCUNHO(self):
        """Despacho pendente: o preço segue vivo até a caixa sair."""
        lot = Lot.open_for_company(self.company, self.gerente, 'ok',
                                   origin='phone')
        _entries(lot, self.brand)                 # tudo cotado no grid
        self._fechar(lot)
        so = SalesOrder.all_companies.get(lot=lot)
        self.assertEqual(so.status, STATUS_DRAFT)
        self.assertIsNone(so.shipped_at)
        self.assertIsNone(so.total_rmb)
        self.assertTrue(all(l.unit_rmb is None for l in so.lines.all()))

    def test_o_DESPACHO_congela_a_ov(self):
        lot = Lot.open_for_company(self.company, self.gerente, 'desp',
                                   origin='phone')
        _entries(lot, self.brand)
        self._fechar(lot)
        so = SalesOrder.all_companies.get(lot=lot)
        self.client.post(reverse('vendas:so_ship', args=[so.pk]),
                         {'carrier': 'DHL', 'tracking': 'JD1',
                          'shipped_at': str(timezone.localdate())})
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CONFIRMED)
        self.assertEqual(so.fx_usd_rate, Decimal('0.1400'))   # taxa DO LOTE
        self.assertIsNotNone(so.total_rmb)
        self.assertTrue(all(l.unit_rmb is not None for l in so.lines.all()))

    def test_categoria_sem_preco_nao_trava_nem_o_fechamento_nem_o_despacho(self):
        """O caso real: K9 sem `k9_rmb_each`, SSD sem taxa, categoria nova.
        A caixa sai do mesmo jeito — o fato é físico."""
        lot = Lot.open_for_company(self.company, self.gerente, 'sem-preco',
                                   origin='phone')
        _entries(lot, self.brand, com_emcp=False)
        InventoryEntry.all_companies.create(       # sem linha no grid
            lot=lot, part_number='SEMPRECO1', quantity=9, brand=self.brand,
            chip_type='UFS', company=self.company,
            price_kind='ufs', price_gen='',
            price_tier_value=Decimal('256'), price_tier_unit='GB')
        self._fechar(lot)
        lot.refresh_from_db()
        self.assertEqual(lot.status, Lot.STATUS_CLOSED)     # fechou mesmo assim
        so = SalesOrder.all_companies.get(lot=lot)
        self.client.post(reverse('vendas:so_ship', args=[so.pk]),
                         {'carrier': 'DHL', 'shipped_at': str(timezone.localdate())})
        so.refresh_from_db()
        self.assertIsNotNone(so.shipped_at)                 # despachou
        self.assertEqual(so.status, STATUS_DRAFT)           # sem congelar
        self.assertIsNone(so.total_rmb)

    def test_pdf_do_admin_sai_com_valor_congelado_depois_do_despacho(self):
        """A razão da decisão antiga, preservada: o documento com preço é
        impresso DEPOIS do despacho, quando o valor já parou."""
        lot = Lot.open_for_company(self.company, self.gerente, 'pdf',
                                   origin='phone')
        _entries(lot, self.brand)
        self._fechar(lot)
        so = SalesOrder.all_companies.get(lot=lot)
        self.client.post(reverse('vendas:so_ship', args=[so.pk]),
                         {'carrier': 'DHL', 'shipped_at': str(timezone.localdate())})
        so.refresh_from_db()
        doc = services.manager_document(so, with_prices=True)
        self.assertEqual(doc['status'], 'confirmed')
        congelado = {l.pk: l.unit_rmb for l in so.lines.all()}
        self.assertEqual(doc['total_rmb'],
                         sum(u * l.quantity for l in so.lines.all()
                             for u in [congelado[l.pk]]))


class K9NoFechamentoTests(TestCase):
    """REGRESSÃO de prod (2026-08-18): lote com K9 fechava SEM criar a OV.

    O K9 tem chave PLANA de propósito (`pricing/convention.py`: NAND cru TSOP,
    preço fixo por unidade — sem capacidade, `tier_value=1` e `tier_unit=''`).
    A `SalesOrderLine.tier_unit` nascia SEM `blank=True`, então o `full_clean()`
    do portão do modelo recusava a linha com "Este campo não pode estar vazio",
    a exceção era engolida pelo `except` do `create_draft_for_lot` (que NUNCA
    pode travar o fechamento) e o lote fechava em silêncio, sem OV.

    Live desde o push do K9 (2026-08-16) até o dono fechar um lote com K9 em
    produção. `brand` e `gen` já tinham `blank=True`; só o `tier_unit` ficou
    para trás.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-k9')
        User = get_user_model()
        cls.user = User.objects.create_user('vd_k9')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)

    def test_fechar_sem_ov_avisa_na_tela(self):
        """O portão de silêncio (2026-08-18): se a OV não nascer, o gerente
        VÊ. A garantia do F8 continua — o lote fecha e o estoque fica salvo.

        Aqui a falha é forçada pelo caminho mais simples de reproduzir (zero
        comprador ativo), mas o aviso é do RESULTADO, não da causa: qualquer
        caminho que deixe o lote sem OV cai nele."""
        from django.contrib.auth import get_user_model
        from tenancy.models import Membership
        User = get_user_model()
        gerente = User.objects.create_user('vd_k9_mgr', password='x')
        Membership.objects.create(user=gerente, company=self.company,
                                  role='manager')
        self.buyer.active = False                      # nenhum comprador ativo
        self.buyer.save(update_fields=['active'])
        lot = Lot.open_for_company(self.company, gerente, 'sem-ov',
                                   origin='phone')
        _entries(lot, self.brand, com_emcp=False)
        self.client.force_login(gerente)
        resp = self.client.post(reverse('estoque:lot_close', args=[lot.pk]),
                                {'confirm_code': lot.code}, follow=True)
        lot.refresh_from_db()
        self.assertEqual(lot.status, Lot.STATUS_CLOSED)   # fechou mesmo assim
        self.assertContains(resp, 'ORDEM DE VENDA')
        avisos = [m.message for m in resp.context['messages']]
        self.assertTrue(any('suporte' in m for m in avisos), avisos)

    def test_refechar_com_ov_existente_nao_avisa(self):
        """O aviso pergunta ao BANCO, não ao retorno da função: re-fechar um
        lote que JÁ tem OV devolve None e não é erro nenhum."""
        lot = Lot.open_for_company(self.company, self.user, 'refecha',
                                   origin='phone')
        _entries(lot, self.brand, com_emcp=False)
        self.assertIsNotNone(services.create_draft_for_lot(lot, self.user))
        self.assertIsNone(services.create_draft_for_lot(lot, self.user))
        self.assertEqual(SalesOrder.all_companies.filter(lot=lot).count(), 1)

    def test_lote_com_k9_gera_ov(self):
        lot = Lot.open_for_company(self.company, self.user, 'k9', origin='phone')
        _entries(lot, self.brand, com_emcp=False)
        InventoryEntry.all_companies.create(
            lot=lot, part_number='K9', quantity=500, brand=self.brand,
            chip_type='NAND Flash', company=self.company,
            price_kind='k9', price_gen='',
            price_tier_value=Decimal('1'), price_tier_unit='')   # chave PLANA
        so = services.create_draft_for_lot(lot, self.user)
        self.assertIsNotNone(so, 'lote com K9 fechou sem OV — o bug voltou')
        k9 = so.lines.get(kind='k9')
        self.assertEqual((k9.quantity, k9.tier_unit, k9.gen), (500, '', ''))
        # E o documento do lote desenha o K9 sem inventar capacidade:
        self.assertEqual(k9.capacity_label, '')
        self.assertEqual(k9.type_label, 'K9')


class VendasGateTests(TestCase):
    """Dois andares (dono, 2026-08-14 — revisa o admin-only da F11.2):

    · COMERCIAL (lista/detalhe/PDF/confirmar/cancelar) = gerente para cima,
      com ¥/US$/taxa MASCARADOS para quem não é admin;
    · FINANCEIRO (acerto/fatura/pagamento) = admin;
    · operador = 403 em tudo; anônimo = login.
    """

    #: Rotas do andar comercial (gerente entra) e do financeiro (só admin).
    COMERCIAIS = ('vendas:so_list',)

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
        self.lot = Lot.open_for_company(self.company, self.users['manager'],
                                        'g', origin='phone')
        _entries(self.lot, self.brand, com_emcp=False)
        self.so = services.create_draft_for_lot(self.lot,
                                                self.users['manager'])

    def test_admin_ve_valor(self):
        self.client.force_login(self.users['admin'])
        resp = self.client.get(reverse('vendas:so_list'))
        self.assertContains(resp, self.so.code)
        detail = self.client.get(reverse('vendas:so_detail',
                                         args=[self.so.pk]))
        # Moeda: SÓ US$ na página da OV (dono, 2026-07-24) — ¥15 @0.14 = 2.10.
        self.assertContains(detail, 'US$ 2.10')
        self.assertNotContains(detail, '¥ 15')

    def test_gerente_entra_mas_sem_nenhum_valor(self):
        """O gerente vê a ordem e a QUANTIDADE; dinheiro nenhum — nem no HTML
        (a view zera o contexto), nem no PDF."""
        # ⚠ 'US$'/'¥' soltos NÃO servem de asserção: os cabeçalhos de coluna e
        #   o badge de câmbio do shell (taxa de mercado, pública por decisão do
        #   PLANO_FX) trazem os símbolos em toda tela. O que não pode aparecer
        #   é NÚMERO de dinheiro.
        self.client.force_login(self.users['manager'])
        lista = self.client.get(reverse('vendas:so_list'))
        self.assertContains(lista, self.so.code)
        self.assertFalse(lista.context['ver_valor'])
        # ⚠ 2026-08-19: a COLUNA some, não vira bolinha. Bolinha é um espaço
        # vazio dizendo "aqui tem dinheiro que você não pode ver"; sem a
        # coluna a barreira é ESTRUTURAL — não há string de valor no HTML.
        self.assertNotContains(lista, '•••')
        self.assertNotContains(lista, 'Total US$')

        _sem_compressao(self)
        detail = self.client.get(reverse('vendas:so_detail',
                                         args=[self.so.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.so.code)
        self.assertNotContains(detail, '•••')
        self.assertNotContains(detail, 'US$ unit.')     # nem o cabeçalho
        self.assertNotContains(detail, 'US$ 2.10')      # unitário
        self.assertNotContains(detail, 'US$ 10.50')     # total (5 × 2.10)
        self.assertNotContains(detail, '0.14')          # taxa do contrato
        self.assertContains(detail, '>5<')              # a QUANTIDADE fica
        # Contexto limpo na origem — não é só CSS/template:
        self.assertIsNone(detail.context['fx_rate'])
        self.assertTrue(all(r['unit_usd'] is None and r['total_usd'] is None
                            for r in detail.context['rows']))

        # PDF: RE-ESPECIFICADO em 2026-08-18. Antes o gerente baixava o PDF
        # comercial com as células de dinheiro tampadas de '***'; agora ele
        # baixa OUTRO DOCUMENTO (conferência do lote) que não tem coluna de
        # dinheiro nenhuma — a barreira passou de máscara a ESTRUTURAL, e é
        # por isso que a asserção do '***' morreu. O detalhe do documento novo
        # está em PdfConferenciaGerenteTests; aqui fica só o "não vaza valor".
        # O reportlab comprime o stream — desligo a compressão SÓ no teste
        # para poder ler o texto do PDF de verdade.
        pdf = self.client.get(reverse('vendas:so_pdf', args=[self.so.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        # ⚠ sobre os TEXTOS, nunca sobre o PDF cru: o blob do logo casa com
        # 'US$' por coincidência de bytes (armadilha documentada no topo).
        junto = b' '.join(_textos_do_pdf(pdf.content))
        self.assertNotIn(b'***', junto)                  # não há o que mascarar
        self.assertNotIn(b'2.10', junto)                 # nenhum valor
        self.assertNotIn(b'US$', junto)                  # nem cabeçalho de US$

    def test_botao_confirmar_saiu_da_tela_da_empresa(self):
        """Dono, 2026-08-18: **quem confirma a ordem é o COMPRADOR**, na tela
        dele (que ainda não existe). O botão saiu da tela da EMPRESA — de
        admin e de gerente.

        A ROTA continua viva de propósito: é o que a tela do comprador vai
        chamar. Este teste trava o botão, não a rota — se alguém devolver o
        botão sem que a decisão mude, a suíte avisa."""
        for papel in ('admin', 'manager'):
            self.client.force_login(self.users[papel])
            tela = self.client.get(reverse('vendas:so_detail',
                                           args=[self.so.pk]))
            self.assertNotContains(tela, 'Confirmar ordem', msg_prefix=papel)
            self.assertNotContains(tela, reverse('vendas:so_confirm',
                                                 args=[self.so.pk]),
                                   msg_prefix=papel)
            # Cancelar também saiu (dono, 2026-08-18): cancelar venda é
            # operação de PLATAFORMA, não do cliente. A rota fica.
            self.assertNotContains(tela, reverse('vendas:so_cancel',
                                                 args=[self.so.pk]),
                                   msg_prefix=papel)
            self.assertNotContains(tela, reverse('vendas:settlement_new',
                                                 args=[self.so.pk]),
                                   msg_prefix=papel)

    def test_gerente_confirma_e_cancela(self):
        """Ciclo comercial inteiro pela ROTA (o botão saiu da tela em
        2026-08-18 — ver o teste acima; a rota é o contrato que a tela do
        comprador vai usar amanhã)."""
        self.client.force_login(self.users['manager'])
        self.client.post(reverse('vendas:so_confirm', args=[self.so.pk]))
        self.so.refresh_from_db()
        self.assertEqual(self.so.status, STATUS_CONFIRMED)
        self.assertIsNotNone(self.so.total_usd)          # congelou no BANCO
        detail = self.client.get(reverse('vendas:so_detail',
                                         args=[self.so.pk]))
        self.assertNotContains(detail, 'US$ 10.50')      # mas não na TELA
        self.assertIsNone(detail.context['so'].total_usd)
        self.client.post(reverse('vendas:so_cancel', args=[self.so.pk]))
        self.so.refresh_from_db()
        self.assertEqual(self.so.status, STATUS_CANCELLED)

    def test_financeiro_continua_admin(self):
        """Acerto/fatura/pagamento: 403 para o gerente, e ele não recebe nem
        o link (CTA de acerto/smart button da fatura)."""
        services.confirm(self.so, self.users['admin'])
        self.client.force_login(self.users['manager'])
        self.assertEqual(
            self.client.get(reverse('vendas:settlement_new',
                                    args=[self.so.pk])).status_code, 403)
        detail = self.client.get(reverse('vendas:so_detail',
                                         args=[self.so.pk]))
        self.assertNotContains(detail, reverse('vendas:settlement_new',
                                               args=[self.so.pk]))

    def test_operador_403_e_anonimo_login(self):
        self.client.force_login(self.users['operator'])
        for rota in self.COMERCIAIS:
            self.assertEqual(self.client.get(reverse(rota)).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('vendas:so_detail',
                                    args=[self.so.pk])).status_code, 403)
        self.client.logout()
        resp = self.client.get(reverse('vendas:so_list'))
        self.assertIn(resp.status_code, (302, 403))          # anônimo → login

    def test_menu_vendas_aparece_pro_gerente_e_some_pro_operador(self):
        """O item de menu é UX (a barreira é a view) — mas tem que bater."""
        alvo = reverse('vendas:so_list')
        self.client.force_login(self.users['manager'])
        self.assertContains(self.client.get(reverse('estoque:index')), alvo)
        self.client.force_login(self.users['operator'])
        self.assertNotContains(self.client.get(reverse('estoque:index')), alvo)


class PdfConferenciaGerenteTests(TestCase):
    """O PDF que o GERENTE baixa (dono, 2026-08-18) — e que viaja com o pacote.

    Não é o PDF comercial com os números tampados: é outro documento, o de
    CONFERÊNCIA do lote e de EMBARQUE. O que ele tem que provar aqui:

    · nenhuma coluna de dinheiro EXISTE (barreira estrutural, não máscara);
    · sai SEMPRE em inglês, qualquer que seja o idioma da sessão (ele é lido
      pela transportadora e pelo destinatário, não por quem clicou);
    · SO e LOTE no MESMO tamanho de fonte (pedido literal do dono);
    · quantidade por caixa WTC, com as MARCAS FUNDIDAS (o mesmo código
      aparecia repetido, uma vez por marca);
    · quantidade por tipo × capacidade REAIS — afrouxamento consciente da F12
      autorizado pelo dono nesta data;
    · o cabeçalho de auditoria (empresa, emissão, fechamento, quem fechou,
      câmbio travado) e o bloco SHIP TO 收貨人;
    · os dois logos: WhatTheChip e o da empresa-cliente.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-pdf')
        # 2ª marca na MESMA categoria: é o que faz o código WTC duplicar.
        cls.brand2 = Brand.objects.create(name='SanDisk vd-pdf', code='VPDF2')
        User = get_user_model()
        cls.manager = User.objects.create_user('vdp_mgr', password='x',
                                               first_name='Ana', last_name='Reis')
        Membership.objects.create(user=cls.manager, company=cls.company,
                                  role='manager')
        cls.admin = User.objects.create_user('vdp_adm', password='x')
        Membership.objects.create(user=cls.admin, company=cls.company,
                                  role='admin')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)
        self.lot = Lot.open_for_company(self.company, self.manager, 'p',
                                        origin='phone')
        _entries(self.lot, self.brand)                     # 5 eMMC 16GB + 4 eMCP + 7 sem chave
        InventoryEntry.all_companies.create(               # OUTRA marca, MESMA caixa
            lot=self.lot, part_number='VDEMMC3', quantity=6, brand=self.brand2,
            chip_type='eMMC', company=self.company,
            price_kind='emmc', price_gen='', price_tier_value=Decimal('16'),
            price_tier_unit='GB')
        self.so = services.create_draft_for_lot(self.lot, self.manager)

    def _endereco(self):
        """Comprador com SHIP TO preenchido (o do agente em Macau)."""
        self.buyer.ship_to_name = 'Tang Dongmei'
        self.buyer.ship_to_address = (
            'Street Avenida de Artur Tamagnini Barbosa\n'
            'Jardim Do Mar Do Sul, Ground Floor F490\n'
            'Macau - Postal Code 999078')
        self.buyer.ship_to_email = '3271719323@qq.com'
        self.buyer.ship_to_phone = '(+853) 63525754'
        self.buyer.save()

    def _pdf(self, user):
        _sem_compressao(self)
        self.client.force_login(user)
        resp = self.client.get(reverse('vendas:so_pdf', args=[self.so.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b'%PDF'))
        return resp.content

    # ── estrutura ───────────────────────────────────────────────────────────

    def test_nenhuma_coluna_de_preco_existe(self):
        import re
        textos = _textos_do_pdf(self._pdf(self.manager))
        for txt in textos:
            for proibido in (b'US$', b'\\245', b'Unit', b'***'):   # \245 = ¥
                self.assertNotIn(proibido, txt, f'vazou {proibido!r} no PDF')
            # E nenhum texto tem cara de dinheiro (2 casas decimais). A taxa
            # 0.1400 tem 4 e sobrevive de propósito — foi o que o dono pediu.
            self.assertIsNone(re.search(rb'\d+\.\d{2}(?!\d)', txt),
                              f'valor com cara de dinheiro no PDF: {txt!r}')
        junto = b' '.join(textos)
        for esperado in (b'Category', b'Qty.', b'Type', b'Capacity', b'Total'):
            self.assertIn(esperado, junto)

    def test_sai_em_ingles_mesmo_com_a_sessao_em_portugues(self):
        """Documento de embarque tem idioma do TRANSPORTE, não do usuário.

        Os rótulos são CANÔNICOS (não passam por gettext), então nem a sessão
        em pt-br nem em zh muda o papel."""
        from django.utils import translation
        for idioma in ('pt-br', 'es', 'zh-hans'):
            with translation.override(idioma):
                junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
            self.assertIn(b'WTC categories', junto, idioma)
            self.assertIn(b'Summary by chip type', junto, idioma)
            self.assertIn(b'Closed by', junto, idioma)
            self.assertNotIn(b'Categorias WTC', junto, idioma)
            self.assertNotIn(b'Fechado por', junto, idioma)

    def test_todo_rotulo_tem_o_chines_tradicional_ao_lado(self):
        """Pedido do dono: inglês + 繁體 entre parênteses em cada rótulo.

        A prova é dupla — o par existe na tabela e o ideograma chega ao PDF
        (glifo ausente na fonte sairia como quadradinho, não como texto)."""
        from vendas.pdf import _L, _t
        for chave, (en, zh) in _L.items():
            self.assertTrue(en and zh, f'{chave} sem par bilíngue')
            self.assertEqual(_t(chave), f'{en} ({zh})')
        # 繁體, não 简体: se alguém colar o catálogo zh-hans aqui, cai.
        self.assertEqual(_L['category'][1], '類別')
        self.assertEqual(_L['qty'][1], '數量')
        self.assertEqual(_L['spec'][1], '晶片類型彙總')
        # Cada ideograma dos rótulos que o gerente vê tem que ter GLIFO na
        # fonte embutida — o CMap da TTF lista os pontos de código usados.
        # Sem glifo o reportlab desenha quadradinho e ninguém percebe.
        self._endereco()                  # p/ o bloco SHIP TO entrar também
        pdf = self._pdf(self.manager)
        self.assertIn(b'/BaseFont', pdf)               # a TTF foi embutida
        # Fora da conta: rótulo de preço (só na versão do admin), os status
        # que ESTE documento não está, e os rótulos do documento de RESULTADO
        # (outro PDF) — glifo só entra na fonte se for usado.
        fora = {'unit_rmb', 'total_rmb', 'total_usd',
                'confirmed', 'cancelled',
                'result', 'received', 'settled', 'sent',
                'rejected', 'accepted', 'brand', 'notes',
                'expected', 'final', 'difference'}
        for ch in set(''.join(zh for k, (_en, zh) in _L.items()
                              if k not in fora)):
            if ch.isspace() or ch.isascii():
                continue
            self.assertIn(f'<{ord(ch):04X}>'.encode(), pdf,
                          f'sem glifo para {ch!r} na fonte embutida')

    def test_subtitulo_sem_as_frases_removidas(self):
        """Dono, 2026-08-18: fora 'documento sem valores' e 'valores
        congelados'; o resto da linha (natureza + status) fica."""
        texto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertIn(b'Lot check', texto)
        self.assertIn(b'quotation', texto)                  # status do draft
        self.assertNotIn(b'without values', texto)
        self.assertNotIn(b'frozen', texto)

    def test_so_e_lote_tem_o_mesmo_tamanho(self):
        """Pedido literal: 'nenhum é mais importante que o outro'. A prova é o
        operador Tf que vale no momento em que cada código é desenhado."""
        import re
        fluxo = _conteudo_do_pdf(self._pdf(self.manager)).decode('latin-1')
        def _fonte_de(codigo):
            pos = fluxo.index(f'({codigo}) Tj')
            achados = re.findall(r'/(F\d+) (\d+(?:\.\d+)?) Tf', fluxo[:pos])
            self.assertTrue(achados, f'nenhum Tf antes de {codigo}')
            return achados[-1]
        self.assertEqual(_fonte_de(self.so.code), _fonte_de(self.lot.code))

    def test_os_dois_logos_entram(self):
        """WhatTheChip (asset commitado) + o da empresa-cliente (blob no
        banco).

        ⚠ A asserção é RELATIVA (o logo do cliente AUMENTA a contagem), não
        '== 2': PNG com transparência vira dois objetos no PDF (imagem +
        /SMask) e um cliente pode subir um logo com alfa — cravar o número
        deixaria a suíte refém do arquivo que o cliente escolheu.
        """
        from tenancy.models import CompanyLogo
        import io
        from PIL import Image
        antes = self._pdf(self.manager).count(b'/Subtype /Image')
        self.assertGreaterEqual(antes, 1, 'o logo do WhatTheChip sumiu')
        buf = io.BytesIO()
        Image.new('RGB', (120, 40), (10, 98, 254)).save(buf, format='PNG')
        CompanyLogo.objects.update_or_create(
            company=self.company, defaults={'data': buf.getvalue()})
        self.company.logo_mime = 'image/png'
        self.company.save(update_fields=['logo_mime'])
        self.assertGreater(self._pdf(self.manager).count(b'/Subtype /Image'),
                           antes, 'o logo da empresa não entrou')

    def test_sem_logo_da_empresa_o_documento_sai_igual(self):
        """Empresa sem logo (o normal em cliente novo): só o do WhatTheChip —
        e nada quebra."""
        self.assertEqual(self.company.logo_mime, '')
        pdf = self._pdf(self.manager)
        self.assertGreaterEqual(pdf.count(b'/Subtype /Image'), 1)
        self.assertIn(b'WTC categories', b' '.join(_textos_do_pdf(pdf)))

    # ── SHIP TO ─────────────────────────────────────────────────────────────

    def test_ship_to_sai_completo(self):
        self._endereco()
        self.assertEqual(services.ship_to(self.buyer)['lines'], [
            'Street Avenida de Artur Tamagnini Barbosa',
            'Jardim Do Mar Do Sul, Ground Floor F490',
            'Macau - Postal Code 999078'])
        textos = _textos_do_pdf(self._pdf(self.manager))
        junto = b' '.join(textos)
        self.assertIn(b'SHIP TO', junto)                    # rótulo canônico
        self.assertIn(b'Tang Dongmei', junto)
        self.assertIn(b'Ground Floor F490', junto)
        self.assertIn(b'Macau', junto)
        self.assertIn(b'3271719323@qq.com', junto)
        self.assertIn(b'63525754', junto)

    def test_ship_from_traz_a_empresa_cliente(self):
        """O comprador recebe lote de VÁRIAS empresas e precisa saber de qual
        veio (dono, 2026-08-18) — por isso o NOME sai sempre, com ou sem
        endereço cadastrado."""
        d = services.ship_from(self.company)
        self.assertEqual(d['name'], self.company.name)
        self.assertEqual(d['lines'], [])                 # ainda sem endereço
        junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertIn(b'SHIP FROM', junto)
        self.assertIn(self.company.name.encode(), junto)

        self.company.address = 'Ruta 1 km 30\nHernandarias - Paraguay'
        self.company.save(update_fields=['address'])
        self.assertEqual(services.ship_from(self.company)['lines'],
                         ['Ruta 1 km 30', 'Hernandarias - Paraguay'])
        junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertIn(b'Hernandarias - Paraguay', junto)

    def test_ship_to_so_com_endereco_e_o_caso_real(self):
        """A configuração que o dono escolheu (2026-08-18): SÓ o endereço —
        nome do contato, e-mail e telefone ficam FORA do documento ("o resto
        revela muita coisa sobre meu contato"). O bloco tem que sair mesmo
        assim, sem linha vazia nem separador sobrando."""
        self.buyer.ship_to_address = (
            'Street Avenida de Artur Tamagnini Barbosa\n'
            'Jardim Do Mar Do Sul, Ground Floor F490\n'
            'Macao - Postal Code 999078')
        self.buyer.save()
        d = services.ship_to(self.buyer)
        self.assertEqual(d['name'], '')
        self.assertEqual((d['email'], d['phone']), ('', ''))
        self.assertEqual(len(d['lines']), 3)
        junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertIn(b'SHIP TO', junto)
        self.assertIn(b'Ground Floor F490', junto)
        self.assertIn(b'Macao', junto)
        for contato in (b'Tang Dongmei', b'qq.com', b'63525754'):
            self.assertNotIn(contato, junto)

    def test_ship_to_sem_endereco_nao_desenha_a_caixa(self):
        """Nunca inventa destino: comprador sem endereço = bloco ausente (é
        melhor a transportadora reclamar do que despachar errado)."""
        self.assertEqual(services.ship_to(self.buyer), {})
        self.assertEqual(services.manager_document(self.so)['ship_to'], {})
        self.assertNotIn(b'SHIP TO',
                         b' '.join(_textos_do_pdf(self._pdf(self.manager))))

    # ── conteúdo ────────────────────────────────────────────────────────────

    def test_categorias_wtc_fundem_as_marcas(self):
        """Samsung e SanDisk eMMC 16GB são DUAS linhas na OV (o comprador cota
        por marca) e UMA caixa — o gerente confere caixa."""
        lines = services.annotate_labels(list(self.so.lines.all()), False)
        self.assertEqual(len([l for l in lines if l.kind == 'emmc']), 2)
        wtc = services.wtc_summary(lines)
        emmc16 = [r for r in wtc if r['label'] == 'B-06']     # eMMC 16GB (tabela fundadora)
        self.assertEqual(len(emmc16), 1, wtc)
        self.assertEqual(emmc16[0]['qty'], 11)                # 5 Samsung + 6 SanDisk
        textos = _textos_do_pdf(self._pdf(self.manager))
        self.assertEqual(textos.count(b'B-06'), 1)

    def test_resumo_por_tipo_e_capacidade(self):
        """⚠ A F12 é afrouxada AQUI de propósito (dono, 2026-08-18): o rótulo
        real sai ao lado do código de caixa. Se algum dia voltar atrás, este
        teste é o que muda primeiro."""
        spec = services.spec_summary(
            services.annotate_labels(list(self.so.lines.all()), False))
        self.assertEqual(
            [(r['type'], r['capacity'], r['qty']) for r in spec],
            [('eMMC', '16GB', 11), ('eMCP', '64GB', 4)])
        textos = _textos_do_pdf(self._pdf(self.manager))
        for esperado in (b'eMMC', b'16GB', b'eMCP', b'64GB'):
            self.assertIn(esperado, textos)

    def test_sem_categoria_entra_e_os_totais_fecham_com_o_lote(self):
        """As 7 unidades sem chave (SoC) contam: sem elas o documento não bate
        com o lote físico, que é justamente o que ele serve para conferir."""
        doc = services.manager_document(self.so)
        self.assertEqual(doc['unkeyed'], 7)
        self.assertEqual(doc['total_units'], 22)              # 11 + 4 + 7
        self.assertEqual(sum(r['qty'] for r in doc['wtc']) + doc['unkeyed'],
                         doc['total_units'])
        self.assertEqual(sum(r['qty'] for r in doc['spec']) + doc['unkeyed'],
                         doc['total_units'])

    # ── cabeçalho de auditoria ──────────────────────────────────────────────

    def _fechar(self):
        from pricing.models import FxRate
        from datetime import date
        FxRate.objects.create(date=date.today(), rate=Decimal('0.1400'),
                              source='teste')
        self.client.force_login(self.manager)
        self.client.post(reverse('estoque:lot_close', args=[self.lot.pk]),
                         {'confirm_code': self.lot.code})
        self.lot.refresh_from_db()

    def test_cabecalho_traz_empresa_fechamento_quem_fechou_e_cambio(self):
        self._fechar()
        self.assertEqual(self.lot.closed_by, self.manager)     # campo novo
        self.assertEqual(self.lot.fx_rate, Decimal('0.1400'))
        doc = services.manager_document(self.so)
        self.assertEqual(doc['company'], self.company.name)
        self.assertEqual(doc['closed_by'], 'Ana Reis')
        self.assertEqual(doc['fx_rate'], Decimal('0.1400'))
        self.assertTrue(doc['fx_from_lot'])
        self.assertEqual(doc['issued_at'], self.so.created_at)  # draft
        junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertIn(b'Ana Reis', junto)
        self.assertIn(self.company.name.encode(), junto)
        self.assertIn(b'1 CNY = 0.1400 USD', junto)  # taxa de MERCADO, pública
        self.assertNotIn(b'US$', junto)              # dinheiro segue fora

    def test_emissao_congela_na_confirmacao(self):
        """'Emitida em' é a data da ORDEM, não a do download: dois PDFs do
        mesmo lote têm que trazer a mesma data (dono, 2026-08-18)."""
        self._fechar()
        services.confirm(self.so, self.manager)
        self.so.refresh_from_db()
        doc = services.manager_document(self.so)
        self.assertEqual(doc['issued_at'], self.so.confirmed_at)

    def test_quem_fechou_cai_no_lotpricing_em_lote_antigo(self):
        """Lote fechado ANTES do campo ``closed_by`` (2026-08-18): o nome vem
        do snapshot de valoração, gravado no mesmo ato do fechamento."""
        from pricing.models import LotPricing
        self._fechar()
        Lot.all_companies.filter(pk=self.lot.pk).update(closed_by=None)
        self.lot.refresh_from_db()
        self.assertIsNone(self.lot.closed_by_id)
        LotPricing.all_companies.create(
            lot=self.lot, buyer=self.buyer, closed_by=self.manager,
            total_low=0, total_mid=0, total_high=0, priced_units=0,
            total_units=0, priced_lines=0, total_lines=0,
            lines=[{'pn': 'VDEMMC1', 'qty': 5}])      # lines=[] não passa no clean
        self.assertEqual(self.lot.closed_by_user, self.manager)
        self.assertEqual(services.manager_document(self.so)['closed_by'],
                         'Ana Reis')

    def test_sem_registro_nenhum_o_documento_nao_quebra(self):
        """Nem campo nem snapshot (congelar valor nunca trava o fechamento —
        padrão F8): o documento sai com travessão, não com exceção."""
        self.assertIsNone(self.lot.closed_by_user)
        doc = services.manager_document(self.so)
        self.assertEqual(doc['closed_by'], '')
        self.assertIn(b'\\227',                       # em dash (WinAnsi)
                      b' '.join(_textos_do_pdf(self._pdf(self.manager))))

    # ── o outro andar segue intacto ─────────────────────────────────────────

    # ── a versão do ADMIN: o MESMO documento, com preços ────────────────────

    def test_admin_recebe_o_mesmo_documento_com_precos(self):
        """RE-ESPECIFICADO em 2026-08-18 (2ª rodada). Antes o admin baixava o
        PDF comercial antigo; agora é *um documento só* — mesmas seções, mais
        as colunas de dinheiro (dono: "a única diferença é que tem preços")."""
        self._endereco()
        junto = b' '.join(_textos_do_pdf(self._pdf(self.admin)))
        for igual_ao_gerente in (b'WTC categories', b'Summary by chip type',
                                 b'SHIP TO', b'SHIP FROM', b'Closed by'):
            self.assertIn(igual_ao_gerente, junto)
        for so_do_admin in (b'Unit', b'Total US$'):
            self.assertIn(so_do_admin, junto)
        # B-06 = 11 eMMC 16GB x \xa5 15 = \xa5 165 / US$ 23.10
        self.assertIn(b'US$ 23.10', junto)
        # A-02 = 4 eMCP 64GB x \xa5 90 = \xa5 360 / US$ 50.40
        self.assertIn(b'US$ 50.40', junto)
        self.assertIn(b'US$ 73.50', junto)                     # total

    def test_valor_da_linha_e_do_total_batem(self):
        """A tabela de categorias FUNDE marcas — o total tem que continuar a
        soma exata das linhas (é o que o comprador confere)."""
        doc = services.manager_document(self.so, with_prices=True)
        self.assertEqual(doc['total_rmb'],
                         sum(r['total_rmb'] for r in doc['wtc']
                             if r['total_rmb'] is not None))
        self.assertEqual(doc['total_usd'],
                         sum(r['total_usd'] for r in doc['wtc']
                             if r['total_usd'] is not None))
        # 11 eMMC x ¥15 + 4 eMCP x ¥90 = ¥525
        self.assertEqual(doc['total_rmb'], Decimal('525.00'))

    def test_unitario_some_quando_as_marcas_fundidas_divergem(self):
        """B-06 junta Samsung e SanDisk. Se o comprador cotar preços
        diferentes, NÃO existe "o unitário da categoria" — mostrar um dos dois
        seria mentira. O total, que é exato, continua saindo.

        Teste de UNIDADE de propósito: o portão do grid proíbe linha de eMMC
        de celular por marca (é unificado), então a divergência não é
        montável pelo banco nesta fixture — mas é montável em PCB e em
        qualquer tipo cotado por marca, e é aí que o bug moraria.
        """
        lines = services.annotate_labels(list(self.so.lines.all()), False)
        emmc = [l for l in lines if l.kind == 'emmc']
        self.assertEqual(len(emmc), 2)
        money = {emmc[0].pk: (Decimal('15'), Decimal('2.10')),
                 emmc[1].pk: (Decimal('20'), Decimal('2.80'))}   # divergem
        b06 = [r for r in services.wtc_summary(lines, money)
               if r['label'] == 'B-06'][0]
        self.assertIsNone(b06['unit_rmb'])                       # ambíguo → some
        self.assertEqual(b06['qty'], 11)
        self.assertEqual(b06['total_rmb'], Decimal('195.00'))    # 5x15 + 6x20
        # Preço igual nas duas marcas → o unitário volta a existir.
        money[emmc[1].pk] = (Decimal('15'), Decimal('2.10'))
        b06 = [r for r in services.wtc_summary(lines, money)
               if r['label'] == 'B-06'][0]
        self.assertEqual(b06['unit_rmb'], Decimal('15'))

    def test_linha_sem_preco_nao_inventa_unitario(self):
        """Categoria com linha fora do grid: o unitário some e as unidades
        entram em ``unpriced`` (o documento diz o que não foi cotado)."""
        lines = services.annotate_labels(list(self.so.lines.all()), False)
        emmc = [l for l in lines if l.kind == 'emmc']
        money = {emmc[0].pk: (Decimal('15'), Decimal('2.10'))}    # a 2ª sem preço
        b06 = [r for r in services.wtc_summary(lines, money)
               if r['label'] == 'B-06'][0]
        self.assertIsNone(b06['unit_rmb'])
        self.assertEqual(b06['unpriced'], 6)
        self.assertEqual(b06['total_rmb'], Decimal('75.00'))      # só as 5 cotadas

    def test_gerente_nao_ve_nada_disso(self):
        """O mesmo lote, o mesmo documento — e zero dinheiro para o gerente."""
        junto = b' '.join(_textos_do_pdf(self._pdf(self.manager)))
        self.assertNotIn(b'US$', junto)
        self.assertNotIn(b'Unit', junto)
        self.assertNotIn(b'10.50', junto)
        self.assertFalse(services.manager_document(self.so)['with_prices'])


class CompradorComprasTests(TestCase):
    """F11.6/F2+F3 — a superfície do COMPRADOR (dono, 2026-08-18).

    O que precisa ser provado aqui, em ordem de importância:

    1. **Isolamento.** O comprador lê OVs de VÁRIAS empresas (o Wu Quan é de
       PLATAFORMA, `company IS NULL`) — é o único lugar do sistema que
       atravessa empresas. Ele tem que ver as suas, de todas as empresas, e
       NENHUMA de outro comprador.
    2. **Escopo.** Toda leitura passa pelo `company_scope` da dona. Sem ele o
       RLS devolveria zero linhas EM SILÊNCIO — o bug apareceria como "OV sem
       linhas", não como erro. Em SQLite o RLS não roda, então o teste vale
       como contrato de código, não como prova de banco.
    3. **A conta.** Recusar unidade abate do valor, linha a linha.
    """

    @classmethod
    def setUpTestData(cls):
        cls.emp_a, cls.buyer, cls.brand = _setup('vd-cmp')
        # ⚠ O comprador vira de PLATAFORMA (company=None) — é o que o Wu Quan
        # é em prod, e é justamente o que faz ele atravessar empresas. Sem
        # isto o `create_draft_for_lot` da 2ª empresa não o enxergaria.
        cls.buyer.company = None
        cls.buyer.save(update_fields=['company'])
        cls.emp_b = Company.objects.create(name='Vd cmp B', slug='vd-cmp-b')
        # …e um comprador RIVAL noutra empresa: ninguém vê o do outro.
        cls.emp_c = Company.objects.create(name='Vd cmp C', slug='vd-cmp-c')
        cls.rival = Buyer.all_companies.create(company=cls.emp_c,
                                               name='Rival', slug='rival-cmp')
        User = get_user_model()
        cls.parceiro = User.objects.create_user('vd_cmp_p', password='x')
        cls.buyer.users.add(cls.parceiro)
        cls.outro = User.objects.create_user('vd_cmp_o', password='x')
        cls.rival.users.add(cls.outro)

    def setUp(self):
        set_current_company(self.emp_a.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)

    def _grid(self, buyer):
        from pricing.models import Price, PriceList, STATUS_QUOTED
        if PriceList.all_companies.filter(buyer=buyer, brand=None).exists():
            return
        pl = PriceList.all_companies.create(buyer=buyer, brand=None)
        Price.all_companies.create(
            price_list=pl, kind='emmc', gen='', origin='phone',
            tier_value=Decimal('16'), tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('15'), price_max=Decimal('15'))

    def _lote_fechado(self, company, sufixo='', marca=None):
        """Lote com entradas cotadas → OV congelada (F11.6/F1)."""
        with company_scope(company):
            self._grid(self.buyer)
            lot = Lot.open_for_company(company, self.parceiro, 'c' + sufixo,
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='CMP' + sufixo, quantity=10,
                brand=marca or self.brand, chip_type='eMMC', company=company,
                price_kind='emmc', price_gen='',
                price_tier_value=Decimal('16'), price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            # ⚠ Desde 2026-08-18 quem CONGELA é o despacho, e o comprador só
            # enxerga o que já saiu — fixture sem despacho é OV invisível.
            services.mark_shipped(so, 'DHL', 'JD' + sufixo, None, self.parceiro)
            so.refresh_from_db()
            return so

    def _ov_do_rival(self):
        """OV do comprador RIVAL, montada à mão de propósito: o que se testa
        aqui é o ISOLAMENTO da leitura, não o caminho de criação (que, com um
        comprador de plataforma em cena, recusaria por ambiguidade)."""
        with company_scope(self.emp_c):
            lot = Lot.open_for_company(self.emp_c, self.outro, 'rival',
                                       origin='phone')
            so = SalesOrder(lot=lot, buyer=self.rival,
                            number=DocSequence.next_number(self.emp_c, SEQ_SO))
            so.save()
            # Despachada de propósito: assim o 404 abaixo prova POSSE, e não
            # apenas que a ordem ainda não saiu.
            SalesOrder.all_companies.filter(pk=so.pk).update(
                shipped_at=timezone.localdate())
            so.refresh_from_db()
            return so

    # ── isolamento ──────────────────────────────────────────────────────────

    def test_ve_as_suas_de_todas_as_empresas_e_nenhuma_do_rival(self):
        minha_a = self._lote_fechado(self.emp_a, sufixo='A')
        minha_b = self._lote_fechado(self.emp_b, sufixo='B')
        do_rival = self._ov_do_rival()
        vistas = {o.pk for o in services.orders_for_buyer(self.buyer)}
        self.assertEqual(vistas, {minha_a.pk, minha_b.pk})   # as DUAS empresas
        self.assertNotIn(do_rival.pk, vistas)

        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:list'))
        self.assertContains(tela, self.emp_a.name)
        self.assertContains(tela, self.emp_b.name)
        # ⚠ NÃO asserte pelo código do lote: a numeração é POR EMPRESA, então
        # LOT/001/08/26 existe em várias — foi o que quebrou este teste na
        # primeira escrita. Na TELA quem desambigua é a coluna Cliente; aqui
        # a prova de isolamento é a empresa do rival não aparecer.
        self.assertNotContains(tela, self.emp_c.name)

    def test_abrir_ov_de_outro_comprador_e_404(self):
        """404 e não 403: não confirmamos nem que a ordem existe."""
        do_rival = self._ov_do_rival()
        self.client.force_login(self.parceiro)
        self.assertEqual(
            self.client.get(reverse('compras:detail',
                                    args=[do_rival.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(reverse('compras:resultado',
                                     args=[do_rival.pk])).status_code, 404)

    def test_compra_ANTIGA_confirmada_sem_despacho_nao_some(self):
        """REGRESSÃO (2026-08-18): a regra "só o que foi despachado" apagou da
        tela toda compra que existia antes do despacho existir — elas nasceram
        confirmadas e nunca terão `shipped_at`. Regra nova não reescreve o
        passado."""
        antiga = self._lote_fechado(self.emp_a, sufixo='OLD')
        with company_scope(self.emp_a):
            SalesOrder.all_companies.filter(pk=antiga.pk).update(
                shipped_at=None, carrier='', tracking='')
            antiga.refresh_from_db()
        self.assertEqual(antiga.status, STATUS_CONFIRMED)
        self.assertIsNone(antiga.shipped_at)
        vistas = {o.pk for o in services.orders_for_buyer(self.buyer)}
        self.assertIn(antiga.pk, vistas)
        self.client.force_login(self.parceiro)
        self.assertEqual(self.client.get(
            reverse('compras:detail', args=[antiga.pk])).status_code, 200)

    def test_ordem_NOVA_sem_despacho_nao_aparece(self):
        """O outro lado da mesma regra: rascunho não despachado é lote fechado
        na bancada do cliente — mostrar seria prometer caixa que não saiu."""
        with company_scope(self.emp_a):
            lot = Lot.open_for_company(self.emp_a, self.parceiro, 'nova',
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='NOVA1', quantity=3, brand=self.brand,
                chip_type='eMMC', company=self.emp_a, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            nova = services.create_draft_for_lot(lot, self.parceiro)
        vistas = {o.pk for o in services.orders_for_buyer(self.buyer)}
        self.assertNotIn(nova.pk, vistas)
        self.client.force_login(self.parceiro)
        self.assertEqual(self.client.get(
            reverse('compras:detail', args=[nova.pk])).status_code, 404)

    def test_quem_nao_e_comprador_nao_entra(self):
        User = get_user_model()
        zé = User.objects.create_user('vd_cmp_ze', password='x')
        self.client.force_login(zé)
        self.assertEqual(
            self.client.get(reverse('compras:list')).status_code, 403)

    # ── a tela ──────────────────────────────────────────────────────────────

    def test_tela_traz_rotulo_real_e_o_cliente(self):
        """Sem máscara (ele compra chip) e COM o nome do cliente — o comprador
        recebe lote de várias empresas e precisa saber de qual veio."""
        so = self._lote_fechado(self.emp_a, sufixo='L')
        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'eMMC')            # rótulo REAL
        self.assertContains(tela, '16GB')
        self.assertContains(tela, self.emp_a.name)   # de quem veio
        self.assertContains(tela, 'B-06')            # e a caixa que ele conhece

    def test_agrupa_por_marca(self):
        """Marca é o agrupamento; capacidade é a linha (dono, 2026-08-18) —
        assim a dedução nunca é ambígua em lote PCB."""
        so = self._lote_fechado(self.emp_a, sufixo='M')
        outra = Brand.objects.create(name='Outra cmp', code='OCMP')
        with company_scope(self.emp_a):
            InventoryEntry.all_companies.create(
                lot=so.lot, part_number='CMPM2', quantity=4, brand=outra,
                chip_type='eMMC', company=self.emp_a, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            services.cancel(so, self.parceiro)
            so2 = services.create_draft_for_lot(so.lot, self.parceiro)
            services.confirm(so2, self.parceiro, unmasked=True)
            grupos = services.result_rows(so2)
        self.assertEqual([g['brand'] for g in grupos],
                         sorted([self.brand, outra.name]))
        self.assertTrue(all(len(g['lines']) == 1 for g in grupos))

    # ── o resultado ─────────────────────────────────────────────────────────

    def test_recusa_abate_do_valor_e_emite_fatura(self):
        so = self._lote_fechado(self.emp_a, sufixo='X')
        linha = so.lines.get()
        self.assertEqual((linha.quantity, linha.unit_rmb), (10, Decimal('15')))
        self.client.force_login(self.parceiro)
        self.client.post(reverse('compras:resultado', args=[so.pk]),
                         {f'rej_{linha.pk}': '4', 'notes': 'quatro queimados'})
        with company_scope(self.emp_a):
            inv = Invoice.all_companies.get(order=so)
            self.assertEqual(inv.total_rmb, Decimal('90.00'))   # 6 × ¥15
            self.assertEqual(inv.settlement.notes, 'quatro queimados')
            self.assertEqual(inv.settlement.created_by, self.parceiro)
            self.assertEqual(inv.settlement.lines.get().qty_rejected, 4)
        # A OV fica INTACTA (padrão Odoo: fatura pelo aceito, OV não muda):
        so.refresh_from_db()
        self.assertEqual(so.total_rmb, Decimal('150.00'))

    def test_campo_em_branco_vale_zero(self):
        """Sem nenhuma recusa, a fatura sai pelo valor cheio — e o acerto é
        registrado do mesmo jeito ("resultado sem diferenças")."""
        so = self._lote_fechado(self.emp_a, sufixo='Z')
        self.client.force_login(self.parceiro)
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        with company_scope(self.emp_a):
            inv = Invoice.all_companies.get(order=so)
            self.assertEqual(inv.total_rmb, so.total_rmb)
            self.assertEqual(inv.settlement.lines.count(), 0)

    def test_recusar_mais_do_que_veio_nao_passa(self):
        so = self._lote_fechado(self.emp_a, sufixo='Y')
        linha = so.lines.get()
        self.client.force_login(self.parceiro)
        resp = self.client.post(reverse('compras:resultado', args=[so.pk]),
                                {f'rej_{linha.pk}': '99'}, follow=True)
        with company_scope(self.emp_a):
            self.assertFalse(Invoice.all_companies.filter(order=so).exists())
        self.assertContains(resp, 'rejeitadas')

    def test_ordem_sem_preco_nao_aceita_resultado(self):
        """Rascunho = falta preço no grid DELE. A tela explica e não deixa
        fechar resultado (o `settle_and_invoice` recusa de novo no servidor,
        então POST forjado também não passa)."""
        with company_scope(self.emp_a):
            lot = Lot.open_for_company(self.emp_a, self.parceiro, 'sp',
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='CMPSP', quantity=5, brand=self.brand,
                chip_type='UFS', company=self.emp_a, price_kind='ufs',
                price_gen='', price_tier_value=Decimal('256'),
                price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            services.mark_shipped(so, 'DHL', 'JDSP', None, self.parceiro)
        self.assertEqual(so.status, STATUS_DRAFT)           # falta preço
        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertNotContains(tela, 'name="rej_')          # sem campo
        resp = self.client.post(reverse('compras:resultado', args=[so.pk]),
                                {}, follow=True)
        with company_scope(self.emp_a):
            self.assertFalse(Invoice.all_companies.filter(order=so).exists())
        self.assertContains(resp, 'CONFIRMADA')

    def test_rascunho_mostra_valor_ao_vivo_e_nomeia_o_que_falta(self):
        """Correção achada em PROD (lote 042, 2026-08-18): a tela do rascunho
        saía com uma parede de "—" e um aviso genérico.

        Rascunho não guarda ¥ nenhum — só a OV congelada guarda. Agora ele
        re-resolve contra o grid do comprador na leitura, e a linha sem preço
        é NOMEADA: sem isso ele não tem como saber o que cotar.
        """
        with company_scope(self.emp_a):
            self._grid(self.buyer)
            lot = Lot.open_for_company(self.emp_a, self.parceiro, 'viva',
                                       origin='phone')
            InventoryEntry.all_companies.create(       # ESTA tem preço
                lot=lot, part_number='CMPV1', quantity=10, brand=self.brand,
                chip_type='eMMC', company=self.emp_a, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            InventoryEntry.all_companies.create(       # esta NÃO
                lot=lot, part_number='CMPV2', quantity=5, brand=self.brand,
                chip_type='UFS', company=self.emp_a, price_kind='ufs',
                price_gen='', price_tier_value=Decimal('256'),
                price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            services.mark_shipped(so, 'DHL', 'JDV', None, self.parceiro)
            self.assertEqual(so.status, STATUS_DRAFT)
            grupos = services.result_rows(so)
        linhas = {(l['type'], l['capacity']): l
                  for g in grupos for l in g['lines']}
        # a cotada mostra valor VIVO, marcado como estimativa…
        emmc = linhas[('eMMC', '16GB')]
        self.assertEqual(emmc['unit_rmb'], Decimal('15'))
        self.assertEqual(emmc['total_rmb'], Decimal('150'))
        self.assertTrue(emmc['estimado'])
        # US$ vivo também (2026-08-18): a tela do CLIENTE é em dólar e sem ele
        # o admin via "—" na ordem ainda não despachada. `estimado` continua
        # dizendo que o número é estimativa.
        self.assertEqual(emmc['total_usd'], Decimal('21.00'))   # ¥150 × 0.14
        # …e a não-cotada é nomeada como pendência
        self.assertTrue(linhas[('UFS', '256GB')]['sem_preco'])
        self.assertEqual(services.draft_pendencias(grupos), ['UFS 256GB'])

        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'UFS 256GB')          # o que cotar
        self.assertContains(tela, '150')                # o valor vivo
        self.assertNotContains(tela, 'name="rej_')      # e ainda não acerta

    def test_rascunho_legado_nao_acusa_falta_de_preco(self):
        """Ordem que nasceu ANTES do congelamento automático: está em rascunho
        sem faltar preço nenhum. O aviso não pode dizer que falta cotação —
        foi exatamente o que confundiu o dono no lote 042."""
        with company_scope(self.emp_a):
            self._grid(self.buyer)
            lot = Lot.open_for_company(self.emp_a, self.parceiro, 'legado',
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='CMPLEG', quantity=8, brand=self.brand,
                chip_type='eMMC', company=self.emp_a, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            SalesOrder.all_companies.filter(pk=so.pk).update(
                shipped_at=timezone.localdate())     # despachada, não congelada
            so.refresh_from_db()
            grupos = services.result_rows(so)
        self.assertEqual(services.draft_pendencias(grupos), [])      # nada falta
        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'ESTIMADOS')
        self.assertNotContains(tela, 'não estão cotadas')

    def test_saldo_a_pagar_aparece_depois_da_fatura(self):
        so = self._lote_fechado(self.emp_a, sufixo='S')
        self.client.force_login(self.parceiro)
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'US$')
        self.assertNotContains(tela, 'name="rej_')          # virou leitura
        self.assertEqual(services.order_stage(
            SalesOrder.all_companies.get(pk=so.pk)), services.STAGE_FATURADO)


class CompradorValorFechadoTests(TestCase):
    """O valor fecha SOZINHO quando o preço que faltava é aprovado
    (dono, 2026-08-18).

    Bug que motivou: no LOT/EMI/041 faltava preço de LPDDR3 1.5GB, ele
    aprovou o preço — e a tela continuou dizendo "falta preço seu", travada.
    Eram DUAS coisas erradas ao mesmo tempo:

    1. o estágio da lista dizia `sem_preco` para QUALQUER rascunho, mesmo já
       cotado por inteiro (agora há `a_congelar`);
    2. aprovar o preço não destravava nada — ninguém retentava o
       congelamento, e a compra ficava presa para sempre.

    ⚠ O valor da compra é fechado pelo CLIENTE, no fechamento do lote (o dono
    é categórico). Este caminho é só o conserto do lote que fechou com uma
    categoria sem preço na tabela do comprador — `confirm` é tudo-ou-nada.
    """

    @classmethod
    def setUpTestData(cls):
        cls.emp, cls.buyer, cls.brand = _setup('vd-cong')
        User = get_user_model()
        cls.parceiro = User.objects.create_user('vd_cong_p', password='x')
        cls.buyer.users.add(cls.parceiro)

    def setUp(self):
        set_current_company(self.emp.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)
        self.client.force_login(self.parceiro)

    def _grid(self):
        from pricing.models import Price, PriceList, STATUS_QUOTED
        if PriceList.all_companies.filter(buyer=self.buyer, brand=None).exists():
            return
        pl = PriceList.all_companies.create(buyer=self.buyer, brand=None)
        Price.all_companies.create(
            price_list=pl, kind='emmc', gen='', origin='phone',
            tier_value=Decimal('16'), tier_unit='GB', status=STATUS_QUOTED,
            price_min=Decimal('15'), price_max=Decimal('15'))

    def _rascunho(self, sufixo, *, com_pendencia=False):
        with company_scope(self.emp):
            self._grid()
            lot = Lot.open_for_company(self.emp, self.parceiro, 'g' + sufixo,
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='CG' + sufixo, quantity=10,
                brand=self.brand, chip_type='eMMC', company=self.emp,
                price_kind='emmc', price_gen='',
                price_tier_value=Decimal('16'), price_tier_unit='GB')
            if com_pendencia:
                InventoryEntry.all_companies.create(
                    lot=lot, part_number='CG' + sufixo + 'X', quantity=5,
                    brand=self.brand, chip_type='UFS', company=self.emp,
                    price_kind='ufs', price_gen='',
                    price_tier_value=Decimal('256'), price_tier_unit='GB')
            return services.create_draft_for_lot(lot, self.parceiro)

    # ── o estágio ───────────────────────────────────────────────────────────

    def test_estagio_separa_falta_preco_de_falta_congelar(self):
        """O bug em uma linha: os dois rascunhos diziam a MESMA coisa."""
        completo = self._rascunho('E1')
        faltando = self._rascunho('E2', com_pendencia=True)
        with company_scope(self.emp):
            self.assertEqual(services.order_stage(completo), 'a_congelar')
            self.assertEqual(services.order_stage(faltando), 'sem_preco')

    def test_lista_traz_data_da_ordem_e_valor_estimado(self):
        """Coluna da data (dono, 2026-08-18) e o ¥ VIVO do rascunho — antes a
        lista mostrava "—" e ele não sabia o tamanho da compra."""
        so = self._rascunho('L1')
        self._fecha_lote(so)          # despachado: é assim que ele o enxerga
        tela = self.client.get(reverse('compras:list'))
        self.assertContains(tela, so.code)                       # SO/EMPRESA/NNN
        self.assertContains(
            tela, timezone.localtime(so.created_at).strftime('%d/%m/%Y'))
        self.assertContains(tela, '≈')                           # é estimativa
        self.assertContains(tela, '150.00')                      # 10 × ¥15

    # ── congelar ────────────────────────────────────────────────────────────

    def _fecha_lote(self, so, despachar=True):
        """Fecha o lote e (por padrão) DESPACHA — desde 2026-08-18 é o
        despacho que congela, e só o que saiu chega ao comprador."""
        Lot.all_companies.filter(pk=so.lot_id).update(closed_at=timezone.now())
        so.lot.refresh_from_db()
        if despachar:
            SalesOrder.all_companies.filter(pk=so.pk).update(
                shipped_at=timezone.localdate(), carrier='DHL')
            so.refresh_from_db()

    def test_aprovar_o_preco_que_faltava_congela_a_ordem_sozinha(self):
        """O laço que faltava: aprovar preço destrava as compras presas."""
        from pricing.models import Price, PriceList, STATUS_QUOTED
        so = self._rascunho('A1', com_pendencia=True)
        self._fecha_lote(so)
        self.assertEqual(so.status, STATUS_DRAFT)

        with company_scope(self.emp):
            pl = PriceList.all_companies.get(buyer=self.buyer, brand=None)
            Price.all_companies.create(
                price_list=pl, kind='ufs', gen='', origin='',
                tier_value=Decimal('256'), tier_unit='GB',
                status=STATUS_QUOTED, price_min=Decimal('40'),
                price_max=Decimal('40'))
            congeladas = services.freeze_pending_orders(self.buyer,
                                                        self.parceiro)
        self.assertEqual([o.pk for o in congeladas], [so.pk])
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CONFIRMED)
        # 10 × ¥15 (eMMC) + 5 × ¥40 (UFS, o preço recém-aprovado)
        self.assertEqual(so.total_rmb, Decimal('350.00'))

    def test_ordem_que_ainda_tem_pendencia_continua_em_rascunho(self):
        """Congelar é tudo-ou-nada: falta UMA categoria, nada congela."""
        so = self._rascunho('A2', com_pendencia=True)
        self._fecha_lote(so)
        with company_scope(self.emp):
            self.assertEqual(services.freeze_pending_orders(self.buyer), [])
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_DRAFT)

    def test_lote_ainda_ABERTO_nao_congela(self):
        """Cotação de lote aberto é rascunho de propósito."""
        so = self._rascunho('A3')                     # sem fechar o lote
        with company_scope(self.emp):
            self.assertEqual(services.freeze_pending_orders(self.buyer), [])
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_DRAFT)

    def test_ordem_NAO_DESPACHADA_nao_congela_ao_aprovar_preco(self):
        """Aprovar preço não pode atropelar o despacho e dar a venda por
        fechada antes de a caixa sair (dono, 2026-08-18)."""
        so = self._rascunho('A5')
        self._fecha_lote(so, despachar=False)
        with company_scope(self.emp):
            self.assertEqual(services.freeze_pending_orders(self.buyer), [])
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_DRAFT)

    def test_aprovar_pedido_de_preco_no_admin_dispara_o_congelamento(self):
        """O gancho de verdade: `PriceChangeRequest.approve()`."""
        from pricing.models import (Price, PriceChangeRequest, PriceList,
                                    STATUS_QUOTED, STATUS_UNQUOTED)
        so = self._rascunho('A4', com_pendencia=True)
        self._fecha_lote(so)
        with company_scope(self.emp):
            pl = PriceList.all_companies.get(buyer=self.buyer, brand=None)
            preco = Price.all_companies.create(
                price_list=pl, kind='ufs', gen='', origin='',
                tier_value=Decimal('256'), tier_unit='GB',
                status=STATUS_UNQUOTED)
            pedido = PriceChangeRequest.all_companies.create(
                price=preco, new_status=STATUS_QUOTED,
                new_price=Decimal('40'), old_status=STATUS_UNQUOTED,
                requested_by=self.parceiro)
            pedido.approve(self.parceiro)
        so.refresh_from_db()
        self.assertEqual(so.status, STATUS_CONFIRMED)
        self.assertEqual(so.total_rmb, Decimal('350.00'))

    # ── a tela do resultado ─────────────────────────────────────────────────

    def test_conferencia_so_abre_DEPOIS_do_recebimento(self):
        """Dono, 2026-08-18: "ele deve acusar como recebido primeiro para ir
        pra parte de resultado". Não se confere caixa que não chegou."""
        so = self._rascunho('R1')
        self._fecha_lote(so)
        with company_scope(self.emp):
            services.confirm(so, self.parceiro, unmasked=True)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertNotContains(tela, 'name="rej_')            # sem campos
        self.assertNotContains(tela, 'id="cmp-modal"')      # sem botão/modal
        self.assertContains(tela, reverse('compras:recebido', args=[so.pk]))
        self.assertContains(tela, 'Marque o recebimento')     # e diz por quê

        self.client.post(reverse('compras:recebido', args=[so.pk]))
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'name="rej_')               # agora sim
        self.assertContains(tela, 'id="cmp-modal"')

    def test_tabela_tem_linha_de_totais_e_os_dados_do_calculo_ao_vivo(self):
        """Totais (dono, 2026-08-18) e o contrato de que o JS depende: cada
        campo de recusa carrega a quantidade e o ¥ unitário da linha, e o
        formulário carrega a taxa e o valor esperado (o topo e o modal saem
        daí)."""
        so = self._rascunho('T1')
        self._fecha_lote(so)
        with company_scope(self.emp):
            services.confirm(so, self.parceiro, unmasked=True)
            services.mark_received(so)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'cmp-t-pagar')          # ¥ a pagar ao vivo
        self.assertContains(tela, 'cmp-t-aceitos')        # chips aceitos
        self.assertContains(tela, 'data-qty="10"')        # o que o JS lê
        self.assertContains(tela, 'data-unit="15.00"')
        self.assertContains(tela, 'data-esperado="150.00"')   # topo + modal
        self.assertContains(tela, 'cmp-h-rmb')                # o valor do topo
        self.assertContains(tela, 'cmp-modal')                # a confirmação

    def test_nada_fica_ABAIXO_da_tabela_na_tela_do_comprador(self):
        """O MESMO esqueleto da tela do cliente (dono, 2026-08-19): ação da
        etapa e pagamento acima; abaixo da tabela, nada."""
        so = self._rascunho('AB')
        self._fecha_lote(so, despachar=False)
        with company_scope(self.emp):
            services.mark_shipped(so, 'DHL', 'JDAB', None, self.parceiro)
            so.refresh_from_db()
            services.mark_received(so)
        self.assertEqual(so.status, STATUS_CONFIRMED)     # dá para conferir
        html = self.client.get(
            reverse('compras:detail', args=[so.pk])).content.decode()
        acao = html.index('cmp-fechar')
        abas = html.index('cmp-abas')
        tabela = html.index('cmp-tab-resumo')
        self.assertLess(acao, abas)
        self.assertLess(abas, tabela)
        # O form envolve as abas e fecha DEPOIS da última — nada de ação solta
        # embaixo da tabela.
        self.assertLess(html.index('</form>', tabela),
                        html.index('id="cmp-modal"'))
        # ⚠ Procure MARCAÇÃO, não classe: o CSS no fim da página cita todos os
        # nomes de classe e faria a asserção falhar sozinha.
        self.assertNotIn('name="notes"', html[tabela:])
        self.assertNotIn('type="submit"', html[tabela:])

    def test_aba_de_chips_lista_PN_spec_caixa_e_preco(self):
        """"Seria aí onde o comprador olha detalhe por detalhe" (dono)."""
        so = self._rascunho('T2')
        self._fecha_lote(so)          # despachado: é assim que ele o enxerga
        with company_scope(self.emp):
            chips = services.lot_chips(so)
        self.assertEqual(chips['qty'], 10)
        self.assertEqual(chips['rmb'], Decimal('150.00'))
        linha = chips['linhas'][0]
        self.assertEqual(linha['pn'], 'CGT2')
        self.assertEqual(linha['type'], 'eMMC')
        self.assertEqual(linha['wtc'], 'B-06')            # a caixa que ele recebe
        self.assertEqual(linha['unit_rmb'], Decimal('15'))
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'CGT2')                 # o PN na tela
        self.assertContains(tela, 'cmp-pane-chips')

    def test_chip_sem_chave_de_preco_aparece_na_aba_sem_sumir(self):
        """Ele viaja na caixa e não entra no comércio — o comprador precisa
        VER isso, em vez de achar que o PN sumiu."""
        so = self._rascunho('T3')
        with company_scope(self.emp):
            InventoryEntry.all_companies.create(
                lot=so.lot, part_number='SEMCHAVE', quantity=3,
                brand=self.brand, chip_type='DDR', company=self.emp)
            chips = services.lot_chips(so)
        pns = {l['pn']: l for l in chips['linhas']}
        self.assertIn('SEMCHAVE', pns)
        self.assertIsNone(pns['SEMCHAVE']['unit_rmb'])
        self.assertEqual(chips['qty'], 13)                # entra na contagem
        self.assertEqual(chips['rmb'], Decimal('150.00'))  # mas não no ¥


class PartnerRaizTests(TestCase):
    """A raiz /partner/ é a lista de COMPRAS (dono, 2026-08-18): é o que ele
    abre todo dia. A tabela de preços virou a segunda tela, /partner/precos/.

    ⚠ Os dois includes moram no MESMO prefixo. O teste do /partner/how/ existe
    para cravar o fall-through do resolvedor: se o Django parasse no primeiro
    include, metade da área do parceiro viraria 404."""

    @classmethod
    def setUpTestData(cls):
        cls.emp, cls.buyer, _brand = _setup('vd-raiz')
        User = get_user_model()
        cls.parceiro = User.objects.create_user('vd_raiz_p', password='x')
        cls.buyer.users.add(cls.parceiro)

    def setUp(self):
        set_current_company(self.emp.pk)
        self.addCleanup(set_current_company, None)
        self.client.force_login(self.parceiro)

    def test_raiz_e_a_lista_de_compras(self):
        self.assertEqual(reverse('compras:list'), '/partner/')
        self.assertContains(self.client.get('/partner/'), 'Suas compras')

    def test_link_antigo_da_lista_redireciona(self):
        resp = self.client.get('/partner/compras/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/partner/')

    def test_precos_continua_servido_no_segundo_include(self):
        self.assertEqual(reverse('pricing:partner_home'), '/partner/precos/')
        self.assertEqual(self.client.get('/partner/precos/').status_code, 200)
        self.assertEqual(self.client.get('/partner/how/').status_code, 200)


class CompradorEtapasEResultadoTests(TestCase):
    """Card de etapas, glossário da convenção e o PDF do resultado
    (dono, 2026-08-18).

    O card responde "em que fase está, de que fase passou, para onde vai" —
    e por isso cada etapa tem que ter DATA de verdade. "Enviado" ficou de
    fora: é a F4 (transportadora + rastreio), e caixa sem data é caixa morta.
    """

    @classmethod
    def setUpTestData(cls):
        cls.emp, cls.buyer, cls.brand = _setup('vd-etp')
        User = get_user_model()
        cls.parceiro = User.objects.create_user('vd_etp_p', password='x')
        cls.buyer.users.add(cls.parceiro)

    def setUp(self):
        set_current_company(self.emp.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)
        self.client.force_login(self.parceiro)

    def _ov(self, sufixo):
        from pricing.models import Price, PriceList, STATUS_QUOTED
        from django.utils import timezone
        with company_scope(self.emp):
            if not PriceList.all_companies.filter(buyer=self.buyer,
                                                  brand=None).exists():
                pl = PriceList.all_companies.create(buyer=self.buyer, brand=None)
                Price.all_companies.create(
                    price_list=pl, kind='emmc', gen='', origin='phone',
                    tier_value=Decimal('16'), tier_unit='GB',
                    status=STATUS_QUOTED, price_min=Decimal('15'),
                    price_max=Decimal('15'))
            lot = Lot.open_for_company(self.emp, self.parceiro, 'e' + sufixo,
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='ET' + sufixo, quantity=10,
                brand=self.brand, chip_type='eMMC', company=self.emp,
                price_kind='emmc', price_gen='',
                price_tier_value=Decimal('16'), price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            Lot.all_companies.filter(pk=lot.pk).update(closed_at=timezone.now())
            so.lot.refresh_from_db()
            # ⚠ O DESPACHO é que congela e é o que faz a ordem existir para
            # o comprador (dono, 2026-08-18).
            services.mark_shipped(so, 'DHL', 'JD' + sufixo, None, self.parceiro)
            so.refresh_from_db()
            return so

    # ── etapas ──────────────────────────────────────────────────────────────

    def test_etapas_andam_conforme_a_compra_anda(self):
        so = self._ov('S1')
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(so)}
        # Fechado e Enviado já vêm ✓: o comprador só vê o que SAIU.
        self.assertEqual(passos['fechado']['state'], 'done')
        self.assertEqual(passos['enviado']['state'], 'done')
        self.assertEqual(passos['recebido']['state'], 'current')  # é o que falta
        self.assertEqual(passos['resultado']['state'], 'todo')
        self.assertEqual(passos['pagamento']['state'], 'todo')

        self.client.post(reverse('compras:recebido', args=[so.pk]))
        so.refresh_from_db()
        self.assertIsNotNone(so.received_at)
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(so)}
        self.assertEqual(passos['recebido']['state'], 'done')
        self.assertEqual(passos['resultado']['state'], 'current')

    def test_etapa_sem_data_DEPOIS_de_uma_com_data_nao_e_a_corrente(self):
        """O cliente esqueceu de registrar o envio e a caixa chegou assim
        mesmo — nada bloqueia isso. A tela não pode dizer "aguardando envio"
        com o recebimento já carimbado."""
        so = self._ov('S14')
        SalesOrder.all_companies.filter(pk=so.pk).update(shipped_at=None)
        so.refresh_from_db()
        services.mark_received(so)
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(so)}
        self.assertEqual(passos['enviado']['state'], 'pulado')
        self.assertEqual(passos['recebido']['state'], 'done')
        self.assertEqual(passos['resultado']['state'], 'current')

    def test_marcar_recebido_e_idempotente(self):
        """A primeira data vale: remarcar reescreveria um fato do passado."""
        so = self._ov('S2')
        self.client.post(reverse('compras:recebido', args=[so.pk]))
        so.refresh_from_db()
        primeira = so.received_at
        self.client.post(reverse('compras:recebido', args=[so.pk]))
        so.refresh_from_db()
        self.assertEqual(so.received_at, primeira)

    def test_fechar_resultado_marca_o_recebimento_que_faltou(self):
        """Senão o card mostraria "Resultado" pronto com "Recebido" em aberto."""
        so = self._ov('S3')
        self.assertIsNone(so.received_at)
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        so.refresh_from_db()
        self.assertIsNotNone(so.received_at)
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(so)}
        self.assertEqual(passos['resultado']['state'], 'done')
        self.assertEqual(passos['pagamento']['state'], 'current')

    def test_card_e_o_cambio_travado_aparecem_na_tela(self):
        so = self._ov('S4')
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'cmp-steps')
        self.assertContains(tela, '1 ¥ = US$')          # câmbio no cabeçalho
        self.assertContains(tela, 'US$ 150.00'[:4])     # US$ tem o mesmo peso

    def test_topo_tem_DUAS_colunas_esperado_e_final(self):
        """Dono, 2026-08-18: o esperado é IMUTÁVEL (o preço fechado com o
        cliente) e o final é o que a conferência produziu. Um número só,
        mudando, apagaria a referência."""
        so = self._ov('S13')
        services.mark_received(so)
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'Resultado esperado')
        self.assertContains(tela, 'Resultado final')
        self.assertContains(tela, 'cmp-h-rmb')          # a coluna que se move
        self.assertContains(tela, '¥ 150.00')

        # Depois do resultado, as DUAS continuam — com a diferença ao lado.
        linha = so.lines.get()
        self.client.post(reverse('compras:resultado', args=[so.pk]),
                         {f'rej_{linha.pk}': '4'})
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'Resultado esperado')
        self.assertContains(tela, '¥ 150.00')           # esperado, parado
        self.assertContains(tela, 'Resultado final')
        self.assertContains(tela, '¥ 90.00')            # final, 6 × ¥15
        self.assertContains(tela, '−¥ 60.00')           # a diferença

    # ── glossário ───────────────────────────────────────────────────────────

    def test_aba_categorias_traz_a_convencao_e_marca_a_desta_compra(self):
        """"Assim o comprador vai se adaptando a esta convenção" (dono)."""
        so = self._ov('S5')
        with company_scope(self.emp):
            glos = services.category_glossary(so)
        codigos = {g['code'] for g in glos}
        self.assertIn('B-06', codigos)                  # eMMC 16GB, a da compra
        self.assertGreater(len(glos), 30)               # a convenção INTEIRA
        marcadas = [g['code'] for g in glos if g['no_lote']]
        self.assertEqual(marcadas, ['B-06'])
        # ordenado por LETRA, como a caixa física — nunca por preço/capacidade
        self.assertEqual([g['letter'] for g in glos],
                         sorted(g['letter'] for g in glos))
        tela = self.client.get(reverse('compras:detail', args=[so.pk]))
        self.assertContains(tela, 'cmp-pane-categorias')

    # ── PDF do resultado ────────────────────────────────────────────────────

    def test_pdf_do_resultado_presta_contas_da_recusa(self):
        _sem_compressao(self)          # senão o stream vira binário
        so = self._ov('S6')
        linha = so.lines.get()
        self.client.post(reverse('compras:resultado', args=[so.pk]),
                         {f'rej_{linha.pk}': '4', 'notes': 'quatro queimados'})
        resp = self.client.get(reverse('compras:resultado_pdf', args=[so.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        texto = b' '.join(_textos_do_pdf(resp.content))
        # Enviado × recusado × aceito: sem os TRÊS não presta contas de nada.
        for pedaco in (b'Sent', b'Rejected', b'Accepted'):
            self.assertIn(pedaco, texto)
        self.assertIn(b'quatro queimados', texto)       # o motivo da recusa
        # ESPERADO × FINAL × DIFERENÇA, a divisão que o dono pediu:
        for pedaco in (b'Expected', b'Final', b'Difference'):
            self.assertIn(pedaco, texto)
        self.assertIn(b'150.00', texto)                 # esperado (10 × \xa515)
        self.assertIn(b'90.00', texto)                  # final (6 × \xa515)

    def test_pdf_do_resultado_nao_fala_em_FATURA(self):
        """Papel interno do WhatTheChip; não diz nada a quem recebe (dono)."""
        _sem_compressao(self)
        so = self._ov('S12')
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        with company_scope(self.emp):
            inv = Invoice.all_companies.get(order=so)
        texto = b' '.join(_textos_do_pdf(self.client.get(
            reverse('compras:resultado_pdf', args=[so.pk])).content))
        self.assertNotIn(b'Invoice', texto)
        self.assertNotIn(inv.code.encode(), texto)
        self.assertIn(so.lot.code.encode(), texto)      # lote e OV, esses ficam
        self.assertIn(so.code.encode(), texto)

    def test_pdf_do_resultado_nao_diz_QUEM_e_o_comprador(self):
        """Sigilo de negócio (dono, 2026-08-18): o documento vai pro CLIENTE,
        e de quem o WhatTheChip compra não é da conta dele."""
        _sem_compressao(self)
        so = self._ov('S9')
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        texto = b' '.join(_textos_do_pdf(self.client.get(
            reverse('compras:resultado_pdf', args=[so.pk])).content))
        self.assertNotIn(self.buyer.name.encode(), texto)
        self.assertNotIn(b'Buyer', texto)
        self.assertIn(self.emp.name.encode(), texto)    # o CLIENTE, esse fica

    def test_pdf_do_resultado_carimba_o_logo_do_CLIENTE(self):
        """Dono, 2026-08-18: o relatório sai com a marca de quem embarcou."""
        from io import BytesIO
        from PIL import Image
        from tenancy.models import CompanyLogo
        buf = BytesIO()
        Image.new('RGB', (60, 20), '#0f62fe').save(buf, format='PNG')
        CompanyLogo.objects.update_or_create(company=self.emp,
                                             defaults={'data': buf.getvalue()})
        self.emp.logo_mime = 'image/png'
        self.emp.save(update_fields=['logo_mime'])
        so = self._ov('S11')
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        with company_scope(self.emp):
            doc = services.result_document(
                so, Invoice.all_companies.get(order=so))
        self.assertIsNotNone(doc['company_logo'])
        pdf = self.client.get(reverse('compras:resultado_pdf',
                                      args=[so.pk])).content
        # Dois XObjects de imagem: o do WhatTheChip e o do cliente.
        self.assertGreaterEqual(pdf.count(b'/Subtype /Image'), 2)

    def test_fechar_o_resultado_manda_pro_PDF(self):
        """É o documento que ele manda pro cliente, e a hora é agora."""
        so = self._ov('S10')
        resp = self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].endswith('?pdf=1'))
        tela = self.client.get(resp['Location'])
        self.assertContains(tela, 'cmp-pdf-link')

    def test_pdf_do_resultado_so_existe_depois_de_fechado(self):
        so = self._ov('S7')
        self.assertEqual(
            self.client.get(reverse('compras:resultado_pdf',
                                    args=[so.pk])).status_code, 404)

    def test_documento_do_resultado_bate_a_conta(self):
        so = self._ov('S8')
        linha = so.lines.get()
        self.client.post(reverse('compras:resultado', args=[so.pk]),
                         {f'rej_{linha.pk}': '4'})
        with company_scope(self.emp):
            inv = Invoice.all_companies.get(order=so)
            doc = services.result_document(so, inv)
        self.assertEqual((doc['sent'], doc['rejected'], doc['accepted']),
                         (10, 4, 6))
        self.assertEqual(doc['order_rmb'], Decimal('150.00'))   # o que foi enviado
        self.assertEqual(doc['total_rmb'], Decimal('90.00'))    # 6 × ¥15
        self.assertEqual(doc['lines'][0]['wtc'], 'B-06')


class CompradorPagamentoTests(TestCase):
    """A etapa de PAGAMENTO na mão do comprador (dono, 2026-08-18).

    Ele paga em US$ — é a moeda do contrato — anexa o comprovante e a compra
    vai para a última etapa. Parcial é normal, por isso o histórico fica na
    mesma tela: a conta que importa é o SALDO, não o total da fatura.

    ⚠ O comprovante mora no BANCO (PaymentReceipt). O filesystem da Render é
    efêmero: em disco, um deploy apagaria a prova do pagamento.
    """

    @classmethod
    def setUpTestData(cls):
        cls.emp, cls.buyer, cls.brand = _setup('vd-pag')
        User = get_user_model()
        cls.parceiro = User.objects.create_user('vd_pag_p', password='x')
        cls.buyer.users.add(cls.parceiro)

    def setUp(self):
        set_current_company(self.emp.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)
        self.client.force_login(self.parceiro)
        self.so = self._faturada('P')

    def _faturada(self, sufixo):
        """OV congelada + resultado fechado → fatura de US$ 21.00
        (10 × ¥15 = ¥150 × 0.14)."""
        from pricing.models import Price, PriceList, STATUS_QUOTED
        from django.utils import timezone
        with company_scope(self.emp):
            if not PriceList.all_companies.filter(buyer=self.buyer,
                                                  brand=None).exists():
                pl = PriceList.all_companies.create(buyer=self.buyer, brand=None)
                Price.all_companies.create(
                    price_list=pl, kind='emmc', gen='', origin='phone',
                    tier_value=Decimal('16'), tier_unit='GB',
                    status=STATUS_QUOTED, price_min=Decimal('15'),
                    price_max=Decimal('15'))
            lot = Lot.open_for_company(self.emp, self.parceiro, 'p' + sufixo,
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='PG' + sufixo, quantity=10,
                brand=self.brand, chip_type='eMMC', company=self.emp,
                price_kind='emmc', price_gen='',
                price_tier_value=Decimal('16'), price_tier_unit='GB')
            so = services.create_draft_for_lot(lot, self.parceiro)
            Lot.all_companies.filter(pk=lot.pk).update(closed_at=timezone.now())
            so.lot.refresh_from_db()
            services.mark_shipped(so, 'DHL', 'JD' + sufixo, None, self.parceiro)
            so.refresh_from_db()
            services.mark_received(so)
        self.client.post(reverse('compras:resultado', args=[so.pk]), {})
        so.refresh_from_db()
        return so

    def _invoice(self):
        with company_scope(self.emp):
            return Invoice.all_companies.get(order=self.so)

    def _png(self, nome='wire.png'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new('RGB', (12, 12), '#0f62fe').save(buf, format='PNG')
        return SimpleUploadedFile(nome, buf.getvalue(), content_type='image/png')

    def _pagar(self, valor, arquivo=None, **extra):
        dados = {'amount_usd': str(valor), 'paid_at': '2026-08-18'}
        dados.update(extra)
        if arquivo is not False:
            dados['receipt'] = arquivo or self._png()
        return self.client.post(reverse('compras:pagar', args=[self.so.pk]),
                                dados, follow=True)

    # ── o pagamento ─────────────────────────────────────────────────────────

    def test_paga_em_usd_com_comprovante_e_quita_a_fatura(self):
        inv = self._invoice()
        self.assertEqual(inv.total_usd, Decimal('21.00'))       # ¥150 × 0.14
        self._pagar('21.00', reference='WIRE-9931')
        inv = self._invoice()
        self.assertEqual(inv.balance_usd, Decimal('0.00'))
        self.assertEqual(inv.status, 'paid')
        with company_scope(self.emp):
            pag = inv.payments.get()
            self.assertEqual(pag.amount_usd, Decimal('21.00'))
            self.assertEqual(pag.reference, 'WIRE-9931')
            self.assertEqual(pag.created_by, self.parceiro)
            self.assertEqual(pag.receipt.mime, 'image/png')     # no BANCO
            self.assertGreater(pag.receipt.size, 0)

    def test_parcial_deixa_saldo_e_o_historico_soma(self):
        self._pagar('9.00')
        self._pagar('12.00')
        inv = self._invoice()
        self.assertEqual(inv.balance_usd, Decimal('0.00'))
        with company_scope(self.emp):
            self.assertEqual(services.payment_history(inv).__len__(), 2)
        tela = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertContains(tela, 'US$ 9.00')
        self.assertContains(tela, 'US$ 12.00')

    def test_acima_do_saldo_nao_passa(self):
        resp = self._pagar('99.00')
        self.assertContains(resp, 'maior que o saldo')
        with company_scope(self.emp):
            self.assertFalse(self._invoice().payments.exists())

    def test_sem_comprovante_nao_registra(self):
        """Sem prova não há pagamento — é o documento da conciliação."""
        resp = self._pagar('21.00', arquivo=False)
        self.assertContains(resp, 'Anexe o comprovante')
        with company_scope(self.emp):
            self.assertFalse(self._invoice().payments.exists())

    def test_comprovante_invalido_desfaz_o_pagamento_junto(self):
        """MESMA transação: pagamento gravado com comprovante corrompido é
        pior que pagamento nenhum — alguém descobriria na conciliação."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        ruim = SimpleUploadedFile('nota.pdf', b'nem PDF nem imagem',
                                  content_type='application/pdf')
        resp = self._pagar('21.00', arquivo=ruim)
        self.assertContains(resp, 'Formato não suportado')
        with company_scope(self.emp):
            self.assertFalse(self._invoice().payments.exists())

    def test_formato_vem_dos_BYTES_e_nao_da_extensao(self):
        """Extensão é palpite do cliente. Um PNG chamado .pdf é PNG."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        png = self._png('mentira.pdf')
        self._pagar('21.00', arquivo=SimpleUploadedFile(
            'mentira.pdf', png.read(), content_type='application/pdf'))
        with company_scope(self.emp):
            self.assertEqual(self._invoice().payments.get().receipt.mime,
                             'image/png')

    # ── o comprovante ───────────────────────────────────────────────────────

    def test_comprovante_e_servido_do_banco_e_nao_entra_em_cache(self):
        self._pagar('21.00')
        with company_scope(self.emp):
            pag = self._invoice().payments.get()
        resp = self.client.get(reverse('compras:comprovante',
                                       args=[self.so.pk, pag.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertIn('no-store', resp['Cache-Control'])   # documento privado
        self.assertTrue(resp.content.startswith(b'\x89PNG'))

    def test_comprovante_de_outra_compra_e_404(self):
        """Trocar o número na URL não lê o comprovante do vizinho."""
        self._pagar('21.00')
        with company_scope(self.emp):
            pag = self._invoice().payments.get()
        outra = self._faturada('Q')
        self.assertEqual(
            self.client.get(reverse('compras:comprovante',
                                    args=[outra.pk, pag.pk])).status_code, 404)

    def test_etapa_de_pagamento_fecha_o_card(self):
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(self.so)}
        self.assertEqual(passos['pagamento']['state'], 'current')
        self._pagar('21.00')
        self.so.refresh_from_db()
        with company_scope(self.emp):
            passos = {p['key']: p for p in services.order_steps(self.so)}
        self.assertEqual(passos['pagamento']['state'], 'done')

    def test_cliente_ve_o_comprovante_na_fatura_dele(self):
        """É o admin da empresa que fecha a conciliação deste lado — sem ver
        o comprovante ele não tem como."""
        self._pagar('21.00')
        with company_scope(self.emp):
            pag = self._invoice().payments.get()
        User = get_user_model()
        adm = User.objects.create_user('vd_pag_adm', password='x')
        Membership.objects.create(user=adm, company=self.emp,
                                  role=Membership.ROLE_ADMIN)
        self.client.force_login(adm)
        tela = self.client.get(reverse('vendas:invoice_detail',
                                       args=[self._invoice().pk]))
        self.assertContains(tela, reverse('vendas:payment_receipt',
                                          args=[pag.pk]))
        resp = self.client.get(reverse('vendas:payment_receipt', args=[pag.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b'\x89PNG'))

    def test_tela_mostra_saldo_em_usd_e_o_formulario(self):
        tela = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertContains(tela, 'US$ 21.00')
        self.assertContains(tela, 'name="receipt"')
        self.assertContains(tela, reverse('compras:pagar', args=[self.so.pk]))


class DeclaracaoAduaneiraTests(TestCase):
    """O valor declarado no documento de embarque (dono, 2026-08-18).

    A transportadora EXIGE descrição e valor; campo em branco trava o pacote
    ou faz alguém que não conhece a carga reavaliá-la. O valor é FICTÍCIO e
    assumido como tal — é sucata para descarte, e o valor comercial é
    justamente o que não pode viajar impresso na caixa.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-adu')
        User = get_user_model()
        cls.user = User.objects.create_user('vd_adu')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)

    def _so(self, sufixo='A'):
        with company_scope(self.company):
            lot = Lot.open_for_company(self.company, self.user, 'a' + sufixo,
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='AD' + sufixo, quantity=4,
                brand=self.brand, chip_type='eMMC', company=self.company,
                price_kind='emmc', price_gen='',
                price_tier_value=Decimal('16'), price_tier_unit='GB')
            return services.create_draft_for_lot(lot, self.user)

    def test_valor_fica_na_faixa_pedida(self):
        for i in range(12):
            valor = services.declared_value_usd(self._so(f'F{i}'))
            self.assertGreaterEqual(valor, 200)
            self.assertLessEqual(valor, 290)

    def test_MESMO_documento_MESMO_valor_sempre(self):
        """⚠ O ponto todo: imprimir duas vezes não pode dar valor diferente —
        divergência de valor declarado é o que trava pacote na alfândega."""
        so = self._so('E')
        valores = {services.declared_value_usd(so) for _ in range(20)}
        self.assertEqual(len(valores), 1)

    def test_documentos_diferentes_valores_diferentes(self):
        """Não é constante: cada OV tem o seu (é o "aleatório" do pedido)."""
        valores = {services.declared_value_usd(self._so(f'D{i}'))
                   for i in range(15)}
        self.assertGreater(len(valores), 3)

    def test_o_documento_carrega_descricao_e_valor(self):
        with company_scope(self.company):
            doc = services.manager_document(self._so('M'))
        self.assertEqual(doc['shipment_desc'], 'PCB CHIPS FOR DISPOSAL')
        self.assertIn(doc['shipment_value'], range(200, 291))

    def test_o_PDF_imprime_os_dois(self):
        _sem_compressao(self)
        with company_scope(self.company):
            doc = services.manager_document(self._so('P'))
            from vendas.pdf import render_so_manager_pdf
            pdf = render_so_manager_pdf(doc)
        texto = b' '.join(_textos_do_pdf(pdf))
        self.assertIn(b'PCB CHIPS FOR DISPOSAL', texto)
        self.assertIn(f"USD {doc['shipment_value']}".encode(), texto)
        self.assertIn(b'Declared value', texto)


class DespachoTests(TestCase):
    """F4 — o DESPACHO, registrado pelo CLIENTE (dono, 2026-08-18).

    Quem embala e leva a caixa na transportadora é a empresa-cliente; o
    comprador só LÊ (é a etapa "Enviado" e o rastreio na tela dele). Uma caixa
    por lote — decisão do dono —, por isso os campos moram na própria OV.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-desp')
        User = get_user_model()
        cls.users = {}
        for papel in ('admin', 'manager', 'operator'):
            u = User.objects.create_user(f'vd_desp_{papel}', password='x')
            Membership.objects.create(user=u, company=cls.company, role=papel)
            cls.users[papel] = u

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        with company_scope(self.company):
            lot = Lot.open_for_company(self.company, self.users['manager'],
                                       'd', origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='DESP1', quantity=6, brand=self.brand,
                chip_type='eMMC', company=self.company, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            self.so = services.create_draft_for_lot(lot, self.users['manager'])

    def _post(self, papel='manager', **dados):
        self.client.force_login(self.users[papel])
        corpo = {'carrier': 'DHL', 'tracking': 'JD014600', 
                 'shipped_at': '2026-08-18'}
        corpo.update(dados)
        return self.client.post(reverse('vendas:so_ship', args=[self.so.pk]),
                                corpo, follow=True)

    def test_gerente_registra_o_despacho(self):
        self._post()
        self.so.refresh_from_db()
        self.assertEqual(self.so.carrier, 'DHL')
        self.assertEqual(self.so.tracking, 'JD014600')
        self.assertEqual(str(self.so.shipped_at), '2026-08-18')
        self.assertEqual(self.so.shipped_by, self.users['manager'])

    def test_despacho_e_CORRIGIVEL(self):
        """Rastreio digitado errado tem que dar para arrumar, e o número às
        vezes só aparece horas depois do envio."""
        self._post(tracking='')
        self.so.refresh_from_db()
        self.assertEqual(self.so.tracking, '')
        self._post(tracking='JD999')
        self.so.refresh_from_db()
        self.assertEqual(self.so.tracking, 'JD999')

    def test_sem_transportadora_nao_passa(self):
        resp = self._post(carrier='')
        self.so.refresh_from_db()
        self.assertIsNone(self.so.shipped_at)
        self.assertContains(resp, 'transportadora')

    def test_data_no_futuro_nao_passa(self):
        from datetime import date, timedelta
        futuro = (date.today() + timedelta(days=3)).isoformat()
        resp = self._post(shipped_at=futuro)
        self.so.refresh_from_db()
        self.assertIsNone(self.so.shipped_at)
        self.assertContains(resp, 'futuro')

    def test_operador_nao_despacha(self):
        self.client.force_login(self.users['operator'])
        self.assertEqual(self.client.post(
            reverse('vendas:so_ship', args=[self.so.pk])).status_code, 403)

    def test_tela_do_cliente_mostra_o_bloco_e_o_rastreio_clicavel(self):
        self.client.force_login(self.users['manager'])
        tela = self.client.get(reverse('vendas:so_detail', args=[self.so.pk]))
        self.assertContains(tela, 'Despacho')
        self.assertContains(tela, 'Ainda não despachado')
        self._post()
        tela = self.client.get(reverse('vendas:so_detail', args=[self.so.pk]))
        self.assertContains(tela, 'dhl.com')            # link montado
        self.assertContains(tela, 'JD014600')

    def test_transportadora_desconhecida_fica_em_texto_puro(self):
        """Melhor sem link do que com link quebrado."""
        self.assertIsNone(services.tracking_url('Correios PY', 'ABC123'))
        self.assertIn('JD01', services.tracking_url('DHL', 'JD01'))
        self.assertIn('JD01', services.tracking_url('  dhl ', 'JD01'))
        self.assertIsNone(services.tracking_url('DHL', ''))

    def test_comprador_LE_o_despacho_e_nao_escreve(self):
        from pricing.models import Price, PriceList, STATUS_QUOTED
        from django.utils import timezone
        User = get_user_model()
        parceiro = User.objects.create_user('vd_desp_p', password='x')
        self.buyer.users.add(parceiro)
        with company_scope(self.company):
            if not PriceList.all_companies.filter(buyer=self.buyer,
                                                  brand=None).exists():
                pl = PriceList.all_companies.create(buyer=self.buyer, brand=None)
                Price.all_companies.create(
                    price_list=pl, kind='emmc', gen='', origin='phone',
                    tier_value=Decimal('16'), tier_unit='GB',
                    status=STATUS_QUOTED, price_min=Decimal('15'),
                    price_max=Decimal('15'))
            Lot.all_companies.filter(pk=self.so.lot_id).update(
                closed_at=timezone.now())
            self.so.lot.refresh_from_db()
            services.confirm(self.so, self.users['admin'], unmasked=True)
        self._post()
        self.client.force_login(parceiro)
        tela = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertContains(tela, 'Enviado')            # a etapa
        self.assertContains(tela, 'JD014600')           # o rastreio
        self.assertContains(tela, 'dhl.com')
        # ⚠ Ele não tem por onde MEXER: a rota é do lado do cliente.
        self.assertNotContains(tela, reverse('vendas:so_ship',
                                             args=[self.so.pk]))


class TelaDaOVEspelhaACompraTests(TestCase):
    """A tabela da OV do CLIENTE é a MESMA da tela do comprador
    (dono, 2026-08-18): marca → capacidade, com enviados/recusados/aprovados.

    "É o mais importante do vendedor saber" — sem o resultado POR CATEGORIA
    ele recebe um total menor e não descobre qual categoria caiu.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.buyer, cls.brand = _setup('vd-esp')
        User = get_user_model()
        cls.adm = User.objects.create_user('vd_esp_adm', password='x')
        Membership.objects.create(user=cls.adm, company=cls.company,
                                  role='admin')

    def setUp(self):
        set_current_company(self.company.pk)
        self.addCleanup(set_current_company, None)
        call_command('seed_category_codes', '--commit', verbosity=0)
        self.client.force_login(self.adm)
        with company_scope(self.company):
            lot = Lot.open_for_company(self.company, self.adm, 'e',
                                       origin='phone')
            InventoryEntry.all_companies.create(
                lot=lot, part_number='ESP1', quantity=10, brand=self.brand,
                chip_type='eMMC', company=self.company, price_kind='emmc',
                price_gen='', price_tier_value=Decimal('16'),
                price_tier_unit='GB')
            Lot.all_companies.filter(pk=lot.pk).update(
                closed_at=timezone.now())
            self.so = services.create_draft_for_lot(lot, self.adm)
            self.so.lot.refresh_from_db()

    def _tela(self):
        return self.client.get(reverse('vendas:so_detail',
                                       args=[self.so.pk]))

    def test_etapas_do_cliente_seguem_as_do_comprador(self):
        tela = self._tela()
        self.assertContains(tela, 'Rascunho')
        self.assertContains(tela, 'Enviada')        # passo novo
        self.assertContains(tela, 'Resultado')      # era "Faturada"
        self.assertNotContains(tela, 'Faturada')
        self.assertNotContains(tela, 'Confirmada')  # virou o mesmo que Enviada

    def test_tabela_traz_marca_capacidade_e_caixa(self):
        tela = self._tela()
        self.assertContains(tela, self.brand)       # agrupada por MARCA
        self.assertContains(tela, 'eMMC')
        self.assertContains(tela, '16GB')
        self.assertContains(tela, 'B-06')           # a caixa WTC
        # Sem resultado ainda, não há coluna de recusa:
        self.assertNotContains(tela, 'Recusados')

    def test_depois_do_resultado_a_recusa_aparece_POR_CATEGORIA(self):
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
            linha = self.so.lines.get()
            services.settle_and_invoice(self.so, {linha.pk: (4, None)},
                                        self.adm)
        tela = self._tela()
        self.assertContains(tela, 'Recusados')
        self.assertContains(tela, 'Aprovados')
        grupos = tela.context['grupos']
        linha = grupos[0]['lines'][0]
        self.assertEqual((linha['qty'], linha['rejected'], linha['accepted']),
                         (10, 4, 6))
        self.assertEqual(grupos[0]['rejected'], 4)

    def test_etapa_de_pagamento_no_lado_do_CLIENTE(self):
        """Previsto × acertado × pago × falta, e o histórico com o
        comprovante que o COMPRADOR anexou (dono, 2026-08-19). Sem isso a
        etapa de pagamento existia só na tela de quem paga."""
        from datetime import date
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
            linha = self.so.lines.get()
            _st, inv = services.settle_and_invoice(
                self.so, {linha.pk: (4, None)}, self.adm)
            services.register_payment(inv, (inv.total_usd / 2).quantize(
                Decimal('0.01')), date.today(), self.adm, reference='WIRE-7')
        tela = self._tela()
        self.assertContains(tela, 'Previsto')
        self.assertContains(tela, 'Acertado')
        self.assertContains(tela, 'Falta')
        self.assertContains(tela, 'WIRE-7')             # o histórico
        inv.refresh_from_db()
        self.assertContains(tela, f'US$ {inv.balance_usd}')

    def test_o_nome_do_COMPRADOR_nao_aparece_em_lugar_nenhum(self):
        """REGRESSÃO (2026-08-19): o painel de pagamento do cliente reusou o
        histórico do comprador com a coluna "Registrado por" e imprimiu o nome
        dele na tela do cliente.

        ⚠ Segredo de mercado (F11.3): nesta superfície a contraparte se chama
        "WhatTheChip" e nada mais — nem o nome do comprador, nem o do usuário
        que registrou o pagamento. O campo é omitido na ORIGEM (`com_autor`),
        não escondido no template: template esconde, contexto vaza.
        """
        from datetime import date
        User = get_user_model()
        wu = User.objects.create_user('wu_quan_x', first_name='Wu',
                                      last_name='Quan', password='x')
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
            linha = self.so.lines.get()
            _st, inv = services.settle_and_invoice(self.so,
                                                   {linha.pk: (1, None)}, wu)
            services.register_payment(inv, Decimal('1.00'), date.today(), wu,
                                      reference='WIRE-1')
        html = self._tela().content.decode()
        self.assertNotIn('Wu Quan', html)
        self.assertNotIn('wu_quan_x', html)
        self.assertNotIn(self.buyer.name, html)
        self.assertNotIn('Registrado por', html)
        self.assertIn('WIRE-1', html)                  # o resto do histórico fica
        # E o contexto NÃO carrega o autor — não é só o template calando:
        for p in self._tela().context['pagamentos']:
            self.assertNotIn('by', p)

    def test_gerente_nao_ve_o_bloco_de_pagamento(self):
        """É dinheiro: some inteiro, não vira bolinha."""
        User = get_user_model()
        ger = User.objects.create_user('vd_esp_ger', password='x')
        Membership.objects.create(user=ger, company=self.company,
                                  role='manager')
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
            linha = self.so.lines.get()
            services.settle_and_invoice(self.so, {linha.pk: (1, None)},
                                        self.adm)
        self.client.force_login(ger)
        tela = self._tela()
        self.assertNotContains(tela, 'Previsto')
        self.assertNotContains(tela, '•••')
        self.assertContains(tela, 'Recusados')          # a operação, essa fica

    def test_status_vira_RECEBIDA_quando_o_comprador_acusa(self):
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
        self.assertContains(self._tela(), 'despachada')
        with company_scope(self.company):
            services.mark_received(self.so)
        self.assertContains(self._tela(), 'recebida pelo comprador')

    def test_nada_fica_ABAIXO_da_tabela(self):
        """Dono, 2026-08-19: lote grande faz a tabela ter centenas de linhas,
        e botão no fim dela é botão que ninguém alcança. Despacho e pagamento
        ficam ACIMA — a mesma ordem da tela do comprador."""
        with company_scope(self.company):
            services.mark_shipped(self.so, 'DHL', 'JD1', None, self.adm)
            self.so.refresh_from_db()
            linha = self.so.lines.get()
            services.settle_and_invoice(self.so, {linha.pk: (1, None)},
                                        self.adm)
        html = self._tela().content.decode()
        despacho = html.index('Despacho')
        pagamento = html.index('Previsto')
        tabela = html.index('Caixa WTC')
        self.assertLess(despacho, tabela)
        self.assertLess(pagamento, tabela)
        # Depois da tabela não sobra ação nenhuma:
        self.assertNotIn('<form', html[tabela:])

    def test_rascunho_ainda_mostra_US_ao_vivo(self):
        """A tela do cliente é em US$; sem o vivo o admin via '—' na ordem
        ainda não despachada."""
        tela = self._tela()
        linha = tela.context['grupos'][0]['lines'][0]
        self.assertTrue(linha['estimado'])
        self.assertIsNotNone(linha['unit_usd'])
        self.assertIsNotNone(linha['total_usd'])
