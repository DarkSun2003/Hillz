# carproject/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from car_rental import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('car_rental.urls')),
    
    path('accounts/', include('allauth.urls')),
    path('socialaccounts/', include('allauth.socialaccount.urls')),
    
    path('reports/', views.ReportsDashboardView.as_view(), name='reports_dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    #urlpatterns += [
    #    path('__debug__/', include('django_debug_toolbar.urls')),
    #]