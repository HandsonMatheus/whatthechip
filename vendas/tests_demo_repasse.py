"""
Travas do `demo_repasse_automatico` — o comando de laboratório.

Comando de demonstração precisa de teste pelo mesmo motivo que qualquer outro,
e por um a mais: ele é o que alguém roda para ENTENDER a regra. Se ele mentir,
mente com autoridade — e a pessoa vai embora convencida do contrário.

As duas garantias que importam: a simulação não deixa NADA no banco, e o
comando recusa banco que não seja local (ele cria empresa e venda falsas).
"""

from unittest import mock
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from pricing.models import Buyer
from tenancy.models import Company
from vendas.models import Invoice, Payout

User = get_user_model()
COMANDO = 'demo_repasse_automatico'


def _rodar(*args):
    out, err = StringIO(), StringIO()
    call_command(COMANDO, *args, stdout=out, stderr=err)
    return out.getvalue()


class SimulacaoTests(TestCase):
    """O padrão do comando: mostra tudo, grava nada."""

    def test_a_simulacao_nao_deixa_nada_no_banco(self):
        """É a garantia que permite rodar sem medo, quantas vezes quiser."""
        antes = Company.objects.count()
        _rodar()
        self.assertEqual(Company.objects.count(), antes)
        self.assertFalse(Company.objects.filter(
            slug__startswith='demo-repasse').exists())
        self.assertFalse(Buyer.all_companies.filter(
            slug='demo-comprador').exists())
        self.assertEqual(Invoice.all_companies.count(), 0)
        self.assertEqual(Payout.all_companies.count(), 0)

    def test_mostra_o_contraste_entre_ligada_e_desligada(self):
        saida = _rodar()
        self.assertIn('chave DESLIGADA', saida)
        self.assertIn('chave LIGADA', saida)
        # O número que a pessoa veio conferir: o LÍQUIDO, não o bruto.
        self.assertIn('US$ 900.00', saida)
        self.assertIn('Transação desfeita', saida)

    def test_roda_duas_vezes_seguidas(self):
        """Se a 1ª rodada deixasse resíduo, a 2ª morreria em slug duplicado —
        que é exatamente como este comando quebrou na primeira escrita."""
        _rodar()
        _rodar()


class BancoLocalTests(TestCase):
    """A trava que impede o laboratório de existir em produção."""

    def test_recusa_host_remoto(self):
        with mock.patch.dict(
                connection.settings_dict,
                {'HOST': 'dpg-abc123.oregon-postgres.render.com'}):
            with self.assertRaises(CommandError) as e:
                _rodar()
        self.assertIn('laboratório', str(e.exception))

    def test_recusa_o_nome_do_banco_de_producao(self):
        with mock.patch.dict(connection.settings_dict,
                             {'HOST': 'localhost', 'NAME': 'whatthechip_db'}):
            with self.assertRaises(CommandError):
                _rodar()


class PlantioTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user('demo_dono', password='x')
        self.comprador = Buyer.all_companies.create(
            company=None, name='Wu Quan', slug='wu-quan')

    def test_planta_a_venda_em_aberto_com_a_chave_ligada(self):
        saida = _rodar('--commit', '--user', 'demo_dono')
        emp = Company.objects.get(slug='demo-repasse')
        self.assertTrue(emp.payout_on_payment)
        inv = Invoice.all_companies.get(company=emp)
        self.assertEqual(inv.status, 'open')
        self.assertEqual(inv.net_usd, inv.total_usd - inv.fee_usd)
        self.assertIn('Demonstração plantada', saida)
        # …e o dono ganha o vínculo, senão a tela do CLIENTE dá 403 e metade
        # do roteiro morre no passo 2.
        from tenancy.models import Membership
        self.assertTrue(Membership.objects.filter(
            user=self.usuario, company=emp, role='admin', active=True).exists())

    def test_a_venda_plantada_APARECE_na_tela_do_comprador(self):
        """A trava do roteiro. Se a venda não aparecer em /partner/, o passo 1
        morre e a pessoa conclui que a feature não funciona — quando o que não
        funcionou foi a demonstração."""
        from vendas import services
        _rodar('--commit', '--user', 'demo_dono')
        vistas = services.orders_for_buyer(self.comprador)
        self.assertEqual(len(vistas), 1)
        so = vistas[0]
        self.assertIsNotNone(so.fatura)              # tem fatura para pagar…
        self.assertEqual(so.fatura.status, 'open')   # …e ela está em aberto
        self.assertEqual(so.fatura_saldo, so.fatura.total_usd)

    def test_plantar_duas_vezes_recusa_em_vez_de_duplicar(self):
        _rodar('--commit', '--user', 'demo_dono')
        with self.assertRaises(CommandError) as e:
            _rodar('--commit', '--user', 'demo_dono')
        self.assertIn('--revert', str(e.exception))

    def test_commit_sem_user_recusa(self):
        with self.assertRaises(CommandError) as e:
            _rodar('--commit')
        self.assertIn('--user', str(e.exception))

    def test_revert_devolve_o_banco_ao_estado_anterior(self):
        empresas, compradores = (Company.objects.count(),
                                 Buyer.all_companies.count())
        _rodar('--commit', '--user', 'demo_dono')
        _rodar('--revert')
        self.assertEqual(Company.objects.count(), empresas)
        self.assertEqual(Buyer.all_companies.count(), compradores)
        self.assertEqual(Invoice.all_companies.count(), 0)

    def test_revert_sem_nada_plantado_avisa(self):
        with self.assertRaises(CommandError):
            _rodar('--revert')
