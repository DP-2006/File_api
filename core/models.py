
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100, verbose_name="نام")
    last_name = models.CharField(max_length=100, verbose_name="نام خانوادگی")
    national_code = models.CharField(max_length=10, verbose_name="کد ملی")
    is_blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.user.username
<<<<<<< HEAD
        
=======
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    font_size = models.IntegerField(default=14)
    menu_size = models.IntegerField(default=200)
    button_size = models.IntegerField(default=40)
    
    def __str__(self):
        return f"Settings for {self.user.username}"


class PasswordPolicy(models.Model):
    min_password_length = models.IntegerField(default=8)
    require_uppercase = models.BooleanField(default=True)
    require_digit = models.BooleanField(default=True)
    require_special_char = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "سیاست رمز عبور"
        verbose_name_plural = "سیاست‌های رمز عبور"
    
    def save(self, *args, **kwargs):
        if not self.pk and PasswordPolicy.objects.exists():
            return PasswordPolicy.objects.first().save(update_fields=[])
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return "تنظیمات رمز عبور"

        


class GroupLeader(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='led_groups')
    
    class Meta:
        unique_together = ('group', 'leader')
    
    def __str__(self):
        return f"{self.leader.username} - رهبر گروه {self.group.name}"


class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    folder_name = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    save_to_cloud = models.BooleanField(default=True)
    sent_to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_files'
    )
    
    def __str__(self):
        return self.file.name

<<<<<<< HEAD
=======

# class FileActionLog(models.Model):
#     ACTION_CHOICES = [
#         ('download', 'دانلود'),
#         ('delete', 'حذف'),
#         ('upload', 'آپلود'),
#         ('send', 'ارسال'),
#     ]
    
#     user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
#     action = models.CharField(max_length=20, choices=ACTION_CHOICES)
#     file_name = models.CharField(max_length=255)
#     file_size = models.BigIntegerField(null=True)
#     ip_address = models.GenericIPAddressField(null=True)
#     action_time = models.DateTimeField(auto_now_add=True)
#     recipient_user = models.ForeignKey(
#         User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_file_logs'
#     )
#     details = models.TextField(blank=True, null=True)
    
#     class Meta:
#         ordering = ['-action_time']
    
#     def __str__(self):
#         return f"{self.user} - {self.action} - {self.file_name}"




>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
# core/models.py - به‌روزرسانی FileActionLog

class FileActionLog(models.Model):
    ACTION_CHOICES = [
        ('download', 'دانلود'),
        ('delete', 'حذف'),
        ('upload', 'آپلود'),
        ('send', 'ارسال'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    action_time = models.DateTimeField(auto_now_add=True)
    recipient_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_file_logs'
    )
    details = models.TextField(blank=True, null=True)
    
    # ====== اضافه کردن فیلدهای جدید ======
    ai_analysis = models.TextField(blank=True, null=True, verbose_name='تحلیل AI')
    ai_summary = models.TextField(blank=True, null=True, verbose_name='خلاصه AI')
    threat_level = models.CharField(max_length=20, blank=True, null=True, verbose_name='سطح تهدید')
    is_threat = models.BooleanField(default=False, verbose_name='تهدید است؟')
    
    class Meta:
        ordering = ['-action_time']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.file_name}"


class File(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.file_name


class FileShare(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='shares')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_shares')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_shares')
    shared_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['file', 'to_user']
        ordering = ['-shared_at']
    
    def __str__(self):
        return f"{self.file.file_name} → {self.to_user.username}"


class DownloaderFile(models.Model):
    file = models.FileField(upload_to='downloads/')
    downloaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.file.name


class LoginLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time} - {'Success' if self.success else 'Failed'}"




class AIThreatAlert(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'کم'),
        ('medium', 'متوسط'),
        ('high', 'بالا'),
        ('critical', 'بحرانی'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('reviewed', 'بررسی شده'),
        ('ignored', 'رد شده'),
        ('blocked', 'مسدود شده'),
    ]
    
    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='threat_alerts')
    threat_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    recommended_action = models.CharField(max_length=50)
    ai_raw_response = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "هشدار تهدید AI"
        verbose_name_plural = "هشدارهای تهدید AI"
    
    def __str__(self):
        return f"{self.file.file.name} - {self.severity} - {self.threat_type}"


# اضافه کنید به انتهای core/models.py

class SystemPermission(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "دسترسی سیستمی"
        verbose_name_plural = "دسترسی‌های سیستمی"
    
    def __str__(self):
        return self.name


class UserPermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_permissions')
    permission = models.ForeignKey(SystemPermission, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    
    class Meta:
        unique_together = ('user', 'permission')
    
    def __str__(self):
        return f"{self.user.username} - {self.permission.name}"


class AISettings(models.Model):
    """تنظیمات هوش مصنوعی"""
    ollama_host = models.CharField(max_length=255, default='localhost', verbose_name='آدرس Host')
    ollama_port = models.IntegerField(default=11434, verbose_name='پورت')
    ollama_model = models.CharField(max_length=100, default='gemma3:27b', verbose_name='مدل')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    timeout_seconds = models.IntegerField(default=120, verbose_name='زمان انتظار (ثانیه)')
    max_tokens = models.IntegerField(default=2048, verbose_name='حداکثر توکن‌ها')
    temperature = models.FloatField(default=0.3, verbose_name='دمای خلاقیت')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "تنظیمات هوش مصنوعی"
        verbose_name_plural = "تنظیمات هوش مصنوعی"
    
    def __str__(self):
        return f"AI Settings - {self.ollama_host}:{self.ollama_port}"
    
    def get_full_url(self):
        return f"http://{self.ollama_host}:{self.ollama_port}"
    
    @classmethod
    def get_settings(cls):
        """دریافت یا ایجاد تنظیمات پیش‌فرض"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings



# core/models.py - کامل کردن SystemSettings

class SystemSettings(models.Model):
    # تنظیمات شبکه
    ip_address = models.CharField(max_length=255, default='', blank=True, verbose_name='IP Address')
    subnet_mask = models.CharField(max_length=255, default='', blank=True, verbose_name='Subnet Mask')
    default_gateway = models.CharField(max_length=255, default='', blank=True, verbose_name='Default Gateway')
    primary_dns = models.CharField(max_length=255, default='', blank=True, verbose_name='Primary DNS')
    secondary_dns = models.CharField(max_length=255, default='', blank=True, verbose_name='Secondary DNS')
    
    # تنظیمات سرور Django (فقط نمایشی)
    server_ip = models.CharField(max_length=255, default='127.0.0.1', verbose_name='Server IP')
    server_port = models.IntegerField(default=8000, verbose_name='Server Port')
    allow_remote_access = models.BooleanField(default=False, verbose_name='Allow Remote Access')
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "تنظیمات سیستم"
        verbose_name_plural = "تنظیمات سیستم"
    
    def __str__(self):
        return f"سیستم - {self.ip_address}"
    
    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(pk=1)
        return settings




# ==================== مدل نوتیفیکیشن ====================

class AINotification(models.Model):
    NOTIFICATION_TYPES = [
        ('file_analysis', 'تحلیل فایل'),
        ('threat_detected', 'تهدید شناسایی شده'),
        ('user_analysis', 'تحلیل کاربر'),
        ('system_alert', 'هشدار سیستمی'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'اطلاعاتی'),
        ('warning', 'هشدار'),
        ('critical', 'بحرانی'),
    ]
    
    STATUS_CHOICES = [
        ('unread', 'خوانده نشده'),
        ('read', 'خوانده شده'),
        ('resolved', 'رسیدگی شده'),
    ]
    
    title = models.CharField(max_length=255, verbose_name='عنوان')
    message = models.TextField(verbose_name='پیام')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='file_analysis')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    
    # ارتباط با فایل (اختیاری)
    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='user_notifications')
    
    # کاربری که نوتیفیکیشن برای اوست (ادمین‌ها)
    target_users = models.ManyToManyField(User, related_name='received_notifications', blank=True)
    
    # متادیتا
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # کاربری که نوتیفیکیشن را ایجاد کرده (سیستم یا ادمین)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_notifications')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'نوتیفیکیشن AI'
        verbose_name_plural = 'نوتیفیکیشن‌های AI'
    
    def __str__(self):
        return f"{self.title} - {self.created_at}"
    
    def mark_as_read(self, user):
        self.status = 'read'
        self.read_at = timezone.now()
        self.save()
    
    @classmethod
    def create_file_analysis_notification(cls, file_obj, analysis_result, threat_level='info'):
        """ایجاد نوتیفیکیشن برای تحلیل فایل"""
        # دریافت ادمین‌ها
        admins = User.objects.filter(is_staff=True)
        
        title = f"📄 تحلیل فایل: {file_obj.file.name}"
        
        if threat_level == 'critical':
            severity = 'critical'
            message = f"⚠️ فایل {file_obj.file.name} آپلود شده توسط {file_obj.uploaded_by.username} دارای تهدید بحرانی است!\n\n"
        elif threat_level == 'warning':
            severity = 'warning'
            message = f"⚡ فایل {file_obj.file.name} آپلود شده توسط {file_obj.uploaded_by.username} نیاز به بررسی دارد.\n\n"
        else:
            severity = 'info'
            message = f"📄 فایل {file_obj.file.name} توسط {file_obj.uploaded_by.username} آپلود شد.\n\n"
        
        message += f"📊 نتیجه تحلیل:\n{analysis_result[:500]}..."
        
        notification = cls.objects.create(
            title=title,
            message=message,
            notification_type='file_analysis',
            severity=severity,
            file=file_obj,
            user=file_obj.uploaded_by,
            created_by=None,  # سیستم
        )
        
        notification.target_users.set(admins)
        return notification


class UserActivity(models.Model):
    """مدل ثبت فعالیت‌های کاربر"""
    ACTIVITY_TYPES = [
        ('login', 'ورود'),
        ('logout', 'خروج'),
        ('upload', 'آپلود فایل'),
        ('download', 'دانلود فایل'),
        ('delete', 'حذف فایل'),
        ('view', 'مشاهده'),
        ('edit', 'ویرایش'),
        ('send', 'ارسال فایل'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ارتباط با فایل (اختیاری)
    file = models.ForeignKey(UploadedFile, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'فعالیت کاربر'
        verbose_name_plural = 'فعالیت‌های کاربر'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.created_at}"



class FileSizeSettings(models.Model):
    
    max_upload_size_mb = models.IntegerField(
        default=100,
        verbose_name="حداکثر حجم آپلود (مگابایت)"
    )
    max_download_size_mb = models.IntegerField(
        default=200,
        verbose_name="حداکثر حجم دانلود (مگابایت)"
    )
    warning_threshold_mb = models.IntegerField(
        default=50,
        verbose_name="آستانه هشدار حجم (مگابایت)"
    )
    allow_large_files = models.BooleanField(
        default=True,
        verbose_name="اجازه آپلود فایل‌های بزرگ"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="بروزرسانی توسط"
    )

    class Meta:
        verbose_name = "تنظیمات حجم فایل"
        verbose_name_plural = "تنظیمات حجم فایل"
        db_table = 'file_size_settings'

    def __str__(self):
        return f"حداکثر آپلود: {self.max_upload_size_mb}MB | دانلود: {self.max_download_size_mb}MB"

    @classmethod
    def get_settings(cls):
        """دریافت یا ایجاد تنظیمات پیش‌فرض"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def get_max_upload_bytes(self):
        """دریافت حداکثر حجم آپلود به بایت"""
        return self.max_upload_size_mb * 1024 * 1024

    def get_max_download_bytes(self):
        """دریافت حداکثر حجم دانلود به بایت"""
        return self.max_download_size_mb * 1024 * 1024


<<<<<<< HEAD
=======









>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
# core/models.py - اضافه کردن به انتهای فایل

class RolePasswordPolicy(models.Model):
    """سیاست رمز عبور به ازای هر نقش"""
    role = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='password_policy')
    min_password_length = models.IntegerField(default=8)
    require_uppercase = models.BooleanField(default=True)
    require_digit = models.BooleanField(default=True)
    require_special_char = models.BooleanField(default=False)
    require_lowercase = models.BooleanField(default=True)
    password_expiry_days = models.IntegerField(default=90, null=True, blank=True)
    max_login_attempts = models.IntegerField(default=5, null=True, blank=True)
    
    class Meta:
        verbose_name = "سیاست رمز عبور نقش"
        verbose_name_plural = "سیاست‌های رمز عبور نقش‌ها"
    
    def __str__(self):
        return f"سیاست رمز برای {self.role.name}"


class RoleAssignment(models.Model):
    """مدل اختصاص نقش به کاربر با تاریخ"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('user', 'role')
        verbose_name = "اختصاص نقش"
        verbose_name_plural = "اختصاص نقش‌ها"
    
    def __str__(self):
        return f"{self.user.username} -> {self.role.name}"


class BulkRoleAssignment(models.Model):
    """مدل برای اختصاص نقش به گروهی از کاربران"""
    role = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='bulk_assignments')
    users = models.ManyToManyField(User, related_name='bulk_role_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bulk_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending', 
                             choices=[('pending', 'در انتظار'), ('completed', 'تکمیل شده'), ('failed', 'خطا')])
    total_users = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "اختصاص نقش گروهی"
        verbose_name_plural = "اختصاص نقش‌های گروهی"
    
    def __str__(self):
        return f"{self.role.name} - {self.total_users} کاربر"


class RolePermissionTemplate(models.Model):
    """قالب دسترسی‌های نقش برای ایجاد سریع"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name='templates')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "قالب دسترسی نقش"
        verbose_name_plural = "قالب‌های دسترسی نقش"
    
    def __str__(self):
        return self.name