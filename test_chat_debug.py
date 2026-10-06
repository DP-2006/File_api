# test_chat_debug.py
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

    print(f" ادمین: {admin.username} (id={admin.id})")
    print(f" فایل: {uploaded.id} - {uploaded.file.name}")

    client = Client()
    client.force_login(admin)

    # شبیه‌سازی دقیق درخواست JS مرورگر
    print("\n POST /api/report-chat/start/")
    r = client.post(
        '/api/report-chat/start/',
        data={
            'file_ids': [uploaded.id],
            'target_user_id': uploaded.uploaded_by_id,
            'title': 'تست Debug',
        },
        content_type='application/json',
    )
    print(f"  status = {r.status_code}")
    print(f"  content-type = {r.get('Content-Type')}")
    try:
        print(f"  body = {r.json()}")
    except Exception:
        print(f"  body (raw) = {r.content[:500]}")


if __name__ == '__main__':
    main()