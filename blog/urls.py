from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.urls import path

from blog import views
from blog import views_site
from blog.forms_site import EmailLoginForm

staff_only = user_passes_test(lambda u: u.is_authenticated and u.is_staff)

urlpatterns = [
    path("", views_site.home, name="home"),
    path("pricing/", views_site.pricing, name="pricing"),
    path("register/", views_site.register, name="register"),
    path("verify-email/", views_site.verify_email, name="verify_email"),
    path("subscribe/", views_site.subscribe, name="subscribe"),
    path("dashboard/", views_site.dashboard, name="dashboard"),
    path("dashboard/submit/", views_site.dashboard_submit, name="dashboard_submit"),
    path("dashboard/entry/<int:pk>/", views_site.customer_entry_detail, name="customer_entry_detail"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="blog/site/login.html",
            authentication_form=EmailLoginForm,
        ),
        name="accounts_login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="accounts_logout",
    ),
    path("pipeline/", staff_only(views.entry_list), name="entry_list"),
    path("pipeline/new/", staff_only(views.entry_create), name="entry_create"),
    path("pipeline/entry/<int:pk>/", staff_only(views.entry_detail), name="entry_detail"),
    path("publish/<int:pk>/<str:token>/", views.publish_entry, name="publish_entry"),
]
