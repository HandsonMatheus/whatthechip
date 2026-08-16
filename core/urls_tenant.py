"""
core/urls_tenant.py — URLconf dos hosts de TENANT (T7/E2 — PLANO_MULTITENANT §17.3)
====================================================================================
Ativada por request pelo ``HostTenantMiddleware`` (``request.urlconf``) quando o
host é ``<slug>.WTC_TENANT_DOMAIN`` de empresa ativa. Serve SÓ o APP (B1/B2):

  - bancada/estoque, vendas, painel, login/logout do próprio host, i18n e os
    endpoints internos de chips (preview/submit/report — os de consulta já são
    plataforma-only por conta própria);
  - site público/CMS (``/``, ``/<slug>/``, ``/fab-*/``), ``/partner/`` e o
    ``/admin/`` NÃO existem aqui — o fallback final redireciona 302 pro mesmo
    caminho no host canônico (nunca 404 — decisão §17.5.5).

Os NOMES de URL espelham o core/urls.py (levantamento 2026-08-07: os templates
do shell resolvem estoque:*, vendas:*, chips:*, painel, login, logout,
set_language, javascript-catalog e home) — reverse() usa a URLconf da request,
então os templates funcionam idênticos nos dois mundos.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog

from estoque import views as estoque_views
from tenancy import views as tenancy_views

urlpatterns = [
    path('chips/', include('chips.urls', namespace='chips')),
    path('estoque/', include('estoque.urls', namespace='estoque')),
    path('painel/', estoque_views.painel, name='painel'),
    # Login/logout DO host do tenant (o bookmark do operador é o subdomínio;
    # o pós-login padrão /painel/ é relativo → fica no host).
    path('login/',  auth_views.LoginView.as_view(),  name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('vendas/', include('vendas.urls', namespace='vendas')),
    path('i18n/setlang/', tenancy_views.set_language, name='set_language'),
    path('i18n/js/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    # Logo por empresa (E4): mesmo nome/rota do core/urls — o <img> do header
    # e o da tela de login do subdomínio servem direto daqui, sem pular de host.
    path('branding/<slug:slug>/logo', tenancy_views.company_logo,
         name='company_logo'),
    # `/` de tenant → painel (nome 'home' MANTIDO: {% url 'home' %} do shell e
    # o LOGOUT_REDIRECT_URL='/' resolvem aqui também).
    path('', tenancy_views.tenant_root, name='home'),
    # B1/B2 — resto do mundo → canônico (302, nunca 404).
    re_path(r'^.*$', tenancy_views.to_canonical),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
