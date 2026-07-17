from django.contrib.auth import get_user_model
from django.test import TestCase


class TopnavSessionTests(TestCase):
    """Bug 2026-07-16 (dono): logado, a home pública seguia mostrando o botão
    'Entrar' — o shell do redesign não tinha ramo de sessão. Agora: anônimo vê
    'Entrar'; logado vê o PRÓPRIO NOME apontando pra lançadeira /painel/
    (que direciona membro ao painel e parceiro ao /partner/)."""

    def test_anonimo_ve_entrar(self):
        resp = self.client.get('/')
        self.assertContains(resp, 'Entrar')
        self.assertContains(resp, '/login/')

    def test_logado_ve_o_proprio_nome(self):
        User = get_user_model()
        u = User.objects.create_user('operador_home', password='x',
                                     first_name='Raphael')
        self.client.force_login(u)
        resp = self.client.get('/')
        self.assertContains(resp, 'Raphael')          # nome na topnav
        self.assertContains(resp, '/painel/')         # destino: lançadeira
        self.assertNotContains(resp, '>Entrar<')      # botão de login sumiu
