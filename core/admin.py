# core/admin.py

from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    UserSettings, 
    UserProfile, 
    PasswordPolicy, 
    GroupLeader, 
    FileActionLog,
    UploadedFile
)


# سفارشی‌سازی User Profile Inline
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'پروفایل کاربر'


# سفارشی‌سازی User Admin
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'get_groups')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = 'نقش‌ها'
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email')}),
        ('دسترسی‌ها', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('تاریخ‌ها', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'groups'),
        }),
    )
    
    filter_horizontal = ('groups', 'user_permissions',)


# ثبت مدل‌ها در ادمین
@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'font_size', 'menu_size', 'button_size')
    search_fields = ('user__username',)


@admin.register(PasswordPolicy)
class PasswordPolicyAdmin(admin.ModelAdmin):
    list_display = ('min_password_length', 'require_uppercase', 'require_digit', 'require_special_char')
    
    def has_add_permission(self, request):
        if PasswordPolicy.objects.exists():
            return False
        return True


@admin.register(GroupLeader)
class GroupLeaderAdmin(admin.ModelAdmin):
    list_display = ('group', 'leader')  
    list_filter = ('group',)
    search_fields = ('group__name', 'leader__username')


@admin.register(FileActionLog)
class FileActionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'file_name', 'action_time', 'ip_address')
    list_filter = ('action', 'action_time')
    search_fields = ('user__username', 'file_name')
    readonly_fields = ('user', 'action', 'file_name', 'file_size', 'ip_address', 'action_time', 'recipient_user', 'details')


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('file', 'uploaded_by', 'uploaded_at', 'folder_name', 'is_deleted')
    list_filter = ('is_deleted', 'uploaded_at', 'folder_name')
    search_fields = ('file', 'uploaded_by__username', 'folder_name')
    readonly_fields = ('uploaded_at',)


# ثبت User Admin سفارشی
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)