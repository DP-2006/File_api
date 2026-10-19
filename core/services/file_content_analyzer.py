# core/services/file_content_analyzer.py
"""
استخراج سریع محتوای فایل — بدون LLM.
برای متن/PDF/DOCX/XLSX: خواندن مستقیم.
برای عکس: متادیتا (ابعاد، فرمت) + EXIF.
هدف: < ۱ ثانیه هر فایل.
"""
import logging
import os
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 4000        # حداکثر متن استخراجی
MAX_PDF_PAGES = 5            # حداکثر صفحات PDF
TEXT_EXTS = {'.txt', '.md', '.csv', '.log', '.json', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf'}
DOC_EXTS = {'.docx'}
SHEET_EXTS = {'.xlsx', '.xlsm'}
PDF_EXTS = {'.pdf'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}


@dataclass
class ContentResult:
    kind: str = 'unknown'          # text / pdf / docx / sheet / image / unknown
    text: str = ''                 # متن استخراج‌شده
    metadata: dict = field(default_factory=dict)
    error: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


def _open_file(uploaded_file):
    """باز کردن فایل جنگو به‌صورت file-like."""
    uploaded_file.file.open('rb')
    return uploaded_file.file


def _read_bytes(uploaded_file, limit=None):
    f = _open_file(uploaded_file)
    try:
        data = f.read(limit) if limit else f.read()
    finally:
        try:
            f.close()
        except Exception:
            pass
    return data


def _extract_text(uploaded_file) -> ContentResult:
    res = ContentResult(kind='text')
    try:
        raw = _read_bytes(uploaded_file, limit=MAX_TEXT_CHARS * 4)
    except Exception as e:
        res.error = f'read fail: {e}'
        return res

    for enc in ('utf-8', 'utf-8-sig', 'cp1256', 'latin-1'):
        try:
            res.text = raw.decode(enc)[:MAX_TEXT_CHARS]
            res.metadata['encoding'] = enc
            return res
        except UnicodeDecodeError:
            continue
    res.error = 'decode failed'
    return res


def _extract_pdf(uploaded_file) -> ContentResult:
    res = ContentResult(kind='pdf')
    try:
        import PyPDF2
        f = _open_file(uploaded_file)
        reader = PyPDF2.PdfReader(f)
        res.metadata['pages'] = len(reader.pages)
        parts = []
        for i, page in enumerate(reader.pages[:MAX_PDF_PAGES]):
            try:
                txt = page.extract_text() or ''
                if txt.strip():
                    parts.append(f'--- page {i+1} ---\n{txt}')
            except Exception:
                continue
        res.text = '\n'.join(parts)[:MAX_TEXT_CHARS]
    except Exception as e:
        res.error = f'pdf fail: {e}'
    finally:
        try:
            uploaded_file.file.close()
        except Exception:
            pass
    return res


def _extract_docx(uploaded_file) -> ContentResult:
    res = ContentResult(kind='docx')
    try:
        import docx
        f = _open_file(uploaded_file)
        d = docx.Document(f)
        paras = [p.text for p in d.paragraphs if p.text.strip()]
        res.text = '\n'.join(paras)[:MAX_TEXT_CHARS]
        res.metadata['paragraphs'] = len(paras)
    except Exception as e:
        res.error = f'docx fail: {e}'
    finally:
        try:
            uploaded_file.file.close()
        except Exception:
            pass
    return res


def _extract_sheet(uploaded_file) -> ContentResult:
    res = ContentResult(kind='sheet')
    try:
        import openpyxl
        f = _open_file(uploaded_file)
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        res.metadata['sheets'] = wb.sheetnames
        parts = []
        for sh in wb.sheetnames[:3]:
            ws = wb[sh]
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= 30:
                    break
                rows.append(' | '.join('' if c is None else str(c) for c in row))
            if rows:
                parts.append(f'--- sheet: {sh} ---\n' + '\n'.join(rows))
        res.text = '\n'.join(parts)[:MAX_TEXT_CHARS]
        wb.close()
    except Exception as e:
        res.error = f'sheet fail: {e}'
    finally:
        try:
            uploaded_file.file.close()
        except Exception:
            pass
    return res


def _extract_image(uploaded_file) -> ContentResult:
    """استخراج محتوای عکس با vision (gemma3:27b multimodal)."""
    res = ContentResult(kind='image')
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        import io, base64, requests
        from core.models import AISettings

        f = _open_file(uploaded_file)
        img = Image.open(f)
        res.metadata['format'] = img.format
        res.metadata['size'] = list(img.size)
        res.metadata['mode'] = img.mode

        try:
            exif = img._getexif() if hasattr(img, '_getexif') else None
            if exif:
                exif_data = {}
                for k, v in exif.items():
                    tag = TAGS.get(k, k)
                    if tag in ('Make', 'Model', 'DateTime', 'Software'):
                        exif_data[tag] = str(v)
                res.metadata['exif'] = exif_data
        except Exception:
            pass

        try:
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            res.error = f'resize fail: {e}'
            return res
        finally:
            try: f.close()
            except Exception: pass

        try:
            s = AISettings.get_settings()
            url = f"http://{s.ollama_host}:{s.ollama_port}/api/generate"
            payload = {
                'model': s.ollama_model or 'gemma3:27b',
                'prompt': 'این عکس چه چیزی را نشان می‌دهد؟ اگر متن، سند، یا اطلاعات حساس در تصویر هست، آن را هم بنویس. توضیح مختصر و دقیق (حداکثر ۲۰۰ کلمه، فارسی).',
                'images': [b64],
                'stream': False,
                'options': {'temperature': 0.2, 'num_predict': 400},
            }
            r = requests.post(url, json=payload, timeout=180)
            r.raise_for_status()
            vision_text = r.json().get('response', '').strip()
            res.text = vision_text or 'تصویر بدون توضیح'
            res.metadata['vision'] = True
        except Exception as e:
            res.text = f"تصویر {res.metadata.get('format','')}"
            res.metadata['vision'] = False
            res.error = f'vision fail: {e}'
    except Exception as e:
        res.error = f'image fail: {e}'
    return res
def extract_content(uploaded_file) -> ContentResult:
    """
    تشخیص نوع فایل و استخراج محتوا.
    خروجی: ContentResult
    """
    if not uploaded_file or not uploaded_file.file:
        return ContentResult(kind='unknown', error='no file')

    name = (uploaded_file.file.name or '').lower()
    ext = os.path.splitext(name)[1]

    if ext in TEXT_EXTS:
        return _extract_text(uploaded_file)
    if ext in PDF_EXTS:
        return _extract_pdf(uploaded_file)
    if ext in DOC_EXTS:
        return _extract_docx(uploaded_file)
    if ext in SHEET_EXTS:
        return _extract_sheet(uploaded_file)
    if ext in IMAGE_EXTS:
        return _extract_image(uploaded_file)

    return ContentResult(kind='unknown', error=f'unsupported ext: {ext}')







# ---------- اتصال به FileAIAnalysis ----------
def ensure_file_analyzed(uploaded_file, force=False) -> 'FileAIAnalysis':  # noqa: F821
    """
    اگر FileAIAnalysis برای این فایل موجود نبود (یا force=True)،
    محتوا را استخراج و در DB ذخیره کن.
    """
    from core.models_file_analysis import FileAIAnalysis

    existing = FileAIAnalysis.objects.filter(file=uploaded_file).first()
    if existing and not force:
        # اگر متن استخراجی خالی بود، دوباره تلاش کن
        if existing.analysis_json and existing.analysis_json.get('text'):
            return existing
        if existing.analysis_json and existing.analysis_json.get('kind') == 'image':
            return existing

    content = extract_content(uploaded_file)

    # خلاصه اولیه (بدون LLM، سریع)
    if content.kind == 'image':
        summary = content.text or 'تصویر'
        top_topic = 'تصویر'
    elif content.text:
        summary = content.text[:300].strip()
        # top_topic: از کلمات پرتکرار (بدون LLM)
        top_topic = _guess_topic(content.text)
    else:
        summary = content.error or 'محتوای قابل استخراج نبود'
        top_topic = 'نامشخص'

    data = {
        'kind': content.kind,
        'text': content.text[:MAX_TEXT_CHARS],
        'metadata': content.metadata,
        'error': content.error,
        'summary': summary,
        'top_topic': top_topic,
    }

    obj, _ = FileAIAnalysis.objects.update_or_create(
        file=uploaded_file,
        defaults={
            'user': uploaded_file.uploaded_by,
            'analysis_json': data,
            'summary': summary[:1000],
            'top_topic': top_topic[:255],
            'threat_level': 'low',
            'relevance_score': 0.0,
            'is_related': True,
            'model_used': 'content_analyzer_v1',
        },
    )

    # index خودکار به FastAPI (fail-safe)
    try:
        if content.text and content.text.strip():
            from core.services.ai_client import AIServiceClient
            _c = AIServiceClient()
            _c._post("/rag/index-files", {
                "files": [{
                    "file_id": uploaded_file.id,
                    "user_id": uploaded_file.uploaded_by_id,
                    "file_name": (uploaded_file.file.name.split("/")[-1] if uploaded_file.file else ""),
                    "chunks": [content.text[:3000]],
                }]
            })
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"rag index fail file={uploaded_file.id}: {_e}")

    return obj


def _guess_topic(text: str) -> str:
    """حدس سریع موضوع از کلمات پرتکرار — بدون LLM."""
    import re
    from collections import Counter
    STOP = {'the', 'and', 'for', 'are', 'but', 'not', 'with', 'this', 'that', 'from',
            'و', 'در', 'به', 'از', 'که', 'این', 'را', 'با', 'است', 'برای', 'آن', 'یک'}
    tokens = re.findall(r'[\u0600-\u06FF\w]{3,}', text.lower())
    freq = Counter(t for t in tokens if t not in STOP)
    top = freq.most_common(3)
    return '، '.join(t for t, _ in top) if top else 'نامشخص'
