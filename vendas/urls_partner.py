"""Rotas da superfície do COMPRADOR (F11.6). Montadas em ``/partner/``
pelo ``core/urls.py`` — namespace ``compras``.

⚠ **A raiz do parceiro é a lista de COMPRAS** (dono, 2026-08-18): é o que ele
abre todo dia; a tabela de preços virou a segunda tela (``/partner/precos/``).
Este include e o do ``pricing`` moram no MESMO prefixo — o resolvedor do
Django tenta este primeiro e, quando nenhum padrão daqui casa, segue para o
próximo include em vez de dar 404 (há teste cravando ``/partner/how/``).

``/partner/compras/`` (a raiz ANTIGA da lista) redireciona: o comprador pode
ter guardado o link.
"""

from django.urls import path
from django.views.generic import RedirectView

from . import views_partner as views

app_name = 'compras'

urlpatterns = [
    path('', views.compras_list, name='list'),
    path('compras/', RedirectView.as_view(pattern_name='compras:list'),
         name='list_legacy'),
    path('compras/<int:pk>/', views.compra_detail, name='detail'),
    path('compras/<int:pk>/congelar/', views.compra_congelar, name='congelar'),
    path('compras/<int:pk>/resultado/', views.compra_resultado, name='resultado'),
]
