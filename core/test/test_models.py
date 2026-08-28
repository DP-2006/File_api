import pytest
from core.models import YourModel  # اسم مدل خود را بگذارید

@pytest.mark.django_db
class TestModels:
    def test_create_object(self):
        # obj = YourModel.objects.create(name="test")
        # assert obj.name == "test"
        assert True  # فعلاً تست را پاس می‌کند