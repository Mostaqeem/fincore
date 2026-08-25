from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import User


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegisterAndVerifyOTPTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_sends_otp_and_returns_tokens(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com",
                "password": "StrongPass123",
                "first_name": "Test",
                "last_name": "User",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])

        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_verified)
        self.assertIsNotNone(user.otp)
        self.assertEqual(len(mail.outbox), 1)

    def test_verify_otp_success(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        otp = user.generate_otp()

        self.client.force_authenticate(user=user)
        response = self.client.post("/api/auth/verify-otp/", {"otp": otp}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_verified"])

        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertIsNone(user.otp)
        self.assertIsNone(user.otp_created_at)

    def test_verify_otp_wrong_otp_rejected(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        user.generate_otp()

        self.client.force_authenticate(user=user)
        response = self.client.post("/api/auth/verify-otp/", {"otp": "0000"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_verify_otp_expired_rejected(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        otp = user.generate_otp()
        user.otp_created_at = timezone.now() - timedelta(minutes=2)
        user.save(update_fields=["otp_created_at"])

        self.client.force_authenticate(user=user)
        response = self.client.post("/api/auth/verify-otp/", {"otp": otp}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        user.refresh_from_db()
        self.assertFalse(user.is_verified)


class ForgotPasswordOTPTests(TestCase):
    def test_password_reset_otp_success(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        otp = user.generate_password_reset_otp()

        client = APIClient()
        response = client.post(
            "/api/auth/verify-forgot-password-otp/",
            {"email": user.email, "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_otp_expired_rejected(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        otp = user.generate_password_reset_otp()
        user.password_reset_otp_created_at = timezone.now() - timedelta(minutes=2)
        user.save(update_fields=["password_reset_otp_created_at"])

        client = APIClient()
        response = client.post(
            "/api/auth/verify-forgot-password-otp/",
            {"email": user.email, "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_with_expired_otp_rejected(self):
        user = User.objects.create_user(email="test@example.com", password="StrongPass123")
        otp = user.generate_password_reset_otp()
        user.password_reset_otp_created_at = timezone.now() - timedelta(minutes=2)
        user.save(update_fields=["password_reset_otp_created_at"])

        client = APIClient()
        response = client.post(
            "/api/auth/reset-password/",
            {
                "email": user.email,
                "otp": otp,
                "new_password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ModelExpiryTests(TestCase):
    def test_login_issues_token_to_unverified_user(self):
        self.client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com",
                "password": "StrongPass123",
                "first_name": "Test",
                "last_name": "User",
            },
            format="json",
        )

        response = self.client.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": "StrongPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_verified)