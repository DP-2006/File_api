
<<<<<<< HEAD
#fale codeing ! , not good! 
=======

>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
# core/services/file_analysis_service.py

from django.contrib.auth.models import User
from django.utils import timezone
from core.models import AINotification, UploadedFile, AIThreatAlert
from core.services.file_reader import FileReader
from core.services.llm_service import llm_service


class FileAnalysisService:
    """سرویس تحلیل خودکار فایل‌ها با AI"""
    
    def __init__(self):
        self.llm = llm_service
<<<<<<< HEAD
        print("🔧 [AI] FileAnalysisService مق
        داردهی اولیه شد")
=======
        print("🔧 [AI] FileAnalysisService مقداردهی اولیه شد")
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
    
    def analyze_uploaded_file(self, file_obj):
        """تحلیل خودکار فایل آپلود شده"""
        print(f"🔍 [AI] شروع تحلیل فایل: {file_obj.file.name}")
        
        try:
            # 1. خواندن محتوای فایل
            file_info = FileReader.read_file(file_obj.file)
            content = file_info.get('content', '')
<<<<<<< HEAD
            print(f" [AI] محتوای فایل خوانده شد: {len(content)} کاراکتر")
            
            # 2. تحلیل با AI
            analysis_result = self._analyze_with_ai(content, file_obj.file.name)
            print(f" [AI] تحلیل انجام شد - طول پاسخ: {len(analysis_result)}")
             
=======
            print(f"📄 [AI] محتوای فایل خوانده شد: {len(content)} کاراکتر")
            
            # 2. تحلیل با AI
            analysis_result = self._analyze_with_ai(content, file_obj.file.name)
            print(f"🤖 [AI] تحلیل انجام شد - طول پاسخ: {len(analysis_result)}")
            
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
            # 3. تعیین سطح تهدید
            threat_level = self._determine_threat_level(analysis_result)
            print(f"⚠️ [AI] سطح تهدید: {threat_level}")
            
            # 4. ذخیره نتیجه تحلیل
            self._save_analysis_result(file_obj, analysis_result, threat_level)
            
            # 5. ایجاد نوتیفیکیشن
            notification = self._create_notification(file_obj, analysis_result, threat_level)
            
            if notification:
                print(f"📬 [AI] نوتیفیکیشن ایجاد شد - ID: {notification.id}")
            else:
<<<<<<< HEAD
                print(f" [AI] نوتیفیکیشن ساخته نشد")
=======
                print(f"❌ [AI] نوتیفیکیشن ساخته نشد")
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
            
            return {
                'success': True,
                'notification': notification,
                'threat_level': threat_level,
                'analysis': analysis_result
            }
            
        except Exception as e:
            print(f"❌ [AI] خطا در تحلیل خودکار فایل: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_with_ai(self, content, filename):
        """تحلیل محتوا با AI"""
        if not self.llm or not self.llm.is_available:
            return "⚠️ سرویس AI در دسترس نیست."
        
        prompt = f"""
        فایل "{filename}" را تحلیل کن و گزارش زیر را بنویس:

        1. موضوع اصلی فایل چیست؟
        2. آیا محتوای مشکوک یا خطرناکی دارد؟ (بله/خیر)
        3. چه نوع اطلاعاتی در فایل وجود دارد؟ (شخصی/حساس/عمومی/فنی/مالی)
        4. سطح ریسک فایل: (کم/متوسط/بالا/بحرانی)
        5. خلاصه محتوا (۲-۳ خط):

        محتوا:
        {content[:3000]}

        پاسخ:
        """
        
        print(f"🤖 [AI] ارسال درخواست به مدل: {self.llm.model}")
        response = self.llm._call_llm_stream(prompt)
        print(f"🤖 [AI] پاسخ دریافت شد: {len(response)} کاراکتر")
        return response
    
    def _determine_threat_level(self, analysis_result):
        """تعیین سطح تهدید از روی تحلیل"""
        analysis_lower = analysis_result.lower()
        
        if any(word in analysis_lower for word in ['بحرانی', 'خطرناک', 'ویروس', 'بدافزار', 'هک']):
            return 'critical'
        elif any(word in analysis_lower for word in ['بالا', 'مشکوک', 'غیرمجاز']):
            return 'warning'
        else:
            return 'info'
    
    def _save_analysis_result(self, file_obj, analysis_result, threat_level):
        """ذخیره نتیجه تحلیل"""
        severity_map = {
            'info': 'low',
            'warning': 'medium',
            'critical': 'high'
        }
        
        try:
            AIThreatAlert.objects.create(
                file=file_obj,
                threat_type='auto_analysis',
                severity=severity_map.get(threat_level, 'low'),
                description=analysis_result[:500],
                recommended_action='review' if threat_level in ['warning', 'critical'] else 'none',
                ai_raw_response=analysis_result,
                status='pending' if threat_level in ['warning', 'critical'] else 'reviewed'
            )
            print(f"💾 [AI] نتیجه تحلیل ذخیره شد")
        except Exception as e:
            print(f"❌ [AI] خطا در ذخیره نتیجه: {e}")
    
    def _create_notification(self, file_obj, analysis_result, threat_level):
        """ایجاد نوتیفیکیشن"""
        try:
            # دریافت ادمین‌ها
            admins = User.objects.filter(is_staff=True)
            
            if not admins.exists():
                print("⚠️ [AI] هیچ ادمینی یافت نشد!")
                return None
            
            # ساخت عنوان
            title = f"📄 تحلیل فایل: {file_obj.file.name}"
            
            # ساخت پیام بر اساس سطح تهدید
            if threat_level == 'critical':
                severity = 'critical'
                message = f"⚠️ **فایل {file_obj.file.name} دارای تهدید بحرانی است!**\n\n"
            elif threat_level == 'warning':
                severity = 'warning'
                message = f"⚡ **فایل {file_obj.file.name} نیاز به بررسی دارد.**\n\n"
            else:
                severity = 'info'
                message = f"📄 **فایل {file_obj.file.name} با موفقیت تحلیل شد.**\n\n"
            
            message += f"👤 **کاربر:** {file_obj.uploaded_by.username}\n"
            message += f"📅 **زمان:** {file_obj.uploaded_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            message += f"📊 **نتیجه تحلیل:**\n{analysis_result[:500]}..."
            
            # ایجاد نوتیفیکیشن
            notification = AINotification.objects.create(
                title=title,
                message=message,
                notification_type='file_analysis',
                severity=severity,
                file=file_obj,
                user=file_obj.uploaded_by,
                created_by=None,
            )
            
            # اضافه کردن ادمین‌ها به target_users
            notification.target_users.set(admins)
            notification.save()
            
            print(f"📬 [AI] نوتیفیکیشن برای {admins.count()} ادمین ارسال شد")
            return notification
            
        except Exception as e:
            print(f"❌ [AI] خطا در ایجاد نوتیفیکیشن: {e}")
            import traceback
            traceback.print_exc()
            return None


# نمونه جهانی
file_analysis_service = FileAnalysisService()
print("✅ [AI] FileAnalysisService بارگذاری شد")