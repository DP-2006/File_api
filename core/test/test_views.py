import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestViews:
    def test_home_page(self, client):
        response = client.get('/')
        assert response.status_code == 200
    
    def test_login_page(self, client):
        response = client.get('/admin/login/')
        # اگر صفحه admin را دارید
        assert response.status_code in [200, 302]