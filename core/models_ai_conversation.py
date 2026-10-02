from django.db import models
from django.contrib.auth.models import User


class AIConversation(models.Model):

    CONVERSATION_TYPES = [
        ('file_summary', 'خلاصه فایل'),
        ('file_question', 'سوال درباره فایل'),
        ('user_analysis', 'تحلیل کاربر'),
        ('general_ask', 'سوال عمومی'),
        ('manual_analysis', 'تحلیل دستی فایل'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_conversations',
        verbose_name='کاربر'
    )
    file = models.ForeignKey(
        'core.UploadedFile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_conversations',
        verbose_name='فایل مرتبط'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='آی‌پی'
    )
    conversation_type = models.CharField(
        max_length=30,
        choices=CONVERSATION_TYPES,
        default='general_ask',
        verbose_name='نوع گفتگو'
    )
    question = models.TextField(
        blank=True,
        null=True,
        verbose_name='سوال کاربر'
    )
    answer = models.TextField(
        verbose_name='پاسخ هوش مصنوعی'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='زمان'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'گفتگوی هوش مصنوعی'
        verbose_name_plural = 'گفتگوهای هوش مصنوعی'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['conversation_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_conversation_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"