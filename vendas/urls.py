from django.urls import path

from . import views

app_name = 'vendas'

urlpatterns = [
    path('', views.so_list, name='so_list'),
    path('<int:pk>/', views.so_detail, name='so_detail'),
    path('<int:pk>/pdf/', views.so_pdf, name='so_pdf'),
    path('<int:pk>/confirmar/', views.so_confirm, name='so_confirm'),
    path('<int:pk>/cancelar/', views.so_cancel, name='so_cancel'),
    # F11.4 — acerto → fatura → pagamentos:
    path('<int:pk>/acerto/', views.settlement_new, name='settlement_new'),
    path('fatura/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('fatura/<int:pk>/pagar/', views.invoice_pay, name='invoice_pay'),
    path('fatura/<int:pk>/cancelar/', views.invoice_cancel,
         name='invoice_cancel'),
]
