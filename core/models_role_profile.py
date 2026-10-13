from django.contrib.auth.models import Group, User
from django.db import models

class RoleProfile(models.Model):

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='role_profile',
        verbose_name='نقش (گروه)',
    )
    title_fa = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='عنوان فارسی سمت',
        help_text='مثلاً: مدیر مالی، کارشناس منابع انسانی',
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='شرح حال سمت',
        help_text='توضیح کلی درباره این سمت و جایگاه آن در سازمان',
    )
    responsibilities = models.TextField(
        blank=True,
        null=True,
        verbose_name='وظایف',
        help_text='فهرست وظایف این سمت (هر وظیفه در یک خط)',
    )
    role_prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name='متن ارسالی به AI',
        help_text='اگر خالی باشد، از description + responsibilities ساخته می‌شود',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='فعال',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین ویرایش')

    class Meta:
        verbose_name = 'پروفایل نقش سازمانی'
        verbose_name_plural = 'پروفایل نقش‌های سازمانی'

    def __str__(self):
        return f"{self.group.name} - {self.title_fa or '—'}"

    def get_effective_role_text(self):
        """متن نهایی برای ارسال به FastAPI"""
        if self.role_prompt:
            return self.role_prompt.strip()

        parts = []
        if self.title_fa:
            parts.append(f"عنوان سمت: {self.title_fa}")
        if self.description:
            parts.append(f"شرح حال: {self.description}")
        if self.responsibilities:
            parts.append(f"وظایف:\n{self.responsibilities}")
        return "\n\n".join(parts).strip()


class RoleFileAccess(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='role_file_accesses',
        verbose_name='نقش (گروه)',
    )
    uploaded_file = models.ForeignKey(
        'core.UploadedFile',
        on_delete=models.CASCADE,
        related_name='role_accesses',
        verbose_name='فایل',
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_role_file_accesses',
        verbose_name='اعطاکننده',
    )
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان اعطا')
    note = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='یادداشت',
    )

    class Meta:
        unique_together = ('group', 'uploaded_file')
        ordering = ['-granted_at']
        verbose_name = 'دسترسی فایل به نقش'
        verbose_name_plural = 'دسترسی‌های فایل به نقش‌ها'
        indexes = [
            models.Index(fields=['group', '-granted_at']),
        ]

    def __str__(self):
        return f"{self.group.name} → {self.uploaded_file.file.name}"