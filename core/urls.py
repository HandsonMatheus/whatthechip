from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from estoque import views as estoque_views
from pages import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chips/', include('chips.urls', namespace='chips')),
    path('estoque/', include('estoque.urls', namespace='estoque')),
    # Home pós-login (lançadeira): orienta e leva ao lote aberto em 1 clique.
    path('painel/', estoque_views.painel, name='painel'),
    # Auth (login/logout — sem cadastro público)
    path('login/',  auth_views.LoginView.as_view(),  name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Dashboard do COMPRADOR (F6 — PRECIFICACAO §7.1): rota em inglês, conta
    # externa via Buyer.users (a lançadeira /painel/ redireciona parceiro p/ cá).
    path('partner/', include('pricing.urls', namespace='pricing')),
    # i18n: set_language (POST) grava o idioma escolhido no cookie/sessão e
    # redireciona de volta. Alimenta o seletor do topo. ANTES da rota <slug>.
    path('i18n/', include('django.conf.urls.i18n')),
    # Páginas de conteúdo (deve ficar por último — captura <slug>)
    path('', views.home, name='home'),
    path('<slug:slug>/', views.page_detail, name='page'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
