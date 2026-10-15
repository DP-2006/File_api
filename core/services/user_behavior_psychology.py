# core/services/user_behavior_psychology.py
import logging
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import timedelta
import json
import urllib.request
import urllib.error
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

WINDOW_DAYS = 30               
OFF_HOURS_START = 22           
OFF_HOURS_END = 6               
HIGH_RISK_THRESHOLD = 0.35      
ENGINE_VERSION = 'psy-v1'


@dataclass
class PsychologyResult:
    
    risk_score: float = 0.0
    anomaly_score: float = 0.0
    stress_index: float = 0.0
    role_fit_score: float = 0.0

    off_hours_activity_ratio: float = 0.0
    deletion_ratio: float = 0.0
    download_upload_ratio: float = 0.0
    login_fail_ratio: float = 0.0
    bulk_upload_flag: bool = False
    off_role_upload_flag: bool = False

    total_activities: int = 0
    total_uploads: int = 0
    total_downloads: int = 0
    total_deletes: int = 0
    total_logins_failed: int = 0
    off_hours_count: int = 0

    narrative: str = ''
    signals: list = field(default_factory=list)
    recommended_action: str = 'none'

    def to_dict(self) -> dict:
        return asdict(self)


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


def _compute_behavioral_patterns(user: User) -> PsychologyResult:
    result = PsychologyResult()

    activities, logs, logins_failed, logins_total = _collect_window(user)

    result.total_activities = activities.count()
    result.total_uploads = activities.filter(activity_type='upload').count()
    result.total_downloads = activities.filter(activity_type='download').count()
    result.total_deletes = activities.filter(activity_type='delete').count()
    result.total_logins_failed = logins_failed.count()

    off_hours_acts = sum(1 for a in activities if _is_off_hours(a.created_at))
    result.off_hours_count = off_hours_acts
    result.off_hours_activity_ratio = _safe_ratio(
        off_hours_acts, result.total_activities
    )

    result.deletion_ratio = _safe_ratio(
        result.total_deletes, result.total_uploads or 1
    )

    result.download_upload_ratio = _safe_ratio(
        result.total_downloads, result.total_uploads or 1
    )

    result.login_fail_ratio = _safe_ratio(
        result.total_logins_failed, logins_total.count() or 1
    )

    one_day_ago = timezone.now() - timedelta(days=1)
    recent_uploads = activities.filter(
        activity_type='upload', created_at__gte=one_day_ago
    ).count()
    result.bulk_upload_flag = recent_uploads >= 5

    return result


def _compute_role_fit(user: User) -> tuple[float, bool, list[dict]]:
    analyses = FileRoleAnalysis.objects.filter(user=user, status='done')
    total = analyses.count()
    if total == 0:
        return 0.0, False, []

    related = analyses.filter(is_related=True).count()
    role_fit = round(related / total, 4)

    suspicious = analyses.filter(
        is_related=False, risk_level__in=['medium', 'high']
    ).values('id', 'file_id', 'risk_level', 'relevance_score')[:10]
    suspicious_list = list(suspicious)

    off_role_flag = (1 - role_fit) >= 0.6 and total >= 3
    return role_fit, off_role_flag, suspicious_list


def _compute_scores(result: PsychologyResult) -> None:
    stress = (
        0.4 * result.off_hours_activity_ratio
        + 0.3 * min(1.0, result.total_activities / 200.0)
        + 0.3 * result.login_fail_ratio
    )
    result.stress_index = round(min(1.0, stress), 4)

    anomaly = (
        0.35 * result.deletion_ratio
        + 0.25 * min(1.0, result.download_upload_ratio / 5.0)
        + 0.25 * result.login_fail_ratio
        + 0.15 * (1.0 if result.bulk_upload_flag else 0.0)
    )
    result.anomaly_score = round(min(1.0, anomaly), 4)

    risk = (
        0.45 * (1.0 - result.role_fit_score)
        + 0.30 * result.anomaly_score
        + 0.15 * result.off_hours_activity_ratio
        + 0.10 * (1.0 if result.off_role_upload_flag else 0.0)
    )
    result.risk_score = round(min(1.0, risk), 4)


def _build_narrative(result: PsychologyResult, user: User) -> str:
    parts = []
    parts.append(f"Ú©Ø§Ø±Ø¨Ø± {user.username} Ø¯Ø± {WINDOW_DAYS} Ø±ÙˆØ² Ø§Ø®ÛŒØ±:")

    if result.total_activities == 0:
        parts.append("Ù‡ÛŒÚ† ÙØ¹Ø§Ù„ÛŒØªÛŒ Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.")
        return " ".join(parts)

    parts.append(f"{result.total_activities} ÙØ¹Ø§Ù„ÛŒØªØŒ {result.total_uploads} Ø¢Ù¾Ù„ÙˆØ¯ØŒ "
                 f"{result.total_downloads} Ø¯Ø§Ù†Ù„ÙˆØ¯ØŒ {result.total_deletes} Ø­Ø°Ù.")

    if result.off_hours_activity_ratio >= 0.4:
        parts.append(f" {result.off_hours_activity_ratio*100:.0f}Ùª ÙØ¹Ø§Ù„ÛŒØªâ€ŒÙ‡Ø§ Ø®Ø§Ø±Ø¬ Ø³Ø§Ø¹Øª Ú©Ø§Ø±ÛŒ.")
    if result.deletion_ratio >= 0.5 and result.total_deletes >= 3:
        parts.append(f" Ù†Ø±Ø® Ø­Ø°Ù Ø¨Ø§Ù„Ø§ ({result.deletion_ratio*100:.0f}Ùª).")
    if result.login_fail_ratio >= 0.4 and result.total_logins_failed >= 3:
        parts.append(f" {result.total_logins_failed} ÙˆØ±ÙˆØ¯ Ù†Ø§Ù…ÙˆÙÙ‚.")
    if result.bulk_upload_flag:
        parts.append(" Ø¢Ù¾Ù„ÙˆØ¯ Ø§Ù†Ø¨ÙˆÙ‡ Ø¯Ø± Û²Û´ Ø³Ø§Ø¹Øª Ø§Ø®ÛŒØ±.")
    if result.off_role_upload_flag:
        parts.append(" Ø¨Ø®Ø´ Ø²ÛŒØ§Ø¯ÛŒ Ø§Ø² ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ Ø¨Ø§ Ù†Ù‚Ø´ Ø³Ø§Ø²Ù…Ø§Ù†ÛŒ Ù‡Ù…â€ŒØ®ÙˆØ§Ù† Ù†ÛŒØ³Øª.")

    parts.append("Ø§Ù…ØªÛŒØ§Ø² Ø±ÛŒØ³Ú©: {result.risk_score:.2f} | "
                 "Ù†Ø§Ù‡Ù†Ø¬Ø§Ø±ÛŒ: {result.anomaly_score:.2f} | "
                 "ÙØ´Ø§Ø±: {result.stress_index:.2f} | "
                 "Ù†Ù‚Ø´â€ŒÙ¾Ø°ÛŒØ±ÛŒ: {result.role_fit_score:.2f}")
    return " ".join(parts)


def _recommend_action(result: PsychologyResult) -> str:
    if result.risk_score >= 0.7:
        return 'escalate'
    if result.risk_score >= HIGH_RISK_THRESHOLD:
        return 'monitor'
    return 'none'



LLM_TIMEOUT_SECONDS = 600
LLM_MAX_TOKENS = 800
LLM_TEMPERATURE = 0.5
LLM_TOP_P = 0.9
def _get_ollama_config() -> dict | None:
    """Ø®ÙˆØ§Ù†Ø¯Ù† ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ollama Ø§Ø² AISettings."""
    try:
        from core.models import AISettings
        s = AISettings.get_settings()
        if not s or not s.is_active:
            return None
        return {
            'url': f"{s.get_full_url()}/api/generate",
            'model': s.ollama_model or 'gemma3:27b',
            'timeout': max(LLM_TIMEOUT_SECONDS, int(s.timeout_seconds or 600)),
        }
    except Exception as e:
        logger.warning('ollama config failed: %s', e)
        return None


def _build_llm_prompt(user, result, role_text):
    """ساخت پرامپت روانشناختی برای Ollama."""
    return (
        "You are an organizational psychologist. Based on the data below, "
        "write ONE short psychological analysis paragraph in fluent Persian. "
        "Rules: (1) do NOT repeat any numbers or labels. (2) No introduction. "
        "(3) Max 5 sentences. (4) Start with the word 'تحلیل:'.\n\n"
        "=== DATA ===\n"
        "user: " + user.username + "\n"
        "role: " + (role_text or "undefined") + "\n"
        "total_activities: " + str(result.total_activities) + "\n"
        "uploads: " + str(result.total_uploads) + "\n"
        "downloads: " + str(result.total_downloads) + "\n"
        "deletes: " + str(result.total_deletes) + "\n"
        "failed_logins: " + str(result.total_logins_failed) + "\n"
        "off_hours_ratio: " + str(round(result.off_hours_activity_ratio, 2)) + "\n"
        "deletion_ratio: " + str(round(result.deletion_ratio, 2)) + "\n"
        "bulk_upload: " + ("yes" if result.bulk_upload_flag else "no") + "\n"
        "off_role_files: " + ("yes" if result.off_role_upload_flag else "no") + "\n"
        "risk_score: " + str(round(result.risk_score, 2)) + "\n"
        "anomaly_score: " + str(round(result.anomaly_score, 2)) + "\n"
        "stress_index: " + str(round(result.stress_index, 2)) + "\n"
        "role_fit_score: " + str(round(result.role_fit_score, 2)) + "\n\n"
        "Analyze:"
    )

def _enrich_with_llm(
    user: User,
    result: PsychologyResult,
    role_text: str = '',
) -> str | None:
    """
    ØªÙ…Ø§Ø³ Ù…Ø³ØªÙ‚ÛŒÙ… Ø¨Ø§ Ollama Ø¨Ø±Ø§ÛŒ ØªÙˆÙ„ÛŒØ¯ Ø±ÙˆØ§ÛŒØª Ø±ÙˆØ§Ù†Ø´Ù†Ø§Ø®ØªÛŒ.
    Ø¯Ø± ØµÙˆØ±Øª Ø®Ø·Ø§ØŒ None Ø¨Ø±Ù…ÛŒâ€ŒÚ¯Ø±Ø¯Ø§Ù†Ø¯ (fallback Ø¨Ù‡ Ø±ÙˆØ§ÛŒØª Ø¢Ù…Ø§Ø±ÛŒ).
    """
    cfg = _get_ollama_config()
    if not cfg:
        return None

    prompt = _build_llm_prompt(user, result, role_text)

    payload = json.dumps({
        'model': cfg['model'],
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': 0.3,
            'num_predict': LLM_MAX_TOKENS,
        },
    }).encode('utf-8')

    req = urllib.request.Request(
        cfg['url'],
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=cfg['timeout']) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        data = json.loads(raw)
        text = (data.get('response') or '').strip()
        return text or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning('ollama enrich failed: %s', e)
        return None
    except Exception as e:
        logger.exception('ollama enrich unexpected: %s', e)
        return None


def analyze_user_psychology(user: User, persist: bool = True) -> PsychologyResult:
    result = _compute_behavioral_patterns(user)

    role_fit, off_role_flag, suspicious = _compute_role_fit(user)
    result.role_fit_score = role_fit
    result.off_role_upload_flag = off_role_flag

    _compute_scores(result)

    result.narrative = _build_narrative(result, user)

    role_text = ''
    try:
        group = user.groups.first()
        if group and hasattr(group, 'role_profile') and group.role_profile.is_active:
            role_text = group.role_profile.get_effective_role_text() or ''
    except Exception:
        role_text = ''

    llm_text = _enrich_with_llm(user, result, role_text)
    if llm_text:
        result.narrative = (
            f"{llm_text}\n\nâ€” Ø®Ù„Ø§ØµÙ‡ Ø¢Ù…Ø§Ø±ÛŒ â€”\n{result.narrative}"
        )
        result.signals.append({'code': 'llm_enriched', 'value': True})

    result.recommended_action = _recommend_action(result)

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




from collections import Counter
from core.models_file_analysis import FileAIAnalysis


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

    ext_counter: Counter = Counter()
    for f in UploadedFile.objects.filter(uploaded_by=user, is_deleted=False):
        ext = (
            f.file.name.rsplit('.', 1)[-1].lower()
            if f.file and '.' in f.file.name
            else 'other'
        )
        ext_counter[ext] += 1

    top_topics = []
    try:
        topic_counter: Counter = Counter()
        for a in FileAIAnalysis.objects.filter(user=user):
            if a.top_topic:
                topic_counter[a.top_topic] += 1
        total_topics = max(1, sum(topic_counter.values()))
        top_topics = [
            {
                'name': k,
                'count': v,
                'weight': round(v / total_topics, 4),
            }
            for k, v in topic_counter.most_common(5)
        ]
    except Exception:
        pass

    analyses_count = max(1, analyses.count())

    obj, _ = UserBehaviorAnalysis.objects.update_or_create(
        user=user,
        defaults={
            'analysis_json': payload,
            'total_files': total_files,
            'related_files_count': related_files,
            'unrelated_files_count': unrelated_files,
            'suspicious_files_count': suspicious_files,
            'relevance_avg': round(
                sum(a.relevance_score for a in analyses) / analyses_count, 4
            ),
            'related_percent': round(100.0 * related_files / analyses_count, 2),
            'suspicious_percent': round(100.0 * suspicious_files / analyses_count, 2),
            'top_topics': top_topics,
            'file_types_distribution': dict(ext_counter),
            'ai_summary': result.narrative,
        },
    )
    return obj
