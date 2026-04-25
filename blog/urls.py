from django.urls import path

from blog import views

urlpatterns = [
    path("", views.entry_list, name="entry_list"),
    path("new/", views.entry_create, name="entry_create"),
    path("entry/<int:pk>/", views.entry_detail, name="entry_detail"),
    path("publish/<int:pk>/<str:token>/", views.publish_entry, name="publish_entry"),
]
