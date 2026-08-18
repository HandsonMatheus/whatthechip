"""
tenancy/views.py — views do app de tenancy
===========================================
1. ``company_new`` — T6, onboarding de empresa pela PLATAFORMA (§17.2/O5).
2. ``set_language`` — i18n: envolve a view nativa do Django e, se o usuário
   está LOGADO, persiste a escolha em ``UserLanguage`` (camada 1 da cadeia de
   resolução; ver I18N.md §3). Anônimo: idêntico ao Django puro (só cookie).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import http_date
from django.views.i18n import set_language as _django_set_language

from .access import platform_required
from .forms import CompanyOnboardingForm


# ── T7 (E2 — §17.3): views do modo multi-host ────────────────────────────────

def tenant_root(request):
    """`/` em host de TENANT (core/urls_tenant): não existe site público lá
    (B1) — manda pro /painel/ (que, anônimo, cai no login DO PRÓPRIO host:
    o bookmark do operador é o subdomínio da empresa dele)."""
    return redirect('painel')


def to_canonical(request, *args, **kwargs):
    """Fallback do core/urls_tenant (B1/B2): qualquer caminho que não é do APP
    (site público/CMS, /fab-*/, /partner/, /admin/, typo) redireciona 302 pro
    MESMO caminho no host canônico — nunca 404 (decisão §17.5.5: quem digitou
    errado não pode achar que o site caiu)."""
    domain = getattr(settings, 'WTC_TENANT_DOMAIN', '')
    return HttpResponseRedirect(
        f'{request.scheme}://{domain}{request.get_full_path()}')


class TenantAwareLoginView(auth_views.LoginView):
    """Login no APEX → redirect pro subdomínio do vínculo (§17.3 item 4).

    Só CONVENIÊNCIA pós-login — navegar logado no apex continua permitido
    (NÃO-OBJETIVO do §10). O salto de host só mantém a sessão por causa do
    cookie domain-wide (B5) — sem WTC_TENANT_DOMAIN nada muda aqui.

    ⚠ O Membership é resolvido AQUI (não via request.membership): o
    TenancyMiddleware rodou quando o usuário ainda era anônimo — o login
    aconteceu DENTRO desta request. Mesmo critério §14.7 (primeira ativa).
    `next` explícito continua com a validação padrão do Django (mesmo host).
    """

    def get_default_redirect_url(self):
        # SUPERUSER é PLATAFORMA: o lugar dele é o /admin/, não a bancada de
        # uma empresa (dono, 2026-08-18). Ele quase sempre TEM Membership — o
        # dono é admin da eMiner — e o salto abaixo o jogava no subdomínio
        # dela mesmo quando ele entrou pelo botão do site só para administrar.
        # Mesmo critério de plataforma do resto do sistema (`is_unmasked`,
        # máscara v3.1) e de quem o /admin/ deixa entrar: o Django admin é
        # superuser-only desde o bootstrap_tenancy.
        # ⚠ `next` explícito continua vencendo — o Django só chama este método
        # quando não há `next` válido. E no host do TENANT quem serve o login
        # é a LoginView crua (core/urls_tenant): entrar por lá segue no host,
        # de propósito.
        if self.request.user.is_superuser:
            return reverse('admin:index')
        domain = getattr(settings, 'WTC_TENANT_DOMAIN', '')
        if domain:
            host = self.request.get_host().split(':')[0].lower()
            if host == domain:                       # só a partir do APEX
                from .models import Membership
                m = (Membership.objects
                     .filter(user=self.request.user, active=True,
                             company__active=True)
                     .select_related('company')
                     .order_by('pk')
                     .first())
                if m is not None:
                    return (f'{self.request.scheme}://'
                            f'{m.company.slug}.{domain}/painel/')
        return super().get_default_redirect_url()


@platform_required
def company_new(request):
    """T6 — onboarding de empresa (PLANO_MULTITENANT §17.2, O5).

    Superfície de PLATAFORMA (gate ``platform_required``): cria, numa transação,
    a Company + a Branch opcional + o primeiro usuário com Membership ADMIN.
    A empresa nasce com ``last_lot_number=0`` → o primeiro lote dela é o #001
    (T2/T3). O slug passa pelo B3 (formato DNS + reservados) no form E no
    ``Company.save()``.

    Sem PRG de propósito: a confirmação renderiza na resposta do POST (com o
    resumo do que foi criado); um F5 re-submeteria e morre nos uniques do
    form (nada duplica). A senha provisória NÃO é reexibida — quem digitou
    foi a plataforma, segundos atrás.
    """
    created = None
    if request.method == 'POST':
        form = CompanyOnboardingForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            from .models import Branch, Company, Membership
            with transaction.atomic():
                company = Company.objects.create(
                    name=data['company_name'], slug=data['slug'])
                branch = None
                if data['branch_name']:
                    branch = Branch.objects.create(
                        company=company, name=data['branch_name'])
                user = get_user_model().objects.create_user(
                    username=data['admin_username'],
                    email=data['admin_email'] or '',
                    password=data['admin_password'])
                Membership.objects.create(
                    user=user, company=company, branch=branch,
                    role=Membership.ROLE_ADMIN)
            created = {
                'company': company,
                'branch': branch,
                'admin_username': user.username,
                'future_host': f'{company.slug}.whatthechip.app',
            }
            form = CompanyOnboardingForm()   # form zerado p/ a próxima
    else:
        form = CompanyOnboardingForm()
    return render(request, 'tenancy/company_new.html',
                  {'form': form, 'created': created})


def company_logo(request, slug):
    """Logo público da empresa (E4 — B4+B7): serve os bytes do BANCO
    (CompanyLogo) com cache de 1 dia — a troca de logo fura o cache pelo
    ``?v=`` (logo_updated_at) que o header põe na tag <img>.

    Existe nos DOIS URLconfs (core/urls e core/urls_tenant) e é ANÔNIMO de
    propósito: a tela de login do subdomínio também mostra a marca. 404
    INDISTINTO pra slug desconhecido, empresa inativa ou sem logo — mesma
    postura anti-enumeração do handshake (§17.3/§17.5.4)."""
    from .models import Company, CompanyLogo
    company = (Company.objects.filter(slug=slug, active=True)
               .exclude(logo_mime='')
               .only('id', 'logo_mime', 'logo_updated_at')
               .first())
    logo = (CompanyLogo.objects.filter(company=company).first()
            if company else None)
    if logo is None:
        raise Http404('Sem logo.')
    response = HttpResponse(bytes(logo.data), content_type=company.logo_mime)
    response['Cache-Control'] = 'public, max-age=86400'
    if company.logo_updated_at:
        response['Last-Modified'] = http_date(
            company.logo_updated_at.timestamp())
    return response


def set_language(request):
    """POST language=<código> → cookie (Django) + preferência no banco (logado)."""
    response = _django_set_language(request)

    lang = request.POST.get('language')
    user = getattr(request, 'user', None)
    if (
        request.method == 'POST'
        and lang
        and lang in {code for code, _name in settings.LANGUAGES}
        and user is not None
        and user.is_authenticated
    ):
        # Import tardio (padrão do app): não toca o registry na importação.
        from .models import UserLanguage
        UserLanguage.objects.update_or_create(
            user=user, defaults={'language': lang})

    return response
