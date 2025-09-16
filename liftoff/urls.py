from django.contrib import admin
from django.urls import path, include
from django.conf import settings

# Configure admin site
admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Trading Bot')
admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'Trading Bot')
admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Welcome!')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('webhooks.urls')),
]
