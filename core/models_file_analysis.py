from django.db import models
from django.contrib.auth.models import User


class FileAIAnalysis(models.Model):

    file = models.OneToOneField(
        'core.UploadedFile',
        on_delete=models.CASCADE,
        related_name='ai_analysis',
        verbose_name='فایل'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='file_analyses',
        verbose_name='کاربر'
    )

    analysis_json = models.JSONField(
        default=dict,
        verbose_name='تحلیل کامل JSON'
    )

    summary = models.TextField(blank=True, null=True, verbose_name='خلاصه')
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name='دسته')
    threat_level = models.CharField(
        max_length=20,
        default='low',
        choices=[('low', 'کم'), ('medium', 'متوسط'), ('high', 'بالا'), ('critical', 'بحرانی')],
        verbose_name='سطح تهدید'
    )
    relevance_score = models.FloatField(default=0.0, verbose_name='امتیاز مرتبط بودن با نقش')
    is_related = models.BooleanField(default=True, verbose_name='مرتبط با کاربر؟')
    user_role_at_upload = models.CharField(max_length=100, blank=True, null=True, verbose_name='نقش کاربر در زمان آپلود')
    top_topic = models.CharField(max_length=255, blank=True, null=True, verbose_name='موضوع غالب')

    model_used = models.CharField(max_length=100, blank=True, null=True, verbose_name='مدل استفاده‌شده')
    analyzed_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان تحلیل')

    class Meta:
        ordering = ['-analyzed_at']
        verbose_name = 'تحلیل فایل'
        verbose_name_plural = 'تحلیل‌های فایل'
        indexes = [
            models.Index(fields=['user', '-analyzed_at']),
            models.Index(fields=['is_related', '-analyzed_at']),
            models.Index(fields=['threat_level']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.file.file.name if self.file and self.file.file else 'file'} - {self.category or '—'}"