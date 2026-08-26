"""Rotas do dashboard do comprador (F6 — inglês por decisão do dono, §1.11)."""

from django.urls import path

from . import views

app_name = 'pricing'

urlpatterns = [
    # A raiz /partner/ é a lista de COMPRAS (vendas/urls_partner) desde
    # 2026-08-18; a tabela de preços é a segunda tela do menu.
    path('precos/',               views.partner_home, name='partner_home'),
    path('lists/<int:list_pk>/',  views.partner_list, name='partner_list'),
    path('tipo/<str:kind>/',      views.partner_kind, name='partner_kind'),
    path('tipo/<str:kind>/enviar/', views.partner_kind_save, name='partner_kind_save'),
    path('save/<int:list_pk>/',   views.partner_save, name='partner_save'),
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
