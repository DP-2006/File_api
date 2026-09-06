# tests/test_integration/test_workflows.py
import pytest
from django.urls import reverse
from django.core.files.base import ContentFile
from rest_framework import status

from core.models import UploadedFile, FileActionLog, AINotification, LoginLog


@pytest.mark.django_db
class TestWorkflows:
    """تست‌های یکپارچگی گردش‌های کاری"""
    
    def test_full_upload_workflow(self, authenticated_client, normal_user):
        # 1. آپلود فایل
        upload_url = reverse('upload_files')
        file_content = ContentFile('Integration test content', 'integration.txt')
        response = authenticated_client.post(
            upload_url,
            {'files': [file_content]},
            format='multipart'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['uploaded_count'] >= 1
        
        # 2. بررسی وجود فایل در دیتابیس
        uploaded_file = UploadedFile.objects.filter(
            uploaded_by=normal_user,
            is_deleted=False
        ).first()
        assert uploaded_file is not None
        
        # 3. دانلود فایل
        download_url = reverse('download_file', kwargs={'file_id': uploaded_file.id})
        response = authenticated_client.get(download_url, HTTP_ACCEPT='application/json')
        assert response.status_code == status.HTTP_200_OK
        
        # 4. حذف فایل
        delete_url = reverse('delete_my_file_view')
        response = authenticated_client.post(
            delete_url,
            {'file_id': uploaded_file.id},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_login_logout_workflow(self, api_client, normal_user):
        # 1. ورود موفق
        login_url = reverse('login')
        response = api_client.post(
            login_url,
            {'username': normal_user.username, 'password': 'NormalPass123!'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        token = response.data.get('token')
        assert token is not None
        
        # 2. بررسی لاگ ورود
        login_log = LoginLog.objects.filter(user=normal_user, success=True)
        assert login_log.exists()
        
        # 3. خروج
        api_client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        logout_url = reverse('logout')
        response = api_client.post(logout_url, format='json')
        assert response.status_code == status.HTTP_200_OK
    
    def test_file_sharing_workflow(self, authenticated_client, normal_user, staff_user):
        # 1. آپلود فایل
        upload_url = reverse('upload_files')
        file_content = ContentFile('Share test', 'share.txt')
        authenticated_client.post(
            upload_url,
            {'files': [file_content]},
            format='multipart'
        )
        
        # 2. ارسال فایل به کاربر دیگر
        send_url = reverse('send_files')
        response = authenticated_client.post(
            send_url,
            {'recipient_id': staff_user.id, 'files': [file_content]},
            format='multipart'
        )
        assert response.status_code == status.HTTP_200_OK
        
        # 3. بررسی فایل دریافتی
        received_file = UploadedFile.objects.filter(
            sent_to_user=staff_user,
            uploaded_by=normal_user
        )
        assert received_file.exists()
