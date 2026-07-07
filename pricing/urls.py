"""Rotas do dashboard do comprador (F6 — inglês por decisão do dono, §1.11)."""

from django.urls import path

from . import views

app_name = 'pricing'

urlpatterns = [
    path('',                      views.partner_home, name='partner_home'),
    path('lists/<int:list_pk>/',  views.partner_list, name='partner_list'),
    path('save/<int:list_pk>/',   views.partner_save, name='partner_save'),
]
