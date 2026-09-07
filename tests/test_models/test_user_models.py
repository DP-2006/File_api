# tests/test_models/test_user_models.py
import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import UserProfile, UserSettings, PasswordPolicy, LoginLog


@pytest.mark.django_db
class TestUserProfile:
    """تست‌های مدل UserProfile"""
    
    def test_create_user_profile(self, normal_user):
        # استفاده از get_or_create به جای create
        profile, created = UserProfile.objects.get_or_create(user=normal_user)
        assert profile.user == normal_user
        # created می‌تواند True یا False باشد، پس assert نمی‌کنیم
    
    def test_user_profile_str(self, normal_user):
        # استفاده از get_or_create
        profile, _ = UserProfile.objects.get_or_create(user=normal_user)
        assert str(profile) == normal_user.username
    
    def test_block_user(self, normal_user):
        profile, _ = UserProfile.objects.get_or_create(user=normal_user)
        profile.is_blocked = True
        profile.blocked_at = timezone.now()
        profile.save()
        assert profile.is_blocked is True
        assert profile.blocked_at is not None
    
    def test_unblock_user(self, normal_user):
        profile, _ = UserProfile.objects.get_or_create(user=normal_user)
        profile.is_blocked = True
        profile.blocked_at = timezone.now()
        profile.save()
        profile.is_blocked = False
        profile.blocked_at = None
        profile.save()
        assert profile.is_blocked is False
        assert profile.blocked_at is None


@pytest.mark.django_db
class TestUserSettings:
    """تست‌های مدل UserSettings"""
    
    def test_create_user_settings(self, normal_user):
        settings, created = UserSettings.objects.get_or_create(
            user=normal_user,
            defaults={'font_size': 14, 'menu_size': 200, 'button_size': 40}
        )
        assert settings.user == normal_user
        assert settings.font_size == 14
        assert settings.menu_size == 200
        assert settings.button_size == 40
    
    def test_update_user_settings(self, normal_user):
        settings, _ = UserSettings.objects.get_or_create(user=normal_user)
        settings.font_size = 18
        settings.menu_size = 250
        settings.button_size = 50
        settings.save()
        updated = UserSettings.objects.get(user=normal_user)
        assert updated.font_size == 18
        assert updated.menu_size == 250
        assert updated.button_size == 50
    
    def test_settings_str(self, normal_user):
        settings = UserSettings.objects.create(user=normal_user)
        assert str(settings) == f"Settings for {normal_user.username}"


@pytest.mark.django_db
class TestPasswordPolicy:
    """تست‌های سیاست رمز عبور"""
    
    def test_create_password_policy(self):
        policy = PasswordPolicy.objects.create(
            min_password_length=10,
            require_uppercase=True,
            require_digit=True,
            require_special_char=True
        )
        assert policy.min_password_length == 10
        assert policy.require_uppercase is True
        assert policy.require_digit is True
        assert policy.require_special_char is True
    
    def test_policy_str(self):
        policy = PasswordPolicy.objects.create()
        assert str(policy) == "تنظیمات رمز عبور"


@pytest.mark.django_db
class TestLoginLog:
    """تست‌های لاگ ورود"""
    
    def test_create_login_log(self, normal_user):
        log = LoginLog.objects.create(
            user=normal_user,
            ip_address='192.168.1.100',
            success=True,
            attempts=1
        )
        assert log.user == normal_user
        assert log.ip_address == '192.168.1.100'
        assert log.success is True
        assert log.attempts == 1
    
    def test_login_log_failed(self, normal_user):
        log = LoginLog.objects.create(
            user=normal_user,
            ip_address='192.168.1.100',
            success=False,
            attempts=3
        )
        assert log.success is False
        assert log.attempts == 3
    
    def test_login_log_str(self, normal_user):
        log = LoginLog.objects.create(
            user=normal_user,
            ip_address='192.168.1.1',
            success=True
        )
        assert str(log) == f"{normal_user.username} - {log.login_time} - Success"
