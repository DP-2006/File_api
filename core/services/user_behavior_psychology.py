# core/services/user_behavior_psychology.py
"""
تحلیل روانشناسی رفتار کاربر بر اساس داده‌های محلی.
بدون هیچ وابستگی به ai-service.
"""
import logging
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from core.models import (
    UserActivity,
    FileActionLog,
    LoginLog,
    UploadedFile,
    FileRoleAnalysis,
)
from core.models_user_behavior import UserBehaviorAnalysis

logger = logging.getLogger(__name__)

# ---------- تنظیمات ----------
WINDOW_DAYS = 30                 # بازه تحلیل
OFF_HOURS_START = 22             # ۲۲ شب
OFF_HOURS_END = 6                # ۶ صبح
HIGH_RISK_THRESHOLD = 0.35       # آستانه هشدار
ENGINE_VERSION = 'psy-v1'


@dataclass
class PsychologyResult:
    # ---- امتیازهای کلیدی (0..1) ----
    risk_score: float = 0.0
    anomaly_score: float = 0.0
    stress_index: float = 0.0
    role_fit_score: float = 0.0

    # ---- الگوهای رفتاری ----
    off_hours_activity_ratio: float = 0.0
    deletion_ratio: float = 0.0
    download_upload_ratio: float = 0.0
    login_fail_ratio: float = 0.0
    bulk_upload_flag: bool = False
    off_role_upload_flag: bool = False

    # ---- شمارنده‌ها ----
    total_activities: int = 0
    total_uploads: int = 0
    total_downloads: int = 0
    total_deletes: int = 0
    total_logins_failed: int = 0
    off_hours_count: int = 0

    # ---- روایت متنی ----
    narrative: str = ''
    signals: list = field(default_factory=list)
    recommended_action: str = 'none'

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- توابع کمکی ----------
def _safe_ratio(num: float, den: float) -> float:
    if not den:
        return 0.0
    return round(min(1.0, num / den), 4)


def _is_off_hours(dt) -> bool:
    if not dt:
        return False
    h = dt.hour
    return h >= OFF_HOURS_START or h < OFF_HOURS_END


def _collect_window(user: User, days: int = WINDOW_DAYS):
    since = timezone.now() - timedelta(days=days)
    activities = UserActivity.objects.filter(user=user, created_at__gte=since)
    logs = FileActionLog.objects.filter(user=user, action_time__gte=since)
    logins_failed = LoginLog.objects.filter(
        user=user, success=False, login_time__gte=since
    )
    logins_total = LoginLog.objects.filter(user=user, login_time__gte=since)
    return activities, logs, logins_failed, logins_total


# ---------- هسته تحلیل ----------
def _compute_behavioral_patterns(user: User) -> PsychologyResult:
    result = PsychologyResult()

    activities, logs, logins_failed, logins_total = _collect_window(user)

    # --- شمارنده‌ها ---
    result.total_activities = activities.count()
    result.total_uploads = activities.filter(activity_type='upload').count()
    result.total_downloads = activities.filter(activity_type='download').count()
    result.total_deletes = activities.filter(activity_type='delete').count()
    result.total_logins_failed = logins_failed.count()

    # --- فعالیت در ساعات غیرکاری ---
    off_hours_acts = sum(1 for a in activities if _is_off_hours(a.created_at))
    result.off_hours_count = off_hours_acts
    result.off_hours_activity_ratio = _safe_ratio(
        off_hours_acts, result.total_activities
    )

    # --- نسبت حذف ---
    result.deletion_ratio = _safe_ratio(
        result.total_deletes, result.total_uploads or 1
    )

    # --- نسبت دانلود به آپلود ---
    result.download_upload_ratio = _safe_ratio(
        result.total_downloads, result.total_uploads or 1
    )

    # --- نرخ شکست ورود ---
    result.login_fail_ratio = _safe_ratio(
        result.total_logins_failed, logins_total.count() or 1
    )

    # --- آپلود انبوه: بیش از ۵ فایل در یک روز ---
    one_day_ago = timezone.now() - timedelta(days=1)
    recent_uploads = activities.filter(
        activity_type='upload', created_at__gte=one_day_ago
    ).count()
    result.bulk_upload_flag = recent_uploads >= 5

    return result


def _compute_role_fit(user: User) -> tuple[float, bool, list[dict]]:
    """
    نقش‌پذیری: چقدر فایل‌های آپلودی کاربر با نقش او هم‌خوان است.
    خروجی: (score 0..1, off_role_flag, top_off_role_files)
    """
    analyses = FileRoleAnalysis.objects.filter(user=user, status='done')
    total = analyses.count()
    if total == 0:
        return 0.0, False, []

    related = analyses.filter(is_related=True).count()
    role_fit = round(related / total, 4)

    # فایل‌های مشکوک (نامرتبط با ریسک بالا)
    suspicious = analyses.filter(
        is_related=False, risk_level__in=['medium', 'high']
    ).values('id', 'file_id', 'risk_level', 'relevance_score')[:10]
    suspicious_list = list(suspicious)

    off_role_flag = (1 - role_fit) >= 0.6 and total >= 3
    return role_fit, off_role_flag, suspicious_list


def _compute_scores(result: PsychologyResult) -> None:
    """ترکیب سیگنال‌ها به امتیازهای نهایی."""
    # stress: فشار کاری (فعالیت خارج ساعت + حجم بالا + شکست ورود)
    stress = (
        0.4 * result.off_hours_activity_ratio
        + 0.3 * min(1.0, result.total_activities / 200.0)
        + 0.3 * result.login_fail_ratio
    )
    result.stress_index = round(min(1.0, stress), 4)

    # anomaly: رفتار غیرعادی (نسبت حذف، دانلود زیاد، شکست ورود)
    anomaly = (
        0.35 * result.deletion_ratio
        + 0.25 * min(1.0, result.download_upload_ratio / 5.0)
        + 0.25 * result.login_fail_ratio
        + 0.15 * (1.0 if result.bulk_upload_flag else 0.0)
    )
    result.anomaly_score = round(min(1.0, anomaly), 4)

    # risk: ترکیب ناسازگاری با نقش + ناهنجاری + ساعت غیرکاری
    risk = (
        0.45 * (1.0 - result.role_fit_score)
        + 0.30 * result.anomaly_score
        + 0.15 * result.off_hours_activity_ratio
        + 0.10 * (1.0 if result.off_role_upload_flag else 0.0)
    )
    result.risk_score = round(min(1.0, risk), 4)


def _build_narrative(result: PsychologyResult, user: User) -> str:
    parts = []
    parts.append(f"کاربر {user.username} در {WINDOW_DAYS} روز اخیر:")

    if result.total_activities == 0:
        parts.append("هیچ فعالیتی ثبت نشده است.")
        return " ".join(parts)

    parts.append(f"{result.total_activities} فعالیت، {result.total_uploads} آپلود، "
                 f"{result.total_downloads} دانلود، {result.total_deletes} حذف.")

    if result.off_hours_activity_ratio >= 0.4:
        parts.append(f"⚠️ {result.off_hours_activity_ratio*100:.0f}٪ فعالیت‌ها خارج ساعت کاری.")
    if result.deletion_ratio >= 0.5 and result.total_deletes >= 3:
        parts.append(f"⚠️ نرخ حذف بالا ({result.deletion_ratio*100:.0f}٪).")
    if result.login_fail_ratio >= 0.4 and result.total_logins_failed >= 3:
        parts.append(f"⚠️ {result.total_logins_failed} ورود ناموفق.")
    if result.bulk_upload_flag:
        parts.append("⚠️ آپلود انبوه در ۲۴ ساعت اخیر.")
    if result.off_role_upload_flag:
        parts.append("⚠️ بخش زیادی از فایل‌ها با نقش سازمانی هم‌خوان نیست.")

    parts.append(f"امتیاز ریسک: {result.risk_score:.2f} | "
                 f"ناهنجاری: {result.anomaly_score:.2f} | "
                 f"فشار: {result.stress_index:.2f} | "
                 f"نقش‌پذیری: {result.role_fit_score:.2f}")
    return " ".join(parts)


def _recommend_action(result: PsychologyResult) -> str:
    if result.risk_score >= 0.7:
        return 'escalate'
    if result.risk_score >= HIGH_RISK_THRESHOLD:
        return 'monitor'
    return 'none'


# ---------- API عمومی ----------
def analyze_user_psychology(user: User, persist: bool = True) -> PsychologyResult:
    """
    تحلیل روانشناسی رفتار کاربر.
    اگر persist=True، در UserBehaviorAnalysis ذخیره می‌کند.
    """
    result = _compute_behavioral_patterns(user)

    # نقش‌پذیری
    role_fit, off_role_flag, suspicious = _compute_role_fit(user)
    result.role_fit_score = role_fit
    result.off_role_upload_flag = off_role_flag

    # امتیازها
    _compute_scores(result)

    # روایت و پیشنهاد
    result.narrative = _build_narrative(result, user)
    result.recommended_action = _recommend_action(result)

    # سیگنال‌های ساختاریافته
    signals = []
    if result.off_hours_activity_ratio >= 0.4:
        signals.append({'code': 'off_hours', 'value': result.off_hours_activity_ratio})
    if result.deletion_ratio >= 0.5:
        signals.append({'code': 'high_deletion', 'value': result.deletion_ratio})
    if result.login_fail_ratio >= 0.4:
        signals.append({'code': 'login_failures', 'value': result.login_fail_ratio})
    if result.bulk_upload_flag:
        signals.append({'code': 'bulk_upload', 'value': True})
    if result.off_role_upload_flag:
        signals.append({'code': 'off_role_files', 'value': True})
    if suspicious:
        signals.append({'code': 'suspicious_files', 'files': suspicious})
    result.signals = signals

    if persist:

        _persist(user, result)

    return result


def _persist(user: User, result: PsychologyResult) -> UserBehaviorAnalysis:
    payload = result.to_dict()

    total_files = UploadedFile.objects.filter(
        uploaded_by=user, is_deleted=False
    ).count()
    analyses = FileRoleAnalysis.objects.filter(user=user, status='done')
    related_files = analyses.filter(is_related=True).count()
    unrelated_files = analyses.filter(is_related=False).count()
    suspicious_files = analyses.filter(
        is_related=False, risk_level__in=['medium', 'high']
    ).count()

    # توزیع انواع فایل
    ext_counter: Counter = Counter()
    for f in UploadedFile.objects.filter(uploaded_by=user, is_deleted=False):
        ext = (f.file.name.rsplit('.', 1)[-1].lower() if f.file and '.' in f.file.name else 'other')
        ext_counter[ext] += 1

    # top topics از تحلیل‌های AI قبلی
    top_topics = []
    try:
        from core.models_file_analysis import FileAIAnalysis
        topic_counter: Counter = Counter()
        for a in FileAIAnalysis.objects.filter(user=user):
            if a.top_topic:
                topic_counter[a.top_topic] += 1
        top_topics = [
            {'name': k, 'count': v, 'weight': round(v / max(1, sum(topic_counter.values())), 4)}
            for k, v in topic_counter.most_common(5)
        ]
    except Exception:
        pass

    obj, _ = UserBehaviorAnalysis.objects.update_or_create(
        user=user,
        defaults={
            'analysis_json': payload,
            'total_files': total_files,
            'related_files_count': related_files,
            'unrelated_files_count': unrelated_files,
            'suspicious_files_count': suspicious_files,
            'relevance_avg': round(
                analyses.aggregate_from_db() if False else (
                    sum(a.relevance_score for a in analyses) / max(1, analyses.count())
                ), 4
            ),
            'related_percent': round(100.0 * related_files / max(1, analyses.count()), 2),
            'suspicious_percent': round(100.0 * suspicious_files / max(1, analyses.count()), 2),
            'top_topics': top_topics,
            'file_types_distribution': dict(ext_counter),
            'ai_summary': result.narrative,
        },
    )
    return obj