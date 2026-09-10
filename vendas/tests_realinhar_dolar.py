# -*- coding: utf-8 -*-
"""O comando que realinha o US$ das OVs abertas (dono, 2026-09-10).

O código novo e os dados TÊM de subir juntos: se o `total_usd` gravado ficar
na conta antiga enquanto o resultado passa a usar a nova, toda venda aberta
mostra RESULTADO acima do ESPERADO sem recusa nenhuma — o sintoma de 07/09.
"""
import io
from datetime import date
from decimal import Decimal as D, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas.models import (DocSequence, Invoice, SEQ_SO, SalesOrder,
                           SalesOrderLine, STATUS_CONFIRMED, STATUS_DRAFT)

User = get_user_model()
CENT = D('0.01')


def _rodar(**kw):
    out = io.StringIO()
    err = io.StringIO()
    call_command('realinhar_dolar_por_linha', stdout=out, stderr=err, **kw)
    return out.getvalue(), err.getvalue()


class _Base(TestCase):
    #: ¥3 × 0,1481 = 0,4443 → o unitário de exibição congela em 0,44.
    #: 10.000 peças: conta ANTIGA 4.400,00 · conta NOVA 4.443,00.
    U, FX, Q = D('3.00'), D('0.1481'), 10000
    U_USD = D('0.44')
    ANTIGO, NOVO = D('4400.00'), D('4443.00')

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.user = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.user, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        self.so = self._ov(1)

    def _ov(self, n, total_usd=None, status=STATUS_CONFIRMED, unit_usd=None):
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=n, description='x', status='closed',
                operator=self.user, origin='pcb')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status=status,
                fx_usd_rate=self.FX,
                total_rmb=self.U * self.Q if status == STATUS_CONFIRMED else None,
                total_usd=(total_usd if total_usd is not None else self.ANTIGO)
                          if status == STATUS_CONFIRMED else None,
                shipped_at=date(2026, 8, 18), received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
            SalesOrderLine.all_companies.create(
                order=so, company=self.emp, brand='Kingston', kind='ddr3',
                gen='', tier_value=D('2'), tier_unit='GB', quantity=self.Q,
                unit_rmb=self.U,
                unit_usd=unit_usd if unit_usd is not None else self.U_USD)
            return so


class ODryRunTests(_Base):

    def test_por_PADRAO_nao_grava_nada(self):
        """A regra da casa: comando que escreve nasce em dry-run."""
        saida, _e = _rodar()
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.ANTIGO)
        self.assertIn('DRY-RUN', saida)

    def test_o_dry_run_MOSTRA_o_numero_que_gravaria(self):
        """Ver antes de gravar é o ponto do dry-run — se ele não mostra o
        valor, o dono não tem como conferir e vai rodar no escuro."""
        saida, _e = _rodar()
        self.assertIn('4,400.00', saida)
        self.assertIn('4,443.00', saida)
        self.assertIn('+43.00', saida)


class OCommitTests(_Base):

    def test_com_commit_o_total_vai_para_a_conta_NOVA(self):
        _rodar(commit=True)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)

    def test_o_novo_total_bate_com_a_CALCULADORA(self):
        """O teste do dono: ¥ do rodapé × taxa tem de dar o US$ do rodapé."""
        _rodar(commit=True)
        self.so.refresh_from_db()
        pela_taxa = (self.so.total_rmb * self.FX).quantize(CENT, ROUND_HALF_UP)
        self.assertLess(abs(self.so.total_usd - pela_taxa), D('1.00'))

    def test_rodar_DUAS_vezes_nao_muda_mais_nada(self):
        """Idempotente: a segunda passada não pode achar diferença — senão
        alguém roda por engano e o número anda de novo."""
        _rodar(commit=True)
        saida, _e = _rodar(commit=True)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)
        self.assertIn('corrigidas .................. 0', saida)

    def test_o_filtro_aceita_o_CODIGO_que_o_dono_digita(self):
        """`code` é propriedade e não coluna: filtrar por `number=` casaria
        com o número interno, e o dono digita EMIN-SO-2026-0004."""
        self.assertTrue(self.so.code.startswith('EMI'), self.so.code)
        _rodar(commit=True, ov=self.so.code)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)

    def test_so_a_OV_pedida_quando_vem_o_filtro(self):
        outra = self._ov(2)
        _rodar(commit=True, ov=self.so.code)
        self.so.refresh_from_db()
        outra.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)
        self.assertEqual(outra.total_usd, self.ANTIGO, 'mexeu na OV errada')


class OQueEleNAOTocaTests(_Base):

    def test_OV_com_fatura_ativa_fica_INTACTA(self):
        """O número já foi para o cliente e pode já ter sido pago. Reescrever
        um documento emitido é pior que a diferença que ele corrige."""
        with company_scope(self.emp.id):
            Invoice.all_companies.create(
                order=self.so, company=self.emp, status='open',
                fx_usd_rate=self.FX, total_rmb=self.so.total_rmb,
                total_usd=self.ANTIGO,
                number=DocSequence.next_number(self.emp, SEQ_SO) + 900)
        _rodar(commit=True)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.ANTIGO)

    def test_OV_em_RASCUNHO_fica_intacta(self):
        """Não há nada congelado ainda — ela congela certo no `confirm`."""
        rasc = self._ov(3, status=STATUS_DRAFT)
        _rodar(commit=True)
        rasc.refresh_from_db()
        self.assertIsNone(rasc.total_usd)

    def test_o_unitario_de_EXIBICAO_nao_e_tocado(self):
        """`unit_usd` continua `round(¥ × taxa, 2)`: ele mostra quanto custa
        UM. Quem faz conta é o ¥."""
        _rodar(commit=True)
        with company_scope(self.emp.id):
            self.assertEqual(self.so.lines.all()[0].unit_usd, self.U_USD)


class ATravaDeSegurancaTests(_Base):
    """A parte que me deixaria dormir se isto rodasse em produção."""

    def test_dolar_de_OUTRA_origem_faz_PULAR_a_OV_inteira(self):
        """Se o `unit_usd` gravado não é `round(¥ × taxa)`, ele veio de outro
        lugar — importação legada, taxa histórica. Recalcular pelo ¥ ali não
        seria corrigir arredondamento, seria TROCAR o valor. Pula e relata.
        """
        estranha = self._ov(4, unit_usd=D('0.30'))     # ¥3 × 0,1481 = 0,44
        _saida, err = _rodar(commit=True)
        estranha.refresh_from_db()
        self.assertEqual(estranha.total_usd, self.ANTIGO, 'mexeu numa OV que '
                         'tem dólar de outra origem')
        self.assertIn('outra origem', err)

    def test_a_OV_pulada_NAO_impede_as_outras(self):
        """Uma OV estranha não pode travar o lote todo — senão o dono não roda
        o comando e a correção não acontece."""
        self._ov(5, unit_usd=D('0.30'))
        _rodar(commit=True)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)

    def test_o_relatorio_CONTA_as_puladas(self):
        self._ov(6, unit_usd=D('0.30'))
        saida, _e = _rodar()
        self.assertIn('PULADAS', saida)
        self.assertIn('PULADAS (dólar de outra origem) 1', saida)

    def test_linha_SEM_preco_nao_estoura_nem_vira_zero(self):
        with company_scope(self.emp.id):
            SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Nanya', kind='ddr3',
                gen='', tier_value=D('4'), tier_unit='GB', quantity=50,
                unit_rmb=None, unit_usd=None)
        _rodar(commit=True)
        self.so.refresh_from_db()
        self.assertEqual(self.so.total_usd, self.NOVO)
