import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='core.analyze_file_role_async',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def analyze_file_role_async(self, uploaded_file_id: int, user_id: int):
    """
    تحلیل مرتبط بودن فایل با نقش کاربر در پس‌زمینه.
    """
    from django.contrib.auth.models import User
    from core.models import UploadedFile, FileRoleAnalysis
    from core.services.file_role_analyzer import upsert_file_role_analysis

    try:
        uploaded = UploadedFile.objects.get(pk=uploaded_file_id, is_deleted=False)
    except UploadedFile.DoesNotExist:
        logger.warning('analyze_file_role_async: file %s not found', uploaded_file_id)
        return {'ok': False, 'reason': 'file_not_found'}

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('analyze_file_role_async: user %s not found', user_id)
        return {'ok': False, 'reason': 'user_not_found'}

    # علامت‌گذاری running
    FileRoleAnalysis.objects.update_or_create(
        file=uploaded, user=user,
        defaults={'status': 'running'},
    )

    try:
        obj = upsert_file_role_analysis(uploaded, user)
        logger.info(
            'file_role_analysis done: file=%s user=%s score=%.3f related=%s',
            uploaded_file_id, user_id, obj.relevance_score, obj.is_related,
        )
        return {'ok': True, 'id': obj.id, 'score': obj.relevance_score}
    except Exception as exc:
        logger.exception('file_role_analysis failed: %s', exc)
        FileRoleAnalysis.objects.update_or_create(
            file=uploaded, user=user,
            defaults={'status': 'failed', 'error_message': str(exc)[:2000]},
        )
        raise self.retry(exc=exc)



@shared_task(
    bind=True,
    name='core.analyze_user_psychology_async',
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def analyze_user_psychology_async(self, user_id: int, persist: bool = True):
    """تحلیل روانشناسی رفتار کاربر در پس‌زمینه."""
    from django.contrib.auth.models import User
    from core.services.user_behavior_psychology import analyze_user_psychology

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('analyze_user_psychology_async: user %s not found', user_id)
        return {'ok': False, 'reason': 'user_not_found'}

    try:
        result = analyze_user_psychology(user, persist=persist)
        logger.info(
            'psychology done: user=%s risk=%.3f anomaly=%.3f',
            user_id, result.risk_score, result.anomaly_score,
        )
        return {
            'ok': True,
            'user_id': user_id,
            'risk_score': result.risk_score,
            'recommended_action': result.recommended_action,
        }
    except Exception as exc:
        logger.exception('psychology failed: %s', exc)
        raise self.retry(exc=exc)





@shared_task(bind=True, name='core.analyze_all_user_files', max_retries=1, time_limit=1800)
def analyze_all_user_files(self, user_id: int, force: bool = False):
    """تحلیل batch همه فایل‌های کاربر در پس‌زمینه."""
    from django.contrib.auth.models import User
    from core.models import UploadedFile
    from core.models_file_analysis import FileAIAnalysis
    from core.services.file_content_analyzer import ensure_file_analyzed

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return {'ok': False, 'reason': 'user_not_found'}

    files = list(UploadedFile.objects.filter(uploaded_by=user, is_deleted=False))
    results = {'total': len(files), 'fresh': 0, 'failed': 0}

    for f in files:
        try:
            ensure_file_analyzed(f, force=force)
            results['fresh'] += 1
        except Exception as e:
            logger.warning('analyze_all fail file=%s err=%s', f.id, e)
            results['failed'] += 1

    return {'ok': True, **results}

@shared_task(
    bind=True,
    name='core.analyze_file_meta_async',
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def analyze_file_meta_async(self, uploaded_file_id: int):
    """????? ???????? AI (summary/category/topics/sensitivity) ?? ????????."""
    from core.models import UploadedFile
    from core.services.file_content_analyzer import ensure_file_analyzed

    try:
        f = UploadedFile.objects.get(pk=uploaded_file_id, is_deleted=False)
    except UploadedFile.DoesNotExist:
        return {'ok': False, 'reason': 'file_not_found'}

    try:
        obj = ensure_file_analyzed(f, force=False)
        logger.info('file_meta async done: file=%s category=%s', uploaded_file_id, obj.category)
        return {'ok': True, 'file_id': uploaded_file_id, 'category': obj.category}
    except Exception as exc:
        logger.exception('file_meta async failed: %s', exc)
        raise self.retry(exc=exc)

