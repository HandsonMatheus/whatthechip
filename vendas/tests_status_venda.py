"""
Testes da coluna STATUS da tela de Vendas (`so_list.html`).

Bug de 2026-09-01 (dono, olhando a lista): os envios legados apareciam como
"despacho pendente" tendo sido recebidos e pagos meses antes. A cadeia de
`{% elif %}` perguntava "tem `shipped_at`?" ANTES de olhar `received_at`, e
registro legado tem recebimento sem despacho — ninguém registrou a saída de
uma caixa que partiu antes de o sistema existir.

A regra travada aqui: **chegar implica ter saído**. E, de propósito, esta
coluna continua sendo LOGÍSTICA — pagamento vive na coluna "A receber".
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope, set_current_company
from vendas.models import DocSequence, SEQ_SO, SalesOrder

User = get_user_model()


class _Lista(TestCase):
    """Uma ordem por cenário; a asserção é o texto do badge na linha dela."""

    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.admin = User.objects.create_user('vd_status_admin', password='x')
        Membership.objects.create(user=self.admin, company=self.empresa,
                                  role='admin')
        set_current_company(self.empresa.pk)
        self.addCleanup(set_current_company, None)
        self.agora = timezone.now()
        self.n = 0

    def _ordem(self, *, status='confirmed', enviada=None, recebida=None,
               cancelada=None):
        self.n += 1
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=self.n, description='x',
                status='closed', operator=self.admin, origin='phone')
            campos = dict(lot=lot, buyer=self.buyer, status=status,
                          number=DocSequence.next_number(self.empresa, SEQ_SO),
                          shipped_at=enviada, received_at=recebida,
                          cancelled_at=cancelada)
            if status == 'confirmed':
                # so_confirmed_is_frozen: confirmada exige valor congelado.
                campos.update(fx_usd_rate='0.1500', total_rmb='100.00',
                              total_usd='15.00')
            so = SalesOrder(**campos)
            so.save()
        return so

    def _badge(self, so):
        self.client.force_login(self.admin)
        html = self.client.get(reverse('vendas:so_list')).content.decode()
        # A linha da ordem começa no link do código dela.
        linha = html.split(so.code, 1)[1].split('</tr>', 1)[0]
        for rotulo in ('cancelada', 'recebida', 'despacho pendente',
                       'falta preço', 'despachada'):
            if f'>{rotulo}<' in linha:
                return rotulo
        return None


class OrdemDosCasosTests(_Lista):

    def test_recebida_sem_despacho_registrado_e_RECEBIDA(self):
        """O caso do dono: legado chegou, mas a saída nunca foi registrada."""
        so = self._ordem(enviada=None, recebida=self.agora)
        self.assertEqual(self._badge(so), 'recebida')

    def test_recebida_com_despacho_continua_recebida(self):
        so = self._ordem(enviada=self.agora - timedelta(days=12),
                         recebida=self.agora)
        self.assertEqual(self._badge(so), 'recebida')

    def test_despachada_e_nao_recebida(self):
        so = self._ordem(enviada=self.agora)
        self.assertEqual(self._badge(so), 'despachada')

    def test_sem_nada_continua_despacho_pendente(self):
        so = self._ordem()
        self.assertEqual(self._badge(so), 'despacho pendente')

    def test_cancelada_ganha_de_tudo(self):
        so = self._ordem(status='cancelled', recebida=self.agora,
                         cancelada=self.agora)
        self.assertEqual(self._badge(so), 'cancelada')

    def test_rascunho_despachado_ainda_diz_falta_preco(self):
        so = self._ordem(status='draft', enviada=self.agora)
        self.assertEqual(self._badge(so), 'falta preço')


class ColunaELogisticaTests(_Lista):
    """A coluna fala de caixa, não de dinheiro — se um dia isso mudar, que
    mude de propósito e não por acidente."""

    def test_ordem_paga_e_nao_despachada_nao_vira_verde(self):
        so = self._ordem()          # confirmada, sem envio, sem recebimento
        self.assertEqual(self._badge(so), 'despacho pendente',
                         'pagamento não pode mexer nesta coluna')
