from django.contrib.auth.models import User
from django.db import models


class RoleProfile(models.Model):
    code = models.SlugField(max_length=80, unique=True, null=True, blank=True, verbose_name='کد یکتای سمت')
    title_fa = models.CharField(max_length=150, null=True, blank=True, verbose_name='عنوان فارسی سمت')
    description = models.TextField(blank=True, null=True, verbose_name='شرح حال سمت')
    responsibilities = models.TextField(blank=True, null=True, verbose_name='وظایف')
    role_prompt = models.TextField(blank=True, null=True, verbose_name='متن ارسالی به AI')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سمت سازمانی'
        verbose_name_plural = 'سمت‌های سازمانی'
        ordering = ['title_fa']

    def __str__(self):
        return f"{self.title_fa or '—'} ({self.code or '—'})"

    def get_effective_role_text(self):
        if self.role_prompt:
            return self.role_prompt.strip()
        parts = [f"سمت سازمانی: {self.title_fa or '—'}"]
        if self.description:
            parts.append(f"شرح حال: {self.description}")
        if self.responsibilities:
            parts.append(f"وظایف:\n{self.responsibilities}")
        return "\n\n".join(parts).strip()


class UserRoleProfile(models.Model):
    """اتصال چند-به-چند بین کاربر و سمت‌های سازمانی (یک کاربر می‌تواند چند سمت داشته باشد)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_roles')
    role_profile = models.ForeignKey(RoleProfile, on_delete=models.CASCADE, related_name='users')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_role_profiles')

    class Meta:
        unique_together = ('user', 'role_profile')
        verbose_name = 'سمت سازمانی کاربر'
        verbose_name_plural = 'سمت‌های سازمانی کاربران'

    def __str__(self):
        return f"{self.user.username} → {self.role_profile.title_fa if self.role_profile else '—'}"


class RoleFileAccess(models.Model):
    role_profile = models.ForeignKey(RoleProfile, on_delete=models.CASCADE, related_name='file_accesses', null=True, blank=True)
    uploaded_file = models.ForeignKey('core.UploadedFile', on_delete=models.CASCADE, related_name='role_accesses', null=True, blank=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_role_file_accesses')
    granted_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'دسترسی فایل به سمت'
        verbose_name_plural = 'دسترسی‌های فایل به سمت‌ها'

    def __str__(self):
        return f"{self.role_profile.title_fa if self.role_profile else '—'}"