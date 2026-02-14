from django.contrib import admin
from django.urls import path, include
from api.views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('health/', health_check, name='health-check'),
]
