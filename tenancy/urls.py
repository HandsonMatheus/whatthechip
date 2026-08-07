"""
tenancy/urls.py — rotas de gestão de empresa (inglês — decisão §14.5)
======================================================================
Montado em ``/company/`` pelo ``core/urls.py`` (T6). Rotas de plataforma e de
gestão que vierem depois (T5 foi descartada; futuras telas de admin-da-empresa)
entram aqui.
"""

from django.urls import path

from . import views

app_name = 'tenancy'

urlpatterns = [
    # T6 (§17.2): onboarding — plataforma cria empresa + primeiro admin.
    path('new/', views.company_new, name='company_new'),
]
