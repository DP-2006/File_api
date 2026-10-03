# core/services/ai_client.py
"""
کلاینت ارتباط امن (HMAC-SHA256) با سرویس FastAPI ai-service
پورت پیش‌فرض: 9000
"""

import hashlib
import hmac
import json
import sys
import time

import requests
from django.conf import settings


class AIServiceClient:
    """کلاینت HMAC برای سرویس FastAPI ai-service"""
    def __init__(self, base_url: str = None, secret: str = None, timeout: int = 600):
        self.base_url = (base_url or getattr(settings, 'AI_SERVICE_URL', 'http://127.0.0.1:9000')).rstrip('/')
        self.secret = (secret or getattr(settings, 'AI_SERVICE_SECRET', '')).encode('utf-8')
        self.timeout = timeout
        self.is_available = False

    def _sign(self, body_bytes: bytes, timestamp: str) -> str:
        msg = body_bytes + timestamp.encode('utf-8')
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _headers(self, body_bytes: bytes) -> dict:
        ts = str(int(time.time()))
        return {
            'Content-Type': 'application/json',
            'X-Timestamp': ts,
            'X-Signature': self._sign(body_bytes, ts),
        }

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        url = f"{self.base_url}{path}"
        try:
            r = requests.post(url, data=body, headers=self._headers(body), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            return {'error': str(e), 'path': path}

    def health(self) -> dict:
        """تست اتصال به FastAPI (بدون HMAC)"""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=10)
            if r.status_code == 200:
                self.is_available = True
                return {'success': True, 'data': r.json()}
            return {'success': False, 'message': f'status={r.status_code}'}
        except Exception as e:
            self.is_available = False
            return {'success': False, 'message': str(e)}

    # ---------- RAG ----------
    def rag_query(self, question: str) -> dict:
        """پرسش از RAG. خروجی: {answer: str, sources: list}"""
        return self._post("/rag/query", {"question": question})

    # ---------- Chat with context ----------
    def chat_with_context(self, question, context_text="", file_ids=None,
                          history=None, user_id=None) -> dict:
        """
        چت با context دلخواه (بدون RAG).
        payload: {question, context_text, file_ids, history[{role,content}], user_id}
        output:  {answer, model, file_ids, user_id}
        """
        return self._post("/chat/with-context", {
            "question": question,
            "context_text": context_text or "",
            "file_ids": file_ids or [],
            "history": history or [],
            "user_id": str(user_id) if user_id else None,
        })


_is_management = any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'createsuperuser', 'shell', 'test', 'check'])
if not _is_management:
    try:
        ai_client = AIServiceClient()
    except Exception as e:
        print(f"⚠️ خطا در ایجاد AIServiceClient: {e}")
        ai_client = None
else:
    ai_client = None