from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import JavaScriptCatalog
from estoque import views as estoque_views
from pages import views
from tenancy import views as tenancy_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chips/', include('chips.urls', namespace='chips')),
    path('estoque/', include('estoque.urls', namespace='estoque')),
    # Home pós-login (lançadeira): orienta e leva ao lote aberto em 1 clique.
    path('painel/', estoque_views.painel, name='painel'),
    # Auth (login/logout — sem cadastro público). T7/E2: o login do CANÔNICO
    # redireciona pro subdomínio do vínculo pós-login (só conveniência —
    # NÃO-OBJETIVO §10 preservado; inerte sem WTC_TENANT_DOMAIN).
    path('login/',  tenancy_views.TenantAwareLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Dashboard do COMPRADOR (F6 — PRECIFICACAO §7.1): rota em inglês, conta
    # externa via Buyer.users (a lançadeira /painel/ redireciona parceiro p/ cá).
    # F11.6: as COMPRAS do comprador (OVs de todos os clientes dele).
    # Views em vendas/ (o domínio é venda), montadas na área do
    # parceiro (o público é ele) — gate `partner_required`.
    # ⚠ Os DOIS includes moram no mesmo prefixo /partner/, nesta ordem: a
    # RAIZ do parceiro é a lista de compras (dono, 2026-08-18 — é o que ele
    # abre todo dia; a tabela de preços virou /partner/precos/). Quando
    # nenhum padrão do primeiro casa, o resolvedor segue para o segundo em
    # vez de dar 404 — há teste cravando /partner/how/.
    path('partner/', include('vendas.urls_partner', namespace='compras')),
    path('partner/', include('pricing.urls', namespace='pricing')),
    # Vendas (F11.2 — PRECIFICACAO §12.19): Cotação → OV do lote; admin-only.
    path('vendas/', include('vendas.urls', namespace='vendas')),
    # Gestão de empresa (T6 — PLANO_MULTITENANT §17.2): rota em inglês
    # (decisão §14.5); hoje só o onboarding de PLATAFORMA (/company/new/).
    path('company/', include('tenancy.urls', namespace='tenancy')),
    # Logo público por empresa (E4 — B4+B7): bytes servidos do BANCO com
    # cache; a rota existe nos DOIS mundos (cf. core/urls_tenant) — o header
    # resolve {% url 'company_logo' %} igual em qualquer host.
    path('branding/<slug:slug>/logo', tenancy_views.company_logo,
         name='company_logo'),
    # i18n: set_language (POST) grava o idioma no cookie E, se logado, na
    # preferência do usuário (tenancy.UserLanguage — cadeia I18N.md §3).
    # Mesma rota/nome do Django puro; alimenta os seletores. ANTES do <slug>.
    path('i18n/setlang/', tenancy_views.set_language, name='set_language'),
    # Catálogo gettext para os .js ESTÁTICOS (mic.js): expõe window.gettext()
    # no idioma ativo. Templates inline não precisam ({% trans %} resolve).
    path('i18n/js/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    # Páginas de conteúdo (deve ficar por último — captura <slug>)
    path('', views.home, name='home'),
    path('<slug:slug>/', views.page_detail, name='page'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ── Páginas de erro ──────────────────────────────────────────────────────────
# 403 com o MENU do site (quem sou eu / sair) em vez do texto cru do Django —
# o porquê está em core/views.py. Precisa estar nas DUAS URLconfs: o Django
# resolve o handler pela URLconf ATIVA da request (a de tenant é trocada em
# core/urls_tenant.py). Sem isto, o host de tenant cairia no 403 padrão.
handler403 = 'core.views.permission_denied'
