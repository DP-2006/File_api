# core/services/action_analyzer.py

import os
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from core.models import FileActionLog, AINotification, UploadedFile, AIThreatAlert
from core.services.file_reader import FileReader
from core.services.llm_service import llm_service


class ActionAnalyzer:
    """تحلیل عملیات کاربران با AI"""
    
    def __init__(self):
        self.llm = llm_service
    
    def analyze_action(self, user, action_type, file_obj, file_name=None, file_size=None, ip_address=None, recipient=None):
        """
        تحلیل یک عملیات (آپلود/دانلود) با AI
        
        Args:
            user: کاربری که عملیات را انجام داده
            action_type: نوع عملیات ('upload', 'download', 'delete', 'send')
            file_obj: شیء UploadedFile یا File
            file_name: نام فایل (اگر file_obj موجود نباشد)
            file_size: حجم فایل
            ip_address: IP کاربر
            recipient: کاربر دریافت‌کننده (برای عملیات send)
        """
        
        # 1. استخراج محتوای فایل
        content = ""
        file_display_name = file_name or (file_obj.file.name if file_obj else 'نامشخص')
        
        if file_obj:
            try:
                file_info = FileReader.read_file(file_obj.file)
                content = file_info.get('content', '')
            except:
                content = "خطا در خواندن فایل"
        
        # 2. تحلیل با AI
        ai_result = self._analyze_with_ai(
            content=content,
            filename=file_display_name,
            action_type=action_type,
            user=user
        )
        
        # 3. ذخیره در لاگ
        log = FileActionLog.objects.create(
            user=user,
            action=action_type,
            file_name=file_display_name,
            file_size=file_size or (file_obj.file.size if file_obj and hasattr(file_obj.file, 'size') else 0),
            ip_address=ip_address,
            recipient_user=recipient,
            details=f"عملیات {dict(FileActionLog.ACTION_CHOICES).get(action_type, action_type)} توسط {user.username}",
            ai_analysis=ai_result.get('full_analysis', ''),
            ai_summary=ai_result.get('summary', ''),
            threat_level=ai_result.get('threat_level', 'low'),
            is_threat=ai_result.get('is_threat', False)
        )
        
        # 4. ارسال نوتیفیکیشن به ادمین‌ها
        self._notify_admins(log, ai_result, user, action_type, file_display_name)
        
        # 5. ارسال نوتیفیکیشن به خود کاربر (اگر آپلود یا دانلود باشد)
        if action_type in ['upload', 'download']:
            self._notify_user(log, ai_result, user, action_type, file_display_name)
        
        # 6. اگر تهدید شناسایی شد، هشدار امنیتی ایجاد کن
        if ai_result.get('is_threat', False) and ai_result.get('threat_level') in ['high', 'critical']:
            self._create_security_alert(file_obj, ai_result, user)
        
        return {
            'success': True,
            'log': log,
            'analysis': ai_result
        }
    
    def _analyze_with_ai(self, content, filename, action_type, user):
        """تحلیل محتوا با AI و تولید گزارش"""
        
        if not self.llm or not self.llm.is_available:
            return {
                'summary': '⚠️ سرویس AI در دسترس نیست',
                'full_analysis': 'سرویس هوش مصنوعی در دسترس نیست. لطفاً Ollama را راه‌اندازی کنید.',
                'threat_level': 'unknown',
                'is_threat': False
            }
        
        # انتخاب پرامپت مناسب بر اساس نوع عملیات
        action_name = dict(FileActionLog.ACTION_CHOICES).get(action_type, action_type)
        
        prompt = f"""
        شما یک تحلیلگر حرفه‌ای امنیت سایبری و تحلیل محتوا هستید.
        
        کاربر {user.username} یک فایل را {action_name} کرده است.
        
        **اطلاعات فایل:**
        - نام: {filename}
        - نوع عملیات: {action_name}
        
        **محتوای فایل:**
        {content[:3000] if content else 'فایل غیرقابل خواندن است'}
        
        **لطفاً تحلیل دقیق زیر را بنویسید:**

        1. **خلاصه محتوا** (۲-۳ خط): موضوع اصلی فایل چیست؟
        2. **نوع فایل**: این فایل چه نوع اطلاعاتی دارد؟ (مالی/شخصی/فنی/آموزشی/تفریحی/اداری)
        3. **سطح حساسیت**: (کم/متوسط/بالا/بحرانی)
        4. **آیا فایل مشکوک است؟** (بله/خیر) - اگر بله، چرا؟
        5. **توصیه به ادمین**:
        6. **توصیه به کاربر**:

        **خروجی را به صورت زیر بنویس:**

        📄 **خلاصه:** [خلاصه ۲-۳ خطی]

        📊 **نوع اطلاعات:** [نوع اطلاعات]

        🔒 **سطح حساسیت:** [سطح]

        ⚠️ **وضعیت امنیتی:** [مشکوک/سالم]

        💡 **توصیه به ادمین:** [توصیه]

        👤 **توصیه به کاربر:** [توصیه]
        """
        
        response = self.llm._call_llm_stream(prompt)
        
        # پردازش پاسخ
        is_threat = False
        threat_level = 'low'
        
        if 'مشکوک' in response or 'بله' in response[:30]:
            is_threat = True
            if 'بحرانی' in response:
                threat_level = 'critical'
            elif 'بالا' in response:
                threat_level = 'high'
            elif 'متوسط' in response:
                threat_level = 'medium'
        
        return {
            'summary': self._extract_summary(response),
            'full_analysis': response,
            'threat_level': threat_level,
            'is_threat': is_threat
        }
    
    def _extract_summary(self, response):
        """استخراج خلاصه از پاسخ AI"""
        try:
            lines = response.split('\n')
            for line in lines:
                if 'خلاصه:' in line or '📄' in line:
                    return line.replace('خلاصه:', '').replace('📄', '').strip()
            return response[:200]
        except:
            return response[:200]
    
    def _notify_admins(self, log, ai_result, user, action_type, filename):
        """ارسال نوتیفیکیشن به ادمین‌ها"""
        admins = User.objects.filter(is_staff=True)
        
        action_name = dict(FileActionLog.ACTION_CHOICES).get(action_type, action_type)
        
        severity = 'info'
        if ai_result.get('is_threat', False):
            severity_map = {
                'low': 'info',
                'medium': 'warning',
                'high': 'critical',
                'critical': 'critical'
            }
            severity = severity_map.get(ai_result.get('threat_level', 'low'), 'info')
        
        # عنوان و پیام
        if ai_result.get('is_threat', False) and ai_result.get('threat_level') in ['high', 'critical']:
            title = f"🚨 هشدار امنیتی: {action_name} فایل {filename} توسط {user.username}"
            message = f"""
🔴 **هشدار امنیتی شناسایی شد!**

📄 **فایل:** {filename}
👤 **کاربر:** {user.username}
🕐 **زمان:** {log.action_time.strftime('%Y-%m-%d %H:%M')}
📋 **عملیات:** {action_name}

📊 **تحلیل AI:**
{ai_result.get('full_analysis', 'تحلیلی ثبت نشده')}

⚠️ **سطح تهدید:** {ai_result.get('threat_level', 'unknown')}

💡 **اقدام پیشنهادی:** فایل را بررسی و در صورت نیاز مسدود کنید.
"""
        else:
            title = f"📄 تحلیل فایل: {filename} - {action_name} توسط {user.username}"
            message = f"""
📄 **تحلیل فایل**

📄 **فایل:** {filename}
👤 **کاربر:** {user.username}
🕐 **زمان:** {log.action_time.strftime('%Y-%m-%d %H:%M')}
📋 **عملیات:** {action_name}

📊 **تحلیل AI:**
{ai_result.get('full_analysis', 'تحلیلی ثبت نشده')}
"""
        
        # ایجاد نوتیفیکیشن
        notification = AINotification.objects.create(
            title=title,
            message=message,
            notification_type='file_analysis',
            severity=severity,
            file=log if hasattr(log, 'file') else None,
            user=user,
            created_by=None
        )
        
        # ارسال به ادمین‌ها
        if admins.exists():
            notification.target_users.set(admins)
    
    def _notify_user(self, log, ai_result, user, action_type, filename):
        """ارسال نوتیفیکیشن به خود کاربر"""
        action_name = dict(FileActionLog.ACTION_CHOICES).get(action_type, action_type)
        
        title = f"📄 {action_name} فایل: {filename}"
        
        if ai_result.get('is_threat', False):
            message = f"""
⚠️ **فایل شما توسط AI تحلیل شد!**

📄 **فایل:** {filename}
🕐 **زمان:** {log.action_time.strftime('%Y-%m-%d %H:%M')}

📊 **نتیجه تحلیل:**
{ai_result.get('summary', 'تحلیلی ثبت نشده')}

⚠️ **هشدار:** این فایل ممکن است مشکوک باشد. لطفاً از امنیت آن مطمئن شوید.
"""
        else:
            message = f"""
✅ **فایل شما با موفقیت تحلیل شد!**

📄 **فایل:** {filename}
🕐 **زمان:** {log.action_time.strftime('%Y-%m-%d %H:%M')}

📊 **نتیجه تحلیل:**
{ai_result.get('summary', 'تحلیلی ثبت نشده')}

✅ فایل سالم است و مشکلی ندارد.
"""
        
        # ایجاد نوتیفیکیشن فقط برای خود کاربر
        notification = AINotification.objects.create(
            title=title,
            message=message,
            notification_type='file_analysis',
            severity='info',
            file=log if hasattr(log, 'file') else None,
            user=user,
            created_by=None
        )
        
        
        notification.target_users.set([user])
    
    def _create_security_alert(self, file_obj, ai_result, user):
        """ایجاد هشدار امنیتی در صورت تهدید"""
        try:
            if file_obj:
                AIThreatAlert.objects.create(
                    file=file_obj,
                    threat_type='ai_detected',
                    severity=ai_result.get('threat_level', 'medium'),
                    description=ai_result.get('summary', 'تهدید شناسایی شده'),
                    recommended_action='review',
                    ai_raw_response=ai_result.get('full_analysis', ''),
                    status='pending'
                )
        except:
            pass


# نمونه جهانی
action_analyzer = ActionAnalyzer()