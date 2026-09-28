import os
import hashlib
import logging
from celery import shared_task, chord, group
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ============================================================
# TASK اصلی: اسکن کامل (Orchestrator)
# ============================================================

@shared_task(bind=True, name='multi_av.tasks.run_full_scan')
def run_full_scan(self, scan_id):
    """
    این task موتورها رو به صورت موازی (celery chord) اجرا می‌کنه
    و بعد از اتمام همه، نتیجه نهایی رو محاسبه می‌کنه.
    """
    from multi_av.models import ScanJob

    try:
        job = ScanJob.objects.get(id=scan_id)
    except ScanJob.DoesNotExist:
        logger.error(f"ScanJob {scan_id} not found")
        return {'error': 'scan not found'}

    job.status = 'running'
    job.celery_task_id = self.request.id
    job.save(update_fields=['status', 'celery_task_id'])

    enabled = settings.MULTI_AV.get('ENABLED_ENGINES', [])
    job.total_engines = len(enabled)
    job.save(update_fields=['total_engines'])

    # ساخت گروه از تسک‌ها (هر موتور یک تسک جدا)
    engine_tasks = []
    for engine_name in enabled:
        if engine_name == 'clamav':
            engine_tasks.append(scan_with_clamav.s(scan_id))
        elif engine_name == 'yara':
            engine_tasks.append(scan_with_yara.s(scan_id))
        elif engine_name == 'virustotal':
            engine_tasks.append(scan_with_virustotal.s(scan_id))
        elif engine_name == 'heuristic':
            engine_tasks.append(scan_with_heuristic.s(scan_id))
        elif engine_name == 'ai':
            engine_tasks.append(scan_with_ai.s(scan_id))

    # chord: اجرای موازی + callback نهایی
    callback = finalize_scan.s(scan_id)
    chord(engine_tasks)(callback)

    return {'scan_id': str(scan_id), 'status': 'dispatched',
            'engines': enabled}


# ============================================================
# TASK های موتورها
# ============================================================

@shared_task(bind=True, name='multi_av.tasks.scan_with_clamav',
             soft_time_limit=300, time_limit=360)
def scan_with_clamav(self, scan_id):
    return _run_engine('clamav', scan_id, self.request.id)


@shared_task(bind=True, name='multi_av.tasks.scan_with_yara',
             soft_time_limit=180, time_limit=240)
def scan_with_yara(self, scan_id):
    return _run_engine('yara', scan_id, self.request.id)


@shared_task(bind=True, name='multi_av.tasks.scan_with_virustotal',
             soft_time_limit=120, time_limit=180)
def scan_with_virustotal(self, scan_id):
    return _run_engine('virustotal', scan_id, self.request.id)


@shared_task(bind=True, name='multi_av.tasks.scan_with_heuristic',
             soft_time_limit=120, time_limit=180)
def scan_with_heuristic(self, scan_id):
    return _run_engine('heuristic', scan_id, self.request.id)


@shared_task(bind=True, name='multi_av.tasks.scan_with_ai',
             soft_time_limit=600, time_limit=660)
def scan_with_ai(self, scan_id):
    return _run_engine('ai', scan_id, self.request.id)


# ============================================================
# تابع کمکی: اجرای یک موتور
# ============================================================

def _run_engine(engine_name, scan_id, task_id):
    from multi_av.models import ScanJob, EngineResult
    from multi_av.services import multi_av

    try:
        job = ScanJob.objects.get(id=scan_id)
    except ScanJob.DoesNotExist:
        return {'engine': engine_name, 'error': 'scan not found'}

    engine = multi_av.get_engine(engine_name)
    if not engine:
        return {'engine': engine_name, 'error': 'engine not found'}

    try:
        if engine_name == 'ai':
            # AI نیاز به file_obj داره
            file_obj = None
            try:
                from core.models import UploadedFile
                file_obj = UploadedFile.objects.filter(
                    file=job.file_path.replace(str(settings.MEDIA_ROOT) + '/', '')
                ).first()
            except Exception:
                pass
            result = engine.scan(job.file_path, file_obj=file_obj)
        else:
            result = engine.scan(job.file_path)

        # ذخیره نتیجه
        EngineResult.objects.update_or_create(
            scan=job,
            engine_name=engine_name,
            defaults={
                'score': result.get('score', 0),
                'threat': result.get('threat', False),
                'details': result.get('details', ''),
                'raw_data': result.get('raw', {}),
                'error': result.get('error', ''),
                'duration_ms': result.get('duration_ms', 0),
            }
        )

        # آپدیت شمارنده
        completed = EngineResult.objects.filter(scan=job).count()
        ScanJob.objects.filter(id=scan_id).update(completed_engines=completed)

        return {'engine': engine_name, 'score': result.get('score', 0),
                'threat': result.get('threat', False)}

    except Exception as e:
        logger.exception(f"Engine {engine_name} failed: {e}")
        EngineResult.objects.update_or_create(
            scan=job, engine_name=engine_name,
            defaults={'score': 0, 'threat': False, 'error': str(e),
                      'details': 'engine crashed'}
        )
        return {'engine': engine_name, 'error': str(e)}


# ============================================================
# TASK نهایی: محاسبه امتیاز و ذخیره
# ============================================================

@shared_task(name='multi_av.tasks.finalize_scan')
def finalize_scan(engine_results, scan_id):
    """بعد از اتمام همه موتورها اجرا میشه (chord callback)"""
    from multi_av.models import ScanJob, EngineResult
    from multi_av.services import multi_av

    try:
        job = ScanJob.objects.get(id=scan_id)
    except ScanJob.DoesNotExist:
        return {'error': 'scan not found'}

    # جمع‌آوری نتایج
    results = {}
    for er in EngineResult.objects.filter(scan=job):
        results[er.engine_name] = {
            'score': er.score,
            'threat': er.threat,
            'details': er.details,
            'error': er.error,
            'duration_ms': er.duration_ms,
            'raw': er.raw_data,
        }

    final = multi_av.calculate_final_score(results)

    job.final_score = final['score']
    job.is_threat = final['is_threat']
    job.severity = final['severity']
    job.verdict = final['verdict']
    job.status = 'completed'
    job.finished_at = timezone.now()
    job.save()

    # ایجاد Alert اگه تهدید بود
    if final['is_threat']:
        _create_threat_alert(job, results, final)

    # ایجاد نوتیفیکیشن
    _create_notification(job, final)

    return {
        'scan_id': str(scan_id),
        'final_score': final['score'],
        'is_threat': final['is_threat'],
        'severity': final['severity'],
    }


def _create_threat_alert(job, results, final):
    try:
        from core.models import UploadedFile, AIThreatAlert
        file_obj = UploadedFile.objects.filter(
            file=job.file_path.replace(str(settings.MEDIA_ROOT) + '/', '')
        ).first()
        if not file_obj:
            return

        AIThreatAlert.objects.create(
            file=file_obj,
            threat_type='multi_av',
            severity=final['severity'] if final['severity'] in
                     ['low', 'medium', 'high', 'critical'] else 'medium',
            description=(
                f"Multi-AV score: {final['score']}\n" +
                "\n".join([f"{k}: {v.get('details', '')}"
                           for k, v in results.items()])
            ),
            recommended_action='review',
            ai_raw_response=str(results),
            status='pending',
        )
    except Exception as e:
        logger.exception(f"Failed to create alert: {e}")


def _create_notification(job, final):
    try:
        from core.models import AINotification, UploadedFile
        from django.contrib.auth.models import User

        file_obj = UploadedFile.objects.filter(
            file=job.file_path.replace(str(settings.MEDIA_ROOT) + '/', '')
        ).first()

        admins = User.objects.filter(is_staff=True)

        title = f"🔍 اسکن Multi-AV: {job.file_name}"
        if final['severity'] == 'critical':
            severity = 'critical'
        elif final['severity'] == 'high':
            severity = 'warning'
        else:
            severity = 'info'

        msg = (f"فایل {job.file_name} اسکن شد.\n"
               f"امتیاز نهایی: {final['score']}/100\n"
               f"نتیجه: {final['verdict']}")

        notif = AINotification.objects.create(
            title=title, message=msg,
            notification_type='file_analysis',
            severity=severity,
            file=file_obj, status='unread',
        )
        notif.target_users.set(admins)
    except Exception as e:
        logger.exception(f"Failed to create notification: {e}")


# ============================================================
# TASK کمکی: پاک کردن اسکن‌های قدیمی
# ============================================================

@shared_task(name='multi_av.tasks.cleanup_old_scans')
def cleanup_old_scans(days=30):
    from datetime import timedelta
    from multi_av.models import ScanJob

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = ScanJob.objects.filter(started_at__lt=cutoff).delete()
    return {'deleted': deleted}