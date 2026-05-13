import uuid

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .firebase_email import send_verification_email
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "password2",
            "first_name",
            "last_name",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(**validated_data)
        # Ensure a verification token is set (model default generates one but let's be explicit)
        if not user.email_verification_token:
            import uuid as _uuid

            user.email_verification_token = _uuid.uuid4()
            user.save(update_fields=["email_verification_token"])
        # Send verification email (fail silently so registration still succeeds)
        try:
            send_verification_email(user)
        except Exception:
            pass
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    # SECURITY: expose a sanitised view of preferences — never include raw API keys
    preferences_safe = serializers.SerializerMethodField()
    onboarding = serializers.SerializerMethodField()
    github_connected = serializers.SerializerMethodField()

    def get_preferences_safe(self, obj):
        prefs = getattr(obj, "preferences", {}) or {}
        # Strip sensitive keys — only expose non-secret preference flags
        return {
            k: v
            for k, v in prefs.items()
            if k
            not in (
                "gemini_api_key",
                "openrouter_api_key",
                "mfa_secret",
                "mfa_backup_codes",
            )
        }

    def get_onboarding(self, obj):
        try:
            prefs = obj.onboarding_prefs
            return {
                "is_onboarded": obj.is_onboarded,
                "current_step": prefs.current_step,
                "interests": prefs.interests,
                "use_case": prefs.use_case,
                "completed": prefs.completed,
            }
        except Exception:
            return {
                "is_onboarded": obj.is_onboarded,
                "current_step": 1,
                "interests": [],
                "use_case": "",
                "completed": False,
            }

    def get_github_connected(self, obj):
        return bool(obj.github_id)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "avatar_url",
            "bio",
            "preferences_safe",
            "created_at",
            "last_login",
            "is_onboarded",
            "onboarded_at",
            "digest_enabled",
            "digest_day",
            "github_connected",
            "github_username",
            "onboarding",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "created_at",
            "last_login",
            "is_onboarded",
            "onboarded_at",
            "github_connected",
        ]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["preferences"]


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Always return success to avoid user enumeration
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password": "Passwords do not match."}
            )
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({"uid": "Invalid reset link."})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Reset link is invalid or has expired."}
            )
        attrs["user"] = user
        return attrs
