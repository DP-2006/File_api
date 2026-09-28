import uuid
from django.db import models
from django.contrib.auth.models import User


class ScanJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('running', 'در حال اجرا'),
        ('completed', 'تکمیل شده'),
        ('failed', 'خطا'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    file_hash_sha256 = models.CharField(max_length=64, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    final_score = models.IntegerField(default=0)
    is_threat = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, default='clean')
    verdict = models.CharField(max_length=200, blank=True)

    celery_task_id = models.CharField(max_length=100, blank=True, db_index=True)
    completed_engines = models.IntegerField(default=0)
    total_engines = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='av_scans')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'اسکن Multi-AV'
        verbose_name_plural = 'اسکن‌های Multi-AV'

    def __str__(self):
        return f"{self.file_name} - {self.final_score} - {self.severity}"


class EngineResult(models.Model):
    scan = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name='engine_results')
    engine_name = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    threat = models.BooleanField(default=False)
    details = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['engine_name']
        unique_together = ('scan', 'engine_name')
        verbose_name = 'نتیجه موتور'
        verbose_name_plural = 'نتایج موتورها'

    def __str__(self):
        return f"{self.scan.file_name} - {self.engine_name} - {self.score}"


class EngineStatus(models.Model):
    engine_name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=False)
    version = models.CharField(max_length=100, blank=True)
    last_check = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = 'وضعیت موتور'
        verbose_name_plural = 'وضعیت موتورها'

    def __str__(self):
        return f"{self.engine_name} - {'active' if self.is_active else 'inactive'}"