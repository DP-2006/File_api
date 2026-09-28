import os
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.models import UploadedFile
from .models import ScanJob, EngineResult, EngineStatus
from .services import multi_av
from .tasks import run_full_scan


def _is_staff(user):
    return user.is_staff or user.is_superuser


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_uploaded_file(request, file_id):
    """شروع اسکن async — Celery task صدا زده میشه"""
    if not _is_staff(request.user):
        return Response({'success': False, 'msg': 'دسترسی غیرمجاز'},
                        status=status.HTTP_403_FORBIDDEN)

    file_obj = get_object_or_404(UploadedFile, id=file_id, is_deleted=False)
    file_path = file_obj.file.path

    # hash
    import hashlib
    try:
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        file_hash = ''

    # ساخت ScanJob
    job = ScanJob.objects.create(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        file_hash_sha256=file_hash,
        status='pending',
        scanned_by=request.user,
    )

    # ارسال به Celery
    task = run_full_scan.delay(str(job.id))

    job.celery_task_id = task.id
    job.save(update_fields=['celery_task_id'])

    return Response({
        'success': True,
        'scan_id': str(job.id),
        'task_id': task.id,
        'status': 'dispatched',
        'message': 'اسکن در پس‌زمینه شروع شد',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_status(request, scan_id):
    """چک وضعیت اسکن (polling)"""
    if not _is_staff(request.user):
        return Response({'success': False}, status=status.HTTP_403_FORBIDDEN)

    job = get_object_or_404(ScanJob, id=scan_id)
    engines = [{
        'engine': e.engine_name, 'score': e.score, 'threat': e.threat,
        'details': e.details, 'error': e.error, 'duration_ms': e.duration_ms,
    } for e in job.engine_results.all()]

    return Response({
        'success': True,
        'scan_id': str(job.id),
        'status': job.status,
        'progress': f"{job.completed_engines}/{job.total_engines}",
        'final_score': job.final_score,
        'is_threat': job.is_threat,
        'severity': job.severity,
        'verdict': job.verdict,
        'engines': engines,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_history(request, file_id=None):
    if not _is_staff(request.user):
        return Response({'success': False}, status=status.HTTP_403_FORBIDDEN)

    qs = ScanJob.objects.all()
    if file_id:
        file_obj = get_object_or_404(UploadedFile, id=file_id)
        qs = qs.filter(file_path=file_obj.file.path)

    data = [{
        'id': str(s.id),
        'file_name': s.file_name,
        'final_score': s.final_score,
        'is_threat': s.is_threat,
        'severity': s.severity,
        'verdict': s.verdict,
        'status': s.status,
        'started_at': s.started_at.strftime('%Y-%m-%d %H:%M:%S'),
        'finished_at': s.finished_at.strftime('%Y-%m-%d %H:%M:%S') if s.finished_at else None,
        'scanned_by': s.scanned_by.username if s.scanned_by else 'سیستم',
    } for s in qs[:100]]

    return Response({'success': True, 'results': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def engines_status(request):
    if not _is_staff(request.user):
        return Response({'success': False}, status=status.HTTP_403_FORBIDDEN)

    statuses = multi_av.get_all_engines_status()
    for name, st in statuses.items():
        EngineStatus.objects.update_or_create(
            engine_name=name,
            defaults={
                'is_active': st.get('active', False),
                'version': str(st.get('version', '')),
                'error_message': st.get('error', ''),
            }
        )
    return Response({'success': True, 'engines': statuses})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistics(request):
    if not _is_staff(request.user):
        return Response({'success': False}, status=status.HTTP_403_FORBIDDEN)

    from django.db.models import Avg
    total = ScanJob.objects.count()
    threats = ScanJob.objects.filter(is_threat=True).count()
    avg_score = ScanJob.objects.aggregate(avg=Avg('final_score'))['avg'] or 0

    return Response({
        'success': True,
        'total_scans': total,
        'threats': threats,
        'clean': total - threats,
        'avg_score': round(avg_score, 2),
    })