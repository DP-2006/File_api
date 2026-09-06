# tests/test_models/test_file_models.py
import pytest
from django.core.files.base import ContentFile

from core.models import UploadedFile, FileActionLog


@pytest.mark.django_db
class TestUploadedFile:
    """تست‌های مدل UploadedFile"""
    
    def test_create_uploaded_file(self, normal_user):
        file_obj = UploadedFile.objects.create(
            uploaded_by=normal_user,
            folder_name='test_folder'
        )
        file_obj.file.save('test.txt', ContentFile('Hello World'), save=True)
        assert file_obj.uploaded_by == normal_user
        assert file_obj.folder_name == 'test_folder'
        assert file_obj.is_deleted is False
    
    def test_file_str(self, normal_user):
        file_obj = UploadedFile.objects.create(uploaded_by=normal_user)
        file_obj.file.save('test_file.txt', ContentFile('content'), save=True)
        assert str(file_obj) == file_obj.file.name
    
    def test_soft_delete_file(self, normal_user):
        file_obj = UploadedFile.objects.create(uploaded_by=normal_user)
        file_obj.file.save('test.txt', ContentFile('content'), save=True)
        file_obj.is_deleted = True
        file_obj.save()
        assert file_obj.is_deleted is True
        active_files = UploadedFile.objects.filter(is_deleted=False)
        assert file_obj not in active_files
    
    def test_send_file_to_user(self, normal_user, staff_user):
        file_obj = UploadedFile.objects.create(
            uploaded_by=normal_user,
            sent_to_user=staff_user
        )
        file_obj.file.save('test.txt', ContentFile('content'), save=True)
        assert file_obj.sent_to_user == staff_user


@pytest.mark.django_db
class TestFileActionLog:
    """تست‌های لاگ عملیات فایل"""
    
    def test_create_action_log(self, normal_user):
        log = FileActionLog.objects.create(
            user=normal_user,
            action='upload',
            file_name='test_file.txt',
            file_size=1024,
            ip_address='192.168.1.1',
            ai_analysis='Safe file',
            threat_level='low'
        )
        assert log.user == normal_user
        assert log.action == 'upload'
        assert log.file_name == 'test_file.txt'
        assert log.threat_level == 'low'
    
    def test_action_log_action_choices(self, normal_user):
        actions = ['download', 'delete', 'upload', 'send']
        for action in actions:
            log = FileActionLog.objects.create(
                user=normal_user,
                action=action,
                file_name='test.txt'
            )
            assert log.action == action
    
    def test_threat_levels(self, normal_user):
        threat_levels = ['low', 'medium', 'high', 'critical']
        for level in threat_levels:
            log = FileActionLog.objects.create(
                user=normal_user,
                action='upload',
                file_name='test.txt',
                threat_level=level
            )
            assert log.threat_level == level
    
    def test_action_log_str(self, normal_user):
        log = FileActionLog.objects.create(
            user=normal_user,
            action='upload',
            file_name='test.txt'
        )
        assert str(log) == f"{normal_user} - upload - test.txt"
    
    def test_action_log_ordering(self, normal_user):
        log1 = FileActionLog.objects.create(
            user=normal_user,
            action='upload',
            file_name='file1.txt'
        )
        log2 = FileActionLog.objects.create(
            user=normal_user,
            action='download',
            file_name='file2.txt'
        )
        logs = FileActionLog.objects.all()
        assert logs[0].action == 'download'
        assert logs[1].action == 'upload'
