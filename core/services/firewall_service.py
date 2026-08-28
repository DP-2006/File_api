



# core/services/firewall_service.py

import re
import hashlib
import os
from datetime import datetime
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import AINotification, UploadedFile, AIThreatAlert
from core.services.llm_service import llm_service
from core.services.file_reader import FileReader


class FirewallService:
    """سرویس فایروال هوشمند با قابلیت‌های امنیتی کامل"""
    
    def __init__(self):
        self.llm = llm_service
        
        # لیست پسوندهای خطرناک
        self.dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.jar', '.apk', '.app', '.msi', '.dmg', '.deb',
            '.sh', '.bash', '.zsh', '.fish', '.pyc', '.pyo',
            '.vbs', '.js', '.jse', '.wsf', '.wsh', '.ps1'
        ]
        
        # کلمات کلیدی خطرناک
        self.suspicious_keywords = [
            'password', 'hack', 'crack', 'malware', 'virus', 
            'phishing', 'ransomware', 'trojan', 'keylogger',
            'backdoor', 'exploit', 'spyware', 'adware',
            'rootkit', 'worm', 'dropper', 'packer'
        ]
        
        # الگوهای regex برای تشخیص تهدید
        self.threat_patterns = {
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'phone': r'(\+98|0)?9\d{9}',
            'national_code': r'\b\d{10}\b',
            'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'credit_card': r'\b(?:\d{4}[- ]?){3}\d{4}\b'
        }
    
    def scan_file(self, uploaded_file):
        """اسکن کامل فایل برای تهدیدات امنیتی"""
        result = {
            "is_threat": False,
            "threat_type": "none",
            "severity": "low",
            "description": "",
            "details": {}
        }
        
        # 1. بررسی پسوند فایل
        ext = os.path.splitext(uploaded_file.file.name)[1].lower()
        if ext in self.dangerous_extensions:
            result["is_threat"] = True
            result["threat_type"] = "dangerous_extension"
            result["severity"] = "high"
            result["description"] = f"⚠️ پسوند خطرناک شناسایی شد: {ext}"
            result["details"]["extension"] = ext
            self._create_threat_alert(uploaded_file, result)
            return result
        
        # 2. بررسی حجم فایل
        if hasattr(uploaded_file.file, 'size'):
            file_size = uploaded_file.file.size
            if file_size > 100 * 1024 * 1024:  # 100 MB
                result["is_threat"] = True
                result["threat_type"] = "large_file"
                result["severity"] = "medium"
                result["description"] = f"📦 حجم فایل بسیار بزرگ: {file_size / (1024*1024):.1f} MB"
                result["details"]["size"] = file_size
                self._create_threat_alert(uploaded_file, result)
                return result
        
        # 3. بررسی محتوای فایل
        try:
            file_info = FileReader.read_file(uploaded_file.file)
            content = file_info.get('content', '')
            metadata = file_info.get('metadata', {})
            
            if content:
                # 3.1 بررسی کلمات کلیدی خطرناک
                found_keywords = []
                content_lower = content.lower()
                for keyword in self.suspicious_keywords:
                    if keyword in content_lower:
                        found_keywords.append(keyword)
                
                if found_keywords:
                    result["is_threat"] = True
                    result["threat_type"] = "suspicious_content"
                    result["severity"] = "high"
                    result["description"] = f"🔍 کلمات مشکوک شناسایی شد: {', '.join(found_keywords)}"
                    result["details"]["keywords"] = found_keywords
                    self._create_threat_alert(uploaded_file, result)
                    return result
                
                # 3.2 بررسی اطلاعات حساس (ایمیل، شماره، کد ملی و...)
                sensitive_info = self._detect_sensitive_info(content)
                if sensitive_info:
                    result["is_threat"] = True
                    result["threat_type"] = "sensitive_data"
                    result["severity"] = "high"
                    result["description"] = f"🔒 اطلاعات حساس شناسایی شد: {', '.join(sensitive_info.keys())}"
                    result["details"]["sensitive"] = sensitive_info
                    self._create_threat_alert(uploaded_file, result)
                    return result
                
                if self.llm and self.llm.is_available:
                    ai_result = self._scan_with_ai(content, uploaded_file.file.name)
                    if ai_result.get("is_threat"):
                        result["is_threat"] = True
                        result["threat_type"] = ai_result.get("threat_type", "ai_detected")
                        result["severity"] = ai_result.get("severity", "medium")
                        result["description"] = ai_result.get("description", "🤖 تشخیص توسط هوش مصنوعی")
                        result["details"]["ai_analysis"] = ai_result
                        self._create_threat_alert(uploaded_file, result)
                        return result
                        
        except Exception as e:
            print(f"⚠️ خطا در اسکن محتوای فایل: {e}")
            result["details"]["error"] = str(e)
        
        result["description"] = "✅ فایل سالم است"
        return result
    
    def _detect_sensitive_info(self, content):
        """تشخیص اطلاعات حساس در محتوا"""
        sensitive = {}
        
        # ایمیل
        emails = re.findall(self.threat_patterns['email'], content)
        if emails:
            sensitive['ایمیل'] = emails[:3]
        
        # شماره تلفن
        phones = re.findall(self.threat_patterns['phone'], content)
        if phones:
            sensitive['شماره تلفن'] = phones[:3]
        
        # کد ملی
        national_codes = re.findall(self.threat_patterns['national_code'], content)
        if national_codes:
            sensitive['کد ملی'] = national_codes[:3]
        
        # IP
        ips = re.findall(self.threat_patterns['ip_address'], content)
        if ips:
            sensitive['آی‌پی'] = ips[:3]
        
        # شماره کارت
        cards = re.findall(self.threat_patterns['credit_card'], content)
        if cards:
            sensitive['شماره کارت'] = cards[:3]
        
        return sensitive
    
    def _scan_with_ai(self, content, filename):
        """اسکن دقیق با AI"""
        if not self.llm or not self.llm.is_available:
            return {"is_threat": False}
        
        prompt = f"""
        فایل "{filename}" را برای تهدیدات امنیتی بررسی کن.
        
        محتوا:
        {content[:3000]}
        
        پاسخ دقیق بده:
        1. آیا تهدید امنیتی وجود دارد؟ (بله/خیر)
        2. نوع تهدید: (ویروس/بدافزار/فیشینگ/غیرمجاز/هک/اطلاعات حساس)
        3. سطح خطر: (کم/متوسط/بالا/بحرانی)
        4. توضیح کوتاه (یک خط):
        """
        
        try:
            response = self.llm._call_llm_stream(prompt)
            
            is_threat = "بله" in response[:30] and "خیر" not in response[:30]
            threat_type = "unknown"
            severity = "low"
            
            # تشخیص نوع تهدید
            response_lower = response.lower()
            if "ویروس" in response_lower:
                threat_type = "virus"
                severity = "critical"
            elif "بدافزار" in response_lower:
                threat_type = "malware"
                severity = "high"
            elif "فیشینگ" in response_lower:
                threat_type = "phishing"
                severity = "high"
            elif "هک" in response_lower or "نفوذ" in response_lower:
                threat_type = "hack"
                severity = "critical"
            elif "اطلاعات حساس" in response_lower or "محرمانه" in response_lower:
                threat_type = "sensitive_data"
                severity = "high"
            elif "غیرمجاز" in response_lower:
                threat_type = "unauthorized"
                severity = "medium"
            elif "مشکوک" in response_lower:
                threat_type = "suspicious"
                severity = "medium"
            
            # استخراج توضیحات
            description = response[:300]
            
            return {
                "is_threat": is_threat,
                "threat_type": threat_type,
                "severity": severity,
                "description": description
            }
        except Exception as e:
<<<<<<< HEAD
            print(f" خطا در تحلیل AI: {e}")
=======
            print(f"⚠️ خطا در تحلیل AI: {e}")
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
            return {"is_threat": False}
    
    def _create_threat_alert(self, uploaded_file, result):
        """ایجاد هشدار تهدید در دیتابیس"""
        try:
            # ایجاد هشدار
            alert = AIThreatAlert.objects.create(
                file=uploaded_file,
                threat_type=result["threat_type"],
                severity=result["severity"],
                description=result["description"],
                recommended_action="block" if result["severity"] in ["high", "critical"] else "review",
                ai_raw_response=result.get("details", {}).get("ai_analysis", {}).get("description", result["description"]),
                status="pending"
            )
            
            # ایجاد نوتیفیکیشن برای ادمین‌ها
            self._create_notification(uploaded_file, result, alert)
            
            return alert
            
        except Exception as e:
<<<<<<< HEAD
            print(f" خطا در ایجاد هشدار: {e}")
=======
            print(f"⚠️ خطا در ایجاد هشدار: {e}")
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
            return None
    
    def _create_notification(self, uploaded_file, result, alert=None):
        """ایجاد نوتیفیکیشن برای ادمین‌ها"""
        try:
            severity_map = {
                "low": "info",
                "medium": "warning",
                "high": "critical",
                "critical": "critical"
            }
            
            severity = severity_map.get(result["severity"], "info")
            
            # عنوان نوتیفیکیشن
            if result["severity"] in ["high", "critical"]:
<<<<<<< HEAD
                title = f" هشدار امنیتی بحرانی: {uploaded_file.file.name}"
            else:
                title = f" هشدار امنیتی: {uploaded_file.file.name}"
            
            # ساخت پیام
            message = f"""
=======
                title = f"🚨 هشدار امنیتی بحرانی: {uploaded_file.file.name}"
            else:
                title = f"⚠️ هشدار امنیتی: {uploaded_file.file.name}"
            
            # ساخت پیام
            message = f"""
🔴 **تهدید امنیتی شناسایی شد!**
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77

📄 **فایل:** {uploaded_file.file.name}
👤 **کاربر:** {uploaded_file.uploaded_by.username}
🕐 **زمان:** {timezone.now().strftime('%Y-%m-%d %H:%M')}

🚨 **نوع تهدید:** {result['threat_type']}
📊 **سطح خطر:** {result['severity']}

📝 **توضیحات:**
{result['description']}

<<<<<<< HEAD
💡 {(' مسدود کردن فایل' if result['severity'] in ['high', 'critical'] else '🔍 بررسی دقیق')}
=======
💡 **اقدام پیشنهادی:** {('🚫 مسدود کردن فایل' if result['severity'] in ['high', 'critical'] else '🔍 بررسی دقیق')}
>>>>>>> c4d29634dd54f9d0cfd7766b2404a86e72ea1f77
"""
            
            # اضافه کردن جزئیات اضافی
            if result.get("details"):
                if "keywords" in result["details"]:
                    message += f"\n🔑 **کلمات مشکوک:** {', '.join(result['details']['keywords'])}"
                if "sensitive" in result["details"]:
                    message += f"\n🔒 **اطلاعات حساس:** {', '.join(result['details']['sensitive'].keys())}"
                if "extension" in result["details"]:
                    message += f"\n📁 **پسوند:** {result['details']['extension']}"
            
            # دریافت ادمین‌ها
            admins = User.objects.filter(is_staff=True)
            
            # ایجاد نوتیفیکیشن
            notification = AINotification.objects.create(
                title=title,
                message=message,
                notification_type='threat_detected',
                severity=severity,
                file=uploaded_file,
                user=uploaded_file.uploaded_by,
                created_by=None
            )
            
            # ارسال به همه ادمین‌ها
            notification.target_users.set(admins)
            
            return notification
            
        except Exception as e:
            print(f"⚠️ خطا در ایجاد نوتیفیکیشن: {e}")
            return None
    
    def extract_file_content(self, uploaded_file):
        """استخراج محتوای فایل برای تحلیل"""
        try:
            file_info = FileReader.read_file(uploaded_file.file)
            content = file_info.get('content', '')
            metadata = file_info.get('metadata', {})
            
            return {
                'content': content,
                'metadata': metadata,
                'filename': uploaded_file.file.name,
                'size': uploaded_file.file.size if hasattr(uploaded_file.file, 'size') else 0
            }
        except Exception as e:
            return {
                'content': f"⚠️ خطا در خواندن فایل: {str(e)}",
                'metadata': {},
                'filename': uploaded_file.file.name,
                'size': 0
            }
    
    def get_pending_alerts(self):
        """دریافت هشدارهای در انتظار بررسی"""
        try:
            return AIThreatAlert.objects.filter(status='pending').order_by('-created_at')
        except:
            return []
    
    def get_alert_stats(self):
        """دریافت آمار هشدارها"""
        try:
            return {
                'total': AIThreatAlert.objects.count(),
                'pending': AIThreatAlert.objects.filter(status='pending').count(),
                'critical': AIThreatAlert.objects.filter(severity='critical').count(),
                'high': AIThreatAlert.objects.filter(severity='high').count(),
                'medium': AIThreatAlert.objects.filter(severity='medium').count(),
                'low': AIThreatAlert.objects.filter(severity='low').count()
            }
        except:
            return {
                'total': 0,
                'pending': 0,
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            }
    
    def resolve_alert(self, alert_id, action, user):
        """رسیدگی به هشدار"""
        try:
            alert = AIThreatAlert.objects.get(id=alert_id)
            
            if action == 'block':
                alert.file.is_deleted = True
                alert.file.save()
                alert.status = 'blocked'
            elif action == 'ignore':
                alert.status = 'ignored'
            elif action == 'review':
                alert.status = 'reviewed'
            
            alert.reviewed_by = user
            alert.reviewed_at = timezone.now()
            alert.save()
            
            return {'success': True, 'alert': alert}
        except AIThreatAlert.DoesNotExist:
            return {'success': False, 'error': 'هشدار یافت نشد'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ایجاد نمونه جهانی
firewall = FirewallService()