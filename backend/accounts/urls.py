from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.UserDetailView.as_view(), name="user_detail"),
    path("auth/verify-otp/", views.VerifyOTPView.as_view(), name="verify_otp"),
    path("auth/resend-otp/", views.ResendOTPView.as_view(), name="resend_otp"),
    path("auth/forgot-password/", views.ForgotPasswordRequestView.as_view(), name="forgot_password"),
    path("auth/verify-forgot-password-otp/", views.VerifyForgotPasswordOTPView.as_view(), name="verify_forgot_password_otp"),
    path("auth/reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
]
