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