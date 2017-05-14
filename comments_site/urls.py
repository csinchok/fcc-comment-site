from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static

from .core.views import index, browse

urlpatterns = [
    # url(r'^admin/', admin.site.urls),
    url(r'^$', index),
    url(r'^browse/?$', browse)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
