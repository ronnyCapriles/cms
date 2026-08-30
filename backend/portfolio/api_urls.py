from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile, name="api-profile"),
    path("projects/", views.project_list, name="api-projects"),
    path("projects/<slug:slug>/", views.project_detail, name="api-project"),
    path("filters/", views.filters, name="api-filters"),
    path("languages/", views.languages, name="api-languages"),
]
