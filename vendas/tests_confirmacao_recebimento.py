# -*- coding: utf-8 -*-
"""
CONFIRMAÇÃO ANTES DE "MARCAR COMO RECEBIDO" (dono, 2026-09-02).

Por que este botão e não outro: o ato é de MÃO ÚNICA. O `mark_received` é
idempotente e a PRIMEIRA data vale — "remarcar reescreveria um fato do
passado", diz o próprio serviço. Não existe tela, nem do comprador nem do
cliente, que corrija um recebimento marcado por engano. O despacho, ao lado,
é editável de propósito: ali um clique errado se conserta.

A confirmação é CAMADA, não portão. Sem JS o formulário continua indo direto,
como sempre foi — é o mesmo desenho dos outros dois diálogos da ficha, que
interceptam o `submit` e o devolvem quando o usuário confirma.

⚠ O teste que mais importa aqui é o de POSIÇÃO do JS. Leia o comentário dele
  antes de "organizar" o bloco.
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
from vendas.models import DocSequence, SEQ_SO, SalesOrder

User = get_user_model()

FICHA = os.path.join(settings.BASE_DIR, 'vendas', 'templates', 'vendas',
                     'partner_compra.html')


def _ler(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


class _Base(TestCase):

    def setUp(self):
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
                company=self.emp, number=1, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1400'), total_rmb=D('1000.00'),
                total_usd=D('140.00'), shipped_at=date(2026, 8, 27),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
        self.client.force_login(self.parceiro)

    def _html(self):
        r = self.client.get(reverse('compras:detail', args=[self.so.pk]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()


class DialogoTests(_Base):

    def test_o_dialogo_aparece_com_a_caixa_a_caminho(self):
        html = self._html()
        self.assertIn('id="m-recebi"', html)
        self.assertIn('id="m-recebi-ok"', html)
        self.assertIn('data-fecha="m-recebi"', html)

    def test_o_dialogo_mostra_a_data_que_vai_ser_gravada(self):
        """A data não é escolhida: o serviço grava `now()`. Se a caixa chegou
        na sexta e ele marcar na segunda, o registro diz segunda — e esta é a
        única chance dele de perceber isso ANTES."""
        html = self._html()
        self.assertIn(timezone.localtime().strftime('%d/%m/%Y'), html)
        self.assertIn('27/08/2026', html)     # a data do envio, para comparar

    def test_o_dialogo_some_depois_de_recebido(self):
        """Junto com o formulário e o botão: os três nascem do mesmo `{% if %}`.
        Um diálogo órfão no DOM é um botão de confirmar apontando para um
        formulário que não existe mais."""
        self.so.received_at = timezone.now()
        self.so.save(update_fields=['received_at'])
        html = self._html()
        self.assertNotIn('id="m-recebi"', html)
        self.assertNotIn('id="f-recebi"', html)

    def test_o_dialogo_avisa_que_nao_da_para_corrigir(self):
        """O texto tem de dizer o que o serviço faz. Se o `mark_received`
        deixar de ser idempotente um dia, este teste não pega — mas o aviso
        vira mentira, e alguém lendo isto vai saber onde olhar."""
        self.assertIn('primeira data vale', self._html())


class SemJavaScriptTests(_Base):

    def test_o_post_direto_continua_marcando(self):
        """A confirmação é camada, não portão. Sem JS o `f-recebi` vai direto —
        e é assim que a tela funcionava antes de existir diálogo nenhum. Se
        este teste quebrar, a confirmação virou requisito e quem estiver sem JS
        não consegue mais marcar recebimento."""
        r = self.client.post(reverse('compras:recebido', args=[self.so.pk]))
        self.assertEqual(r.status_code, 302)
        self.so.refresh_from_db()
        self.assertIsNotNone(self.so.received_at)

    def test_o_botao_nao_tem_javascript_embutido(self):
        """Nada de `onclick` no botão: quem intercepta é o listener do
        `submit`, e é isso que mantém o caminho sem JS intacto."""
        html = self._html()
        self.assertIn('form="f-recebi"', html)
        self.assertNotIn('onclick', html)


class PosicaoDoScriptTests(TestCase):
    """O teste que justifica este arquivo existir.

    O IIFE grande da ficha tem, no meio dele:

        if (!campos.length || !elPagar || !form) return;

    `campos` são os inputs de recusa da grade de resultado. Essa condição é
    VERDADEIRA exatamente no estado em que o botão "Marcar como recebido"
    aparece: enviada, ainda não recebida, sem grade nenhuma na tela. Um bloco
    de JS escrito DEPOIS dessa linha nunca roda nesse estado.

    O modo de falhar é o pior que existe: a tela continua funcionando. O botão
    marca o recebimento na hora, sem perguntar nada, e ninguém percebe que a
    confirmação sumiu — até alguém marcar por engano uma data que não dá para
    desfazer.
    """

    def test_o_js_da_confirmacao_vem_antes_do_return(self):
        src = _ler(FICHA)
        js = src.find("okRec.addEventListener('click'")
        ret = src.find('if (!campos.length || !elPagar || !form) return;')
        self.assertNotEqual(js, -1, 'o bloco da confirmação sumiu do template')
        self.assertNotEqual(ret, -1,
                            'o `return` mudou de forma — releia o docstring '
                            'desta classe antes de ajustar a busca')
        self.assertLess(js, ret,
                        'o JS da confirmação está DEPOIS do return do IIFE: '
                        'ele não roda no estado em que o botão aparece, e o '
                        'recebimento passa a ser marcado sem perguntar')

    def test_a_confirmacao_esta_dentro_do_escopo_de_abrir_e_fechar(self):
        """Ela chama `abrir`/`fechar`, que são declaradas dentro do IIFE. Se o
        bloco for movido para fora, as duas ficam indefinidas e o clique
        estoura no console — sem diálogo e sem submit."""
        src = _ler(FICHA)
        self.assertLess(src.find('function abrir(id)'),
                        src.find("abrir('m-recebi')"))
        self.assertLess(src.find("okRec.addEventListener('click'"),
                        src.find('})();', src.find("abrir('m-recebi')")))
