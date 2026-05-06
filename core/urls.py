from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from pages import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chips/', include('chips.urls', namespace='chips')),
    path('', views.home, name='home'),
    path('<slug:slug>/', views.page_detail, name='page'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
