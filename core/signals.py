# core/signals.py
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import UploadedFile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UploadedFile, dispatch_uid='core.uploadedfile.role_analysis')
def trigger_file_role_analysis(sender, instance: UploadedFile, created: bool, **kwargs):
    if not created:
        return
    if not instance.file or not instance.uploaded_by_id:
        return
    if getattr(instance, 'is_deleted', False):
        return

    from core.tasks import analyze_file_role_async
    try:
        analyze_file_role_async.delay(instance.pk, instance.uploaded_by_id)
    except Exception as e:
        logger.warning('enqueue role_analysis failed: %s', e)
