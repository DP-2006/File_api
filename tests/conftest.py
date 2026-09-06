#cd ~/Downloads/File_api-main/tests


# tests/conftest.py
import os
import sys
from pathlib import Path

# ============================================
# تنظیم مسیر پروژه
# ============================================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'kiosk'))

# ============================================
# تنظیم متغیرهای محیطی - استفاده از kiosk.settings
# ============================================

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiosk.settings')
os.environ.setdefault('DJANGO_ENV', 'test')

# ============================================
# راه‌اندازی Django
# ============================================

import django
django.setup()

# ============================================
# ایمپورت‌ها
# ============================================

import pytest
from django.test import RequestFactory
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient
from django.core.files.base import ContentFile

# ایمپورت از core (مدل‌های پروژه)
from core.models import (
    UploadedFile, FileActionLog, LoginLog, UserProfile,
    UserSettings, AISettings, SystemSettings, FileSizeSettings,
    AINotification, AIThreatAlert, PasswordPolicy
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def api_client():
    """کلاینت API برای تست‌ها"""
    return APIClient()


@pytest.fixture
def request_factory():
    """Request factory برای تست ویوها"""
    return RequestFactory()


@pytest.fixture
def superuser(db):
    """ایجاد سوپرادمین"""
    user = User.objects.create_superuser(
        username='superadmin',
        password='SuperSecurePass123!',
        email='super@admin.com'
    )
    UserProfile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def staff_user(db):
    """ایجاد کاربر ادمین"""
    user = User.objects.create_user(
        username='staffuser',
        password='StaffPass123!',
        email='staff@test.com',
        is_staff=True
    )
    UserProfile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def normal_user(db):
    """ایجاد کاربر عادی"""
    user = User.objects.create_user(
        username='normaluser',
        password='NormalPass123!',
        email='user@test.com'
    )
    UserProfile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def test_group(db):
    """ایجاد گروه تست"""
    group = Group.objects.create(name='test_group')
    content_type = ContentType.objects.get_for_model(User)
    permission = Permission.objects.get_or_create(
        codename='view_user',
        name='Can view user',
        content_type=content_type
    )[0]
    group.permissions.add(permission)
    return group


@pytest.fixture
def test_file(db, normal_user):
    """ایجاد فایل تست"""
    file_obj = UploadedFile.objects.create(
        uploaded_by=normal_user,
        folder_name='test_folder'
    )
    file_obj.file.save('test_file.txt', ContentFile('This is test content'), save=True)
    return file_obj


@pytest.fixture
def login_log(db, normal_user):
    """ایجاد لاگ ورود"""
    return LoginLog.objects.create(
        user=normal_user,
        ip_address='192.168.1.1',
        success=True,
        attempts=1
    )


@pytest.fixture
def action_log(db, normal_user, test_file):
    """ایجاد لاگ عملیات"""
    return FileActionLog.objects.create(
        user=normal_user,
        action='upload',
        file_name=test_file.file.name,
        file_size=1024,
        ip_address='192.168.1.1',
        ai_analysis='Test analysis',
        threat_level='low'
    )


@pytest.fixture
def ai_settings(db):
    """ایجاد تنظیمات AI"""
    settings, _ = AISettings.objects.get_or_create(
        pk=1,
        defaults={
            'ollama_host': 'localhost',
            'ollama_port': 11434,
            'ollama_model': 'gemma3:27b',
            'is_active': True,
            'timeout_seconds': 120,
            'max_tokens': 2048,
            'temperature': 0.3
        }
    )
    return settings


@pytest.fixture
def file_size_settings(db):
    """ایجاد تنظیمات حجم فایل"""
    settings, _ = FileSizeSettings.objects.get_or_create(
        pk=1,
        defaults={
            'max_upload_size_mb': 100,
            'max_download_size_mb': 200,
            'warning_threshold_mb': 50,
            'allow_large_files': True
        }
    )
    return settings


@pytest.fixture
def authenticated_client(db, normal_user):
    """کلاینت احراز هویت شده"""
    client = APIClient()
    client.force_authenticate(user=normal_user)
    return client


@pytest.fixture
def authenticated_staff_client(db, staff_user):
    """کلاینت احراز هویت شده برای ادمین"""
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def authenticated_super_client(db, superuser):
    """کلاینت احراز هویت شده برای سوپرادمین"""
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture(autouse=True)
def cleanup_files():
    """پاک کردن فایل‌های ایجاد شده در تست‌ها"""
    yield
    for file_obj in UploadedFile.objects.all():
        if file_obj.file and file_obj.file.storage.exists(file_obj.file.path):
            try:
                file_obj.file.delete()
            except:
                pass
