from django.urls import path
from . import views

app_name = 'estoque'

urlpatterns = [
    path('',                                    views.lot_list,    name='index'),
    path('novo/',                               views.lot_create,  name='lot_create'),
    path('lote/<int:lot_pk>/',                  views.lot_detail,  name='lot_detail'),
    path('lote/<int:lot_pk>/preview/',          views.preview_chip, name='preview'),
    path('lote/<int:lot_pk>/add/',              views.add_chip,    name='add'),
    path('lote/<int:lot_pk>/remove/<int:pk>/',  views.remove_entry, name='remove'),
    path('lote/<int:lot_pk>/export/',           views.export_xls,  name='export'),
    path('lote/<int:lot_pk>/fechar/',           views.lot_close,   name='lot_close'),
    path('fx/',                                 views.fx_badge,    name='fx_badge'),
    path('lote/<int:lot_pk>/valoracao/',        views.lot_valuation_live, name='lot_valuation'),
    path('lote/<int:lot_pk>/reabrir/',          views.lot_reopen,  name='lot_reopen'),
    path('lote/<int:lot_pk>/excluir/',          views.lot_delete,  name='lot_delete'),
]
