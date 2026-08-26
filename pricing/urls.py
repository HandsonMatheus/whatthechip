"""Rotas do dashboard do comprador (F6 — inglês por decisão do dono, §1.11)."""

from django.urls import path

from . import views

app_name = 'pricing'

urlpatterns = [
    # A raiz /partner/ é a lista de COMPRAS (vendas/urls_partner) desde
    # 2026-08-18; a tabela de preços é a segunda tela do menu.
    #
    # ⚠ `lists/<pk>/` e `save/<pk>/` SAÍRAM em 2026-08-26 (decisão C7 do
    # dono). Elas funcionavam, mas nenhum link apontava para elas desde que a
    # navegação virou POR TIPO (2026-07-27) — e um segundo caminho para gravar
    # preço, com regra própria, é onde os dois divergem calado. A moderação
    # inteira vive em `tipo/<kind>/enviar/`.
    path('precos/',               views.partner_home, name='partner_home'),
    path('tipo/<str:kind>/',      views.partner_kind, name='partner_kind'),
    path('tipo/<str:kind>/enviar/', views.partner_kind_save, name='partner_kind_save'),
    path('notifications/',        views.partner_notifications,
         name='partner_notifications'),
    path('how/',                  views.partner_how, name='partner_how'),
    # A TELA do catálogo (spec v2 §5.2). O `.pdf` abaixo continua sendo quem
    # gera — a tela só monta o pedido.
    path('catalogo/',             views.partner_catalog,
         name='partner_catalog_page'),
    # GET (o card da home, desde julho) e POST (o formulário da tela nova,
    # spec v2 §10.2) na MESMA rota: link guardado continua valendo.
    path('catalog.pdf',           views.partner_catalog_pdf,
         name='partner_catalog'),
]
