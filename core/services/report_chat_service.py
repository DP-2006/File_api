# core/services/report_chat_service.py
"""
سرویس چت با فایل‌ها (RAG-based).
- کاملاً مستقل از FileAIAnalysis
- محتوای خام فایل‌ها را استخراج می‌کند (متن → متن، عکس → base64)
- به FastAPI `/chat/with-context` می‌فرستد
- پیام‌ها را در ReportChatMessage ذخیره می‌کند
"""

import base64
import logging
import os

from core.models_report_chat import ReportChatSession, ReportChatMessage
from core.services.ai_client import AIServiceClient
from core.services.file_reader import FileReader

log = logging.getLogger(__name__)

MAX_FILE_CHARS = 3000
MAX_CONTEXT_CHARS = 20000

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}


class ReportChatService:
    """سرویس چت با فایل‌های گزارشات (بدون وابستگی به تحلیل)"""

    def __init__(self, client: AIServiceClient = None):
        self.client = client or AIServiceClient()

    def _is_image(self, fname: str) -> bool:
        ext = os.path.splitext(fname or '')[1].lower()
        return ext in IMAGE_EXTS

    def build_context(self, session: ReportChatSession) -> str:
        parts = []

        if session.target_user:
            u = session.target_user
            parts.append(
                f"=== اطلاعات کارر\n"
                f"نام کاربری: {u.username}\n"
                f"نام: {u.get_full_name() or '—'}"
            )

        for uploaded in session.files.all():
            block = self._build_file_block(uploaded)
            if block:
                parts.append(block)
            if sum(len(p) for p in parts) > MAX_CONTEXT_CHARS:
                parts.append("[... بقیه فایل‌ها به دلیل حجم حذف شد ...]")
                break

        if not parts:
            return "(هیچ فایل متنی انتخاب نشده است)"
        return "\n\n".join(parts)

    def _build_file_block(self, uploaded) -> str:

        try:
            fname = uploaded.file.name.split('/')[-1]
        except Exception:
            fname = str(uploaded)

        if self._is_image(fname):
            return None  # عکس‌ها در context متنی نمی‌آیند

        try:
            info = FileReader.read_file(uploaded.file)
            content = (info.get('content') or '')[:MAX_FILE_CHARS]
        except Exception as e:
            log.warning(f"FileReader failed for {fname}: {e}")
            content = f"[خطا در خواندن فایل: {e}]"

        return (
            f"=== فایل: {fname} ===\n"
            f"--- محتوای خام ---\n"
            f"{content}"
        )

    def _collect_images_b64(self, session: ReportChatSession) -> list:
        """همه عکس‌های فایل‌های انتخابی را base64 می‌کند."""
        images = []
        for uploaded in session.files.all():
            try:
                fname = uploaded.file.name.split('/')[-1]
            except Exception:
                continue
            if not self._is_image(fname):
                continue
            try:
                import os as _os
                from django.conf import settings as _settings
                raw = None
                try:
                    uploaded.file.open('rb')
                    raw = uploaded.file.read()
                    uploaded.file.close()
                except FileNotFoundError:
                    base = _os.path.basename(fname)
                    for cand in [_os.path.join(_settings.MEDIA_ROOT, base),
                                 _os.path.join(_settings.MEDIA_ROOT, 'uploads', base)]:
                        if _os.path.exists(cand):
                            with open(cand, 'rb') as fp:
                                raw = fp.read()
                            break
                if raw is None:
                    log.warning(f"image not found on disk: {fname}")
                    continue
                b64 = base64.b64encode(raw).decode('ascii')
                images.append(b64)
            except Exception as e:
                log.warning(f"failed to read image {fname}: {e}")
        return images

    def ask(self, session: ReportChatSession, question: str) -> dict:
        if not question or not question.strip():
            return {'success': False, 'error': 'سوال خالی است'}

        # context متنی (فقط فایل‌های متنی)
        # همیشه context را بازسازی کن (بدون cache)
        session.context_text = self.build_context(session)
        session.save(update_fields=['context_text'])

        # عکس‌ها به صورت base64 (هر بار دوباره خوانده می‌شوند)
        images_b64 = self._collect_images_b64(session)

        history = list(
            session.messages.order_by('created_at').values('role', 'content')[:50]
        )
        history = history[-10:]

        ReportChatMessage.objects.create(
            session=session,
            role='user',
            content=question,
        )

        try:
            result = self.client.chat_with_context(
                question=question,
                context_text=session.context_text,
                file_ids=[str(f.id) for f in session.files.all()],
                history=history,
                user_id=session.target_user_id or session.admin_id,
                images_b64=images_b64,
            )
        except Exception as e:
            log.exception(f"chat_with_context failed: {e}")
            return {'success': False, 'error': str(e)}

        if 'error' in result:
            return {'success': False, 'error': result['error']}

        answer = result.get('answer', '') or '(پاسخی دریافت نشد)'

        ReportChatMessage.objects.create(
            session=session,
            role='assistant',
            content=answer,
            ai_response_json=result,
        )

        session.save(update_fields=['updated_at'])
        return {'success': True, 'answer': answer, 'raw': result}