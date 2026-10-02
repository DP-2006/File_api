# core/models_report_chat.py
"""
مدل‌های چت‌بات گزارشات (RAG-based) برای پنل ادمین.
ادمین یک جلسه با مجموعه‌ای از فایل‌های انتخاب‌شده باز می‌کند و سوال می‌پرسد.
"""

from django.contrib.auth.models import User
from django.db import models


class ReportChatSession(models.Model):
    """یک جلسه چت بین ادمین و AI روی مجموعه‌ای از فایل‌ها"""

    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='report_chat_sessions',
        verbose_name='ادمین',
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='عنوان جلسه',
    )
    files = models.ManyToManyField(
        'core.UploadedFile',
        related_name='report_chat_sessions',
        blank=True,
        verbose_name='فایل‌های انتخاب‌شده',
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_chat_sessions_about_me',
        verbose_name='کاربر هدف (اختیاری)',
    )
    context_text = models.TextField(
        blank=True,
        default='',
        verbose_name='متن context ارسالی به FastAPI',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='فعال',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'جلسه چت گزارشات'
        verbose_name_plural = 'جلسات چت گزارشات'
        indexes = [
            models.Index(fields=['admin', '-updated_at']),
        ]

    def __str__(self):
        return f"Session #{self.pk} - {self.admin.username} - {self.title or 'بدون عنوان'}"


class ReportChatMessage(models.Model):
    """یک پیام در جلسه چت گزارشات"""

    ROLE_CHOICES = [
        ('user', 'ادمین'),
        ('assistant', 'هوش مصنوعی'),
        ('system', 'سیستم'),
    ]

    session = models.ForeignKey(
        ReportChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='جلسه',
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        verbose_name='نقش',
    )
    content = models.TextField(verbose_name='محتوا')
    ai_response_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='پاسخ کامل FastAPI',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'پیام چت گزارشات'
        verbose_name_plural = 'پیام‌های چت گزارشات'
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.role}] session#{self.session_id} - {self.content[:50]}"