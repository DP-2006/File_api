# core/views_management.py

from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.core.paginator import Paginator

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import (
    UserProfile, RolePasswordPolicy, RoleAssignment, 
    BulkRoleAssignment, PasswordPolicy
)

from .permissions import has_permission


# =============================================
# ============ ROLE MANAGEMENT ADVANCED ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_role_advanced_api(request):
    """ایجاد نقش با دسترسی‌ها و سیاست رمز عبور"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        role_name = data.get('name', '').strip()
        permissions_ids = data.get('permissions', [])
        
        # سیاست رمز عبور
        password_policy = data.get('password_policy', {})
        
        if not role_name:
            return Response({'success': False, 'msg': 'نام نقش نمی‌تواند خالی باشد'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if Group.objects.filter(name=role_name).exists():
            return Response({'success': False, 'msg': 'نقش با این نام قبلاً وجود دارد'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # ایجاد نقش
        role = Group.objects.create(name=role_name)
        
        # اختصاص دسترسی‌ها
        if permissions_ids:
            permissions = Permission.objects.filter(id__in=permissions_ids)
            role.permissions.set(permissions)
        
        # ایجاد سیاست رمز عبور مخصوص نقش
        if password_policy:
            RolePasswordPolicy.objects.create(
                role=role,
                min_password_length=password_policy.get('min_length', 8),
                require_uppercase=password_policy.get('require_uppercase', True),
                require_digit=password_policy.get('require_digit', True),
                require_special_char=password_policy.get('require_special_char', False),
                require_lowercase=password_policy.get('require_lowercase', True),
                password_expiry_days=password_policy.get('expiry_days', 90),
                max_login_attempts=password_policy.get('max_attempts', 5)
            )
        
        return Response({
            'success': True,
            'msg': f'نقش {role_name} با موفقیت ایجاد شد',
            'role': {
                'id': role.id,
                'name': role.name,
                'permissions': [{'id': p.id, 'name': p.name} for p in role.permissions.all()],
                'password_policy': {
                    'min_length': password_policy.get('min_length', 8),
                    'require_uppercase': password_policy.get('require_uppercase', True),
                    'require_digit': password_policy.get('require_digit', True),
                } if password_policy else None
            }
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_role_password_policy_api(request, role_id):
    """دریافت سیاست رمز عبور یک نقش"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = get_object_or_404(Group, id=role_id)
        policy, created = RolePasswordPolicy.objects.get_or_create(role=role)
        
        return Response({
            'success': True,
            'policy': {
                'min_password_length': policy.min_password_length,
                'require_uppercase': policy.require_uppercase,
                'require_digit': policy.require_digit,
                'require_special_char': policy.require_special_char,
                'require_lowercase': policy.require_lowercase,
                'password_expiry_days': policy.password_expiry_days,
                'max_login_attempts': policy.max_login_attempts
            }
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_role_password_policy_api(request, role_id):
    """به‌روزرسانی سیاست رمز عبور نقش"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = get_object_or_404(Group, id=role_id)
        policy, created = RolePasswordPolicy.objects.get_or_create(role=role)
        
        data = request.data
        policy.min_password_length = data.get('min_length', policy.min_password_length)
        policy.require_uppercase = data.get('require_uppercase', policy.require_uppercase)
        policy.require_digit = data.get('require_digit', policy.require_digit)
        policy.require_special_char = data.get('require_special_char', policy.require_special_char)
        policy.require_lowercase = data.get('require_lowercase', policy.require_lowercase)
        policy.password_expiry_days = data.get('expiry_days', policy.password_expiry_days)
        policy.max_login_attempts = data.get('max_attempts', policy.max_login_attempts)
        policy.save()
        
        return Response({
            'success': True,
            'msg': 'سیاست رمز عبور نقش به‌روزرسانی شد',
            'policy': {
                'min_password_length': policy.min_password_length,
                'require_uppercase': policy.require_uppercase,
                'require_digit': policy.require_digit,
                'require_special_char': policy.require_special_char,
                'require_lowercase': policy.require_lowercase,
                'password_expiry_days': policy.password_expiry_days,
                'max_login_attempts': policy.max_login_attempts
            }
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role_to_users_bulk_api(request):
    """اختصاص یک نقش به گروهی از کاربران"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        role_id = data.get('role_id')
        user_ids = data.get('user_ids', [])
        
        if not role_id or not user_ids:
            return Response({'success': False, 'msg': 'نقش و کاربران باید مشخص شوند'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        role = get_object_or_404(Group, id=role_id)
        
        # ایجاد رکورد اختصاص گروهی
        bulk_assignment = BulkRoleAssignment.objects.create(
            role=role,
            assigned_by=request.user,
            total_users=len(user_ids)
        )
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                # اختصاص نقش به کاربر (می‌تواند چند نقش داشته باشد)
                user.groups.add(role)
                
                # ثبت در RoleAssignment
                RoleAssignment.objects.get_or_create(
                    user=user,
                    role=role,
                    defaults={'assigned_by': request.user}
                )
                success_count += 1
            except User.DoesNotExist:
                failed_count += 1
                errors.append(f"کاربر {user_id} یافت نشد")
            except Exception as e:
                failed_count += 1
                errors.append(str(e))
        
        bulk_assignment.success_count = success_count
        bulk_assignment.failed_count = failed_count
        bulk_assignment.error_log = '\n'.join(errors) if errors else ''
        bulk_assignment.status = 'completed' if failed_count == 0 else 'failed' if success_count == 0 else 'completed'
        bulk_assignment.save()
        
        # اضافه کردن کاربران به ManyToMany
        users = User.objects.filter(id__in=user_ids)
        bulk_assignment.users.set(users)
        
        return Response({
            'success': True,
            'msg': f'{success_count} کاربر به نقش {role.name} اضافه شدند',
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors[:10]
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_multiple_roles_to_user_api(request):
    """اختصاص چند نقش به یک کاربر (همزمان)"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        user_id = data.get('user_id')
        role_ids = data.get('role_ids', [])
        
        if not user_id or not role_ids:
            return Response({'success': False, 'msg': 'کاربر و نقش‌ها باید مشخص شوند'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, id=user_id)
        roles = Group.objects.filter(id__in=role_ids)
        
        assigned_roles = []
        for role in roles:
            user.groups.add(role)
            RoleAssignment.objects.get_or_create(
                user=user,
                role=role,
                defaults={'assigned_by': request.user}
            )
            assigned_roles.append(role.name)
        
        return Response({
            'success': True,
            'msg': f'نقش‌های {", ".join(assigned_roles)} به کاربر {user.username} اختصاص یافت',
            'assigned_roles': assigned_roles
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_roles_with_permissions_api(request, user_id):
    """دریافت نقش‌های کاربر با دسترسی‌های کامل"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        roles_data = []
        for role in user.groups.all():
            # دریافت دسترسی‌های نقش
            permissions = role.permissions.all().values('id', 'name', 'codename')
            
            # دریافت سیاست رمز عبور نقش
            try:
                policy = RolePasswordPolicy.objects.get(role=role)
                policy_data = {
                    'min_length': policy.min_password_length,
                    'require_uppercase': policy.require_uppercase,
                    'require_digit': policy.require_digit,
                }
            except RolePasswordPolicy.DoesNotExist:
                policy_data = None
            
            roles_data.append({
                'id': role.id,
                'name': role.name,
                'permissions': list(permissions),
                'password_policy': policy_data
            })
        
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            },
            'roles': roles_data,
            'total_roles': len(roles_data)
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_role_from_user_api(request):
    """حذف یک نقش از کاربر"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Group, id=role_id)
        
        # جلوگیری از حذف آخرین نقش کاربر
        if user.groups.count() <= 1:
            return Response({
                'success': False,
                'msg': 'کاربر حداقل باید یک نقش داشته باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.groups.remove(role)
        RoleAssignment.objects.filter(user=user, role=role).delete()
        
        return Response({
            'success': True,
            'msg': f'نقش {role.name} از کاربر {user.username} حذف شد'
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users_by_role_api(request, role_id):
    """دریافت کاربران دارای یک نقش خاص"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = get_object_or_404(Group, id=role_id)
        users = User.objects.filter(groups=role)
        
        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'is_active': user.is_active,
                'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return Response({
            'success': True,
            'role': {
                'id': role.id,
                'name': role.name
            },
            'users': user_list,
            'total_users': len(user_list)
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================
# ============ BULK USER MANAGEMENT ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_block_users_api(request):
    """مسدود کردن گروهی از کاربران"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        user_ids = data.get('user_ids', [])
        block = data.get('block', True)
        
        if not user_ids:
            return Response({'success': False, 'msg': 'هیچ کاربری انتخاب نشده است'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # جلوگیری از مسدود کردن خود
        if str(request.user.id) in [str(uid) for uid in user_ids]:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را مسدود کنید'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                
                # جلوگیری از مسدود کردن سوپرادمین توسط غیر سوپرادمین
                if user.is_superuser and not request.user.is_superuser:
                    failed_count += 1
                    errors.append(f"کاربر {user.username} سوپرادمین است و نمی‌توانید مسدود کنید")
                    continue
                
                user.is_active = not block
                user.save()
                
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.is_blocked = block
                profile.blocked_at = timezone.now() if block else None
                profile.save()
                
                success_count += 1
            except User.DoesNotExist:
                failed_count += 1
                errors.append(f"کاربر {user_id} یافت نشد")
            except Exception as e:
                failed_count += 1
                errors.append(str(e))
        
        status_text = 'مسدود' if block else 'فعال'
        return Response({
            'success': True,
            'msg': f'{success_count} کاربر {status_text} شدند',
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors[:10]
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_change_password_api(request):
    """تغییر رمز عبور گروهی از کاربران"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        user_ids = data.get('user_ids', [])
        new_password = data.get('new_password')
        
        if not user_ids or not new_password:
            return Response({'success': False, 'msg': 'کاربران و رمز عبور جدید باید مشخص شوند'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if len(new_password) < 8:
            return Response({'success': False, 'msg': 'رمز عبور باید حداقل ۸ کاراکتر باشد'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                
                # جلوگیری از تغییر رمز خود
                if user.id == request.user.id:
                    failed_count += 1
                    errors.append(f"نمی‌توانید رمز خودتان را تغییر دهید")
                    continue
                
                user.set_password(new_password)
                user.save()
                success_count += 1
            except User.DoesNotExist:
                failed_count += 1
                errors.append(f"کاربر {user_id} یافت نشد")
            except Exception as e:
                failed_count += 1
                errors.append(str(e))
        
        return Response({
            'success': True,
            'msg': f'رمز عبور {success_count} کاربر تغییر یافت',
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors[:10]
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)










@api_view(['PUT', 'POST'])
@permission_classes([IsAuthenticated])
def update_role_api(request, role_id):
    """ویرایش نقش - تغییر نام و دسترسی‌ها"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = get_object_or_404(Group, id=role_id)
        data = request.data
        
        # بررسی نقش‌های محافظت شده
        protected_roles = ['admin', 'superadmin', 'user']
        if role.name.lower() in protected_roles:
            return Response({
                'success': False, 
                'msg': f'نقش {role.name} قابل ویرایش نیست'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # تغییر نام نقش
        new_name = data.get('name', '').strip()
        if new_name and new_name != role.name:
            if Group.objects.filter(name=new_name).exclude(id=role_id).exists():
                return Response({
                    'success': False, 
                    'msg': 'نقش با این نام قبلاً وجود دارد'
                }, status=status.HTTP_400_BAD_REQUEST)
            role.name = new_name
        
        # تغییر دسترسی‌ها
        perm_ids = data.get('permissions', [])
        if perm_ids:
            permissions = Permission.objects.filter(id__in=perm_ids)
            role.permissions.set(permissions)
        else:
            role.permissions.clear()
        
        role.save()
        
        return Response({
            'success': True,
            'msg': f'نقش با موفقیت ویرایش شد',
            'role': {
                'id': role.id,
                'name': role.name,
                'permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} 
                              for p in role.permissions.all()]
            }
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)