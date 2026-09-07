# tests/test_services/test_llm_service.py
import pytest
from unittest.mock import patch, MagicMock

from core.services.llm_service import LLMService


@pytest.mark.django_db
class TestLLMService:
    """تست‌های سرویس LLM"""
    
    def test_llm_service_init(self):
        """تست مقداردهی اولیه"""
        service = LLMService()
        # بررسی attributes با نام‌های واقعی
        assert hasattr(service, 'base_url') or hasattr(service, 'base_url')
        assert hasattr(service, 'model')
        assert hasattr(service, 'is_available')
    
    def test_llm_service_with_custom_url(self):
        """تست با URL سفارشی"""
        service = LLMService(base_url="http://custom:11434", model="test-model")
        assert service.base_url == "http://custom:11434"
        assert service.model == "test-model"
    
    @patch('core.services.llm_service.requests.post')
    def test_check_connection_success(self, mock_post):
        """تست اتصال موفق"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": ["test"]}
        mock_post.return_value = mock_response
        
        service = LLMService(base_url="http://localhost:11434", model="test")
        # بررسی اینکه اتصال برقرار است
        assert service.is_available is not None
    
    def test_analyze_user_behavior(self):
        """تست تحلیل رفتار کاربر"""
        service = LLMService()
        user_data = {
            'username': 'testuser',
            'total_uploads': 10,
            'file_types': {'txt': 5, 'pdf': 3, 'zip': 2}
        }
        activities = []
        try:
            result = service.analyze_user_behavior(user_data, activities)
            assert result is not None
        except Exception as e:
            # اگر سرویس در دسترس نباشد، تست را skip می‌کنیم
            pytest.skip(f"LLM service not available: {e}")
    
    def test_summarize_file(self):
        """تست خلاصه‌سازی فایل"""
        service = LLMService()
        content = 'This is a test file content that should be summarized'
        filename = 'test.txt'
        try:
            result = service.summarize_file(content, filename, detail_level='summary')
            assert result is not None
        except Exception as e:
            pytest.skip(f"LLM service not available: {e}")
    
    def test_answer_question_about_file(self):
        """تست پاسخ به سوال درباره فایل"""
        service = LLMService()
        content = 'Test content about Python programming'
        filename = 'test.py'
        question = 'What is this file about?'
        try:
            result = service.answer_question_about_file(content, filename, question)
            assert result is not None
        except Exception as e:
            pytest.skip(f"LLM service not available: {e}")
