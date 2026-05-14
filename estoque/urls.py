from django.urls import path
from . import views

app_name = "estoque"

urlpatterns = [
    path("",                  views.estoque_view, name="index"),
    path("preview/",          views.preview_chip, name="preview"),
    path("add/",              views.add_chip,     name="add"),
    path("remove/<int:pk>/",  views.remove_entry, name="remove"),
    path("export/",           views.export_xls,   name="export"),
]
