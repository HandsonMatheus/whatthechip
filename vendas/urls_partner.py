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
    # O MESMO recorte filtrado da lista, em CSV (spec v2 §5.3). Mora ANTES do
    # `compras/<pk>/` porque `export.csv` não é um pk — e o resolvedor do
    # Django para no primeiro padrão que casa.
    path('compras/export.csv', views.compras_csv, name='export_csv'),
    path('compras/', RedirectView.as_view(pattern_name='compras:list'),
         name='list_legacy'),
    path('compras/<int:pk>/', views.compra_detail, name='detail'),
    path('compras/<int:pk>/recebido/', views.compra_recebido, name='recebido'),
    path('compras/<int:pk>/resultado/', views.compra_resultado, name='resultado'),
    path('compras/<int:pk>/resultado.pdf', views.compra_resultado_pdf,
         name='resultado_pdf'),
    # A aba aberta em CSV (spec v2 §6.10). Uma rota POR ABA, não `?aba=`: o
    # nome do arquivo faz parte da entrega.
    # A planilha vem ANTES do `<slug:aba>.csv` por clareza de leitura, não
    # por precedência: as duas rotas não colidem (extensões diferentes).
    path('compras/<int:pk>/planilha.xlsx', views.compra_planilha,
         name='planilha'),
    path('compras/<int:pk>/<slug:aba>.csv', views.compra_aba_csv,
         name='aba_csv'),
    path('compras/<int:pk>/pagar/', views.compra_pagar, name='pagar'),
    path('compras/<int:pk>/observacao/', views.compra_observacao,
         name='observacao'),
    path('compras/<int:pk>/observacao/<int:nota_pk>/remover/',
         views.compra_observacao_remover, name='observacao_remover'),
    path('compras/<int:pk>/pagamento/<int:pagamento_pk>/comprovante',
         views.compra_comprovante, name='comprovante'),
]
