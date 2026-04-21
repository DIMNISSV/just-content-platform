from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from content.views import HomeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('content.urls')),
    path('', include('media.urls')),
    path('', HomeView.as_view(), name='home'),
]

# Раздача медиа-файлов сервером Django (только для режима разработки)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
