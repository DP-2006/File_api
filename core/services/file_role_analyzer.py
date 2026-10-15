# core/services/file_role_analyzer.py
"""
تحلیلگر مستقل مرتبط بودن فایل با نقش و سمت سازمانی کاربر.
بدون هیچ وابستگی به ai-service یا FastAPI.
"""
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any

from django.contrib.auth.models import User, Group
from django.utils import timezone

from core.models import UploadedFile
from core.models_role_profile import RoleProfile

logger = logging.getLogger(__name__)

# ---------- تنظیمات ----------
MAX_EXCERPT_CHARS = 8000          # حداکثر کاراکتر استخراجی از فایل
MIN_KEYWORD_LEN = 3               # حداقل طول کلیدواژه
TOP_KEYWORDS = 25                 # تعداد کلیدواژه نهایی
STOPWORDS_FA = {
    'و', 'در', 'به', 'از', 'که', 'این', 'را', 'با', 'است', 'برای', 'آن',
    'یک', 'خود', 'تا', 'هم', 'شد', 'بر', 'بود', 'گر', 'یا', 'شده', 'بوده',
    'می', 'های', 'ها', 'هایی', 'ای', 'اگر', 'اما', 'نیز', 'چون', 'بین',
    'هر', 'دو', 'بعد', 'قبل', 'روی', 'زیر', 'پیش', 'پس', 'چه', 'چون',
    'همه', 'هیچ', 'دیگر', 'فقط', 'بیش', 'کم', 'بسیار', 'همان', 'چنین',
}
STOPWORDS_EN = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'any', 'can',
    'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him',
    'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who',
    'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'that',
    'with', 'have', 'this', 'will', 'your', 'from', 'they', 'know', 'want',
    'been', 'good', 'much', 'some', 'time', 'very', 'when', 'come', 'here',
    'just', 'like', 'long', 'make', 'many', 'over', 'such', 'take', 'than',
    'them', 'well', 'were', 'what', 'would', 'there', 'their', 'about',
}
TEXT_EXTENSIONS = {
    '.txt', '.md', '.csv', '.log', '.json', '.xml', '.yaml', '.yml',
    '.html', '.htm', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.cs',
    '.go', '.rb', '.php', '.sh', '.bat', '.ps1', '.sql', '.ini', '.cfg',
    '.conf', '.env',
}


# ---------- ساختار نتیجه ----------
@dataclass
class RoleAnalysisResult:
    relevance_score: float = 0.0
    is_related: bool = False
    keyword_hits: list = field(default_factory=list)
    off_role_signals: list = field(default_factory=list)
    reasoning: str = ''
    risk_level: str = 'low'
    role_text_snapshot: str = ''
    file_excerpt: str = ''
    engine_version: str = 'v1'

    def to_dict(self) -> dict:
        return asdict(self)

def _extract_text_from_uploaded_file(uploaded: UploadedFile) -> str:
    """تلاش برای خواندن متن فایل. در صورت عدم پشتیبانی، رشته خالی."""
    if not uploaded or not uploaded.file:
        return ''
    name = (uploaded.file.name or '').lower()
    ext = os.path.splitext(name)[1]

    if ext not in TEXT_EXTENSIONS:
        return ''

    try:
        uploaded.file.open('rb')
        raw = uploaded.file.read(MAX_EXCERPT_CHARS * 4)
        uploaded.file.close()
    except Exception as e:
        logger.warning('read file failed: %s', e)
        return ''

    for enc in ('utf-8', 'utf-8-sig', 'cp1256', 'latin-1'):
        try:
            text = raw.decode(enc)
            return text[:MAX_EXCERPT_CHARS]
        except UnicodeDecodeError:
            continue
    return ''


# ---------- توکن‌سازی و کلیدواژه ----------
def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    # حروف فارسی/عربی + لاتین + اعداد
    tokens = re.findall(r'[\u0600-\u06FF\w]{2,}', text.lower())
    out = []
    for t in tokens:
        if t in STOPWORDS_FA or t in STOPWORDS_EN:
            continue
        if len(t) < MIN_KEYWORD_LEN:
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


def _top_keywords(text: str, k: int = TOP_KEYWORDS) -> list[dict]:
    tokens = _tokenize(text)
    if not tokens:
        return []
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    total = sum(freq.values()) or 1
    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:k]
    return [
        {'kw': kw, 'count': cnt, 'weight': round(cnt / total, 4)}
        for kw, cnt in items
    ]


# ---------- هسته تحلیل ----------
def _compute_relevance(
    role_keywords: list[dict],
    file_keywords: list[dict],
) -> tuple[float, list[dict], list[dict]]:
    """
    شباهت وزنی بین دو مجموعه کلیدواژه.
    خروجی: (score, hits, misses)
    """
    if not role_keywords or not file_keywords:
        return 0.0, [], []

    role_map = {k['kw']: k['weight'] for k in role_keywords}
    file_map = {k['kw']: k['weight'] for k in file_keywords}

    hits = []
    for kw, fw in file_map.items():
        if kw in role_map:
            hits.append({
                'kw': kw,
                'count': next((x['count'] for x in file_keywords if x['kw'] == kw), 0),
                'weight': round(min(fw, role_map[kw]), 4),
            })

    # نرمال‌سازی: مجموع وزن hits تقسیم بر مجموع وزن کل کلیدواژه‌های نقش
    role_total = sum(role_map.values()) or 1.0
    hit_total = sum(h['weight'] for h in hits)
    score = min(1.0, round(hit_total / role_total, 4))

    # سیگنال‌های خارج از نقش: کلیدواژه‌های پرتکرار فایل که در نقش نیستند
    misses = []
    for kw, fw in sorted(file_map.items(), key=lambda x: x[1], reverse=True):
        if kw not in role_map and fw >= 0.02:  # فقط وزن‌های قابل توجه
            misses.append({'kw': kw, 'weight': round(fw, 4)})
        if len(misses) >= 10:
            break

    return score, hits, misses


def _decide_related(score: float, hits_count: int) -> bool:
    # آستانه سختگیرانه‌تر برای مرتبط بودن
    return score >= 0.08 and hits_count >= 2


def _decide_risk(
    score: float,
    is_related: bool,
    user_is_staff: bool,
    file_ext: str,
) -> str:
    # ریسک بالا: فایل حساس در کاربر غیرمرتبط، یا فایل اجرایی از کاربر غیرمجاز
    sensitive_ext = {'.exe', '.dll', '.bat', '.ps1', '.sh', '.msi', '.vbs'}
    if file_ext in sensitive_ext and not user_is_staff:
        return 'high'
    if not is_related and score < 0.02:
        return 'medium'
    if not is_related:
        return 'medium'
    return 'low'


# ---------- API عمومی ----------
def analyze_file_for_user(
    uploaded: UploadedFile,
    user: User,
) -> RoleAnalysisResult:
    """
    تحلیل کامل یک فایل برای یک کاربر.
    خروجی: RoleAnalysisResult
    """
    result = RoleAnalysisResult()

    # ۱) نقش کاربر
    group: Group | None = user.groups.first()
    role_profile: RoleProfile | None = None
    if group:
        try:
            role_profile = group.role_profile  # OneToOne
        except RoleProfile.DoesNotExist:
            role_profile = None

    role_text = ''
    if role_profile and role_profile.is_active:
        role_text = role_profile.get_effective_role_text() or ''
    result.role_text_snapshot = role_text

    # ۲) متن فایل
    file_text = _extract_text_from_uploaded_file(uploaded)
    result.file_excerpt = file_text[:MAX_EXCERPT_CHARS]

    # ۳) کلیدواژه‌ها
    role_kw = _top_keywords(role_text)
    file_kw = _top_keywords(file_text)

    # ۴) امتیاز
    score, hits, misses = _compute_relevance(role_kw, file_kw)
    result.relevance_score = score
    result.keyword_hits = hits
    result.off_role_signals = misses
    result.is_related = _decide_related(score, len(hits))

    # ۵) ریسک
    ext = os.path.splitext((uploaded.file.name or '').lower())[1]
    result.risk_level = _decide_risk(
        score, result.is_related, user.is_staff, ext
    )

    # ۶) استدلال متنی
    if not role_text and not file_text:
        result.reasoning = 'نه متن نقش و نه متن فایل قابل استخراج نبود؛ تحلیل ناقص.'
    elif not role_text:
        result.reasoning = 'برای نقش کاربر RoleProfile تنظیم نشده است.'
    elif not file_text:
        result.reasoning = 'فرمت فایل متنی نیست و استخراج متن ممکن نشد.'
    else:
        result.reasoning = (
            f"تعداد {len(hits)} کلیدواژه مشترک با نقش؛ "
            f"امتیاز وزنی {score:.4f}. "
            f"{'مرتبط' if result.is_related else 'نامرتبط'} تشخیص داده شد."
        )

    return result


def upsert_file_role_analysis(
    uploaded: UploadedFile,
    user: User,
) -> 'FileRoleAnalysis':  # noqa: F821
    """
    تحلیل را انجام می‌دهد و در دیتابیس ذخیره/به‌روزرسانی می‌کند.
    """
    from core.models import FileRoleAnalysis  # import داخل تابع برای جلوگیری از circular

    result = analyze_file_for_user(uploaded, user)
    group = user.groups.first()

    obj, _created = FileRoleAnalysis.objects.update_or_create(
        file=uploaded,
        user=user,
        defaults={
            'role_group': group,
            'role_text_snapshot': result.role_text_snapshot,
            'file_excerpt': result.file_excerpt,
            'relevance_score': result.relevance_score,
            'is_related': result.is_related,
            'keyword_hits': result.keyword_hits,
            'off_role_signals': result.off_role_signals,
            'reasoning': result.reasoning,
            'risk_level': result.risk_level,
            'status': 'done',
            'error_message': None,
            'engine_version': result.engine_version,
        },
    )
    return obj