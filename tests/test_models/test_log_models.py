# tests/test_models/test_log_models.py
import pytest
from django.utils import timezone

from core.models import AINotification, AIThreatAlert


@pytest.mark.django_db
class TestAINotification:
    """تست‌های نوتیفیکیشن‌های AI"""
    
    def test_create_notification(self, normal_user, test_file):
        notif = AINotification.objects.create(
            title='Test Notification',
            message='This is a test message',
            notification_type='file_analysis',
            severity='info',
            status='unread',
            file=test_file,
            user=normal_user
        )
        notif.target_users.set([normal_user])
        assert notif.title == 'Test Notification'
        assert notif.severity == 'info'
        assert notif.status == 'unread'
        assert notif.target_users.count() == 1
    
    def test_mark_as_read(self, normal_user, test_file):
        notif = AINotification.objects.create(
            title='Test',
            message='Test message',
            file=test_file,
            user=normal_user
        )
        notif.target_users.set([normal_user])
        notif.mark_as_read(normal_user)
        assert notif.status == 'read'
        assert notif.read_at is not None
    
    def test_notification_str(self, normal_user):
        notif = AINotification.objects.create(
            title='Test Notification',
            message='Message',
            user=normal_user
        )
        assert str(notif) == f"Test Notification - {notif.created_at}"


@pytest.mark.django_db
class TestAIThreatAlert:
    """تست‌های هشدارهای تهدید"""
    
    def test_create_threat_alert(self, test_file):
        alert = AIThreatAlert.objects.create(
            file=test_file,
            threat_type='malware',
            severity='high',
            description='Potential malware detected',
            recommended_action='quarantine',
            ai_raw_response='Raw AI response',
            status='pending'
        )
        assert alert.file == test_file
        assert alert.threat_type == 'malware'
        assert alert.severity == 'high'
        assert alert.status == 'pending'
    
    def test_alert_severity_choices(self, test_file):
        severities = ['low', 'medium', 'high', 'critical']
        for severity in severities:
            alert = AIThreatAlert.objects.create(
                file=test_file,
                threat_type='test',
                severity=severity,
                description='Test',
                recommended_action='none',
                ai_raw_response='test'
            )
            assert alert.severity == severity
    
    def test_alert_status_choices(self, test_file):
        statuses = ['pending', 'reviewed', 'ignored', 'blocked']
        for status in statuses:
            alert = AIThreatAlert.objects.create(
                file=test_file,
                threat_type='test',
                severity='low',
                description='Test',
                recommended_action='none',
                ai_raw_response='test',
                status=status
            )
            assert alert.status == status
    
    def test_alert_str(self, test_file):
        alert = AIThreatAlert.objects.create(
            file=test_file,
            threat_type='malware',
            severity='high',
            description='Test',
            recommended_action='none',
            ai_raw_response='test'
        )
        assert str(alert) == f"{test_file.file.name} - high - malware"
    
    def test_review_alert(self, test_file, staff_user):
        alert = AIThreatAlert.objects.create(
            file=test_file,
            threat_type='test',
            severity='low',
            description='Test',
            recommended_action='none',
            ai_raw_response='test',
            status='pending'
        )
        alert.status = 'reviewed'
        alert.reviewed_by = staff_user
        alert.reviewed_at = timezone.now()
        alert.save()
        assert alert.status == 'reviewed'
        assert alert.reviewed_by == staff_user
        assert alert.reviewed_at is not None