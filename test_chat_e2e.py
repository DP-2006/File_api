# test_chat_e2e.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiosk.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UploadedFile
from core.models_report_chat import ReportChatSession
from core.services.report_chat_service import ReportChatService


def main():
    # 1. یک ادمین پیدا کن
    admin = User.objects.filter(is_staff=True).first()
    if not admin:
        print("❌ هیچ ادمینی نیست")
        return
    print(f"👤 ادمین: {admin.username}")

    # 2. یک فایل آپلودشده پیدا کن
    uploaded = UploadedFile.objects.filter(is_deleted=False, file__icontains='Ordi').first()
    if not uploaded:
        print("❌ هیچ فایلی آپلود نشده")
        return
    print(f"📄 فایل: {uploaded.file.name} (user={uploaded.uploaded_by.username})")

    # 3. جلسه جدید بساز
    session = ReportChatSession.objects.create(
        admin=admin,
        title='تست E2E',
        target_user=uploaded.uploaded_by,
    )
    session.files.add(uploaded)
    print(f"🗂️  جلسه #{session.id} ساخته شد")

    # 4. context را بساز و چاپ کن (فقط ۵۰۰ کاراکتر اول)
    svc = ReportChatService()
    ctx = svc.build_context(session)
    print(f"\n📋 context ({len(ctx)} chars):\n{ctx[:500]}\n...")

    # 5. یک سوال بپرس
    print("\n❓ سوال: این فایل درباره چیست؟")
    result = svc.ask(session, 'این فایل درباره چیست؟ خلاصه بده.')
    print(f"\n💬 پاسخ: {result.get('answer', result)}\n")

    # 6. پیام‌های ذخیره‌شده را چک کن
    print(f"📨 تعداد پیام‌های جلسه: {session.messages.count()}")
    for m in session.messages.all():
        print(f"  [{m.role}] {m.content[:80]}")


if __name__ == '__main__':
    main()