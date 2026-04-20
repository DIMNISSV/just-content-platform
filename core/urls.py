from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns =[
    path('admin/', admin.site.urls),
    path('', include('content.urls')),
]

# Раздача медиа-файлов сервером Django (только для режима разработки)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)