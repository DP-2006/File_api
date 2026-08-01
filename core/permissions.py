# # core/permissions.py

# from django.core.exceptions import PermissionDenied
# from functools import wraps
# from .models import SystemPermission, UserPermission
# # تعریف تمام دسترسی‌های سیستم
# SYSTEM_PERMISSIONS = {

#     # دسترسی‌های کاربر
#     'view_dashboard': {'name': 'مشاهده داشبورد', 'description': 'دسترسی به داشبورد اصلی'},
#     'upload_file': {'name': 'آپلود فایل', 'description': 'امکان آپلود فایل'},
#     'download_file': {'name': 'دانلود فایل', 'description': 'امکان دانلود فایل'},
#     'delete_own_file': {'name': 'حذف فایل خود', 'description': 'حذف فایل‌های آپلود شده توسط خود'},
    
#     # دسترسی‌های ادمین
#     'view_users': {'name': 'مشاهده کاربران', 'description': 'دیدن لیست کاربران'},
#     'create_user': {'name': 'ایجاد کاربر', 'description': 'ایجاد کاربر جدید'},
#     'edit_user': {'name': 'ویرایش کاربر', 'description': 'ویرایش اطلاعات کاربران'},
#     'delete_user': {'name': 'حذف کاربر', 'description': 'حذف کاربران (به جز خود)'},
#     'block_user': {'name': 'مسدود کردن کاربر', 'description': 'مسدود کردن کاربران (به جز خود)'},
#     'change_password': {'name': 'تغییر رمز کاربر', 'description': 'تغییر رمز عبور کاربران'},
#     'assign_role': {'name': 'اختصاص نقش', 'description': 'اختصاص نقش به کاربران'},
    
#     # دسترسی‌های مدیریت گروه
#     'create_role': {'name': 'ایجاد نقش', 'description': 'ایجاد نقش جدید'},
#     'edit_role': {'name': 'ویرایش نقش', 'description': 'ویرایش نقش‌ها'},
#     'delete_role': {'name': 'حذف نقش', 'description': 'حذف نقش‌ها'},
#     'assign_group_leader': {'name': 'تعیین رهبر گروه', 'description': 'تعیین رهبر برای گروه‌ها'},
    
#     # دسترسی‌های هوش مصنوعی
#     'ai_analyze_file': {'name': 'تحلیل فایل با AI', 'description': 'استفاده از AI برای تحلیل فایل'},
#     'ai_analyze_user': {'name': 'تحلیل کاربر با AI', 'description': 'تحلیل رفتار کاربر با AI'},
#     'view_ai_alerts': {'name': 'مشاهده هشدارهای AI', 'description': 'دیدن هشدارهای امنیتی AI'},
#     'resolve_ai_alerts': {'name': 'رفع هشدارهای AI', 'description': 'بررسی و رفع هشدارهای AI'},
    
#     # دسترسی‌های سوپر ادمین
#     'super_admin_access': {'name': 'دسترسی سوپر ادمین', 'description': 'تمام دسترسی‌های سیستمی'},

# }




# def check_permission(permission_code):
#     """دکوراتور برای بررسی دسترسی"""
#     def decorator(view_func):
#         @wraps(view_func)
#         def wrapped(request, *args, **kwargs):
#             if not has_permission(request.user, permission_code):
#                 raise PermissionDenied("شما دسترسی لازم را ندارید")
#             return view_func(request, *args, **kwargs)
#         return wrapped
#     return decorator




# def has_permission(user, permission_code):
#     """بررسی دسترسی کاربر (مستقیم یا از طریق گروه)"""
#     if user.is_superuser:
#         return True
    
#     # بررسی دسترسی مستقیم
    
#     try:
#         perm = SystemPermission.objects.get(code=permission_code)
#         if UserPermission.objects.filter(user=user, permission=perm).exists():
#             return True
#     except SystemPermission.DoesNotExist:
#         pass
    
#     # بررسی دسترسی از طریق گروه‌ها
#     required_perm_name = SYSTEM_PERMISSIONS.get(permission_code, {}).get('name', '')
#     if required_perm_name:
#         for group in user.groups.all():
#             if group.permissions.filter(codename=permission_code).exists():
#                 return True
    
#     return False


# def get_user_permissions_list(user):
#     """دریافت لیست تمام دسترسی‌های کاربر"""
#     permissions = []
    
#     if user.is_superuser:
#         return list(SYSTEM_PERMISSIONS.keys())
    
#     # دسترسی‌های مستقیم
#     from .models import SystemPermission, UserPermission
#     direct_perms = UserPermission.objects.filter(user=user).select_related('permission')
#     permissions.extend([p.permission.code for p in direct_perms])
    
#     # دسترسی‌های گروه
#     for group in user.groups.all():
#         group_perms = group.permissions.all()
#         permissions.extend([p.codename for p in group_perms])
    
#     return list(set(permissions))


# def can_modify_user(admin_user, target_user):
#     """بررسی اینکه آیا ادمین می‌تواند کاربر دیگری را修改 کند"""
#     # نمی‌تواند خودش  کند
#     if admin_user.id == target_user.id:
#         return False
    
#     # سوپر ادمین می‌تواند همه  کند
#     if admin_user.is_superuser:
#         return True
    
#     # ادمین عادی نمی‌تواند سوپر ادمین  کند
#     if target_user.is_superuser:
#         return False
    
#     return has_permission(admin_user, 'edit_user')




from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import SystemPermission, UserPermission
from rest_framework import permissions  # <--- این رو اضافه کن

# تعریف تمام دسترسی‌های سیستم
SYSTEM_PERMISSIONS = {

    # دسترسی‌های کاربر
    'view_dashboard': {'name': 'مشاهده داشبورد', 'description': 'دسترسی به داشبورد اصلی'},
    'upload_file': {'name': 'آپلود فایل', 'description': 'امکان آپلود فایل'},
    'download_file': {'name': 'دانلود فایل', 'description': 'امکان دانلود فایل'},
    'delete_own_file': {'name': 'حذف فایل خود', 'description': 'حذف فایل‌های آپلود شده توسط خود'},
    
    # دسترسی‌های ادمین
    'view_users': {'name': 'مشاهده کاربران', 'description': 'دیدن لیست کاربران'},
    'create_user': {'name': 'ایجاد کاربر', 'description': 'ایجاد کاربر جدید'},
    'edit_user': {'name': 'ویرایش کاربر', 'description': 'ویرایش اطلاعات کاربران'},
    'delete_user': {'name': 'حذف کاربر', 'description': 'حذف کاربران (به جز خود)'},
    'block_user': {'name': 'مسدود کردن کاربر', 'description': 'مسدود کردن کاربران (به جز خود)'},
    'change_password': {'name': 'تغییر رمز کاربر', 'description': 'تغییر رمز عبور کاربران'},
    'assign_role': {'name': 'اختصاص نقش', 'description': 'اختصاص نقش به کاربران'},
    
    # دسترسی‌های مدیریت گروه
    'create_role': {'name': 'ایجاد نقش', 'description': 'ایجاد نقش جدید'},
    'edit_role': {'name': 'ویرایش نقش', 'description': 'ویرایش نقش‌ها'},
    'delete_role': {'name': 'حذف نقش', 'description': 'حذف نقش‌ها'},
    'assign_group_leader': {'name': 'تعیین رهبر گروه', 'description': 'تعیین رهبر برای گروه‌ها'},
    
    # دسترسی‌های هوش مصنوعی
    'ai_analyze_file': {'name': 'تحلیل فایل با AI', 'description': 'استفاده از AI برای تحلیل فایل'},
    'ai_analyze_user': {'name': 'تحلیل کاربر با AI', 'description': 'تحلیل رفتار کاربر با AI'},
    'view_ai_alerts': {'name': 'مشاهده هشدارهای AI', 'description': 'دیدن هشدارهای امنیتی AI'},
    'resolve_ai_alerts': {'name': 'رفع هشدارهای AI', 'description': 'بررسی و رفع هشدارهای AI'},
    
    # دسترسی‌های سوپر ادمین
    'super_admin_access': {'name': 'دسترسی سوپر ادمین', 'description': 'تمام دسترسی‌های سیستمی'},

}


def check_permission(permission_code):
    """دکوراتور برای بررسی دسترسی"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_permission(request.user, permission_code):
                raise PermissionDenied("شما دسترسی لازم را ندارید")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def has_permission(user, permission_code):
    """بررسی دسترسی کاربر (مستقیم یا از طریق گروه)"""
    if user.is_superuser:
        return True
    
    # بررسی دسترسی مستقیم
    try:
        perm = SystemPermission.objects.get(code=permission_code)
        if UserPermission.objects.filter(user=user, permission=perm).exists():
            return True
    except SystemPermission.DoesNotExist:
        pass
    
    # بررسی دسترسی از طریق گروه‌ها
    required_perm_name = SYSTEM_PERMISSIONS.get(permission_code, {}).get('name', '')
    if required_perm_name:
        for group in user.groups.all():
            if group.permissions.filter(codename=permission_code).exists():
                return True
    
    return False


def get_user_permissions_list(user):
    """دریافت لیست تمام دسترسی‌های کاربر"""
    permissions_list = []
    
    if user.is_superuser:
        return list(SYSTEM_PERMISSIONS.keys())
    
    # دسترسی‌های مستقیم
    direct_perms = UserPermission.objects.filter(user=user).select_related('permission')
    permissions_list.extend([p.permission.code for p in direct_perms])
    
    # دسترسی‌های گروه
    for group in user.groups.all():
        group_perms = group.permissions.all()
        permissions_list.extend([p.codename for p in group_perms])
    
    return list(set(permissions_list))


def can_modify_user(admin_user, target_user):
    """بررسی اینکه آیا ادمین می‌تواند کاربر دیگری را修改 کند"""
    # نمی‌تواند خودش را修改 کند
    if admin_user.id == target_user.id:
        return False
    
    # سوپر ادمین می‌تواند همه را修改 کند
    if admin_user.is_superuser:
        return True
    
    # ادمین عادی نمی‌تواند سوپر ادمین را修改 کند
    if target_user.is_superuser:
        return False
    
    return has_permission(admin_user, 'edit_user')


# ============================================================
# ============ کلاس‌های Permission برای DRF ============
# ============================================================

class IsSuperUser(permissions.BasePermission):
    """فقط سوپرادمین"""
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_superuser


class IsStaffOrAdmin(permissions.BasePermission):
    """کارکنان یا ادمین‌ها"""
    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_superuser)
    
    def has_object_permission(self, request, view, obj):
        return request.user and (request.user.is_staff or request.user.is_superuser)


class IsOwnerOrStaff(permissions.BasePermission):
    """مالک فایل یا کارکنان"""
    def has_object_permission(self, request, view, obj):
        # اگر کاربر کارمند یا سوپرادمین باشه
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # بررسی مالکیت
        if hasattr(obj, 'uploaded_by'):
            return obj.uploaded_by == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class HasSystemPermission(permissions.BasePermission):
    """بررسی دسترسی سیستمی با کد"""
    def __init__(self, permission_code):
        self.permission_code = permission_code
    
    def has_permission(self, request, view):
        return has_permission(request.user, self.permission_code)
    
    def has_object_permission(self, request, view, obj):
        return has_permission(request.user, self.permission_code)