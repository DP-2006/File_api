# tests/test_services/test_llm_service.py
import pytest
from unittest.mock import patch, MagicMock

from core.services.llm_service import LLMService


@pytest.mark.django_db
class TestLLMService:
    """تست‌های سرویس LLM"""
    
    def test_llm_service_init(self):
        service = LLMService()
        assert service.host is not None
        assert service.port is not None
        assert service.model is not None
    
    def test_analyze_user_behavior(self):
        service = LLMService()
        user_data = {
            'username': 'testuser',
            'total_uploads': 10,
            'file_types': {'txt': 5, 'pdf': 3, 'zip': 2}
        }
        activities = []
        result = service.analyze_user_behavior(user_data, activities)
        assert result is not None
    
    def test_analyze_user_personality(self):
        service = LLMService()
        user_data = {'username': 'testuser', 'total_uploads': 5}
        content = 'Sample file content for analysis'
        result = service.analyze_user_personality(user_data, content)
        assert result is not None
    
    def test_summarize_file(self):
        service = LLMService()
        content = 'This is a test file content that should be summarized'
        filename = 'test.txt'
        result = service.summarize_file(content, filename, detail_level='summary')
        assert result is not None
    
    def test_answer_question_about_file(self):
        service = LLMService()
        content = 'Test content about Python programming'
        filename = 'test.py'
        question = 'What is this file about?'
        result = service.answer_question_about_file(content, filename, question)
        assert result is not None
