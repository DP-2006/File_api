FROM python:3.12-slim

WORKDIR /app

# کپی فایل requirements
COPY requirements.txt .

# نصب وابستگی‌ها
RUN pip install --no-cache-dir -r requirements.txt

# کپی بقیه فایل‌ها
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p /app/staticfiles /app/media /app/uploads

# پورت
EXPOSE 8000

# اجرا
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]