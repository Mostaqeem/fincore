import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=4, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    password_reset_otp = models.CharField(max_length=4, blank=True, null=True)
    password_reset_otp_created_at = models.DateTimeField(blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def generate_otp(self):
        self.otp = f"{random.randint(1000, 9999)}"
        self.otp_created_at = timezone.now()
        self.save(update_fields=["otp", "otp_created_at"])
        return self.otp

    def is_otp_expired(self):
        if not self.otp_created_at:
            return True
        return timezone.now() > self.otp_created_at + timedelta(minutes=10)

    def verify_otp(self, otp):
        if self.otp == otp and not self.is_otp_expired():
            self.is_verified = True
            self.otp = None
            self.otp_created_at = None
            self.save(update_fields=["is_verified", "otp", "otp_created_at"])
            return True
        return False

    def send_otp_email(self):
        if not self.otp:
            self.generate_otp()
        subject = "Welcome — Verify Your Email"
        html_message = render_to_string("accounts/welcome_email.html", {
            "first_name": self.first_name or "User",
            "otp": self.otp,
        })
        send_mail(
            subject,
            "",
            settings.EMAIL_HOST_USER,
            [self.email],
            html_message=html_message,
            fail_silently=False,
        )

    def generate_password_reset_otp(self):
        self.password_reset_otp = f"{random.randint(1000, 9999)}"
        self.password_reset_otp_created_at = timezone.now()
        self.save(update_fields=["password_reset_otp", "password_reset_otp_created_at"])
        return self.password_reset_otp

    def is_password_reset_otp_expired(self):
        if not self.password_reset_otp_created_at:
            return True
        return timezone.now() > self.password_reset_otp_created_at + timedelta(minutes=10)

    def verify_password_reset_otp(self, otp):
        if self.password_reset_otp == otp and not self.is_password_reset_otp_expired():
            return True
        return False

    def send_password_reset_email(self):
        if not self.password_reset_otp:
            self.generate_password_reset_otp()
        subject = "Reset Your Password"
        html_message = render_to_string("accounts/password_reset_email.html", {
            "first_name": self.first_name or "User",
            "otp": self.password_reset_otp,
        })
        send_mail(
            subject,
            "",
            settings.EMAIL_HOST_USER,
            [self.email],
            html_message=html_message,
            fail_silently=False,
        )
