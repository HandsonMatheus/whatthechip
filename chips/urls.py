from django.urls import path
from . import views

app_name = "chips"

urlpatterns = [
    path("search/", views.search_api,   name="search"),
    path("decode/", views.decode_html,  name="decode"),
    path("stats/",  views.stats_api,    name="stats"),
    path("report/", views.report_error, name="report"),
    path("submit/", views.submit_chip,  name="submit"),
]
