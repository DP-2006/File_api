# tests/test_views/test_auth_views.py
import pytest
from django.urls import reverse
from rest_framework import status

from core.models import LoginLog


@pytest.mark.django_db
class TestAuthViews:
    """تست‌های احراز هویت"""
    
    def test_login_view_get(self, api_client):
        url = reverse('login')
        response = api_client.get(url)
        assert response.status_code == 200
    
    def test_login_success_json(self, api_client, normal_user):
        url = reverse('login')
        data = {
            'username': normal_user.username,
            'password': 'NormalPass123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['username'] == normal_user.username
        assert LoginLog.objects.filter(user=normal_user, success=True).exists()
    
    def test_login_failed_json(self, api_client):
        url = reverse('login')
        data = {
            'username': 'wronguser',
            'password': 'wrongpass'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['success'] is False
        assert LoginLog.objects.filter(success=False).exists()
    
    def test_logout_view(self, authenticated_client):
        url = reverse('logout')
        response = authenticated_client.post(url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_log_out_view(self, authenticated_client):
        url = reverse('log_out')
        response = authenticated_client.post(url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        from rest_framework.authtoken.models import Token
        assert Token.objects.filter(user=authenticated_client._user).count() == 0
    
    def test_login_with_superuser(self, api_client, superuser):
        url = reverse('login')
        data = {
            'username': superuser.username,
            'password': 'SuperSecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['role'] == 'superadmin'
