# core/views_role_profile.py
from django.contrib.auth.models import Group, User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models_role_profile import RoleProfile, RoleFileAccess
from .permissions import has_permission


def _can_manage(user):
    if user.is_superuser or user.is_staff:
        return True
    try:
        return has_permission(user, 'manage_role_profile')
    except Exception:
        return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def role_profile_get_api(request, group_id):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    group = get_object_or_404(Group, id=group_id)
    rp, _ = RoleProfile.objects.get_or_create(group=group)
    return Response({
        'success': True,
        'group': {'id': group.id, 'name': group.name},
        'profile': {
            'title_fa': rp.title_fa or '',
            'description': rp.description or '',
            'responsibilities': rp.responsibilities or '',
            'role_prompt': rp.role_prompt or '',
            'is_active': rp.is_active,
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def role_profile_save_api(request, group_id):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    group = get_object_or_404(Group, id=group_id)
    rp, _ = RoleProfile.objects.get_or_create(group=group)

    data = request.data
    rp.title_fa = (data.get('title_fa') or '').strip()
    rp.description = (data.get('description') or '').strip()
    rp.responsibilities = (data.get('responsibilities') or '').strip()
    rp.role_prompt = (data.get('role_prompt') or '').strip()
    rp.is_active = bool(data.get('is_active', True))
    rp.save()

    return Response({'success': True, 'msg': f'پروفایل نقش {group.name} ذخیره شد'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def role_profiles_list_api(request):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    items = []
    for g in Group.objects.all().order_by('name'):
        rp = RoleProfile.objects.filter(group=g).first()
        items.append({
            'group_id': g.id,
            'group_name': g.name,
            'title_fa': rp.title_fa if rp else '',
            'has_profile': bool(rp and (rp.title_fa or rp.description or rp.responsibilities)),
            'is_active': rp.is_active if rp else True,
        })
    return Response({'success': True, 'items': items})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role_profile_to_user_api(request, user_id):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    user = get_object_or_404(User, id=user_id)
    group_id = request.data.get('group_id')
    if not group_id:
        return Response({'success': False, 'msg': 'group_id ارسال نشد'}, status=400)

    group = get_object_or_404(Group, id=group_id)
    user.groups.add(group)
    return Response({'success': True, 'msg': f'سمت {group.name} به {user.username} اختصاص یافت'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_role_profile_from_user_api(request, user_id):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    user = get_object_or_404(User, id=user_id)
    group_id = request.data.get('group_id')
    if not group_id:
        return Response({'success': False, 'msg': 'group_id ارسال نشد'}, status=400)

    group = get_object_or_404(Group, id=group_id)
    user.groups.remove(group)
    return Response({'success': True, 'msg': f'سمت {group.name} از {user.username} حذف شد'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_role_profile_api(request, user_id):
    if not _can_manage(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'}, status=403)

    user = get_object_or_404(User, id=user_id)
    items = []
    for g in user.groups.all():
        rp = RoleProfile.objects.filter(group=g).first()
        items.append({
            'group_id': g.id,
            'group_name': g.name,
            'title_fa': rp.title_fa if rp else '',
            'description': rp.description if rp else '',
            'responsibilities': rp.responsibilities if rp else '',
        })
    return Response({'success': True, 'user_id': user.id, 'username': user.username, 'roles': items})