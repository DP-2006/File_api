# core/tasks.py
import logging
from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(name="core.analyze_file_via_ai")
def analyze_file_via_ai(file_id: int):
    #see the file on the secdnd sys 
    log.info(f"[ANALYZE] file_id={file_id} enqueued (stub)")
    return {"file_id": file_id, "status": "stub"}