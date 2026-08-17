# -*- coding: utf-8 -*-
"""
tenancy/tests_403.py — a página de ACESSO NEGADO e a rota de escape
====================================================================
Dois comportamentos que andam juntos (dono, 2026-08-17):

  1. o ``handler403`` (core/views.py) renderiza o 403 DENTRO do shell do painel
     — com menu, empresa, usuário, papel e o botão **Sair** — em vez do texto
     cru do Django, que não deixava nem saber com qual conta você estava;
  2. ``/logout/`` (e as outras rotas de SESSÃO) passam a escapar do 403 de host
     do ``HostTenantMiddleware``. Sem isso o item 1 seria decorativo: no host
     da empresa errada o próprio botão Sair levaria outro 403 e a única saída
     seria limpar cookie na mão (a sessão vale em todos os subdomínios).

⚠ O teste de VAZAMENTO (``test_403_de_host_nao_revela_a_empresa_dona``) é o
cadeado do §10.2: a página pode mostrar o que o requisitante já sabe (a conta
DELE, a empresa DELE, o host que ELE digitou) e nunca de quem é o subdomínio.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.views import permission_denied
from tenancy.middleware import ESCAPE_EXATAS, ESCAPE_PREFIXOS
from tenancy.models import Company, Membership

User = get_user_model()


class Pagina403Tests(TestCase):
    """A página em si, no host canônico (gate de view = ``platform_required``:
    ``/company/new/`` é 403 até pra admin de empresa)."""

    URL = '/company/new/'

    @classmethod
    def setUpTestData(cls):
        cls.cia = Company.objects.create(name='Cia do 403', slug='cia403')
        cls.user = User.objects.create_user('op403')
        Membership.objects.create(user=cls.user, company=cls.cia,
                                  role=Membership.ROLE_OPERATOR)

    def test_403_tem_identidade_e_saida(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.URL)
        corpo = resp.content.decode()
        self.assertEqual(resp.status_code, 403)          # continua NEGANDO
        self.assertIn('op403', corpo)                    # com qual conta estou
        self.assertIn('Cia do 403', corpo)               # em qual empresa
        self.assertIn('Acesso negado', corpo)
        self.assertIn('Página exclusiva da plataforma.', corpo)   # o motivo
        # a SAÍDA: form POST pro logout (Django 5 não aceita mais GET)
        self.assertIn(f'action="{reverse("logout")}"', corpo)
        self.assertIn('csrfmiddlewaretoken', corpo)
        # e o menu do shell (é o pedido original: poder navegar/deslogar)
        self.assertIn(reverse('painel'), corpo)

    def test_403_de_papel_mostra_o_motivo_do_gate(self):
        """Mensagem do ``role_required`` (a que o operador mais vê)."""
        self.client.force_login(self.user)
        resp = self.client.get(reverse('vendas:so_list'))
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Seu papel não permite esta ação.',
                      resp.content.decode())

    def test_htmx_recebe_fragmento_e_nao_o_documento(self):
        """Endpoint de bancada é htmx: devolver <html> inteiro só sujaria o
        responseText (o htmx não faz swap de 4xx)."""
        self.client.force_login(self.user)
        resp = self.client.get(self.URL, HTTP_HX_REQUEST='true')
        corpo = resp.content.decode()
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('<html', corpo.lower())
        self.assertIn('Acesso negado', corpo)

    def test_anonimo_cai_no_casco_minimo_com_entrar(self):
        """Anônimo quase sempre é redirecionado pro login pelos gates; quando
        alguma camada levanta PermissionDenied mesmo assim, a página não pode
        quebrar tentando montar o shell logado (avatar/empresa vazios)."""
        req = RequestFactory().get('/qualquer/')
        req.user = AnonymousUser()
        resp = permission_denied(req, PermissionDenied('Sem permissão.'))
        corpo = resp.content.decode()
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Acesso negado', corpo)
        self.assertIn(reverse('login'), corpo)
        self.assertNotIn('wtc-header__menu', corpo)      # nada de shell logado

    def test_status_403_nao_virou_200(self):
        """Paranoia de regressão: página bonita que devolve 200 quebraria
        monitoração, testes de gate e o próprio htmx."""
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.post(self.URL, {}).status_code, 403)


@override_settings(WTC_TENANT_DOMAIN='whatthechip.app',
                   ALLOWED_HOSTS=['.whatthechip.app', 'testserver'])
class RotaDeEscapeTests(TestCase):
    """O 403 de HOST (§12.6) com a rota de escape do ``/logout/``."""

    A_HOST = 'alfa.whatthechip.app'

    @classmethod
    def setUpTestData(cls):
        cls.cia_a = Company.objects.create(name='Alfa Recicla', slug='alfa')
        cls.cia_b = Company.objects.create(name='Beta Recicla', slug='beta')
        cls.user_b = User.objects.create_user('op_beta')
        Membership.objects.create(user=cls.user_b, company=cls.cia_b,
                                  role=Membership.ROLE_OPERATOR)

    # ── o cadeado: a lista hardcoded tem que bater com as URLs reais ────────
    def test_escape_bate_com_as_urls_das_duas_urlconfs(self):
        """O middleware roda ANTES da URLconf ser resolvida, então os caminhos
        são hardcoded — este teste é o que impede um rename de rota de prender
        o usuário em silêncio."""
        for urlconf in ('core.urls', 'core.urls_tenant'):
            self.assertIn(reverse('logout', urlconf=urlconf), ESCAPE_EXATAS,
                          urlconf)
            self.assertIn(reverse('set_language', urlconf=urlconf),
                          ESCAPE_EXATAS, urlconf)
            self.assertTrue(
                reverse('company_logo', kwargs={'slug': 'x'}, urlconf=urlconf)
                .startswith(ESCAPE_PREFIXOS), urlconf)

    def test_logout_funciona_no_host_da_outra_empresa(self):
        """O caso que motivou tudo: preso no subdomínio errado, o Sair sai."""
        self.client.force_login(self.user_b)
        resp = self.client.post('/logout/', HTTP_HOST=self.A_HOST)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_o_botao_sair_da_pagina_de_erro_aponta_pra_rota_liberada(self):
        """Amarra a página ao escape: o action do form renderizado no host
        errado tem que ser exatamente um caminho da lista."""
        self.client.force_login(self.user_b)
        corpo = self.client.get('/painel/', HTTP_HOST=self.A_HOST
                                ).content.decode()
        self.assertIn(f'action="{reverse("logout")}"', corpo)
        self.assertIn(reverse('logout'), ESCAPE_EXATAS)

    def test_403_de_host_nao_revela_a_empresa_dona_do_subdominio(self):
        """§10.2 — o host AFIRMA, o vínculo CONCEDE. A página mostra a empresa
        DO USUÁRIO (Beta) e nunca a do endereço (Alfa). O slug no texto do
        host não conta: veio da barra de endereço do próprio usuário."""
        self.client.force_login(self.user_b)
        resp = self.client.get('/estoque/', HTTP_HOST=self.A_HOST)
        corpo = resp.content.decode()
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('Alfa Recicla', corpo)          # nome da empresa dona
        self.assertIn('Beta Recicla', corpo)             # a do próprio usuário
        # e oferece a saída pro canônico, que aceita qualquer empresa
        self.assertIn('http://whatthechip.app/', corpo)

    def test_escape_nao_abriu_o_app(self):
        """Regressão do handshake: só rotas de SESSÃO escapam — estoque,
        painel e vendas seguem 403 no host da outra empresa."""
        self.client.force_login(self.user_b)
        for path in ('/painel/', '/estoque/', '/vendas/'):
            self.assertEqual(
                self.client.get(path, HTTP_HOST=self.A_HOST).status_code,
                403, path)

    def test_setlang_e_logo_passam(self):
        """Idioma e logo são do próprio requisitante / públicos — sem eles o
        cabeçalho da página de erro renderiza quebrado."""
        self.client.force_login(self.user_b)
        resp = self.client.post('/i18n/setlang/', {'language': 'es'},
                                HTTP_HOST=self.A_HOST)
        self.assertNotEqual(resp.status_code, 403)
        resp = self.client.get('/branding/alfa/logo', HTTP_HOST=self.A_HOST)
        self.assertEqual(resp.status_code, 404)          # sem logo, indistinto
