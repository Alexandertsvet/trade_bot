from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from user.views import (
    AddPositionPostOrderRequest,
    AddPositionView,
    SandboxAccountAdd,
    SandboxAccountCreateView,
    SandboxAccountDelAll,
    SandboxAccountDeleteView,
    SandboxAccountListView,
    TinkoffSandboxAccountDetailView,
)

from .views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    SignUpView,
)

app_name = "user"

urlpatterns = [
    # path('user/', include('django.contrib.auth.urls')),
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "login/",
        LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "password_change/",
        PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="done/",
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path(
        "password_reset/",
        PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            subject_template_name="registration/password_reset_subject.txt",
            email_template_name="registration/password_reset_email.html",
            success_url="done/",
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("user:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        "sandbox/add/", SandboxAccountCreateView.as_view(), name="sandbox_add"
    ),
    path("sandbox/", SandboxAccountListView.as_view(), name="sandbox_list"),
    path(
        "sandbox/<int:pk>/delete/",
        SandboxAccountDeleteView.as_view(),
        name="sandbox_delete",
    ),
    path(
        "sandbox/account/add/",
        SandboxAccountAdd.as_view(),
        name="sandbox_account_add",
    ),
    path(
        "sandbox/account/delete/all/",
        SandboxAccountDelAll.as_view(),
        name="sandbox_account_del_all",
    ),
    path(
        "sandbox/<str:pk>/",
        TinkoffSandboxAccountDetailView.as_view(),
        name="sandbox_detail",
    ),
    path(
        "sandbox/<int:pk>/add-position/",
        AddPositionView.as_view(),
        name="add_position",
    ),
    path(
        "sandbox/<int:pk>/add/",
        AddPositionPostOrderRequest.as_view(),
        name="add",
    ),
]
