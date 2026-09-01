"""
A ORIGEM do lote nas telas de `vendas` — 4ª quebra do mesmo campo (2026-09-01).

O dono viu a lista de compras em chinês e os selos diziam **CELULAR** e **PCB**,
em português. A causa não era o catálogo: era o template, que trazia o rótulo
DIGITADO à mão dentro de um `if origin == 'phone' / elif 'pcb'`. Texto digitado
em template não passa por tradução nenhuma, e uma chave de dois caminhos não
tem onde pôr as outras três origens — o LOT/004 aparecia sem selo na mesma
tela, e no detalhe do cliente um lote MIXED era chamado de "Celular".

É o bug de 2026-08-28 (CLAUDE.md §7) vivo em `vendas/`: a trava escrita na
época varria só `estoque/templates/`. Estes testes cobrem o outro lado — o
que a tela realmente escreve —, e o scanner do `OrigemRamTests` foi alargado
para o projeto inteiro.

⚠ Não testam o modelo: ele sempre esteve certo (`ORIGIN_CHOICES` já traz
  `_lazy('Celular')` desde sempre). Quem mentia era quem não perguntou a ele.
"""

from decimal import Decimal as D
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas.models import DocSequence, SEQ_SO, SalesOrder

User = get_user_model()


class _Base(TestCase):

    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer',
                                          code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq_org', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g_org', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        self._n = 0

    def _venda(self, origem):
        self._n += 1
        with company_scope(self.emp.id):
            lot = Lot.all_companies.create(
                company=self.emp, number=self._n, description='x',
                status='closed', operator=self.gerente, origin=origem)
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=D('10.00'),
                total_usd=D('10.00'), shipped_at=date(2026, 7, 11),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            so.save()
        return so

    def _lista_do_comprador(self, **extra):
        self.client.force_login(self.parceiro)
        return self.client.get(reverse('compras:list'),
                               **extra).content.decode()

    def _venda_do_cliente(self, so):
        self.client.force_login(self.gerente)
        return self.client.get(
            reverse('vendas:so_detail', args=[so.pk])).content.decode()


class ListaDoCompradorTests(_Base):

    def test_celular_sai_do_modelo_e_por_isso_TRADUZ(self):
        """O que o dono reportou. Em chinês o selo tem de dizer 手机 — com o
        rótulo digitado no template ele dizia "Celular" em qualquer idioma."""
        self._venda('phone')
        html = self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='zh-hans')
        self.assertIn('手机', html)
        self.assertNotIn('>Celular<', html)

    def test_em_portugues_continua_Celular(self):
        self._venda('phone')
        self.assertIn('Celular',
                      self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='pt-br'))

    def test_PCB_e_token_canonico_e_NAO_traduz(self):
        """`PCB` não é palavra, é a sigla que a bancada fala nos quatro
        idiomas — o modelo a declara sem `_lazy` de propósito."""
        self._venda('pcb')
        self.assertIn('PCB',
                      self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='zh-hans'))

    def test_origem_de_RAM_aparece_em_vez_de_sumir(self):
        """A chave de dois caminhos deixava o lote de RAM SEM selo nenhum."""
        self._venda('ram')
        html = self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='pt-br')
        self.assertIn('otag--origem', html)
        self.assertIn('Módulo de memória', html)

    def test_lote_LEGADO_ganha_selo_com_o_proprio_nome(self):
        """MIXED/K9 vinham do controle antigo. Sem selo o comprador não sabe
        o que é aquela caixa; com o selo errado, sabe errado."""
        self._venda('mixed')
        html = self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='pt-br')
        self.assertIn('otag--origem', html)
        self.assertIn('MIXED', html)
        self.assertNotIn('Celular', html)

    def test_k9_tambem(self):
        """A outra origem legada. Duas linhas de teste porque MIXED e K9 são
        rótulos DIFERENTES vindos do mesmo lugar — se alguém reintroduzir um
        mapa no template, é comum acertar um e esquecer o outro."""
        self._venda('k9')
        self.assertIn('K9', self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='pt-br'))

    def test_selo_NAO_tem_icone_nem_cor_por_origem(self):
        """Pedido do dono: um selo, uma cor, sem ícone. Trava porque a
        tentação de "melhorar" com emoji ou cor por valor já apareceu uma vez
        — e recria o mapa por origem que este campo não pode ter."""
        self._venda('phone')
        html = self._lista_do_comprador(HTTP_ACCEPT_LANGUAGE='pt-br')
        self.assertIn('otag--origem', html)
        for classe in ('otag--phone', 'otag--pcb', 'otag--ram',
                       'otag--mixed', 'otag--k9'):
            self.assertNotIn(classe, html)
        for emoji in ('📱', '🔌', '💾', '🧩', '🧱'):
            self.assertNotIn(emoji, html)


class DetalheDoClienteTests(_Base):

    def test_lote_legado_NAO_e_chamado_de_celular(self):
        """O `if origin == 'pcb' / else Celular` de dois caminhos chamava de
        CELULAR tudo que não fosse PCB — o sistema mentindo sobre a
        procedência declarada do material."""
        so = self._venda('mixed')
        html = self._venda_do_cliente(so)
        self.assertIn('MIXED', html)
        self.assertNotIn(f'{so.lot.code} · Celular', html)

    def test_ram_aparece_com_o_nome_dela(self):
        so = self._venda('ram')
        self.assertIn('Módulo de memória', self._venda_do_cliente(so))

    def test_pcb_continua_pcb(self):
        so = self._venda('pcb')
        self.assertIn('PCB', self._venda_do_cliente(so))
