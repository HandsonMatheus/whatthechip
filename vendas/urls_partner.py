"""Rotas da superfície do COMPRADOR (F11.6). Montadas em ``/partner/compras/``
pelo ``core/urls.py`` — namespace ``compras``."""

from django.urls import path

from . import views_partner as views

app_name = 'compras'

urlpatterns = [
    path('', views.compras_list, name='list'),
    path('<int:pk>/', views.compra_detail, name='detail'),
    path('<int:pk>/resultado/', views.compra_resultado, name='resultado'),
]
