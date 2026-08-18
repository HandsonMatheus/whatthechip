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
        Lot.all_companies.create(number=1, origin='phone', operator=self.user,
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
        Lot.all_companies.create(number=41, origin='phone', operator=self.op1,
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


class CompanySlugValidatorTests(TestCase):
    """B3 (T6/T7 — §17.2): o slug vira HOSTNAME quase-permanente na T7 —
    formato de rótulo DNS + lista de reservados, travados em código E no
    ``Company.save()`` (portão no modelo: shell/ORM também são barrados)."""

    def test_slugs_validos_passam(self):
        from .models import validate_company_slug
        for ok in ('eminer', 'erecyclo', 'a2-b3', 'x' * 63, 'a', '9dragons'):
            validate_company_slug(ok)   # não levanta

    def test_formatos_invalidos_para_hostname(self):
        from .models import validate_company_slug
        for ruim in ('Mundo_Metal', 'mundo_metal', 'ERecyclo', '-abc', 'abc-',
                     'a.b', 'a b', 'ação', 'x' * 64, ''):
            with self.assertRaises(ValidationError, msg=ruim):
                validate_company_slug(ruim)

    def test_reservados_sao_barrados(self):
        from .models import RESERVED_COMPANY_SLUGS, validate_company_slug
        # amostra + a lista inteira precisa ser DNS-válida (reservado com typo
        # de formato seria inalcançável e mascararia o motivo real do erro)
        for r in ('www', 'admin', 'api', 'partner', 'estoque', 'whatthechip'):
            self.assertIn(r, RESERVED_COMPANY_SLUGS)
            with self.assertRaises(ValidationError, msg=r):
                validate_company_slug(r)
        from .models import _DNS_LABEL_RE
        for r in RESERVED_COMPANY_SLUGS:
            self.assertTrue(_DNS_LABEL_RE.match(r),
                            f'reservado {r!r} nem é DNS label válido')

    def test_portao_no_save_barra_escrita_adhoc(self):
        with self.assertRaises(ValidationError):
            Company.objects.create(name='Ruim', slug='Mundo_Metal')
        self.assertFalse(Company.objects.filter(name='Ruim').exists())
        # e o caminho bom continua bom (os slugs REAIS da §17.5.1):
        Company.objects.create(name='eRecyclo T', slug='erecyclo')

    def test_slugs_de_producao_da_decisao_17_5_1_sao_validos(self):
        from .models import validate_company_slug
        for slug in ('eminer', 'erecyclo'):
            validate_company_slug(slug)   # decisão do dono, 2026-08-07


class CompanyOnboardingTests(TestCase):
    """T6 (§17.2, O5): a PLATAFORMA cria empresa + 1º admin em UM passo.
    Gate ``platform_required``: anônimo → login; empresa/avulso → 403."""

    URL = '/company/new/'

    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser('root_onb', password='x')
        cls.cia = Company.objects.create(name='JáExiste', slug='jaexiste')
        cls.admin_cia = User.objects.create_user('admin_cia')
        Membership.objects.create(user=cls.admin_cia, company=cls.cia,
                                  role=Membership.ROLE_ADMIN)

    def _payload(self, **extra):
        base = {'company_name': 'eRecyclo', 'slug': 'erecyclo',
                'branch_name': '', 'admin_username': 'erecyclo_admin',
                'admin_email': '', 'admin_password': 'provisoria8'}
        base.update(extra)
        return base

    def test_anonimo_redireciona_pro_login(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_nao_plataforma_403_mesmo_admin_de_empresa(self):
        self.client.force_login(self.admin_cia)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.post(
            self.URL, self._payload()).status_code, 403)

    def test_plataforma_cria_tudo_num_passo(self):
        """O5: Company ativa + contador 0 (1º lote = #001) + filial opcional +
        usuário novo + Membership ADMIN — numa transação."""
        self.client.force_login(self.root)
        resp = self.client.post(self.URL, self._payload(
            branch_name='Matriz', admin_email='adm@erecyclo.com'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'erecyclo.whatthechip.app')
        cia = Company.objects.get(slug='erecyclo')
        self.assertTrue(cia.active)
        self.assertEqual(cia.last_lot_number, 0)
        filial = Branch.objects.get(company=cia)
        self.assertEqual(filial.name, 'Matriz')
        novo = User.objects.get(username='erecyclo_admin')
        self.assertTrue(novo.check_password('provisoria8'))
        m = Membership.objects.get(user=novo)
        self.assertEqual((m.company, m.branch, m.role),
                         (cia, filial, Membership.ROLE_ADMIN))
        # e o admin recém-criado NAVEGA: middleware resolve o vínculo
        self.client.logout()
        self.client.force_login(novo)
        self.assertEqual(self.client.get('/painel/').status_code, 200)

    def test_filial_e_email_sao_opcionais(self):
        self.client.force_login(self.root)
        self.client.post(self.URL, self._payload())
        cia = Company.objects.get(slug='erecyclo')
        self.assertFalse(Branch.objects.filter(company=cia).exists())
        self.assertIsNone(Membership.objects.get(company=cia).branch)

    def test_slug_reservado_e_invalido_nao_criam_nada(self):
        self.client.force_login(self.root)
        for ruim in ('www', 'Mundo_Metal'):
            resp = self.client.post(self.URL, self._payload(slug=ruim))
            self.assertEqual(resp.status_code, 200)   # form com erro
            self.assertFalse(Company.objects.filter(name='eRecyclo').exists(),
                             ruim)

    def test_duplicatas_dao_erro_de_form_sem_criar(self):
        self.client.force_login(self.root)
        casos = (self._payload(slug='jaexiste'),               # slug em uso
                 self._payload(company_name='JáExiste'),       # nome em uso
                 self._payload(admin_username='admin_cia'))    # usuário em uso
        for payload in casos:
            resp = self.client.post(self.URL, payload)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(Company.objects.filter(slug='erecyclo').exists())

    def test_senha_curta_barra(self):
        self.client.force_login(self.root)
        resp = self.client.post(self.URL, self._payload(admin_password='curta'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='erecyclo_admin').exists())


from django.test import override_settings  # noqa: E402 — usado só no bloco T7


@override_settings(WTC_TENANT_DOMAIN='whatthechip.app',
                   ALLOWED_HOSTS=['.whatthechip.app', 'testserver'])
class HostHandshakeTests(TestCase):
    """T7/E2 — o handshake de HOST do §12.6 (teste permanente da suíte).

    Prova que o host é AFIRMAÇÃO e não CONCESSÃO (§10.2): sessão da empresa B
    no host da empresa A = 403 — nunca 200 com dados de A, nunca "troca de
    empresa". Host desconhecido/reservado/inativo cai no canônico sem revelar
    qual caso é; www → 301 (B6); tenant serve SÓ o app (B1/B2); login no apex
    segue LOGADO no subdomínio (B5); e o middleware é INERTE sem a env var.
    No Django o Client fala com `testserver` — os casos usam HTTP_HOST= +
    override_settings(ALLOWED_HOSTS), como o §12.6 manda.
    """

    A_HOST = 'eminer.whatthechip.app'
    B_HOST = 'erecyclo.whatthechip.app'

    @classmethod
    def setUpTestData(cls):
        cls.cia_a = Company.objects.create(name='eMiner H', slug='eminer')
        cls.cia_b = Company.objects.create(name='eRecyclo H', slug='erecyclo')
        cls.cia_off = Company.objects.create(name='Desativada H',
                                             slug='desativada', active=False)
        cls.user_a = User.objects.create_user('op_a', password='x12345678')
        Membership.objects.create(user=cls.user_a, company=cls.cia_a,
                                  role=Membership.ROLE_OPERATOR)
        cls.user_b = User.objects.create_user('op_b')
        Membership.objects.create(user=cls.user_b, company=cls.cia_b,
                                  role=Membership.ROLE_OPERATOR)
        cls.root = User.objects.create_superuser('root_host', password='x')
        Membership.objects.create(user=cls.root, company=cls.cia_a,
                                  role=Membership.ROLE_ADMIN)

    # ── canônico intacto + feature desligada ────────────────────────────────
    def test_canonico_e_testserver_seguem_como_hoje(self):
        self.assertEqual(self.client.get('/login/').status_code, 200)
        self.assertEqual(self.client.get(
            '/login/', HTTP_HOST='whatthechip.app').status_code, 200)

    @override_settings(WTC_TENANT_DOMAIN='')
    def test_sem_env_var_o_middleware_e_inerte(self):
        # sem a env var nem host de tenant é tratado (cai no DisallowedHost do
        # Django por não estar no ALLOWED_HOSTS — aqui só provamos o no-op
        # num host permitido)
        self.assertEqual(self.client.get(
            '/login/', HTTP_HOST='testserver').status_code, 200)

    # ── www e hosts que caem no canônico (indistintos) ──────────────────────
    def test_www_301_preservando_caminho(self):
        resp = self.client.get('/fabricantes/?x=1',
                               HTTP_HOST='www.whatthechip.app')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'],
                         'http://whatthechip.app/fabricantes/?x=1')

    def test_desconhecido_reservado_inativo_subsub_vao_pro_canonico(self):
        for host in ('naoexiste.whatthechip.app', 'api.whatthechip.app',
                     'desativada.whatthechip.app', 'a.b.whatthechip.app'):
            resp = self.client.get('/painel/', HTTP_HOST=host)
            self.assertEqual(resp.status_code, 302, host)
            self.assertEqual(resp['Location'],
                             'http://whatthechip.app/painel/', host)

    # ── o handshake em si (§12.6) ───────────────────────────────────────────
    def test_membro_no_proprio_host_entra(self):
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(
            '/painel/', HTTP_HOST=self.A_HOST).status_code, 200)

    def test_sessao_de_b_no_host_de_a_leva_403(self):
        """O caso central: host AFIRMA A, vínculo CONCEDE só B → 403 nas duas
        superfícies — e nunca 200 (nem com dados de A, nem 'trocando' pra B)."""
        self.client.force_login(self.user_b)
        for path in ('/painel/', '/estoque/'):
            resp = self.client.get(path, HTTP_HOST=self.A_HOST)
            self.assertEqual(resp.status_code, 403, path)

    def test_avulso_logado_em_host_de_tenant_leva_403(self):
        avulso = User.objects.create_user('sem_vinculo_host')
        self.client.force_login(avulso)
        self.assertEqual(self.client.get(
            '/painel/', HTTP_HOST=self.A_HOST).status_code, 403)

    def test_anonimo_em_host_de_tenant_cai_no_login_do_host(self):
        resp = self.client.get('/painel/', HTTP_HOST=self.A_HOST)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith('/login/'))  # relativo: fica no host

    def test_superuser_passa_em_host_de_cliente_sem_trocar_escopo(self):
        """§17.5.3: plataforma passa (espelha app.platform) — e o ESCOPO segue
        o do vínculo dele (eMiner), nunca o host: request.company não muda."""
        self.client.force_login(self.root)
        resp = self.client.get('/painel/', HTTP_HOST=self.B_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.wsgi_request.company, self.cia_a)      # vínculo
        self.assertEqual(resp.wsgi_request.tenant_host_company,
                         self.cia_b)                                  # afirmação

    def test_host_nunca_e_fonte_de_escopo(self):
        """A prova §12.6 'nenhuma view lê a empresa do hostname': membro de A
        no host de A tem escopo vindo do MEMBERSHIP (mesmo objeto), e o
        middleware nunca gravou request.company a partir do host."""
        self.client.force_login(self.user_a)
        resp = self.client.get('/painel/', HTTP_HOST=self.A_HOST)
        self.assertEqual(resp.wsgi_request.company, self.cia_a)
        self.assertEqual(resp.wsgi_request.company,
                         resp.wsgi_request.membership.company)

    # ── B1/B2: tenant serve só o app ────────────────────────────────────────
    def test_tenant_raiz_vai_pro_painel_e_cms_vai_pro_canonico(self):
        self.client.force_login(self.user_a)
        raiz = self.client.get('/', HTTP_HOST=self.A_HOST)
        self.assertEqual(raiz.status_code, 302)
        self.assertEqual(raiz['Location'], '/painel/')
        for path in ('/fabricantes/', '/fab-samsung/', '/partner/', '/admin/',
                     '/company/new/'):
            resp = self.client.get(path, HTTP_HOST=self.A_HOST)
            self.assertEqual(resp.status_code, 302, path)
            self.assertEqual(resp['Location'],
                             f'http://whatthechip.app{path}', path)

    # ── B5 + item 4: login no apex → segue LOGADO no subdomínio ────────────
    def test_login_no_apex_redireciona_pro_subdominio_logado(self):
        resp = self.client.post(
            '/login/', {'username': 'op_a', 'password': 'x12345678'},
            HTTP_HOST='whatthechip.app')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'],
                         'http://eminer.whatthechip.app/painel/')
        # o test client carrega o cookie entre hosts; no navegador é o
        # SESSION_COOKIE_DOMAIN='.whatthechip.app' (B5, settings) que garante
        seg = self.client.get('/painel/', HTTP_HOST=self.A_HOST)
        self.assertEqual(seg.status_code, 200)

    def test_superuser_no_apex_vai_pro_admin(self):
        """Dono, 2026-08-18: superuser entrando pelo botão do site vai pro
        /admin/, não pro subdomínio da empresa em que ele tem vínculo.

        `cls.root` é exatamente o caso dele: superuser E admin da eMiner. O
        salto do apex o levava pra bancada da eMiner mesmo quando ele só
        queria administrar."""
        resp = self.client.post('/login/',
                                {'username': 'root_host', 'password': 'x'},
                                HTTP_HOST='whatthechip.app')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/admin/')     # e NÃO o subdomínio

    def test_superuser_com_next_explicito_respeita_o_next(self):
        """O atalho é só o DEFAULT: quem chega numa página protegida e é
        mandado ao login volta pra ela, superuser ou não."""
        resp = self.client.post('/login/?next=/painel/',
                                {'username': 'root_host', 'password': 'x'},
                                HTTP_HOST='whatthechip.app')
        self.assertEqual(resp['Location'], '/painel/')

    def test_nao_superuser_continua_indo_pro_subdominio(self):
        """O salto do apex (B5/item 4) segue valendo para quem trabalha numa
        empresa — só a PLATAFORMA foi desviada."""
        resp = self.client.post('/login/',
                                {'username': 'op_a', 'password': 'x12345678'},
                                HTTP_HOST='whatthechip.app')
        self.assertEqual(resp['Location'],
                         'http://eminer.whatthechip.app/painel/')

    def test_login_no_host_do_tenant_fica_no_host(self):
        resp = self.client.post(
            '/login/', {'username': 'op_a', 'password': 'x12345678'},
            HTTP_HOST=self.A_HOST)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/painel/')   # relativo → mesmo host


# ── E4 (B4+B7): logo por empresa no BANCO ────────────────────────────────────

def _instala_logo(company):
    """Helper E4: instala um PNG 2×2 como logo da empresa — blob em
    CompanyLogo + metadados (mime/updated_at) na Company. Devolve os bytes."""
    from io import BytesIO

    from django.utils import timezone
    from PIL import Image

    from .models import CompanyLogo

    buf = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(buf, format='PNG')
    raw = buf.getvalue()
    CompanyLogo.objects.update_or_create(company=company,
                                         defaults={'data': raw})
    company.logo_mime = 'image/png'
    company.logo_updated_at = timezone.now()
    company.save(update_fields=['logo_mime', 'logo_updated_at'])
    return raw


class CompanyLogoTests(TestCase):
    """E4: a view pública serve o blob do banco com cache e 404 INDISTINTO
    (desconhecida/inativa/sem logo — anti-enumeração, como o handshake);
    o admin valida com Pillow (formato REAL) e grava blob+metadados juntos."""

    @classmethod
    def setUpTestData(cls):
        cls.cia = Company.objects.create(name='eMiner Logo', slug='eminerlogo')
        cls.cia_off = Company.objects.create(
            name='Inativa Logo', slug='inativalogo', active=False)

    # ── a view pública ──────────────────────────────────────────────────────
    def test_view_serve_bytes_com_cache_anonimo(self):
        raw = _instala_logo(self.cia)
        resp = self.client.get(reverse('company_logo',
                                       kwargs={'slug': 'eminerlogo'}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertEqual(resp.content, raw)
        self.assertIn('max-age=86400', resp['Cache-Control'])
        self.assertTrue(resp.has_header('Last-Modified'))

    def test_view_404_indistinto(self):
        _instala_logo(self.cia_off)   # inativa COM logo → 404 igual aos outros
        for slug in ('naoexiste', 'eminerlogo', 'inativalogo'):
            resp = self.client.get(f'/branding/{slug}/logo')
            self.assertEqual(resp.status_code, 404, slug)

    # ── admin: form valida, save_model grava/limpa ──────────────────────────
    def _form(self, company, files=None, extra=None):
        from tenancy.admin import CompanyAdminForm
        data = {'name': company.name, 'slug': company.slug,
                'last_lot_number': company.last_lot_number,
                'notes': company.notes}
        if company.active:
            data['active'] = 'on'
        if extra:
            data.update(extra)
        return CompanyAdminForm(data=data, files=files or {}, instance=company)

    def _save_model(self, obj, form):
        from django.contrib import admin as dj_admin

        from tenancy.admin import CompanyAdmin
        CompanyAdmin(Company, dj_admin.site).save_model(None, obj, form, True)

    def test_admin_upload_grava_blob_e_metadados(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from .models import CompanyLogo
        buf = BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(buf, format='PNG')
        raw = buf.getvalue()
        form = self._form(self.cia, files={
            'logo_upload': SimpleUploadedFile('logo.png', raw, 'image/png')})
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        self._save_model(obj, form)
        obj.refresh_from_db()
        self.assertEqual(obj.logo_mime, 'image/png')
        self.assertIsNotNone(obj.logo_updated_at)
        self.assertEqual(bytes(CompanyLogo.objects.get(pk=obj.pk).data), raw)

    def test_admin_clear_remove_blob_e_metadados(self):
        from .models import CompanyLogo
        _instala_logo(self.cia)
        form = self._form(self.cia, extra={'logo_clear': 'on'})
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        self._save_model(obj, form)
        obj.refresh_from_db()
        self.assertEqual(obj.logo_mime, '')
        self.assertIsNone(obj.logo_updated_at)
        self.assertFalse(CompanyLogo.objects.filter(pk=obj.pk).exists())

    def test_admin_form_rejeita_nao_imagem_e_gigante(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        # SVG/qualquer não-imagem: o Pillow do ImageField barra (sem SVG
        # servido inline = sem vetor de XSS por SVG)
        falso = SimpleUploadedFile('logo.svg', b'<svg></svg>', 'image/svg+xml')
        self.assertFalse(self._form(
            self.cia, files={'logo_upload': falso}).is_valid())
        # imagem válida porém > 1 MB: barra no clean_logo_upload
        raw = _instala_logo(self.cia)   # só pra reusar os bytes de PNG
        gigante = SimpleUploadedFile(
            'logo.png', raw + b'\0' * (1024 * 1024), 'image/png')
        self.assertFalse(self._form(
            self.cia, files={'logo_upload': gigante}).is_valid())


@override_settings(WTC_TENANT_DOMAIN='whatthechip.app',
                   ALLOWED_HOSTS=['.whatthechip.app', 'testserver'])
class HeaderLogoTests(TestCase):
    """E4 no shell: com logo → <img> apontando pra company_logo (com ?v= de
    cache-buster) nos DOIS mundos; sem logo → iniciais (nada de /branding/)."""

    @classmethod
    def setUpTestData(cls):
        cls.cia = Company.objects.create(name='eMiner Hdr', slug='eminerhdr')
        cls.user = User.objects.create_user('op_hdr')
        Membership.objects.create(user=cls.user, company=cls.cia,
                                  role=Membership.ROLE_OPERATOR)

    def test_header_sem_logo_mostra_iniciais_e_nao_aponta_pra_view(self):
        self.client.force_login(self.user)
        resp = self.client.get('/painel/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, '/branding/eminerhdr/logo')

    def test_header_com_logo_aponta_pra_view_nos_dois_mundos(self):
        _instala_logo(self.cia)
        self.client.force_login(self.user)
        resp = self.client.get('/painel/')                       # canônico
        self.assertContains(resp, '/branding/eminerhdr/logo?v=')
        resp = self.client.get('/painel/',                       # host tenant
                               HTTP_HOST='eminerhdr.whatthechip.app')
        self.assertContains(resp, '/branding/eminerhdr/logo?v=')
        img = self.client.get('/branding/eminerhdr/logo',        # serve local
                              HTTP_HOST='eminerhdr.whatthechip.app')
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img['Content-Type'], 'image/png')


# ── E5 (§17.7): canary de frontend por empresa ───────────────────────────────

class UiV2CanaryTests(TestCase):
    """E5: o flag por empresa decide v2×atual SEM deploy. Prova o helper
    (unidade), o fallback (flag ON sem arquivo v2 → tela atual, nunca 500) e
    a troca real (arquivo v2 presente → v2 servida SÓ pra empresa com flag)."""

    @classmethod
    def setUpTestData(cls):
        cls.cia = Company.objects.create(name='Canary SA', slug='canary')
        cls.user = User.objects.create_user('op_canary')
        Membership.objects.create(user=cls.user, company=cls.cia,
                                  role=Membership.ROLE_OPERATOR)
        cls.cia_v1 = Company.objects.create(name='Segue V1 SA', slug='seguev1')
        cls.user_v1 = User.objects.create_user('op_seguev1')
        Membership.objects.create(user=cls.user_v1, company=cls.cia_v1,
                                  role=Membership.ROLE_OPERATOR)

    # ── unidade: o helper ───────────────────────────────────────────────────
    def test_helper_flag_off_devolve_o_nome_puro(self):
        from tenancy.ui import ui

        class R:
            company = self.cia
        self.assertEqual(ui(R(), 'estoque/painel.html'),
                         'estoque/painel.html')

    def test_helper_flag_on_devolve_lista_v2_primeiro(self):
        from tenancy.ui import ui, v2_name
        self.cia.ui_v2 = True

        class R:
            company = self.cia
        self.assertEqual(ui(R(), 'estoque/painel.html'),
                         ['estoque/v2/painel.html', 'estoque/painel.html'])
        self.assertEqual(v2_name('estoque/partials/confirm_card.html'),
                         'estoque/v2/partials/confirm_card.html')
        self.assertEqual(v2_name('base.html'), 'v2/base.html')

    def test_helper_anonimo_segue_o_host_e_sem_empresa_e_atual(self):
        from tenancy.ui import ui
        self.cia.ui_v2 = True

        class Anon:                       # anônimo em host de tenant flagado
            company = None
            tenant_host_company = self.cia
        self.assertIsInstance(ui(Anon(), 'estoque/painel.html'), list)

        class Nada:                       # anônimo no canônico
            pass
        self.assertEqual(ui(Nada(), 'estoque/painel.html'),
                         'estoque/painel.html')

    # ── integração: fallback e troca real ───────────────────────────────────
    def test_flag_on_sem_arquivo_v2_cai_na_tela_atual(self):
        self.cia.ui_v2 = True
        self.cia.save(update_fields=['ui_v2'])
        self.client.force_login(self.user)
        resp = self.client.get('/painel/')
        self.assertEqual(resp.status_code, 200)   # nunca 500 por template

    def test_arquivo_v2_presente_so_vale_pra_empresa_com_flag(self):
        import copy
        import os
        import shutil
        import tempfile

        from django.conf import settings as dj_settings

        tmp = tempfile.mkdtemp(prefix='wtc_v2_')
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, 'estoque', 'v2'))
        with open(os.path.join(tmp, 'estoque', 'v2', 'painel.html'),
                  'w', encoding='utf-8') as f:
            f.write('<main>V2MARKER-painel</main>')
        templates = copy.deepcopy(dj_settings.TEMPLATES)
        templates[0]['DIRS'] = ([tmp] +
                                [str(d) for d in templates[0]['DIRS']])
        self.cia.ui_v2 = True
        self.cia.save(update_fields=['ui_v2'])
        with override_settings(TEMPLATES=templates):
            self.client.force_login(self.user)          # empresa flagada
            self.assertContains(self.client.get('/painel/'),
                                'V2MARKER-painel')
            self.client.force_login(self.user_v1)       # empresa SEM flag
            resp = self.client.get('/painel/')
            self.assertEqual(resp.status_code, 200)
            self.assertNotContains(resp, 'V2MARKER-painel')


class CodigoDeDocumentoTests(TestCase):
    """`Company.code` no identificador (dono, 2026-08-18).

    A numeração é POR EMPRESA — "o lote 41 continua sendo o 41" — então o
    código COLIDIA entre clientes: o comprador, que lê ordens de várias
    empresas, via dois `LOT/001/08/26` na lista dele.

    ⚠ Código de PAÍS foi recusado de propósito: duas recicladoras do mesmo
    país voltariam a colidir, e esse é o caminho de crescimento. País é
    metadado de embarque — já viaja no endereço do SHIP FROM.

    E o formato novo vale só para documento NOVO: papel já impresso não pode
    divergir da tela.
    """

    def setUp(self):
        self.emi = Company.objects.create(name='eMiner cod', slug='eminer-cod',
                                          code='EMI')
        self.erc = Company.objects.create(name='eRecyclo cod',
                                          slug='erecyclo-cod', code='ERC')
        self.user = User.objects.create_user('cod_op')

    def _lote(self, comp):
        from estoque.models import Lot
        with company_scope(comp):
            return Lot.open_for_company(comp, self.user, 'x', origin='phone')

    def test_mesmo_numero_em_empresas_diferentes_nao_colide_mais(self):
        a, b = self._lote(self.emi), self._lote(self.erc)
        self.assertEqual(a.number, b.number)          # a numeração é por empresa
        self.assertTrue(a.code.startswith('LOT/EMI/001/'))
        self.assertTrue(b.code.startswith('LOT/ERC/001/'))
        self.assertNotEqual(a.code, b.code)           # o que motivou a mudança

    def test_documento_antigo_fica_no_formato_antigo(self):
        """`code_str` vazio = documento anterior à mudança. O papel que já
        circulou continua batendo com a tela."""
        from estoque.models import Lot
        lot = self._lote(self.emi)
        Lot.all_companies.filter(pk=lot.pk).update(code_str='')   # simula legado
        lot.refresh_from_db()
        self.assertTrue(lot.code.startswith('LOT/001/'))
        self.assertNotIn('EMI', lot.code)

    def test_renomear_o_codigo_da_empresa_nao_reescreve_o_passado(self):
        """O identificador é IMUTÁVEL depois de emitido — é assim que número
        de documento tem que se comportar."""
        lot = self._lote(self.emi)
        antes = lot.code
        self.emi.code = 'EMN'
        self.emi.save()
        lot.refresh_from_db()
        self.assertEqual(lot.code, antes)
        self.assertTrue(self._lote(self.emi).code.startswith('LOT/EMN/'))

    def test_empresa_sem_codigo_sai_no_formato_antigo(self):
        sem = Company.objects.create(name='Sem cod', slug='sem-cod')
        self.assertEqual(sem.code, '')
        self.assertTrue(self._lote(sem).code.startswith('LOT/001/'))

    def test_codigo_e_normalizado_e_validado(self):
        from django.core.exceptions import ValidationError
        c = Company.objects.create(name='Min cod', slug='min-cod', code=' zzz ')
        self.assertEqual(c.code, 'ZZZ')               # trim + maiúscula
        # Só LETRAS de propósito: o código é DIGITADO (type-to-confirm do
        # fechamento) e impresso — dígito convida a confundir 0/O e 1/I.
        for ruim in ('E', 'ABCDE', 'E-M', 'EM1', 'EMÍ'):
            with self.assertRaises(ValidationError, msg=ruim):
                Company.objects.create(name=f'R {ruim}', slug=f'r-{ruim.lower()}',
                                       code=ruim)

    def test_codigo_e_unico_entre_empresas(self):
        """…mas vazio se repete: é o legado, e há N empresas sem código."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Company.objects.create(name='Clone', slug='clone-cod', code='EMI')

    def test_ov_e_fatura_carregam_o_mesmo_prefixo(self):
        """Colidiam pelo mesmo motivo do lote — a numeração é por empresa."""
        from vendas.models import DocSequence, SEQ_SO, SalesOrder
        lot = self._lote(self.emi)
        from pricing.models import Buyer
        with company_scope(self.emi):
            comprador = Buyer.all_companies.create(company=self.emi, name='B',
                                                   slug='b-cod')
            so = SalesOrder(lot=lot, buyer=comprador,
                            number=DocSequence.next_number(self.emi, SEQ_SO))
            so.save()
        self.assertTrue(so.code.startswith('SO/EMI/001/'))
