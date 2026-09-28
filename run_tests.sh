#!/bin/bash

echo "🚀 شروع اجرای تست‌ها..."
echo "========================================="

# تنظیم متغیرهای محیطی
export DJANGO_SETTINGS_MODULE=kiosk.settings
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/core:$(pwd)/kiosk"

# رفتن به پوشه tests
cd tests

# اجرای تست‌ها
pytest -v --tb=short --disable-warnings

# بازگشت به پوشه اصلی
cd ..

echo "========================================="
echo "✅ پایان اجرای تست‌ها"
