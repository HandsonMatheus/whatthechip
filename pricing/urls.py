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
    path('catalog.pdf',           views.partner_catalog_pdf,
         name='partner_catalog'),
]
