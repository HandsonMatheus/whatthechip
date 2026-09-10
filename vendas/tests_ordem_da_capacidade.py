# -*- coding: utf-8 -*-
"""A capacidade em ordem CRESCENTE dentro da marca (dono, 2026-09-10).

> "agora está o eMMC 128 na primeira linha por exemplo e abaixo dele o de
> 16GB, esta uma bagunça, pode ser crescente? nesse caso seria de 8GB, depois
> 16, 32, assim vai"

O defeito era ordenar pelo RÓTULO: no alfabeto '128GB' vem antes de '16GB'.
A armadilha, que uma correção ingênua (ler o número do rótulo) erraria, é que
o vocabulário tem duas unidades e elas valem 8× diferente — `GB` é gigaBYTE e
`Gb` é gigaBIT (`pricing/models.py:86`, com o aviso de case-sensitive).
"""
import io
import os
from datetime import date
from decimal import Decimal as D

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import services
from vendas.models import (DocSequence, SEQ_SO, SalesOrder, SalesOrderLine,
                           STATUS_CONFIRMED)

FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')


class AGrandezaTests(TestCase):
    """A conta sozinha, sem banco. É onde a unidade morde."""

    def test_GB_e_o_proprio_numero(self):
        self.assertEqual(services._grandeza(D('64'), 'GB'), D('64'))

    def test_Gb_vale_um_OITAVO_porque_e_BIT(self):
        """2Gb é um die de 2 gigaBITS = 0,25 gigaBYTE. Se isto virar 2, um die
        de 2Gb passa à frente de um pacote de 1GB — quatro vezes maior."""
        self.assertEqual(services._grandeza(D('2'), 'Gb'), D('0.25'))

    def test_o_caso_que_a_correcao_INGENUA_erra(self):
        """Ler o número do rótulo diria 8Gb > 1GB. Em bytes, 8Gb = 1GB."""
        self.assertEqual(services._grandeza(D('8'), 'Gb'),
                         services._grandeza(D('1'), 'GB'))
        self.assertLess(services._grandeza(D('4'), 'Gb'),
                        services._grandeza(D('1'), 'GB'))

    def test_a_case_sensitive_e_a_regra_toda(self):
        """`GB` e `Gb` diferem só na caixa da segunda letra, e valem 8×. Este
        teste existe porque um `.upper()` distraído em qualquer ponto do
        caminho apagaria a diferença sem quebrar mais nada."""
        self.assertNotEqual(services._grandeza(D('16'), 'GB'),
                            services._grandeza(D('16'), 'Gb'))

    def test_chave_PLANA_nao_finge_capacidade(self):
        """K9 nasce com tier 1/'' de propósito: o tipo não tem capacidade."""
        self.assertEqual(services._grandeza(D('1'), ''), D('-1'))
        self.assertLess(services._grandeza(D('1'), ''),
                        services._grandeza(D('1'), 'Gb'))

    def test_tier_nulo_nao_estoura(self):
        self.assertEqual(services._grandeza(None, 'GB'), D('0'))


class _Base(TestCase):
    """Uma marca com eMMC fora de ordem — o caso exato do print."""

    #: Na ordem BAGUNÇADA que o alfabeto produz, para o teste falhar se a
    #: correção sumir: 128, 16, 32, 64, 8.
    CAPS = [D('128'), D('16'), D('32'), D('64'), D('8')]

    def setUp(self):
        User = get_user_model()
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=9, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1481'), total_rmb=D('0'), total_usd=D('0'),
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            for cap in self.CAPS:
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.emp, brand='Foresee',
                    kind='emmc', gen='', tier_value=cap, tier_unit='GB',
                    quantity=10, unit_rmb=D('1.00'), unit_usd=D('0.15'))
            self.so.total_rmb = D('50.00')
            self.so.total_usd = D('7.50')
            self.so.save()
        self.client.force_login(self.parceiro)

    def _linhas_da_marca(self):
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so)
        g = next(x for x in grupos if x['brand'] == 'Foresee')
        return [l['capacity'] for l in g['lines']]


class NaTelaTests(_Base):

    def test_a_capacidade_sobe(self):
        self.assertEqual(self._linhas_da_marca(),
                         ['8GB', '16GB', '32GB', '64GB', '128GB'])

    def test_NAO_esta_em_ordem_de_texto(self):
        """O `assertNotEqual` é o teste de verdade: sem ele, um sort que por
        acaso acertasse a lista curta passaria e o defeito voltaria."""
        self.assertNotEqual(self._linhas_da_marca(),
                            sorted(self._linhas_da_marca()))

    def test_a_linha_carrega_os_campos_CRUS(self):
        """A ordenação lê `tier_value`/`tier_unit`, não o rótulo. Se alguém
        tirar os campos da linha, o sort volta a ser de texto em silêncio."""
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so)
        linha = grupos[0]['lines'][0]
        self.assertIn('tier_value', linha)
        self.assertIn('tier_unit', linha)
        self.assertEqual(linha['tier_unit'], 'GB')

    def test_na_FICHA_a_ordem_e_a_mesma(self):
        """Do servidor até o HTML: as capacidades saem na ordem crescente."""
        html = self.client.get(
            reverse('compras:detail', args=[self.so.pk])).content.decode()
        posicoes = [html.find('>%sGB<' % c) for c in ('8', '16', '32', '64',
                                                      '128')]
        self.assertNotIn(-1, posicoes, 'alguma capacidade sumiu da ficha')
        self.assertEqual(posicoes, sorted(posicoes))


class OTipoEAUnidadeJuntosTests(TestCase):
    """O caso do print: DDR3 em `Gb` e eMMC em `GB`, na mesma marca."""

    def setUp(self):
        User = get_user_model()
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=9, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1481'), total_rmb=D('0'), total_usd=D('0'),
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            # eMMC fora de ordem…
            for cap in (D('128'), D('8'), D('16')):
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.emp, brand='Foresee',
                    kind='emmc', gen='', tier_value=cap, tier_unit='GB',
                    quantity=5, unit_rmb=D('1.00'), unit_usd=D('0.15'))
            # …e DDR3 em Gb, fora de ordem também
            for cap in (D('4'), D('2')):
                SalesOrderLine.all_companies.create(
                    order=self.so, company=self.emp, brand='Foresee',
                    kind='ddr', gen='DDR3', tier_value=cap, tier_unit='Gb',
                    quantity=5, unit_rmb=D('1.00'), unit_usd=D('0.15'))
            self.so.total_rmb = D('25.00')
            self.so.total_usd = D('3.75')
            self.so.save()
        self.client.force_login(self.parceiro)

    def test_cada_tipo_sobe_dentro_de_si(self):
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so)
        g = next(x for x in grupos if x['brand'] == 'Foresee')
        pares = [(l['type'], l['capacity']) for l in g['lines']]
        self.assertEqual(pares, [('DDR3', '2Gb'), ('DDR3', '4Gb'),
                                 ('eMMC', '8GB'), ('eMMC', '16GB'),
                                 ('eMMC', '128GB')])

    def test_o_tipo_manda_ANTES_da_capacidade(self):
        """Um DDR3 de 4Gb (0,5GB) não pode se infiltrar no meio dos eMMC só
        porque é menor: primeiro agrupa por tipo, depois ordena dentro dele."""
        with company_scope(self.emp.id):
            grupos = services.result_rows(self.so)
        tipos = [l['type'] for l in grupos[0]['lines']]
        self.assertEqual(tipos, sorted(tipos), 'os tipos se misturaram')


class OPapelSegueATelaTests(_Base):
    """Se as duas superfícies discordarem, o cliente recebe um papel numa
    ordem e vê a tela noutra — foi por isso que o `order_by('brand')` sozinho
    saiu: ele descartava o `Meta.ordering` e deixava o banco decidir."""

    def test_o_PDF_lista_na_mesma_ordem(self):
        with company_scope(self.emp.id):
            doc = services.result_preview(self.so, {})
        caps = [l['capacity'] for l in doc['lines']]
        self.assertEqual(caps, ['8GB', '16GB', '32GB', '64GB', '128GB'])

    def test_a_PLANILHA_lista_na_mesma_ordem(self):
        """Ela herda a ordem do `result_rows` — mas o teste lê as CÉLULAS de
        verdade, não o dicionário: é a diferença entre provar que os dados
        estão ordenados e provar que o comprador vê ordenado."""
        import openpyxl
        from vendas.planilha import compra_em_planilha
        from vendas.views_partner import _detalhe
        with company_scope(self.emp.id):
            dados, _nome = compra_em_planilha(self.so, _detalhe(self.so))
        ws = openpyxl.load_workbook(io.BytesIO(dados))['Resumo']
        caps = [c.value for col in ws.iter_cols(min_col=2, max_col=2)
                for c in col
                if isinstance(c.value, str) and c.value.endswith('GB')]
        self.assertEqual(caps, ['8GB', '16GB', '32GB', '64GB', '128GB'])
