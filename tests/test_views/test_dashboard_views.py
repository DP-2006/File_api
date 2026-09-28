# tests/test_views/test_dashboard_views.py
import pytest
from django.urls import reverse
from django.core.files.base import ContentFile
from rest_framework import status

from core.models import UploadedFile, UserSettings


@pytest.mark.django_db
class TestDashboardViews:
    """تست‌های داشبورد"""
    
    def test_dashboard_unauthenticated(self, api_client):
        url = reverse('dashboard')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_dashboard_authenticated_html(self, authenticated_client, normal_user):
        url = reverse('dashboard')
        response = authenticated_client.get(url)
        assert response.status_code == 200
        settings = UserSettings.objects.get(user=normal_user)
        assert settings is not None
    
    def test_dashboard_authenticated_json(self, authenticated_client):
        url = reverse('dashboard') + '?format=json'
        response = authenticated_client.get(url, HTTP_ACCEPT='application/json')
        assert response.status_code == status.HTTP_200_OK
        assert 'settings' in response.data
        assert 'user' in response.data
    
    def test_save_settings(self, authenticated_client, normal_user):
        url = reverse('save_settings')
        data = {
            'font_size': 20,
            'menu_size': 250,
            'button_size': 50
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        settings = UserSettings.objects.get(user=normal_user)
        assert settings.font_size == 20
        assert settings.menu_size == 250
        assert settings.button_size == 50


@pytest.mark.django_db
class TestFileViews:
    """تست‌های عملیات فایل"""
    
    def test_upload_files(self, authenticated_client):
        url = reverse('upload_files')
        file_content = ContentFile('Test file content', 'test.txt')
        data = {
            'files': [file_content],
            'folder_name': 'test_folder'
        }
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['uploaded_count'] >= 1
    
    def test_upload_exe_rejected(self, authenticated_client):
        url = reverse('upload_files')
        file_content = ContentFile('EXE content', 'malware.exe')
        data = {'files': [file_content]}
        response = authenticated_client.post(url, data, format='multipart')
        assert response.data['success'] is True
        assert response.data['rejected_count'] >= 1
    
    def test_download_file(self, authenticated_client, normal_user, test_file):
        url = reverse('download_file', kwargs={'file_id': test_file.id})
        response = authenticated_client.get(url, HTTP_ACCEPT='application/json')
        assert response.status_code == status.HTTP_200_OK
        assert 'file_url' in response.data
    
    def test_download_file_unauthorized(self, authenticated_client, staff_user):
        file_obj = UploadedFile.objects.create(uploaded_by=staff_user)
        file_obj.file.save('private.txt', ContentFile('Private'), save=True)
        url = reverse('download_file', kwargs={'file_id': file_obj.id})
        response = authenticated_client.get(url, HTTP_ACCEPT='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_file(self, authenticated_client, normal_user, test_file):
        # ✅ اصلاح: استفاده از نام درست URL
        url = reverse('delete_my_file')  # قبلاً: delete_my_file_view
        data = {'file_id': test_file.id}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        with pytest.raises(UploadedFile.DoesNotExist):
            UploadedFile.objects.get(id=test_file.id)
