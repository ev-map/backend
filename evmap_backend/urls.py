"""
URL configuration for evmap_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path

from evmap_backend.data_sources.nobil.api import api as nobil_api
from evmap_backend.data_sources.openstreetmap.api import api as osm_api

from . import views
from .api import api as main_api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("nobil/api/", nobil_api.urls),
    path("osm/api/", osm_api.urls),
    path("api/", main_api.urls),
    path("playground/", views.playground),
]
