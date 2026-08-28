# core/tests/test_api.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from core.models import Post
from core.factories import UserFactory, PostFactory

# ===================== تست‌های عمومی API =====================
@pytest.mark.django_db
class TestAPIGeneral:
    """تست‌های عمومی API"""
    
    @pytest.fixture
    def api_client(self):
        """کلاینت API"""
        return APIClient()
    
    def test_api_root(self, api_client):
        """تست ریشه API"""
        response = api_client.get('/api/')
        assert response.status_code == status.HTTP_200_OK


# ===================== تست پست‌ها =====================
@pytest.mark.django_db
class TestPostAPI:
    """تست‌های API پست‌ها"""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.fixture
    def authenticated_client(self, api_client, user):
        """کلاینت احراز هویت شده"""
        api_client.force_authenticate(user=user)
        return api_client
    
    def test_list_posts_empty(self, api_client):
        """تست لیست پست‌ها وقتی خالی است"""
        response = api_client.get('/api/posts/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []  # لیست خالی
    
    def test_list_posts_with_data(self, api_client):
        """تست لیست پست‌ها با داده"""
        # ساخت چند پست
        posts = PostFactory.create_batch(3)
        
        response = api_client.get('/api/posts/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        
        # بررسی ساختار داده
        first_post = response.data[0]
        assert 'id' in first_post
        assert 'title' in first_post
        assert 'content' in first_post
        assert 'author' in first_post
    
    def test_create_post_unauthenticated(self, api_client):
        """تست ایجاد پست بدون احراز هویت (باید خطا بدهد)"""
        data = {
            'title': 'پست جدید',
            'content': 'محتوای پست جدید',
            'category': 'tech'
        }
        response = api_client.post('/api/posts/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_create_post_authenticated(self, authenticated_client):
        """تست ایجاد پست با احراز هویت"""
        data = {
            'title': 'پست جدید',
            'content': 'محتوای کامل برای پست جدید',
            'category': 'tech',
            'is_published': True
        }
        response = authenticated_client.post('/api/posts/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == data['title']
        assert response.data['is_published'] == True
        
        # بررسی اینکه نویسنده ذخیره شده است
        post_id = response.data['id']
        post = Post.objects.get(id=post_id)
        assert post.author is not None
    
    def test_create_post_invalid_data(self, authenticated_client):
        """تست ایجاد پست با داده‌های نامعتبر"""
        data = {
            'title': 'تست',  # کمتر از ۵ کاراکتر و شامل 'تست'
            'content': 'کوتاه',  # کمتر از ۱۰ کاراکتر
        }
        response = authenticated_client.post('/api/posts/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'title' in response.data or 'content' in response.data
    
    def test_get_single_post(self, api_client):
        """تست دریافت یک پست"""
        post = PostFactory()
        
        response = api_client.get(f'/api/posts/{post.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == post.id
        assert response.data['title'] == post.title
    
    def test_get_nonexistent_post(self, api_client):
        """تست دریافت پست وجود ندارد"""
        response = api_client.get('/api/posts/999/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_post_author_only(self, authenticated_client, api_client):
        """تست اینکه فقط نویسنده می‌تواند پست را ویرایش کند"""
        # یک کاربر دیگر
        other_user = UserFactory()
        
        # ساخت پست توسط کاربر دیگر
        post = PostFactory(author=other_user)
        
        # تلاش برای ویرایش با کاربر اول (نویسنده نیست)
        data = {'title': 'عنوان جدید'}
        response = authenticated_client.patch(f'/api/posts/{post.id}/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_update_post_by_author(self, api_client, user):
        """تست ویرایش پست توسط نویسنده"""
        # ساخت پست توسط این کاربر
        post = PostFactory(author=user)
        
        # احراز هویت با همان کاربر
        api_client.force_authenticate(user=user)
        
        data = {'title': 'عنوان ویرایش شده'}
        response = api_client.patch(f'/api/posts/{post.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'عنوان ویرایش شده'
    
    def test_update_post_by_admin(self, api_client, admin_user):
        """تست ویرایش پست توسط ادمین"""
        # ساخت پست توسط یک کاربر عادی
        normal_user = UserFactory()
        post = PostFactory(author=normal_user)
        
        # احراز هویت با ادمین
        api_client.force_authenticate(user=admin_user)
        
        data = {'title': 'ویرایش توسط ادمین'}
        response = api_client.patch(f'/api/posts/{post.id}/', data)
        assert response.status_code == status.HTTP_200_OK
    
    def test_delete_post_by_author(self, api_client, user):
        """تست حذف پست توسط نویسنده"""
        post = PostFactory(author=user)
        api_client.force_authenticate(user=user)
        
        response = api_client.delete(f'/api/posts/{post.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Post.objects.filter(id=post.id).exists()
    
    def test_filter_posts_by_category(self, api_client):
        """تست فیلتر پست‌ها بر اساس دسته‌بندی"""
        # ساخت پست‌ها با دسته‌بندی‌های مختلف
        PostFactory(category='tech')
        PostFactory(category='tech')
        PostFactory(category='sport')
        
        response = api_client.get('/api/posts/?category=tech')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        for post in response.data:
            assert post['category'] == 'tech'
    
    def test_pagination(self, api_client):
        """تست صفحه‌بندی API"""
        # ساخت ۲۰ پست
        PostFactory.create_batch(20)
        
        response = api_client.get('/api/posts/?page=1&page_size=5')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) <= 5
        assert 'count' in response.data
        assert response.data['count'] == 20


# ===================== تست ثبت‌نام کاربر =====================
@pytest.mark.django_db
class TestUserRegistrationAPI:
    """تست‌های API ثبت‌نام کاربر"""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    def test_register_user_success(self, api_client):
        """تست ثبت‌نام موفق کاربر"""
        data = {
            'username': 'newuser123',
            'email': 'newuser@example.com',
            'password': 'StrongPass123',
            'first_name': 'علی',
            'last_name': 'محمدی'
        }
        response = api_client.post('/api/register/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == 'newuser123'
        assert User.objects.filter(username='newuser123').exists()
    
    def test_register_user_duplicate_username(self, api_client, user):
        """تست ثبت‌نام با نام کاربری تکراری"""
        data = {
            'username': user.username,  # تکراری
            'email': 'new@example.com',
            'password': 'StrongPass123',
        }
        response = api_client.post('/api/register/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'username' in response.data
    
    def test_register_user_invalid_data(self, api_client):
        """تست ثبت‌نام با داده‌های نامعتبر"""
        data = {
            'username': 'ab',  # کوتاه
            'email': 'invalid-email',  # نامعتبر
            'password': '123',  # کوتاه
        }
        response = api_client.post('/api/register/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'username' in response.data or 'email' in response.data


# ===================== تست احراز هویت =====================
@pytest.mark.django_db
class TestAuthenticationAPI:
    """تست‌های احراز هویت API"""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    def test_login_get_token(self, api_client, user):
        """تست دریافت توکن با لاگین"""
        user.set_password('testpass123')
        user.save()
        
        response = api_client.post('/api/token/', {
            'username': user.username,
            'password': 'testpass123'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_login_wrong_password(self, api_client, user):
        """تست لاگین با رمز اشتباه"""
        user.set_password('testpass123')
        user.save()
        
        response = api_client.post('/api/token/', {
            'username': user.username,
            'password': 'wrongpassword'
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_access_protected_endpoint_with_token(self, api_client, user):
        """تست دسترسی به endpoint محافظت شده با توکن"""
        user.set_password('testpass123')
        user.save()
        
        # گرفتن توکن
        token_response = api_client.post('/api/token/', {
            'username': user.username,
            'password': 'testpass123'
        })
        token = token_response.data['access']
        
        # دسترسی با توکن
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = api_client.get('/api/protected/')
        assert response.status_code == status.HTTP_200_OK


# ===================== تست API با پارامتری کردن =====================
@pytest.mark.django_db
class TestAPIParametrized:
    """تست‌های پارامتری API"""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.mark.parametrize("method,url,expected_status", [
        ('GET', '/api/posts/', 200),
        ('POST', '/api/posts/', 403),  # بدون احراز هویت
        ('GET', '/api/posts/1/', 200),
        ('PATCH', '/api/posts/1/', 403),
        ('DELETE', '/api/posts/1/', 403),
    ])
    def test_api_endpoints_status(self, api_client, method, url, expected_status):
        """تست وضعیت endpoints مختلف"""
        if method == 'GET':
            response = api_client.get(url)
        elif method == 'POST':
            response = api_client.post(url, {})
        elif method == 'PATCH':
            response = api_client.patch(url, {})
        elif method == 'DELETE':
            response = api_client.delete(url)
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize("category,count", [
        ('tech', 3),
        ('sport', 2),
        ('art', 0),
    ])
    def test_filter_by_category(self, api_client, category, count):
        """تست فیلتر بر اساس دسته‌بندی"""
        # ساخت داده‌های تست
        PostFactory(category='tech')
        PostFactory(category='tech')
        PostFactory(category='tech')
        PostFactory(category='sport')
        PostFactory(category='sport')
        
        response = api_client.get(f'/api/posts/?category={category}')
        assert response.status_code == 200
        assert len(response.data) == count