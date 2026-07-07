"""
Testes da fundação multi-empresa (PLANO_MULTITENANT.md, T1).

Rodar com o settings de teste (SQLite em memória):

    python manage.py test tenancy --settings=core.settings_test

Blocos:
  - ScopeTests: o contextvar fail-closed (tenancy/scope.py) — a Camada A nasce
    aqui; os managers escopados entram nos modelos do estoque na T3.
  - MembershipModelTests: hierarquia de papel + portão filial×empresa.
  - MiddlewareTests: resolução do vínculo → request.company/role + limpeza do
    escopo no fim da request (worker reciclado não herda empresa).
  - LoginRedirectTests: pós-login → /estoque/ (papéis mudam a navegação, não a rota).
  - ScopeAnnotationTests: SearchLog/UnknownChip GLOBAIS anotam a empresa (§14.1).
  - BootstrapTenancyTests: o comando de backfill da T1 (dry-run/--commit).

A matriz papel×view (O1) vive em estoque/tests.py::RoleMatrixTests, junto das
views que ela prova.
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from chips.engine import _log_search, _log_unknown
from chips.models import SearchLog, UnknownChip
from estoque.models import Lot

from .models import Branch, Company, Membership
from .scope import (CompanyScopedManager, CompanyScopeMissing, company_scope,
                    current_company_id, require_company_id)

User = get_user_model()


class ScopeTests(TestCase):
    """Camada A (§6.1): fail-closed — sem escopo é ERRO, nunca 'todas'."""

    def test_sem_escopo_default_none(self):
        self.assertIsNone(current_company_id())

    def test_require_sem_escopo_explode(self):
        with self.assertRaises(CompanyScopeMissing):
            require_company_id()

    def test_company_scope_seta_e_restaura(self):
        with company_scope(42):
            self.assertEqual(current_company_id(), 42)
            self.assertEqual(require_company_id(), 42)
        self.assertIsNone(current_company_id())

    def test_company_scope_aninhado_restaura_o_anterior(self):
        with company_scope(1):
            with company_scope(2):
                self.assertEqual(current_company_id(), 2)
            self.assertEqual(current_company_id(), 1)

    def test_company_scope_aceita_objeto_company(self):
        c = Company.objects.create(name='Acme', slug='acme')
        with company_scope(c):
            self.assertEqual(current_company_id(), c.pk)

    def test_manager_escopado_fail_closed_e_filtra(self):
        """O CompanyScopedManager (adoção real na T3) já se prova aqui usando o
        Membership como cobaia (tem company FK): sem escopo → explode; com
        escopo → SÓ as linhas da empresa corrente."""
        a = Company.objects.create(name='A', slug='a')
        b = Company.objects.create(name='B', slug='b')
        ua = User.objects.create_user('scope_ua')
        ub = User.objects.create_user('scope_ub')
        Membership.objects.create(user=ua, company=a)
        Membership.objects.create(user=ub, company=b)

        mgr = CompanyScopedManager()
        mgr.model = Membership          # bind manual (em T3 vira `objects`)

        with self.assertRaises(CompanyScopeMissing):
            mgr.get_queryset()          # FAIL-CLOSED: explode antes de qualquer SQL

        with company_scope(a):
            qs = list(mgr.get_queryset())
            self.assertEqual([m.company_id for m in qs], [a.pk])
        with company_scope(b):
            self.assertEqual(mgr.get_queryset().count(), 1)


class MembershipModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Acme', slug='acme')
        self.user = User.objects.create_user('roleuser')

    def test_hierarquia_de_papel(self):
        m = Membership(user=self.user, company=self.company,
                       role=Membership.ROLE_MANAGER)
        self.assertTrue(m.has_role('operator'))
        self.assertTrue(m.has_role('manager'))
        self.assertFalse(m.has_role('admin'))
        with self.assertRaises(ValueError):
            m.has_role('ceo')

    def test_filial_de_outra_empresa_barrada_no_save(self):
        outra = Company.objects.create(name='Outra', slug='outra')
        branch_outra = Branch.objects.create(company=outra, name='Matriz')
        with self.assertRaises(ValidationError):
            Membership.objects.create(user=self.user, company=self.company,
                                      branch=branch_outra)

    def test_um_vinculo_por_usuario_empresa(self):
        Membership.objects.create(user=self.user, company=self.company)
        from django.db import IntegrityError, transaction
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Membership.objects.create(user=self.user, company=self.company,
                                          role=Membership.ROLE_ADMIN)


class MiddlewareTests(TestCase):
    """O TenancyMiddleware publica request.company/role e LIMPA o escopo no
    finally (senão worker reciclado herdaria a empresa da request anterior)."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme', slug='acme')
        self.user = User.objects.create_user('mwuser', password='x')
        Membership.objects.create(user=self.user, company=self.company,
                                  role=Membership.ROLE_MANAGER)
        # T3: all_companies — setUp roda fora de request (sem escopo ambiente).
        Lot.all_companies.create(number=1, operator=self.user,
                                 company=self.company)

    def test_publica_company_e_role_no_contexto(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('estoque:index'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['wtc_role'], 'manager')
        self.assertEqual(resp.context['wtc_company'], self.company)
        self.assertTrue(resp.context['wtc_is_manager'])
        self.assertFalse(resp.context['wtc_is_admin'])

    def test_escopo_limpo_apos_a_request(self):
        self.client.force_login(self.user)
        self.client.get(reverse('estoque:index'))
        self.assertIsNone(current_company_id())   # reset no finally

    def test_anonimo_sem_vinculo(self):
        resp = self.client.get('/login/')
        self.assertIsNone(resp.wsgi_request.membership)
        self.assertIsNone(resp.wsgi_request.company)

    def test_vinculo_inativo_ou_empresa_inativa_nao_conta(self):
        Membership.objects.filter(user=self.user).update(active=False)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('estoque:index')).status_code, 403)

        Membership.objects.filter(user=self.user).update(active=True)
        Company.objects.filter(pk=self.company.pk).update(active=False)
        self.assertEqual(self.client.get(reverse('estoque:index')).status_code, 403)

    def test_multi_empresa_usa_a_primeira_ativa(self):
        """§14.7 (v1): consultor em 2+ empresas → primeira ativa (pk); o
        seletor de empresa fica para depois."""
        c2 = Company.objects.create(name='Beta', slug='beta')
        Membership.objects.create(user=self.user, company=c2,
                                  role=Membership.ROLE_OPERATOR)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('estoque:index'))
        self.assertEqual(resp.context['wtc_company'], self.company)  # a 1ª


class LoginRedirectTests(TestCase):
    def test_pos_login_vai_para_o_painel(self):
        """Pós-login → /painel/ (lançadeira, UX 2026-07-06); o trabalho segue
        em /estoque/ a 1 clique."""
        user = User.objects.create_user('login1', password='x')
        Company.objects.create(name='Acme', slug='acme')
        resp = self.client.post('/login/', {'username': 'login1', 'password': 'x'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/painel/')


class ScopeAnnotationTests(TestCase):
    """§14.1: SearchLog/UnknownChip continuam GLOBAIS (sem manager escopado,
    sem RLS) e ANOTAM a empresa quando o escopo existe."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme', slug='acme')

    def test_searchlog_anota_empresa_no_escopo(self):
        with company_scope(self.company):
            _log_search('PNTESTE1', found=False, source_used='not_found')
        log = SearchLog.objects.get(part_number='PNTESTE1')
        self.assertEqual(log.company_id, self.company.pk)

    def test_searchlog_sem_escopo_fica_null(self):
        _log_search('PNTESTE2', found=True, source_used='grammar')
        self.assertIsNone(SearchLog.objects.get(part_number='PNTESTE2').company_id)

    def test_unknown_anota_primeira_empresa_e_dedup_global(self):
        with company_scope(self.company):
            _log_unknown('PNDESC1')
        outra = Company.objects.create(name='Beta', slug='beta')
        with company_scope(outra):
            _log_unknown('PNDESC1')     # dedup global: NÃO cria segunda linha
        rows = UnknownChip.objects.filter(part_number='PNDESC1')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().company_id, self.company.pk)  # 1ª a reportar


class BootstrapTenancyTests(TestCase):
    """bootstrap_tenancy: o backfill da T1 (dry-run por padrão; --commit grava)."""

    def setUp(self):
        self.dono = User.objects.create_superuser('dono', password='x')
        self.chefe = User.objects.create_user('chefe', password='x', is_staff=True)
        self.op1 = User.objects.create_user('op1', password='x')

    def _run(self, *extra):
        call_command('bootstrap_tenancy', '--company', 'eMiner',
                     '--admin', 'dono', '--manager', 'chefe',
                     '--operator', 'op1', *extra)

    def test_dry_run_nao_grava_nada(self):
        self._run()                                     # sem --commit
        self.assertFalse(Company.objects.exists())
        self.assertFalse(Membership.objects.exists())
        self.chefe.refresh_from_db()
        self.assertTrue(self.chefe.is_staff)            # intacto no dry-run

    def test_commit_cria_empresa_papeis_e_restringe_admin(self):
        # T3: o lote precisa de empresa — pré-cria a eMiner (o comando então
        # acha "já existia" e só completa papéis/contador; mesmo nome/slug).
        eminer = Company.objects.create(name='eMiner', slug='eminer')
        Lot.all_companies.create(number=41, operator=self.op1,
                                 company=eminer)           # seed do contador
        self.client.login(username='op1', password='x')    # cria uma sessão
        self.assertTrue(Session.objects.exists())

        self._run('--commit')

        company = Company.objects.get(name='eMiner')
        self.assertEqual(company.slug, 'eminer')
        self.assertEqual(company.last_lot_number, 41)      # herdou a sequência (T2)
        roles = {m.user.username: m.role
                 for m in Membership.objects.filter(company=company)}
        self.assertEqual(roles, {'dono': 'admin', 'chefe': 'manager',
                                 'op1': 'operator'})
        self.chefe.refresh_from_db()
        self.assertFalse(self.chefe.is_staff)              # admin só-plataforma
        self.dono.refresh_from_db()
        self.assertTrue(self.dono.is_staff)                # superuser mantém
        self.assertFalse(Session.objects.exists())         # todos relogam

    def test_commit_e_idempotente_e_atualiza_papel(self):
        self._run('--commit')
        call_command('bootstrap_tenancy', '--company', 'eMiner',
                     '--admin', 'dono', '--manager', 'op1',   # op1 promovido
                     '--commit')
        self.assertEqual(Company.objects.count(), 1)
        m = Membership.objects.get(user=self.op1)
        self.assertEqual(m.role, Membership.ROLE_MANAGER)

    def test_usuario_inexistente_erra_antes_de_gravar(self):
        with self.assertRaises(CommandError):
            call_command('bootstrap_tenancy', '--company', 'eMiner',
                         '--admin', 'fantasma', '--commit')
        self.assertFalse(Company.objects.exists())

    def test_usuario_em_dois_papeis_erra(self):
        with self.assertRaises(CommandError):
            call_command('bootstrap_tenancy', '--company', 'eMiner',
                         '--admin', 'dono', '--operator', 'dono', '--commit')
