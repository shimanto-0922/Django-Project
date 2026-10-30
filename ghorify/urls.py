from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Ghorify Administration'
admin.site.site_title = 'Ghorify Admin'
admin.site.index_title = 'Platform management'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('search/', include('search.urls')),
    path('me/', include('interactions.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('', include('properties.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
