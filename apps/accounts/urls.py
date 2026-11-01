from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("register/verificar/", views.register_verify_view, name="register_verify"),
    path("senha/esqueci/", views.password_reset_view, name="password_reset"),
    path(
        "senha/redefinir/",
        views.password_reset_confirm_view,
        name="password_reset_confirm",
    ),
    path(
        "codigo/<str:purpose>/reenviar/",
        views.resend_code_view,
        name="resend_code",
    ),
    path("login/", views.login_view, name="login"),
    path("google/", views.google_login_view, name="google_login"),
    path("logout/", views.logout_view, name="logout"),
    path("usuarios/", views.user_management_view, name="user_management"),
    path(
        "usuarios/<int:user_id>/tipo/",
        views.user_update_type_view,
        name="user_update_type",
    ),
    path(
        "usuarios/<int:user_id>/status/",
        views.user_toggle_status_view,
        name="user_toggle_status",
    ),
    path(
        "usuarios/<int:user_id>/excluir/",
        views.user_delete_view,
        name="user_delete",
    ),
]
