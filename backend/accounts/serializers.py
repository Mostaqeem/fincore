from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from employees.serializers import EmployeeSummarySerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_verified",
            "date_joined",
            "is_admin",
            "employee",
        )
        read_only_fields = ("id", "is_active", "is_verified", "date_joined")

    def get_is_admin(self, obj):
        return obj.is_staff or obj.is_superuser

    def get_employee(self, obj):
        profile = getattr(obj, "employee_profile", None)
        if profile is None:
            return None
        return EmployeeSummarySerializer(profile).data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "password")

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["is_verified"] = user.is_verified
        return token
