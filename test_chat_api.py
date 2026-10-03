# test_chat_api.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiosk.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import UploadedFile


def main():
    admin = User.objects.filter(is_staff=True).first()
    uploaded = UploadedFile.objects.filter(is_deleted=False, file__icontains='Ordi').first()

    if not admin or not uploaded:
        print("ادمین یا فایل پیدا نشد")
        return

    client = Client()
    client.force_login(admin)

    # ۱. ساخت جلسه
    print("▶ ساخت جلسه چت...")
    r = client.post('/api/report-chat/start/', {
        'file_ids': [uploaded.id],
        'target_user_id': uploaded.uploaded_by_id,
        'title': 'تست API',
    }, content_type='application/json')
    print(f"  status={r.status_code}, body={r.json()}")
    if r.status_code != 200:
        return
    session_id = r.json()['session_id']

    # ۲. پرسیدن سوال
    print(f"\n▶ ارسال سوال به جلسه #{session_id}...")
    r = client.post(f'/api/report-chat/{session_id}/ask/', {
        'question': 'این فایل درباره چیست؟',
    }, content_type='application/json')
    print(f"  status={r.status_code}, body={r.json()}")

    # ۳. دریافت پیام‌ها
    print(f"\n▶ دریافت پیام‌های جلسه #{session_id}...")
    r = client.get(f'/api/report-chat/{session_id}/')
    data = r.json()
    print(f"  status={r.status_code}, تعداد پیام‌ها={len(data.get('messages', []))}")
    for m in data.get('messages', []):
        print(f"    [{m['role']}] {m['content'][:80]}")


if __name__ == '__main__':
    main()