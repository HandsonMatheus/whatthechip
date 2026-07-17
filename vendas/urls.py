from django.urls import path

from . import views

app_name = 'vendas'

urlpatterns = [
    path('', views.so_list, name='so_list'),
    path('<int:pk>/', views.so_detail, name='so_detail'),
    path('<int:pk>/pdf/', views.so_pdf, name='so_pdf'),
    path('<int:pk>/confirmar/', views.so_confirm, name='so_confirm'),
    path('<int:pk>/cancelar/', views.so_cancel, name='so_cancel'),
]
