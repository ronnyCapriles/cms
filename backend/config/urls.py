from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from portfolio import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("portfolio.api_urls")),
    path("", include("mcp_server.urls")),
    # Everything else is handed to the React router, so every prefix above has
    # to be named in the lookahead too.
    re_path(r"^(?!api/|admin/|static/|media/|mcp|oauth/|\.well-known/).*$",
            views.spa, name="spa"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
