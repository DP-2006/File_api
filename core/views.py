import json
import re
import socket
import subprocess
import platform
import psutil

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import models
from django.db.models import Count, Q

# Import از serializers.py
from .serializers import (
    GroupSerializer, UserSerializer, UploadedFileSerializer, 
    GroupLeaderSerializer
)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from .services.llm_service import llm_service

from .services.firewall_service import firewall
from .services.action_analyzer import action_analyzer
from .services.file_reader import FileReader
from .services.ai_manager import ai_manager

# Import مدل‌ها
from .models import (
    FileActionLog, UploadedFile, UserSettings, UserProfile,
    PasswordPolicy, GroupLeader, LoginLog, AINotification, 
    AIThreatAlert, SystemPermission, UserPermission, AISettings, 
    SystemSettings, FileSizeSettings
)

from .permissions import has_permission, can_modify_user, check_permission, get_user_permissions_list


def get_or_create_settings(user):
    settings, created = UserSettings.objects.get_or_create(user=user)
    return settings


def is_api_request(request):
    """بررسی اینکه درخواست API هست یا HTML"""
    return request.accepted_renderer.format == 'json' if hasattr(request, 'accepted_renderer') else False


# =============================================
# ============ Auth Views ============
# =============================================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def login_view(request):
    if request.method == 'POST':
        if request.content_type == 'application/json':
            username = request.data.get('username')
            password = request.data.get('password')
        else:
            username = request.POST.get('username')
            password = request.POST.get('password')
            
        user = authenticate(request, username=username, password=password)
        success = user is not None

        LoginLog.objects.create(
            user=user if user else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            success=success
        )

        if user:
            login(request, user)
            role = 'superadmin' if user.is_superuser else 'admin' if user.is_staff else 'user'
            
            token, created = Token.objects.get_or_create(user=user)
            
            if request.content_type == 'application/json' or is_api_request(request):
                return Response({
                    'success': True,
                    'uid': user.id,
                    'role': role,
                    'token': token.key,
                    'username': user.username,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser
                })
            else:
                return JsonResponse({'success': True, 'uid': user.id, 'role': role})
        else:
            if request.content_type == 'application/json' or is_api_request(request):
                return Response({
                    'success': False,
                    'msg': 'نام کاربری یا رمز عبور اشتباه است'
                }, status=status.HTTP_401_UNAUTHORIZED)
            else:
                return JsonResponse({'success': False, 'msg': 'نام کاربری یا رمز عبور اشتباه است'})
    
    return render(request, 'login.html')


@api_view(['GET', 'POST'])
def logout_view(request):
    logout(request)
    if is_api_request(request):
        return Response({'success': True, 'msg': 'خروج موفقیت‌آمیز'})
    return redirect('login')


@api_view(['GET', 'POST'])
def log_out_view(request):  
    if request.user.is_authenticated:
        Token.objects.filter(user=request.user).delete()  
    logout(request)
    if is_api_request(request):
        return Response({'success': True, 'msg': 'successfully exit System'})    
    return redirect('login')


# =============================================
# ============ Dashboard Views ============
# =============================================

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def dashboard_view(request):
#     settings = get_or_create_settings(request.user)
    
#     my_files = UploadedFile.objects.filter(
#         Q(uploaded_by=request.user, is_deleted=False) |
#         Q(sent_to_user=request.user, is_deleted=False)
#     ).order_by('-uploaded_at')
    
#     if is_api_request(request):
#         serializer = UploadedFileSerializer(my_files, many=True, context={'request': request})
#         return Response({
#             'settings': {
#                 'font_size': settings.font_size,
#                 'menu_size': settings.menu_size,
#                 'button_size': settings.button_size
#             },
#             'files': serializer.data,
#             'user': {
#                 'id': request.user.id,
#                 'username': request.user.username,
#                 'is_staff': request.user.is_staff,
#                 'is_superuser': request.user.is_superuser
#             }
#         })
    
#     return render(request, 'dashboard.html', {'settings': settings, 'my_files': my_files})




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    settings = get_or_create_settings(request.user)
    
    # دیباگ - چاپ تعداد فایل‌ها
    print(f"=== USER: {request.user.username} (ID: {request.user.id}) ===")
    
    # همه فایل‌های کاربر (برای دیباگ)
    all_user_files = UploadedFile.objects.filter(
        Q(uploaded_by=request.user) | Q(sent_to_user=request.user),
        is_deleted=False
    )
    print(f"همه فایل‌های مرتبط با کاربر: {all_user_files.count()}")
    
    # فایل‌های شخصی کاربر (فقط فایل‌هایی که خودش آپلود کرده و برای کسی ارسال نشده)
    my_files = UploadedFile.objects.filter(
        uploaded_by=request.user,
        sent_to_user__isnull=True,
        is_deleted=False
    ).order_by('-uploaded_at')
    print(f"فایل‌های شخصی (sent_to_user__isnull=True): {my_files.count()}")
    
    # فایل‌هایی که کاربر آپلود کرده (حتی اگه ارسال شده باشن)
    all_uploaded = UploadedFile.objects.filter(
        uploaded_by=request.user,
        is_deleted=False
    )
    print(f"همه فایل‌های آپلود شده توسط کاربر: {all_uploaded.count()}")
    
    # فایل‌های دریافتی از دیگران
    received_files = UploadedFile.objects.filter(
        sent_to_user=request.user,
        is_deleted=False
    ).exclude(
        uploaded_by=request.user
    ).order_by('-uploaded_at')
    print(f"فایل‌های دریافتی: {received_files.count()}")
    
    # اگر فایل‌ها خالی هستن، همه فایل‌ها رو نشون بده (برای دیباگ)
    if my_files.count() == 0 and received_files.count() == 0:
        # همه فایل‌های غیرحذف شده رو نشون بده
        all_files = UploadedFile.objects.filter(is_deleted=False)
        print(f"همه فایل‌های سیستم: {all_files.count()}")
        for f in all_files:
            print(f"  - ID: {f.id}, نام: {f.file.name}, آپلود کننده: {f.uploaded_by.username}, ارسال به: {f.sent_to_user.username if f.sent_to_user else 'هیچ‌کس'}")
    
    if is_api_request(request):
        serializer = UploadedFileSerializer(my_files, many=True, context={'request': request})
        received_serializer = UploadedFileSerializer(received_files, many=True, context={'request': request})
        return Response({
            'settings': {
                'font_size': settings.font_size,
                'menu_size': settings.menu_size,
                'button_size': settings.button_size
            },
            'files': serializer.data,
            'received_files': received_serializer.data,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser
            }
        })
    
    django_data = {
        'user': {
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
            'username': request.user.username,
            'id': request.user.id
        },
        'settings': {
            'font_size': settings.font_size,
            'menu_size': settings.menu_size,
            'button_size': settings.button_size
        },
        'files': [
            {
                'id': f.id,
                'name': f.file.name,
                'url': f.file.url,
                'size': f.file.size,
                'uploaded_at': f.uploaded_at.strftime('%y/%m/%d - %H:%M'),
                'extension': f.file.name[-4:].lower() if f.file.name else '',
                'file_size_bytes': f.file.size or 0
            } for f in my_files
        ],
        'received_files': [
            {
                'id': f.id,
                'name': f.file.name,
                'url': f.file.url,
                'size': f.file.size,
                'received_at': f.uploaded_at.strftime('%y/%m/%d - %H:%M'),
                'extension': f.file.name[-4:].lower() if f.file.name else '',
                'file_size_bytes': f.file.size or 0,
                'sender_name': f.uploaded_by.username,
                'sender_id': f.uploaded_by.id
            } for f in received_files
        ]
    }
    
    return render(request, 'dashboard.html', {
        'settings': settings,
        'my_files': my_files,
        'received_files': received_files,
        'django_data': django_data
    })










# =============================================
# ============ Upload Files ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_files_view(request):
    file_size_settings = FileSizeSettings.get_settings()
    max_upload_bytes = file_size_settings.get_max_upload_bytes()
    
    files = request.FILES.getlist('files')
    folder_name = request.data.get('folder_name', 'Unknown')
    
    folders_data = request.data.get('folders', '[]')
    if isinstance(folders_data, str):
        try:
            folders = json.loads(folders_data)
        except:
            folders = []
    else:
        folders = folders_data
    
    uploaded_count = 0
    rejected_count = 0
    size_rejected_count = 0
    threats_found = []
    notifications_created = []
    folder_file_count = 0

    for f in files:
        if f.size > max_upload_bytes:
            size_rejected_count += 1
            continue
            
        if f.name.lower().endswith('.exe'):
            rejected_count += 1
            continue

        is_folder_file = False
        for folder_path in folders:
            if f.name in folder_path or folder_path in f.name:
                is_folder_file = True
                break
        
        if is_folder_file:
            folder_file_count += 1

        uploaded_file = UploadedFile.objects.create(
            file=f,
            uploaded_by=request.user,
            folder_name=folder_name
        )
        uploaded_count += 1

        try:
            from .services.file_analysis_service import file_analysis_service
            analysis_result = file_analysis_service.analyze_uploaded_file(uploaded_file)

            if analysis_result.get('success'):
                notifications_created.append({
                    'file': f.name,
                    'threat_level': analysis_result.get('threat_level', 'info'),
                    'notification_id': analysis_result.get('notification').id if analysis_result.get('notification') else None
                })

                if analysis_result.get('threat_level') in ['warning', 'critical']:
                    threats_found.append({
                        "file": f.name,
                        "threat": analysis_result.get('threat_level', 'unknown'),
                        "severity": analysis_result.get('threat_level', 'low')
                    })
        except Exception as e:
            print(f"Error in AI analysis for {f.name}: {e}")

        try:
            scan_result = firewall.scan_file(uploaded_file)
            if scan_result.get("is_threat", False):
                threats_found.append({
                    "file": f.name,
                    "threat": scan_result.get("threat_type", "unknown"),
                    "severity": scan_result.get("severity", "low")
                })
        except Exception as e:
            print(f"Error scanning {f.name}: {e}")

    msg = f'{uploaded_count} فایل آپلود شد.'
    if rejected_count > 0:
        msg += f' {rejected_count} فایل EXE مجاز نبود.'
    if size_rejected_count > 0:
        msg += f' {size_rejected_count} فایل به دلیل حجم بالا رد شد (حداکثر {file_size_settings.max_upload_size_mb}MB).'
    if folder_file_count > 0:
        msg += f' {folder_file_count} فایل از داخل پوشه‌ها آپلود شد.'
    if threats_found:
        msg += f' ⚠️ {len(threats_found)} فایل مشکوک شناسایی شد!'
    if notifications_created:
        msg += f' 📬 {len(notifications_created)} نوتیفیکیشن جدید برای ادمین‌ها ارسال شد.'

    return Response({
        'success': True,
        'msg': msg,
        'uploaded_count': uploaded_count,
        'rejected_count': rejected_count,
        'size_rejected_count': size_rejected_count,
        'folder_file_count': folder_file_count,
        'threats': threats_found,
        'notifications': notifications_created
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_settings_view(request):
    data = request.data
    settings = get_or_create_settings(request.user)
    settings.font_size = int(data.get('font_size', 14))
    settings.menu_size = int(data.get('menu_size', 200))
    settings.button_size = int(data.get('button_size', 40))
    settings.save()
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file_view(request, file_id):
    try:
        uploaded_file = UploadedFile.objects.get(id=file_id, is_deleted=False)

        if uploaded_file.uploaded_by != request.user and uploaded_file.sent_to_user != request.user and not request.user.is_staff:
            if is_api_request(request):
                return Response({
                    'success': False,
                    'msg': 'دسترسی ندارید'
                }, status=status.HTTP_403_FORBIDDEN)
            return JsonResponse({'success': False, 'msg': 'دسترسی ندارید'}, status=403)

        if is_api_request(request):
            return Response({
                'success': True,
                'file_url': request.build_absolute_uri(uploaded_file.file.url),
                'file_name': uploaded_file.file.name,
                'file_size': uploaded_file.file.size if uploaded_file.file else 0
            })

        return redirect(uploaded_file.file.url)

    except UploadedFile.DoesNotExist:
        if is_api_request(request):
            return Response({
                'success': False,
                'msg': 'فایل یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        return JsonResponse({'success': False, 'msg': 'فایل یافت نشد'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_my_file_view(request):
    try:
        file_id = request.data.get('file_id')

        if not file_id:
            return Response({'success': False, 'msg': 'شناسه فایل ارسال نشده است'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = UploadedFile.objects.get(id=file_id, uploaded_by=request.user)
        
        if uploaded_file.file:
            uploaded_file.file.delete()
        uploaded_file.delete()

        return Response({'success': True, 'msg': 'فایل با موفقیت حذف شد'})

    except UploadedFile.DoesNotExist:
        return Response({'success': False, 'msg': 'فایل یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_files_view(request):
    recipient_id = request.data.get('recipient_id')
    files = request.FILES.getlist('files')

    if not recipient_id or not files:
        return Response({'success': False, 'msg': 'اطلاعات ناقص'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = User.objects.get(id=recipient_id)
        sent_count = 0
        for f in files:
            if f.name.lower().endswith('.exe'):
                continue
            UploadedFile.objects.create(
                file=f,
                uploaded_by=request.user,
                folder_name=f'ارسال شده به {recipient.username}',
                sent_to_user=recipient
            )
            sent_count += 1
        return Response({'success': True, 'msg': f'{sent_count} فایل ارسال شد'})
    except User.DoesNotExist:
        return Response({'success': False, 'msg': 'کاربر یافت نشد'}, status=status.HTTP_404_NOT_FOUND)


# =============================================
# ============ Admin Views ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_panel_view(request):
    if not request.user.is_staff:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')
        
    users = User.objects.all()
    history = UploadedFile.objects.filter(is_deleted=False).select_related('uploaded_by').order_by('-uploaded_at')
    
    if is_api_request(request):
        user_serializer = UserSerializer(users, many=True)
        file_serializer = UploadedFileSerializer(history, many=True, context={'request': request})
        return Response({
            'users': user_serializer.data,
            'history': file_serializer.data,
            'total_users': users.count(),
            'total_files': history.count()
        })
    
    all_roles = Group.objects.all()
    context = {
        'users': users,
        'history': history,
        'all_roles': all_roles,
    }
    return render(request, 'admin_panel.html', context)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def super_admin_panel(request):
    if not request.user.is_superuser:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    policy, _ = PasswordPolicy.objects.get_or_create(pk=1)
    all_perms = Permission.objects.all()
    users = User.objects.all()
    all_roles = Group.objects.all()
    
    if is_api_request(request):
        return Response({
            'policy': {
                'min_password_length': policy.min_password_length,
                'require_uppercase': policy.require_uppercase,
                'require_digit': policy.require_digit,
                'require_special_char': policy.require_special_char
            },
            'users': UserSerializer(users, many=True).data,
            'roles': [{'id': r.id, 'name': r.name} for r in all_roles],
            'permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} for p in all_perms]
        })

    context = {
        'policy': policy,
        'all_perms': all_perms,
        'users': users,
        'all_roles': all_roles,
    }
    return render(request, 'super_admin_panel.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_action_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return Response({'success': False, 'msg': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    action = data.get('action')

    if action == 'create_user':
        if not has_permission(request.user, 'create_user'):
            return Response({'success': False, 'msg': 'شما دسترسی ایجاد کاربر ندارید'}, status=status.HTTP_403_FORBIDDEN)

        username = data.get('username')
        password = data.get('password')
        is_staff = data.get('is_staff', False)
        groups = data.get('groups', [])

        if User.objects.filter(username=username).exists():
            return Response({'success': False, 'msg': 'نام کاربری تکراری است'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password)
        user.is_staff = is_staff
        user.save()

        if groups:
            group_objs = Group.objects.filter(id__in=groups)
            user.groups.set(group_objs)

        UserProfile.objects.get_or_create(user=user)
        return Response({'success': True, 'msg': 'کاربر جدید ساخته شد', 'user': UserSerializer(user).data})

    elif action == 'change_password':
        if not has_permission(request.user, 'change_password'):
            return Response({'success': False, 'msg': 'شما دسترسی تغییر رمز ندارید'}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(User, id=data.get('user_id'))

        if target_user.id == request.user.id and not request.user.is_superuser:
            return Response({
                'success': False,
                'msg': 'نمی‌توانید رمز خودتان را تغییر دهید. از بخش پروفایل اقدام کنید.'
            }, status=status.HTTP_403_FORBIDDEN)

        target_user.set_password(data.get('new_password'))
        target_user.save()
        return Response({'success': True, 'msg': 'رمز عبور تغییر کرد'})

    elif action == 'block_user':
        if not has_permission(request.user, 'block_user'):
            return Response({'success': False, 'msg': 'شما دسترسی مسدود کردن کاربر را ندارید'}, status=status.HTTP_403_FORBIDDEN)

        user_id = data.get('user_id')
        if not user_id:
            return Response({'success': False, 'msg': 'شناسه کاربر نامعتبر'}, status=status.HTTP_400_BAD_REQUEST)

        if int(user_id) == request.user.id:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را مسدود کنید'}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)

        if user.is_superuser and not request.user.is_superuser:
            return Response({'success': False, 'msg': 'نمی‌توانید سوپر ادمین را مسدود کنید'}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = False
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.is_blocked = True
        profile.blocked_at = timezone.now()
        profile.save()

        return Response({'success': True, 'msg': f'کاربر {user.username} مسدود شد'})

    elif action == 'unblock_user':
        if not has_permission(request.user, 'block_user'):
            return Response({'success': False, 'msg': 'شما دسترسی فعال کردن کاربر را ندارید'}, status=status.HTTP_403_FORBIDDEN)

        user_id = data.get('user_id')
        user = get_object_or_404(User, id=user_id)

        if user.id == request.user.id:
            return Response({'success': False, 'msg': 'نمی‌توانید وضعیت خودتان را تغییر دهید'}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = True
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.is_blocked = False
        profile.blocked_at = None
        profile.save()

        return Response({'success': True, 'msg': f'کاربر {user.username} آزاد شد'})

    elif action == 'delete_file':
        if not has_permission(request.user, 'delete_own_file') and not request.user.is_superuser:
            return Response({'success': False, 'msg': 'شما دسترسی حذف فایل را ندارید'}, status=status.HTTP_403_FORBIDDEN)

        file_id = data.get('file_id')
        uploaded_file = get_object_or_404(UploadedFile, id=file_id)

        if uploaded_file.uploaded_by != request.user and not request.user.is_staff:
            return Response({'success': False, 'msg': 'شما مالک این فایل نیستید'}, status=status.HTTP_403_FORBIDDEN)

        if uploaded_file.file:
            uploaded_file.file.delete()
        uploaded_file.delete()

        return Response({'success': True, 'msg': 'فایل حذف شد'})

    elif action == 'delete_user':
        if not request.user.is_superuser:
            return Response({'success': False, 'msg': 'فقط سوپرادمین می‌تواند کاربر حذف کند'}, status=status.HTTP_403_FORBIDDEN)

        user_id = data.get('user_id')
        if not user_id:
            return Response({'success': False, 'msg': 'شناسه کاربر نامعتبر'}, status=status.HTTP_400_BAD_REQUEST)

        target_user = get_object_or_404(User, id=user_id)

        if target_user.id == request.user.id:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را حذف کنید'}, status=status.HTTP_403_FORBIDDEN)

        if target_user.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
            return Response({'success': False, 'msg': 'نمی‌توانید آخرین سوپرادمین را حذف کنید'}, status=status.HTTP_403_FORBIDDEN)

        username = target_user.username
        user_files = UploadedFile.objects.filter(uploaded_by=target_user)
        for file_obj in user_files:
            if file_obj.file:
                try:
                    file_obj.file.delete()
                except:
                    pass
            file_obj.delete()

        target_user.delete()
        return Response({'success': True, 'msg': f'کاربر {username} با موفقیت حذف شد'})

    elif action == 'assign_role':
        if not has_permission(request.user, 'assign_role'):
            return Response({'success': False, 'msg': 'شما دسترسی اختصاص نقش را ندارید'}, status=status.HTTP_403_FORBIDDEN)

        user_id = data.get('user_id')
        role_id = data.get('role_id')
        assign = data.get('assign', True)

        target_user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Group, id=role_id)

        if target_user.id == request.user.id and not request.user.is_superuser:
            return Response({'success': False, 'msg': 'نمی‌توانید نقش خودتان را تغییر دهید'}, status=status.HTTP_403_FORBIDDEN)

        if assign:
            target_user.groups.add(role)
            msg = f'نقش {role.name} به کاربر {target_user.username} اضافه شد'
        else:
            target_user.groups.remove(role)
            msg = f'نقش {role.name} از کاربر {target_user.username} حذف شد'

        return Response({'success': True, 'msg': msg})

    return Response({'success': False, 'msg': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def super_admin_action(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    action = data.get('action')

    if action == 'update_policy':
        policy = PasswordPolicy.objects.first()
        if policy:
            policy.min_password_length = data.get('min_length', 8)
            policy.require_uppercase = data.get('require_uppercase', True)
            policy.require_digit = data.get('require_digit', True)
            policy.require_special_char = data.get('require_special_char', False)
            policy.save()
        return Response({'success': True, 'msg': 'سیاست رمز عبور ذخیره شد.'})

    elif action == 'create_role_with_perms':
        role_name = data.get('role_name')
        perm_ids = data.get('permissions', [])
        leader_id = data.get('leader_id')

        if not role_name:
            return Response({'success': False, 'msg': 'نام نقش نمی‌تواند خالی باشد'}, status=status.HTTP_400_BAD_REQUEST)

        if Group.objects.filter(name=role_name).exists():
            return Response({'success': False, 'msg': 'نقش با این نام وجود دارد'}, status=status.HTTP_400_BAD_REQUEST)

        group = Group.objects.create(name=role_name)

        if perm_ids:
            permissions = Permission.objects.filter(id__in=perm_ids)
            group.permissions.set(permissions)

        if leader_id:
            try:
                leader = User.objects.get(id=leader_id)
                GroupLeader.objects.create(group=group, leader=leader)
            except User.DoesNotExist:
                pass

        return Response({'success': True, 'msg': f'نقش {role_name} ساخته شد.'})

    return Response({'success': False, 'msg': 'اکشن نامعتبر'}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ User Management ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_users(request):
    users = User.objects.exclude(id=request.user.id).values('id', 'username', 'first_name', 'last_name')
    return Response(list(users))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users_list(request):
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)

    users = User.objects.all().values('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser')
    user_list = []
    for u in users:
        full_name = f"{u['first_name']} {u['last_name']}".strip() or u['username']
        user_list.append({
            'id': u['id'],
            'username': u['username'],
            'full_name': full_name,
            'email': u['email'],
            'is_active': u['is_active'],
            'is_staff': u['is_staff'],
            'is_superuser': u['is_superuser']
        })
    return Response(user_list)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_detail_view(request, user_id):
    if not request.user.is_superuser:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)
    
    if is_api_request(request):
        return Response(UserSerializer(user).data)
    
    context = {'target_user': user}
    return render(request, 'user_detail.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_block_user(request, user_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        target_user = User.objects.get(id=user_id)

        if target_user.id == request.user.id:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را مسدود کنید'}, status=status.HTTP_403_FORBIDDEN)

        target_user.is_active = not target_user.is_active
        target_user.save()

        profile, _ = UserProfile.objects.get_or_create(user=target_user)
        profile.is_blocked = not target_user.is_active
        profile.blocked_at = timezone.now() if profile.is_blocked else None
        profile.save()

        status_text = 'مسدود' if not target_user.is_active else 'فعال'
        return Response({'success': True, 'msg': f'کاربر {status_text} شد'})
    except User.DoesNotExist:
        return Response({'success': False, 'msg': 'کاربر یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_user_by_id(request, user_id):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        target_user = User.objects.get(id=user_id)

        if target_user.id == request.user.id:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را حذف کنید'}, status=status.HTTP_403_FORBIDDEN)

        username = target_user.username
        target_user.delete()

        return Response({'success': True, 'msg': f'کاربر {username} با موفقیت حذف شد'})
    except User.DoesNotExist:
        return Response({'success': False, 'msg': 'کاربر یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_permissions_view(request):
    permissions = get_user_permissions_list(request.user)
    return Response({
        'user_id': request.user.id,
        'username': request.user.username,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
        'permissions': permissions
    })


# =============================================
# ============ Roles & Permissions ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_roles(request):
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    roles = Group.objects.all().values('id', 'name')
    return Response(list(roles))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_roles_detailed(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    roles = Group.objects.all()
    serializer = GroupSerializer(roles, many=True)
    return Response({
        'success': True,
        'roles': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_permissions(request):
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    permissions = Permission.objects.all().values('id', 'name', 'codename')
    return Response(list(permissions))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_role_permissions(request, role_id):
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    try:
        role = Group.objects.get(id=role_id)
        permissions = role.permissions.all().values_list('id', flat=True)
        return Response(list(permissions))
    except Group.DoesNotExist:
        return Response([], status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_role_permissions(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    role_id = data.get('role_id')
    perm_ids = data.get('permissions', [])

    try:
        role = Group.objects.get(id=role_id)
        permissions = Permission.objects.filter(id__in=perm_ids)
        role.permissions.set(permissions)

        return Response({'success': True, 'msg': 'دسترسی‌ها با موفقیت ذخیره شد'})
    except Group.DoesNotExist:
        return Response({'success': False, 'msg': 'نقش یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_new_role(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    role_name = data.get('name', '').strip()

    if not role_name:
        return Response({'success': False, 'msg': 'نام نقش نمی‌تواند خالی باشد'}, status=status.HTTP_400_BAD_REQUEST)

    if Group.objects.filter(name=role_name).exists():
        return Response({'success': False, 'msg': 'نقش با این نام قبلاً وجود دارد'}, status=status.HTTP_400_BAD_REQUEST)

    group = Group.objects.create(name=role_name)
    return Response({'success': True, 'msg': f'نقش {role_name} با موفقیت ایجاد شد', 'role_id': group.id})


@login_required
def create_role_view(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        if role_name and not Group.objects.filter(name=role_name).exists():
            Group.objects.create(name=role_name)
            messages.success(request, f'نقش {role_name} ایجاد شد')
        else:
            messages.error(request, 'خطا در ایجاد نقش')
        return redirect('super_admin_panel')

    return redirect('super_admin_panel')


# =============================================
# ============ FILE SIZE SETTINGS API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_file_size_settings_api(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    settings = FileSizeSettings.get_settings()
    return Response({
        'success': True,
        'settings': {
            'max_upload_size_mb': settings.max_upload_size_mb,
            'max_download_size_mb': settings.max_download_size_mb,
            'warning_threshold_mb': settings.warning_threshold_mb,
            'allow_large_files': settings.allow_large_files,
            'updated_at': settings.updated_at.strftime('%Y-%m-%d %H:%M') if settings.updated_at else None,
            'updated_by': settings.updated_by.username if settings.updated_by else None
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_file_size_settings_api(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        settings = FileSizeSettings.get_settings()
        
        settings.max_upload_size_mb = int(data.get('max_upload_size_mb', 100))
        settings.max_download_size_mb = int(data.get('max_download_size_mb', 200))
        settings.warning_threshold_mb = int(data.get('warning_threshold_mb', 50))
        settings.allow_large_files = data.get('allow_large_files', True)
        settings.updated_by = request.user
        settings.save()
        
        return Response({
            'success': True,
            'msg': 'تنظیمات حجم فایل با موفقیت ذخیره شد',
            'settings': {
                'max_upload_size_mb': settings.max_upload_size_mb,
                'max_download_size_mb': settings.max_download_size_mb,
                'warning_threshold_mb': settings.warning_threshold_mb,
                'allow_large_files': settings.allow_large_files
            }
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ User Analysis Views ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_user_view(request, user_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    user = get_object_or_404(User, id=user_id)

    user_files = UploadedFile.objects.filter(uploaded_by=user, is_deleted=False)
    file_types = {}
    for uf in user_files:
        ext = uf.file.name.split('.')[-1] if '.' in uf.file.name else 'unknown'
        file_types[ext] = file_types.get(ext, 0) + 1

    user_data = {
        'id': user.id,
        'username': user.username,
        'total_uploads': user_files.count(),
        'file_types': file_types,
        'is_staff': user.is_staff,
        'date_joined': user.date_joined.strftime('%Y/%m/%d') if user.date_joined else 'نامشخص'
    }

    try:
        if llm_service is None:
            analysis = "⚠️ سرویس هوش مصنوعی در دسترس نیست. لطفاً اطمینان حاصل کنید که Ollama در حال اجراست."
        else:
            analysis = llm_service.analyze_user_behavior(user_data, [])

        return Response({
            'success': True,
            'analysis': analysis,
            'total_uploads': user_files.count(),
            'user': {
                'username': user.username,
                'id': user.id,
                'file_types': file_types
            }
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': f"خطا در تحلیل: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_user_personality_view(request, user_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    user = get_object_or_404(User, id=user_id)

    user_files = UploadedFile.objects.filter(uploaded_by=user, is_deleted=False).order_by('-uploaded_at')[:20]

    all_content = []
    file_types = {}
    suspicious_files = []

    for uf in user_files:
        try:
            file_info = FileReader.read_file(uf.file)
            ext = file_info['extension']
            file_types[ext] = file_types.get(ext, 0) + 1

            if file_info['content']:
                all_content.append(f"\n\n--- فایل: {uf.file.name} ---\n{file_info['content'][:2000]}")

            if ext in ['.exe', '.jar', '.bat', '.ps1', '.sh']:
                suspicious_files.append(uf.file.name)

        except Exception as e:
            all_content.append(f"\n\n--- فایل: {uf.file.name} (خطا در خواندن: {e}) ---")

    user_data = {
        'username': user.username,
        'total_uploads': user_files.count(),
        'file_types': file_types,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined.strftime('%Y/%m/%d') if user.date_joined else 'نامشخص'
    }

    try:
        if llm_service is None:
            analysis = "⚠️ سرویس هوش مصنوعی در دسترس نیست. لطفاً اطمینان حاصل کنید که Ollama در حال اجراست."
        else:
            analysis = llm_service.analyze_user_personality(
                user_data,
                "\n".join(all_content)[:8000]
            )

        return Response({
            'success': True,
            'analysis': analysis,
            'stats': {
                'total_files': user_files.count(),
                'file_types': file_types,
                'suspicious_files': suspicious_files
            }
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': f"خطا در تحلیل: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================
# ============ Logs Views ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_logs_view(request):
    if not request.user.is_superuser:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    logs = LoginLog.objects.all().order_by('-login_time')
    
    if is_api_request(request):
        return Response({
            'logs': [{
                'id': log.id,
                'username': log.user.username if log.user else 'Unknown',
                'ip_address': log.ip_address,
                'login_time': log.login_time.strftime('%Y-%m-%d %H:%M:%S'),
                'success': log.success
            } for log in logs[:100]]
        })
    
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_logs': logs.count(),
    }
    return render(request, 'login_logs.html', context)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def action_log_view(request):
    if not request.user.is_staff:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    logs = FileActionLog.objects.all().order_by('-action_time')
    
    if is_api_request(request):
        return Response({
            'logs': [{
                'id': log.id,
                'user': log.user.username if log.user else 'سیستم',
                'action': log.action,
                'file_name': log.file_name,
                'action_time': log.action_time.strftime('%Y-%m-%d %H:%M:%S'),
                'ip_address': log.ip_address,
                'ai_analysis': log.ai_analysis,
                'threat_level': log.threat_level
            } for log in logs[:50]]
        })
    
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_logs': logs.count(),
    }
    return render(request, 'action_log.html', context)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def action_log_detail_api(request, log_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        log = FileActionLog.objects.get(id=log_id)
        return Response({
            'success': True,
            'analysis': log.ai_analysis or 'تحلیلی برای این عملیات ثبت نشده است',
            'summary': log.ai_summary or '',
            'action': log.action,
            'file_name': log.file_name,
            'user': log.user.username if log.user else 'نامشخص',
            'created_at': log.action_time.strftime('%Y-%m-%d %H:%M')
        })
    except FileActionLog.DoesNotExist:
        return Response({'success': False, 'error': 'لاگ یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================
# ============ AI & System Settings ============
# =============================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ai_settings_panel(request):
    if not request.user.is_staff:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        messages.error(request, "شما دسترسی به این صفحه را ندارید!")
        return redirect('dashboard')

    ai_settings = AISettings.get_settings()
    system_settings = SystemSettings.get_settings()
    
    if is_api_request(request):
        return Response({
            'ai_settings': {
                'ollama_host': ai_settings.ollama_host,
                'ollama_port': ai_settings.ollama_port,
                'ollama_model': ai_settings.ollama_model,
                'is_active': ai_settings.is_active,
                'timeout_seconds': ai_settings.timeout_seconds,
                'max_tokens': ai_settings.max_tokens,
                'temperature': ai_settings.temperature,
                'updated_at': ai_settings.updated_at.strftime('%Y-%m-%d %H:%M') if ai_settings.updated_at else None
            },
            'system_settings': {
                'server_ip': system_settings.server_ip,
                'server_port': system_settings.server_port,
                'allow_remote_access': system_settings.allow_remote_access
            }
        })

    context = {
        'ai_settings': ai_settings,
        'system_settings': system_settings,
        'is_superuser': request.user.is_superuser
    }
    return render(request, 'ai_settings.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_test_connection_api(request):
    if not request.user.is_staff:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        data = request.data
        host = data.get('host')
        port = data.get('port')
        model = data.get('model')

        result = ai_manager.test_connection(host, port, model)
        return Response(result)
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_save_settings_api(request):
    if not request.user.is_staff:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        data = request.data
        result = ai_manager.save_settings(data)
        return Response(result)
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_get_models_api(request):
    if not request.user.is_staff:
        return Response({'success': False, 'models': []}, status=status.HTTP_403_FORBIDDEN)

    host = request.GET.get('host')
    port = request.GET.get('port')

    result = ai_manager.get_available_models(host, port)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_restart_ollama_api(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        result = subprocess.run(['ollama', 'serve', '--restart'], capture_output=True, text=True)
        return Response({
            'success': True,
            'message': 'درخواست ریستارت ارسال شد',
            'output': result.stdout
        })
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ Notifications ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications_api(request):
    if not request.user.is_staff:
        return Response({'notifications': [], 'unread_count': 0, 'total': 0}, status=status.HTTP_403_FORBIDDEN)

    try:
        notifications = AINotification.objects.filter(target_users=request.user)
        unread_count = notifications.filter(status='unread').count()

        notifications_list = []
        for notif in notifications[:50]:
            notifications_list.append({
                'id': notif.id,
                'title': notif.title or 'بدون عنوان',
                'message': notif.message[:200] if notif.message else '',
                'severity': notif.severity or 'info',
                'status': notif.status or 'unread',
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else '',
                'file_name': notif.file.file.name if notif.file and notif.file.file else None,
                'user_name': notif.user.username if notif.user else None
            })

        return Response({
            'notifications': notifications_list,
            'unread_count': unread_count,
            'total': notifications.count()
        })
    except Exception as e:
        return Response({
            'notifications': [],
            'unread_count': 0,
            'total': 0,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read_api(request, notification_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        notification = AINotification.objects.get(id=notification_id, target_users=request.user)
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        return Response({'success': True, 'msg': 'نوتیفیکیشن خوانده شد'})
    except AINotification.DoesNotExist:
        return Response({'success': False, 'msg': 'نوتیفیکیشن یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read_api(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        notifications = AINotification.objects.filter(target_users=request.user, status='unread')
        count = notifications.count()

        for notif in notifications:
            notif.status = 'read'
            notif.read_at = timezone.now()
            notif.save()

        return Response({'success': True, 'msg': f'{count} نوتیفیکیشن خوانده شد'})
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_panel_view(request):
    if not request.user.is_staff:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    notifications = AINotification.objects.filter(target_users=request.user).order_by('-created_at')
    
    if is_api_request(request):
        return Response({
            'notifications': [{
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'severity': n.severity,
                'status': n.status,
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
            } for n in notifications[:50]],
            'total_count': notifications.count(),
            'unread_count': notifications.filter(status='unread').count()
        })
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': notifications.count(),
        'unread_count': notifications.filter(status='unread').count(),
    }
    return render(request, 'notifications_panel.html', context)


@login_required
def notifications_html_view(request):
    if not request.user.is_staff:
        messages.error(request, "شما دسترسی به این صفحه را ندارید!")
        return redirect('dashboard')
    
    notifications = AINotification.objects.filter(target_users=request.user).order_by('-created_at')
    unread_count = notifications.filter(status='unread').count()
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'unread_count': unread_count,
        'total_count': notifications.count(),
    }
    return render(request, 'notifications.html', context)


# =============================================
# ============ Alerts ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_alerts_view(request):
    if not request.user.is_staff:
        if is_api_request(request):
            return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        return redirect('dashboard')

    alerts = firewall.get_pending_alerts()
    stats = {
        'total': AIThreatAlert.objects.count(),
        'pending': AIThreatAlert.objects.filter(status='pending').count(),
        'critical': AIThreatAlert.objects.filter(severity='critical').count(),
        'high': AIThreatAlert.objects.filter(severity='high').count(),
    }
    
    if is_api_request(request):
        return Response({
            'alerts': [{
                'id': a.id,
                'file_name': a.file.file.name if a.file else 'Unknown',
                'threat_type': a.threat_type,
                'severity': a.severity,
                'status': a.status,
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M')
            } for a in alerts],
            'stats': stats
        })

    return render(request, 'security_alerts.html', {'alerts': alerts, 'stats': stats})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def resolve_alert_view(request, alert_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    alert = get_object_or_404(AIThreatAlert, id=alert_id)

    if request.method == 'POST':
        action = request.data.get('action')

        if action == 'block':
            alert.file.is_deleted = True
            alert.file.save()
            alert.status = 'blocked'
        elif action == 'ignore':
            alert.status = 'ignored'
        elif action == 'review':
            alert.status = 'reviewed'

        alert.reviewed_by = request.user
        alert.reviewed_at = timezone.now()
        alert.save()
        
        if is_api_request(request):
            return Response({'success': True, 'msg': f'هشدار با موفقیت {alert.status} شد'})
        
        messages.success(request, f'هشدار با موفقیت {dict(alert.STATUS_CHOICES).get(alert.status)} شد')
        return redirect('security_alerts')

    return render(request, 'resolve_alert.html', {'alert': alert})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alerts_count_view(request):
    if not request.user.is_staff:
        return Response({'count': 0})

    count = AIThreatAlert.objects.filter(status='pending').count()
    return Response({'count': count})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alerts_count_api(request):
    if not request.user.is_staff:
        return Response({'count': 0})

    try:
        count = AIThreatAlert.objects.filter(status='pending').count()
        return Response({'count': count})
    except Exception as e:
        return Response({'count': 0})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_stats_view(request):
    if not request.user.is_staff:
        return Response({})

    pending = AIThreatAlert.objects.filter(status='pending').count()
    critical = AIThreatAlert.objects.filter(severity='critical').count()
    high = AIThreatAlert.objects.filter(severity='high').count()
    total = AIThreatAlert.objects.count()

    return Response({
        'pending_alerts': pending,
        'critical_alerts': critical,
        'high_alerts': high,
        'total_alerts': total,
        'recommendation': 'لطفاً هشدارهای بحرانی را فوری بررسی کنید' if critical > 0 else 'وضعیت امنیتی خوب است'
    })


# =============================================
# ============ Network Settings ============
# =============================================

def get_network_info():
    info = {
        'hostname': socket.gethostname(),
        'ip_address': '',
        'subnet_mask': '',
        'default_gateway': '',
        'primary_dns': '',
        'secondary_dns': '',
        'mac_address': '',
        'os': platform.system(),
        'os_version': platform.version(),
        'os_release': platform.release(),
        'python_version': platform.python_version(),
        'processor': platform.processor() or 'نامشخص',
        'ram_total': '',
        'ram_available': '',
    }

    try:
        if platform.system() == 'Windows':
            result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True, encoding='cp1256', errors='ignore')
            output = result.stdout

            ip_pattern = r'IPv4 Address[.\s]*: ([\d.]+)'
            subnet_pattern = r'Subnet Mask[.\s]*: ([\d.]+)'
            gateway_pattern = r'Default Gateway[.\s]*: ([\d.]+)'
            dns_pattern = r'DNS Servers[.\s]*: ([\d.]+)'
            mac_pattern = r'Physical Address[.\s]*: ([\w-]+)'

            ip_matches = re.findall(ip_pattern, output)
            for ip in ip_matches:
                if ip != '127.0.0.1' and ip != '0.0.0.0':
                    info['ip_address'] = ip
                    break

            subnet_match = re.search(subnet_pattern, output)
            gateway_match = re.search(gateway_pattern, output)
            dns_matches = re.findall(dns_pattern, output)
            mac_match = re.search(mac_pattern, output)

            if subnet_match:
                info['subnet_mask'] = subnet_match.group(1)
            if gateway_match and gateway_match.group(1) != '' and gateway_match.group(1) != '0.0.0.0':
                info['default_gateway'] = gateway_match.group(1)
            if dns_matches:
                valid_dns = [d for d in dns_matches if d != '0.0.0.0']
                if valid_dns:
                    info['primary_dns'] = valid_dns[0] if len(valid_dns) > 0 else ''
                    info['secondary_dns'] = valid_dns[1] if len(valid_dns) > 1 else ''
            if mac_match:
                info['mac_address'] = mac_match.group(1)

    except Exception as e:
        print(f"Error getting network info: {e}")

    try:
        mem = psutil.virtual_memory()
        info['ram_total'] = f"{mem.total / (1024 ** 3):.1f} GB"
        info['ram_available'] = f"{mem.available / (1024 ** 3):.1f} GB"
    except:
        info['ram_total'] = 'نامشخص'
        info['ram_available'] = 'نامشخص'

    return info


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_network_info_api(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    info = get_network_info()
    return Response({'success': True, 'network_info': info})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_network_settings_api(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        data = request.data
        settings = SystemSettings.get_settings()

        settings.server_ip = data.get('ip_address', settings.server_ip)
        settings.server_port = int(data.get('port', settings.server_port))
        settings.allow_remote_access = data.get('allow_remote_access', False)
        settings.save()

        return Response({'success': True, 'message': 'تنظیمات شبکه با موفقیت ذخیره شد'})
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_network_settings_api(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'message': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    if platform.system() != 'Windows':
        return Response({'success': False, 'message': 'این قابلیت فقط در ویندوز پشتیبانی می‌شود'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        data = request.data
        settings = SystemSettings.get_settings()

        interface_name = "Wi-Fi"
        ip = data.get('ip_address', settings.server_ip)
        subnet = data.get('subnet_mask', '255.255.255.0')
        gateway = data.get('default_gateway', '')
        dns1 = data.get('primary_dns', '8.8.8.8')
        dns2 = data.get('secondary_dns', '8.8.4.4')

        if ip and subnet:
            commands = [
                f'netsh interface ip set address "{interface_name}" static {ip} {subnet} {gateway}',
                f'netsh interface ip set dns "{interface_name}" static {dns1}',
                f'netsh interface ip add dns "{interface_name}" {dns2} index=2'
            ]

            results = []
            for cmd in commands:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                results.append({'command': cmd, 'output': result.stdout, 'error': result.stderr})

            return Response({
                'success': True,
                'message': 'تنظیمات شبکه با موفقیت اعمال شد',
                'results': results
            })
        else:
            return Response({'success': False, 'message': 'IP و Subnet نمی‌توانند خالی باشند'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ Delete Views ============
# =============================================

@login_required
def delete_role_view(request, role_id):
    if not request.user.is_superuser:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)
        messages.error(request, 'شما دسترسی حذف نقش را ندارید!')
        return redirect('super_admin_panel')

    role = get_object_or_404(Group, id=role_id)

    protected_roles = ['admin', 'superadmin', 'user']
    if role.name.lower() in protected_roles:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': f'نقش {role.name} قابل حذف نیست'}, status=400)
        messages.error(request, f'نقش {role.name} قابل حذف نیست!')
        return redirect('super_admin_panel')

    role_name = role.name
    role.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'msg': f'نقش {role_name} با موفقیت حذف شد'})

    messages.success(request, f'نقش {role_name} با موفقیت حذف شد')
    return redirect('super_admin_panel')


@login_required
def delete_user_view(request, user_id):
    if not request.user.is_superuser:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)
        messages.error(request, 'شما دسترسی حذف کاربر را ندارید!')
        return redirect('dashboard')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': 'نمی‌توانید خودتان را حذف کنید'}, status=400)
        messages.error(request, 'نمی‌توانید خودتان را حذف کنید!')
        return redirect('super_admin_panel')

    if target_user.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': 'نمی‌توانید آخرین سوپرادمین را حذف کنید'}, status=400)
        messages.error(request, 'نمی‌توانید آخرین سوپرادمین را حذف کنید!')
        return redirect('super_admin_panel')

    username = target_user.username

    user_files = UploadedFile.objects.filter(uploaded_by=target_user)
    for file_obj in user_files:
        if file_obj.file:
            try:
                file_obj.file.delete()
            except:
                pass
        file_obj.delete()

    target_user.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'msg': f'کاربر {username} با موفقیت حذف شد'})

    messages.success(request, f'کاربر {username} با موفقیت حذف شد')
    return redirect('super_admin_panel')

@login_required
def delete_user_modal_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')

    target_user = get_object_or_404(User, id=user_id)
    context = {'target_user': target_user}
    return render(request, 'includes/delete_user_modal.html', context)


@login_required
def delete_role_modal_view(request, role_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    role = get_object_or_404(Group, id=role_id)
    context = {'role': role}
    return render(request, 'includes/delete_role_modal.html', context)


# =============================================
# ============ Bulk Operations ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_delete_users_view(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        data = request.data
        user_ids = data.get('user_ids', [])

        if not user_ids:
            return Response({'success': False, 'msg': 'هیچ کاربری انتخاب نشده است'}, status=status.HTTP_400_BAD_REQUEST)

        if str(request.user.id) in user_ids:
            return Response({'success': False, 'msg': 'نمی‌توانید خودتان را حذف کنید'}, status=status.HTTP_403_FORBIDDEN)

        superadmins = User.objects.filter(is_superuser=True)
        if len(superadmins) <= 1:
            for uid in user_ids:
                user = User.objects.filter(id=uid, is_superuser=True).first()
                if user:
                    return Response({'success': False, 'msg': 'نمی‌توانید آخرین سوپرادمین را حذف کنید'}, status=status.HTTP_403_FORBIDDEN)

        deleted_count = 0
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                if user.id != request.user.id:
                    user_files = UploadedFile.objects.filter(uploaded_by=user)
                    for file_obj in user_files:
                        if file_obj.file:
                            try:
                                file_obj.file.delete()
                            except:
                                pass
                        file_obj.delete()
                    user.delete()
                    deleted_count += 1
            except User.DoesNotExist:
                continue

        return Response({'success': True, 'msg': f'{deleted_count} کاربر با موفقیت حذف شدند'})
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_delete_roles_view(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        data = request.data
        role_ids = data.get('role_ids', [])

        if not role_ids:
            return Response({'success': False, 'msg': 'هیچ نقشی انتخاب نشده است'}, status=status.HTTP_400_BAD_REQUEST)

        protected_roles = ['admin', 'superadmin', 'user']
        deleted_count = 0

        for role_id in role_ids:
            try:
                role = Group.objects.get(id=role_id)
                if role.name.lower() not in protected_roles:
                    role.delete()
                    deleted_count += 1
            except Group.DoesNotExist:
                continue

        return Response({'success': True, 'msg': f'{deleted_count} نقش با موفقیت حذف شدند'})
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ File Analysis Views ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_file_with_ai(request, file_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    file_obj = get_object_or_404(UploadedFile, id=file_id)

    content = ""
    file_path = file_obj.file.path
    ext = file_obj.file.name.split('.')[-1].lower() if '.' in file_obj.file.name else 'unknown'

    if ext == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()[:5000]
        except:
            content = "خطا در خواندن فایل"
    elif ext == 'pdf':
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                for page in pdf.pages[:5]:
                    content += page.extract_text() or ""
        except:
            content = "خطا در خواندن PDF"
    else:
        content = f"فایل {ext} - محتوا قابل نمایش نیست"

    action = request.data.get('action', 'summarize')
    level = request.data.get('level', 'summary')
    question = request.data.get('question', '')

    try:
        if action == 'ask' and question:
            result = llm_service.answer_question_about_file(
                content=content,
                filename=file_obj.file.name,
                question=question
            )
            return Response({
                'success': True,
                'result': result,
                'file_name': file_obj.file.name
            })
        else:
            result = llm_service.summarize_file(
                content=content,
                filename=file_obj.file.name,
                detail_level=level
            )

            threat_status = {'severity': 'low', 'threat_type': 'none'}
            suspicious_keywords = ['password', 'hack', 'crack', 'malware', 'virus', 'phishing']
            content_lower = content.lower()
            for keyword in suspicious_keywords:
                if keyword in content_lower:
                    threat_status = {'severity': 'high', 'threat_type': keyword}
                    break

            return Response({
                'success': True,
                'result': result,
                'file_name': file_obj.file.name,
                'threat_status': threat_status
            })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_file_manual_api(request, file_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    file_obj = get_object_or_404(UploadedFile, id=file_id, is_deleted=False)

    try:
        file_info = FileReader.read_file(file_obj.file)
        content = file_info.get('content', '')
    except Exception as e:
        content = f"خطا در خواندن فایل: {str(e)}"

    if not llm_service or not llm_service.is_available:
        return Response({
            'success': False,
            'error': 'سرویس AI در دسترس نیست. لطفاً Ollama را راه‌اندازی کنید.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    prompt = f"""
    تحلیل فایل "{file_obj.file.name}":

    محتوا (خلاصه):
    {content[:1500]}

    پاسخ دهید:
    1. موضوع اصلی:
    2. آیا خطرناک است؟ (بله/خیر/مشکوک)
    3. سطح ریسک: (کم/متوسط/بالا/بحرانی)
    4. توصیه:
    """

    analysis = llm_service._call_llm_stream(prompt)

    threat_level = 'low'
    analysis_lower = analysis.lower()
    if any(word in analysis_lower for word in ['بحرانی', 'خطرناک', 'ویروس', 'بدافزار']):
        threat_level = 'critical'
    elif any(word in analysis_lower for word in ['بالا', 'مشکوک', 'غیرمجاز']):
        threat_level = 'high'
    elif any(word in analysis_lower for word in ['متوسط']):
        threat_level = 'medium'
    elif 'مشکوک' in analysis_lower:
        threat_level = 'warning'

    severity_map = {
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'warning': 'medium',
        'critical': 'critical'
    }

    AIThreatAlert.objects.create(
        file=file_obj,
        threat_type='manual_analysis',
        severity=severity_map.get(threat_level, 'low'),
        description=analysis[:500],
        recommended_action='review' if threat_level in ['high', 'critical', 'warning'] else 'none',
        ai_raw_response=analysis,
        status='reviewed',
        reviewed_by=request.user,
        reviewed_at=timezone.now()
    )

    return Response({
        'success': True,
        'analysis': analysis,
        'threat_level': threat_level
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_file_detail_view(request, file_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    try:
        file_obj = get_object_or_404(UploadedFile, id=file_id, is_deleted=False)

        analysis = "تحلیلی برای این فایل ثبت نشده است"
        try:
            alert = AIThreatAlert.objects.filter(file=file_obj).first()
            if alert:
                analysis = alert.description
        except:
            pass

        if is_api_request(request):
            return Response({
                'file': UploadedFileSerializer(file_obj, context={'request': request}).data,
                'analysis': analysis,
                'user': UserSerializer(file_obj.uploaded_by).data
            })

        context = {
            'file': file_obj,
            'analysis': analysis,
            'user': file_obj.uploaded_by,
        }
        return render(request, 'file_analysis_detail.html', context)

    except Exception as e:
        if is_api_request(request):
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        messages.error(request, f'خطا در بارگذاری تحلیل فایل: {str(e)}')
        return redirect('dashboard')


# =============================================
# ============ Password Policy ============
# =============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_password_policy(request):
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    min_length = data.get('min_length', 8)

    try:
        policy, created = PasswordPolicy.objects.get_or_create(pk=1)
        policy.min_password_length = min_length
        policy.save()

        return Response({'success': True, 'msg': 'سیاست رمز عبور ذخیره شد'})
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================
# ============ File Summary ============
# =============================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def file_summary_view(request, file_id):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    file_obj = get_object_or_404(UploadedFile, id=file_id)

    if request.method == 'POST':
        level = request.data.get('level', 'summary')
        question = request.data.get('question', '')

        content = firewall.extract_file_content(file_obj)

        try:
            if question:
                result = llm_service.answer_question_about_file(
                    content=content,
                    filename=file_obj.file.name,
                    question=question
                )
                return Response({'success': True, 'result': result, 'type': 'answer'})
            else:
                result = llm_service.summarize_file(
                    content=content,
                    filename=file_obj.file.name,
                    detail_level=level
                )
                return Response({'success': True, 'result': result, 'type': 'summary'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return render(request, 'file_summary.html', {'file': file_obj})


# =============================================
# ============ Analyze All ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_all_files_view(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    total_files = UploadedFile.objects.filter(is_deleted=False).count()
    files_by_user = UploadedFile.objects.filter(is_deleted=False).values('uploaded_by__username').annotate(
        count=models.Count('id'))

    return Response({
        'success': True,
        'total_files': total_files,
        'files_by_user': list(files_by_user)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_all_users_view(request):
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)

    users = User.objects.all()
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    staff_users = users.filter(is_staff=True).count()

    return Response({
        'success': True,
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users
    })


# =============================================
# ============ LOGS API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_logs_api(request):
    """دریافت لاگ‌های سیستم"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    # ترکیب لاگ‌های ورود و عملیات
    login_logs = LoginLog.objects.all().order_by('-login_time')[:100]
    action_logs = FileActionLog.objects.all().order_by('-action_time')[:100]
    
    logs = []
    
    # لاگ‌های ورود
    for log in login_logs:
        logs.append({
            'time': log.login_time.strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'info',
            'message': f'ورود کاربر {log.user.username if log.user else "ناشناس"} از {log.ip_address}'
        })
    
    # لاگ‌های عملیات
    for log in action_logs:
        level = log.threat_level or 'info'
        if level in ['critical', 'high']:
            level = 'error'
        elif level == 'warning':
            level = 'warning'
        else:
            level = 'info'
        
        logs.append({
            'time': log.action_time.strftime('%Y-%m-%d %H:%M:%S'),
            'level': level,
            'message': f'{log.action} - {log.file_name} توسط {log.user.username if log.user else "سیستم"}'
        })
    
    # مرتب‌سازی بر اساس زمان (جدیدترین اول)
    logs.sort(key=lambda x: x['time'], reverse=True)
    
    return Response({
        'success': True,
        'logs': logs[:200]  # حداکثر 200 لاگ
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_logs_api(request):
    """پاک کردن لاگ‌ها"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # پاک کردن لاگ‌های ورود قدیمی (فقط 1000 تای آخر نگهداری می‌شود)
        total_login = LoginLog.objects.count()
        if total_login > 1000:
            to_delete = LoginLog.objects.order_by('login_time')[:total_login - 1000]
            to_delete.delete()
        
        # پاک کردن لاگ‌های عملیات قدیمی
        total_action = FileActionLog.objects.count()
        if total_action > 1000:
            to_delete = FileActionLog.objects.order_by('action_time')[:total_action - 1000]
            to_delete.delete()
        
        return Response({
            'success': True,
            'msg': 'لاگ‌های قدیمی پاک شدند'
        })
    except Exception as e:
        return Response({
            'success': False,
            'msg': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================
# ============ USERS LIST API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users_list_api(request):
    """دریافت لیست کامل کاربران"""
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.all()
    user_list = []
    
    for user in users:
        # دریافت نقش‌های کاربر
        roles = [{'id': g.id, 'name': g.name} for g in user.groups.all()]
        
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'roles': roles
        })
    
    return Response(user_list)


# =============================================
# ============ ROLES API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_roles_api(request):
    """دریافت لیست تمام نقش‌ها"""
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    
    roles = Group.objects.all()
    role_list = []
    
    for role in roles:
        # دریافت تعداد کاربران دارای این نقش
        user_count = User.objects.filter(groups=role).count()
        
        role_list.append({
            'id': role.id,
            'name': role.name,
            'user_count': user_count,
            'permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} 
                          for p in role.permissions.all()]
        })
    
    return Response(role_list)


# =============================================
# ============ ALL PERMISSIONS API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_permissions_api(request):
    """دریافت لیست تمام دسترسی‌ها"""
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    
    permissions = Permission.objects.all().order_by('content_type__app_label', 'codename')
    perm_list = []
    
    for perm in permissions:
        perm_list.append({
            'id': perm.id,
            'name': perm.name,
            'codename': perm.codename,
            'app_label': perm.content_type.app_label,
            'model': perm.content_type.model
        })
    
    return Response(perm_list)


# =============================================
# ============ ROLE PERMISSIONS API ============
# =============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_role_permissions_api(request, role_id):
    """دریافت دسترسی‌های یک نقش خاص"""
    if not request.user.is_staff:
        return Response([], status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = Group.objects.get(id=role_id)
        permissions = role.permissions.all().values_list('id', flat=True)
        return Response(list(permissions))
    except Group.DoesNotExist:
        return Response([], status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_role_permissions_api(request):
    """ذخیره دسترسی‌های یک نقش"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        role_id = data.get('role_id')
        perm_ids = data.get('permissions', [])
        
        role = Group.objects.get(id=role_id)
        permissions = Permission.objects.filter(id__in=perm_ids)
        role.permissions.set(permissions)
        
        return Response({
            'success': True,
            'msg': f'دسترسی‌های نقش {role.name} با موفقیت ذخیره شد'
        })
    except Group.DoesNotExist:
        return Response({'success': False, 'msg': 'نقش یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_role_api(request):
    """ایجاد نقش جدید"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = request.data
        role_name = data.get('name', '').strip()
        
        if not role_name:
            return Response({'success': False, 'msg': 'نام نقش نمی‌تواند خالی باشد'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if Group.objects.filter(name=role_name).exists():
            return Response({'success': False, 'msg': 'نقش با این نام قبلاً وجود دارد'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        role = Group.objects.create(name=role_name)
        
        return Response({
            'success': True,
            'msg': f'نقش {role_name} با موفقیت ایجاد شد',
            'role': {'id': role.id, 'name': role.name}
        })
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_role_api(request, role_id):
    """حذف نقش"""
    if not request.user.is_superuser:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        role = Group.objects.get(id=role_id)
        
        # نقش‌های محافظت شده
        protected_roles = ['admin', 'superadmin', 'user']
        if role.name.lower() in protected_roles:
            return Response({'success': False, 'msg': f'نقش {role.name} قابل حذف نیست'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        role_name = role.name
        role.delete()
        
        return Response({
            'success': True,
            'msg': f'نقش {role_name} با موفقیت حذف شد'
        })
    except Group.DoesNotExist:
        return Response({'success': False, 'msg': 'نقش یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_permissions_view(request):
    from .permissions import get_user_permissions_by_roles
    
    if request.user.is_superuser and request.user.groups.count() == 0:
        permissions = get_user_permissions_list(request.user)
    else:
        permissions = get_user_permissions_by_roles(request.user)
    
    roles = [{'id': g.id, 'name': g.name} for g in request.user.groups.all()]
    
    return Response({
        'user_id': request.user.id,
        'username': request.user.username,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
        'roles': roles,
        'permissions': permissions,
        'has_permissions': len(permissions) > 0,
        'has_roles': len(roles) > 0
    })  









@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_files_view(request):
    all_files = UploadedFile.objects.all().values(
        'id', 'file', 'uploaded_by__username', 'sent_to_user__username', 
        'is_deleted', 'uploaded_at'
    )
    return Response({
        'all_files': list(all_files),
        'user_id': request.user.id,
        'username': request.user.username
    })




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def browse_zip_view(request, file_id):
    """نمایش محتوای فایل‌های فشرده (ZIP/RAR/7z)"""
    if not request.user.is_staff:
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)
    
    file_obj = get_object_or_404(UploadedFile, id=file_id, is_deleted=False)
    
    # بررسی پسوند
    ext = file_obj.file.name.split('.')[-1].lower()
    if ext not in ['zip', 'rar', '7z']:
        return Response({'success': False, 'msg': 'فایل فشرده نیست'}, status=400)
    
    try:
        import zipfile
        import tempfile
        import os
        
        # لیست فایل‌های داخل
        files_list = []
        
        if ext == 'zip':
            with zipfile.ZipFile(file_obj.file.path, 'r') as zip_ref:
                for item in zip_ref.namelist():
                    info = zip_ref.getinfo(item)
                    files_list.append({
                        'name': item,
                        'size': info.file_size,
                        'is_dir': item.endswith('/'),
                        'modified': f"{info.date_time[0]}-{info.date_time[1]:02d}-{info.date_time[2]:02d}"
                    })
        else:
            # برای RAR و 7z نیاز به pyunpack و patool
            try:
                from pyunpack import Archive
                import patoolib
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    Archive(file_obj.file.path).extract(tmpdir)
                    for root, dirs, files in os.walk(tmpdir):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, tmpdir)
                            files_list.append({
                                'name': rel_path,
                                'size': os.path.getsize(full_path),
                                'is_dir': False
                            })
            except ImportError:
                return Response({
                    'success': False,
                    'msg': 'برای پشتیبانی از RAR/7z لطفاً کتابخانه pyunpack را نصب کنید'
                }, status=400)
        
        return Response({
            'success': True,
            'file_name': file_obj.file.name,
            'total_files': len(files_list),
            'files': sorted(files_list, key=lambda x: x['name'])
        })
        
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_zip_file_content(request, file_id, file_path):
    """مشاهده محتوای یک فایل خاص داخل ZIP بدون استخراج"""
    file_obj = get_object_or_404(UploadedFile, id=file_id)
    
    try:
        import zipfile
        
        with zipfile.ZipFile(file_obj.file.path, 'r') as zip_ref:
            # بررسی وجود فایل
            if file_path not in zip_ref.namelist():
                return Response({'success': False, 'msg': 'فایل در آرشیو یافت نشد'}, status=404)
            
            info = zip_ref.getinfo(file_path)
            
            # فقط فایل‌های متنی رو نمایش بده
            ext = file_path.split('.')[-1].lower()
            text_exts = ['txt', 'py', 'js', 'html', 'css', 'json', 'xml', 'csv', 'log', 'md']
            
            if ext in text_exts:
                content = zip_ref.read(file_path).decode('utf-8', errors='ignore')
                return Response({
                    'success': True,
                    'name': file_path,
                    'size': info.file_size,
                    'content': content[:50000]  # محدودیت 50k کاراکتر
                })
            else:
                # فایل باینری - فقط اطلاعات نشون بده
                return Response({
                    'success': True,
                    'name': file_path,
                    'size': info.file_size,
                    'is_binary': True,
                    'msg': 'این فایل باینری است و قابل نمایش نیست'
                })
                
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def extract_single_file(request, file_id, file_path):
    """استخراج یک فایل خاص از ZIP"""
    file_obj = get_object_or_404(UploadedFile, id=file_id)
    
    try:
        import zipfile
        from django.http import FileResponse
        import tempfile
        import os
        
        with zipfile.ZipFile(file_obj.file.path, 'r') as zip_ref:
            if file_path not in zip_ref.namelist():
                return Response({'success': False, 'msg': 'فایل یافت نشد'}, status=404)
            
            # استخراج به temp
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_ref.extract(file_path, tmpdir)
                extracted_path = os.path.join(tmpdir, file_path)
                
                # ارسال فایل
                response = FileResponse(
                    open(extracted_path, 'rb'),
                    as_attachment=True,
                    filename=os.path.basename(file_path)
                )
                return response
                
    except Exception as e:
        return Response({'success': False, 'msg': str(e)}, status=500)