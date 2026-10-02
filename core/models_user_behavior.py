from django.db import models
from django.contrib.auth.models import User


class UserBehaviorAnalysis(models.Model):
    """تحلیل رفتار کاربر بر اساس سوابق فایل‌ها و موضوعات"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='behavior_analysis',
        verbose_name='کاربر'
    )

    # JSON کامل تحلیل
    analysis_json = models.JSONField(default=dict, verbose_name='تحلیل کامل JSON')

    # خلاصه‌های کلیدی
    total_files = models.IntegerField(default=0, verbose_name='تعداد کل فایل‌ها')
    related_files_count = models.IntegerField(default=0, verbose_name='فایل‌های مرتبط')
    unrelated_files_count = models.IntegerField(default=0, verbose_name='فایل‌های غیرمرتبط')
    suspicious_files_count = models.IntegerField(default=0, verbose_name='فایل‌های مشکوک')

    relevance_avg = models.FloatField(default=0.0, verbose_name='میانگین relevance')
    related_percent = models.FloatField(default=0.0, verbose_name='درصد مرتبط')
    suspicious_percent = models.FloatField(default=0.0, verbose_name='درصد مشکوک')

    # موضوعات غالب (لیست)
    top_topics = models.JSONField(
        default=list,
        verbose_name='موضوعات غالب (top 5)',
        help_text='[{"name": "...", "count": N, "weight": 0.8}, ...]'
    )

    # توزیع انواع فایل
    file_types_distribution = models.JSONField(
        default=dict,
        verbose_name='توزیع انواع فایل',
        help_text='{"pdf": 10, "txt": 3, ...}'
    )

    # خلاصه متنی از تحلیل LLM
    ai_summary = models.TextField(blank=True, null=True, verbose_name='خلاصه تحلیل AI')

    last_analyzed_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تحلیل')

    class Meta:
        verbose_name = 'تحلیل رفتار کاربر'
        verbose_name_plural = 'تحلیل‌های رفتار کاربران'
        indexes = [
            models.Index(fields=['-last_analyzed_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.total_files} فایل - {self.related_percent:.1f}% مرتبط"