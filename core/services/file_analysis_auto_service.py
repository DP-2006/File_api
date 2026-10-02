import json
import logging
from django.utils import timezone
from django.contrib.auth.models import User

from core.models_file_analysis import FileAIAnalysis
from core.models_user_behavior import UserBehaviorAnalysis
from core.services.llm_service import llm_service
from core.services.file_reader import FileReader

log = logging.getLogger(__name__)


ANALYSIS_PROMPT = """
شما یک سیستم تحلیل فایل برای سازمان هستید. فایل زیر را دقیق تحلیل کنید و پاسخ را **فقط به صورت JSON معتبر** برگردانید (بدون توضیح اضافی، بدون ```json).

اطلاعات کاربر:
- نام کاربری: {username}
- نقش‌های کاربر: {user_roles}
- تعداد فایل‌های قبلی کاربر: {previous_files}
- موضوعات غالب قبلی کاربر: {top_topics}

اطلاعات فایل:
- نام فایل: {file_name}
- حجم: {file_size} bytes
- نوع: {file_type}

محتوای فایل (بخش اول):
{content}

پاسخ JSON با این ساختار دقیق:
{{
  "topics": [
    {{"name": "نام موضوع به فارسی", "weight": 0.85}},
    {{"name": "موضوع دوم", "weight": 0.6}}
  ],
  "summary": "خلاصه‌ای 2-3 خطی از محتوای فایل به فارسی",
  "category": "یکی از: educational, financial, technical, legal, personal, confidential, other",
  "threat_level": "یکی از: low, medium, high, critical",
  "relevance_to_user_role": 0.85,
  "is_related_to_user": true,
  "detected_keywords": ["کلمه1", "کلمه2"],
  "reason_for_relevance": "دلیل کوتاه مرتبط یا غیرمرتبط بودن با نقش کاربر"
}}

قوانین:
- relevance_to_user_role عددی بین 0.0 تا 1.0
- is_related_to_user اگر relevance >= 0.5 باشد true
- topics حداکثر 5 مورد
- اگر فایل تهدید است، threat_level را بالا بگذار
"""


def _extract_json(text):
    """استخراج JSON از پاسخ LLM"""
    if not text:
        return None
    text = text.strip()
    # حذف markdown code fence
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    # پیدا کردن اولین { و آخرین }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception as e:
        log.error(f"JSON parse error: {e}\nText: {text[:300]}")
        return None


def _get_user_context(user):
    """جمع‌آوری context کاربر برای prompt"""
    user_roles = list(user.groups.values_list('name', flat=True))
    prev = UserBehaviorAnalysis.objects.filter(user=user).first()

    previous_files = prev.total_files if prev else 0
    top_topics = prev.top_topics if prev and prev.top_topics else []

    return {
        'user_roles': user_roles or ['user'],
        'previous_files': previous_files,
        'top_topics': top_topics,
    }


def analyze_and_save(uploaded_file):
    """
    تحلیل یک فایل آپلودشده با AI و ذخیره در FileAIAnalysis.
    Returns: FileAIAnalysis or None
    """
    try:
        user = uploaded_file.uploaded_by

        # خواندن محتوا
        try:
            file_info = FileReader.read_file(uploaded_file.file)
            content = file_info.get('content', '') or ''
            file_type = file_info.get('extension', 'unknown')
        except Exception as e:
            log.warning(f"FileReader error: {e}")
            content = f"[خطا در خواندن فایل: {e}]"
            file_type = 'unknown'

        # کوتاه کردن محتوا
        content_for_prompt = content[:5000] if content else '[محتوای متنی ندارد یا خالی است]'

        ctx = _get_user_context(user)
        prompt = ANALYSIS_PROMPT.format(
            username=user.username,
            user_roles=', '.join(ctx['user_roles']),
            previous_files=ctx['previous_files'],
            top_topics=json.dumps(ctx['top_topics'], ensure_ascii=False) if ctx['top_topics'] else 'ندارد',
            file_name=uploaded_file.file.name.split('/')[-1],
            file_size=uploaded_file.file.size,
            file_type=file_type,
            content=content_for_prompt,
        )

        # فراخوانی LLM
        if not llm_service or not llm_service.is_available:
            log.warning("LLM not available, skipping auto analysis")
            return None

        raw_answer = llm_service._call_llm_stream(prompt)
        parsed = _extract_json(raw_answer)

        if not parsed:
            log.error(f"AI did not return valid JSON for file {uploaded_file.id}")
            parsed = {
                'topics': [],
                'summary': (raw_answer or '')[:500],
                'category': 'other',
                'threat_level': 'low',
                'relevance_to_user_role': 0.0,
                'is_related_to_user': True,
                'detected_keywords': [],
                'reason_for_relevance': 'تحلیل نامعتبر',
                'raw_response': (raw_answer or '')[:2000],
            }

        # ذخیره
        topics = parsed.get('topics') or []
        top_topic = topics[0]['name'] if topics and isinstance(topics[0], dict) else None

        analysis, _ = FileAIAnalysis.objects.update_or_create(
            file=uploaded_file,
            defaults={
                'user': user,
                'analysis_json': {
                    **parsed,
                    'file_id': uploaded_file.id,
                    'file_name': uploaded_file.file.name.split('/')[-1],
                    'analyzed_at': timezone.now().isoformat(),
                },
                'summary': parsed.get('summary', '')[:2000],
                'category': parsed.get('category', 'other'),
                'threat_level': parsed.get('threat_level', 'low'),
                'relevance_score': float(parsed.get('relevance_to_user_role', 0.0) or 0.0),
                'is_related': bool(parsed.get('is_related_to_user', True)),
                'user_role_at_upload': ', '.join(ctx['user_roles']),
                'top_topic': top_topic,
                'model_used': 'gemma3:27b',
            }
        )

        log.info(f"FileAIAnalysis saved for file_id={uploaded_file.id}, user={user.username}")
        return analysis

    except Exception as e:
        log.exception(f"analyze_and_save failed for file {uploaded_file.id}: {e}")
        return None


def refresh_user_behavior(user_id):
    """
    بازتولید UserBehaviorAnalysis برای یک کاربر.
    Returns: UserBehaviorAnalysis or None
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

    try:
        analyses = FileAIAnalysis.objects.filter(user=user)

        total = analyses.count()
        if total == 0:
            UserBehaviorAnalysis.objects.update_or_create(
                user=user,
                defaults={
                    'analysis_json': {'total': 0},
                    'total_files': 0,
                    'related_files_count': 0,
                    'unrelated_files_count': 0,
                    'suspicious_files_count': 0,
                    'relevance_avg': 0.0,
                    'related_percent': 0.0,
                    'suspicious_percent': 0.0,
                    'top_topics': [],
                    'file_types_distribution': {},
                    'ai_summary': 'کاربر هیچ فایل تحلیل‌شده‌ای ندارد.',
                }
            )
            return UserBehaviorAnalysis.objects.get(user=user)

        related = analyses.filter(is_related=True).count()
        unrelated = analyses.filter(is_related=False).count()
        suspicious = analyses.filter(threat_level__in=['medium', 'high', 'critical']).count()

        rel_avg = sum(a.relevance_score for a in analyses) / total

        # topic aggregation
        topic_counter = {}
        for a in analyses:
            for t in (a.analysis_json.get('topics') or []):
                if isinstance(t, dict) and t.get('name'):
                    name = t['name']
                    topic_counter[name] = topic_counter.get(name, 0) + 1

        top_topics = sorted(
            [{'name': k, 'count': v, 'weight': round(v / total, 3)} for k, v in topic_counter.items()],
            key=lambda x: -x['count']
        )[:5]

        # file types
        file_types = {}
        for a in analyses:
            fname = a.file.file.name if a.file and a.file.file else ''
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else 'unknown'
            file_types[ext] = file_types.get(ext, 0) + 1

        related_percent = round(related / total * 100, 2)
        suspicious_percent = round(suspicious / total * 100, 2)

        behavior, _ = UserBehaviorAnalysis.objects.update_or_create(
            user=user,
            defaults={
                'analysis_json': {
                    'total': total,
                    'related': related,
                    'unrelated': unrelated,
                    'suspicious': suspicious,
                    'relevance_avg': round(rel_avg, 3),
                    'top_topics': top_topics,
                    'file_types': file_types,
                },
                'total_files': total,
                'related_files_count': related,
                'unrelated_files_count': unrelated,
                'suspicious_files_count': suspicious,
                'relevance_avg': round(rel_avg, 3),
                'related_percent': related_percent,
                'suspicious_percent': suspicious_percent,
                'top_topics': top_topics,
                'file_types_distribution': file_types,
                'ai_summary': (
                    f"کاربر {user.username} دارای {total} فایل تحلیل‌شده است. "
                    f"{related_percent}% فایل‌ها مرتبط با نقش کاربر، "
                    f"{suspicious_percent}% مشکوک. "
                    f"موضوع غالب: {top_topics[0]['name'] if top_topics else '—'}."
                ),
            }
        )

        log.info(f"UserBehaviorAnalysis refreshed for user={user.username}")
        return behavior

    except Exception as e:
        log.exception(f"refresh_user_behavior failed for user_id={user_id}: {e}")
        return None