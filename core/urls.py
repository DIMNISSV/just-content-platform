from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from content.views import HomeView, upload_wizard_view
from taxonomy.admin_views import taxonomy_manager_view

urlpatterns = [
    path('admin/upload-wizard/', upload_wizard_view, name='upload_wizard'),
    path('admin/taxonomy-manager/', taxonomy_manager_view, name='taxonomy_manager'),
    path('admin/', admin.site.urls),
    path('api/v1/recommendations/', include('recommendations.urls')),
    path('', include('content.urls')),
    path('', include('media.urls')),
    path('', include('aggregator.urls')),
    path('', include('taxonomy.urls')),
    path('', HomeView.as_view(), name='home'),
    path('', include('users.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
