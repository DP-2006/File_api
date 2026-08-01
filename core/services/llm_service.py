# core/services/llm_service.py

import requests
import json
import sys
import socket


class LLMService:
    """سرویس ارتباط با Ollama - با قابلیت انتخاب خودکار مدل"""

    def __init__(self, base_url: str = None, model: str = None):
        # دریافت تنظیمات از دیتابیس 
        self._load_settings_from_db()
        
        # اگر base_url مشخص نشده، از تنظیمات دیتابیس استفاده کن
        if base_url is None:
            base_url = self._get_base_url_from_settings()
        
        # اگر model مشخص نشده، از تنظیمات دیتابیس استفاده کن
        if model is None and self._ai_settings:
            model = self._ai_settings.ollama_model
        
        self.base_url = base_url
        self.model = model
        self.is_available = self.check_connection()
        print(f"🔗 اتصال به Ollama: {self.base_url}")
        print(f"🤖 مدل: {self.model}")
    
    def _load_settings_from_db(self):
        """بارگذاری تنظیمات از دیتابیس"""
        self._ai_settings = None
        try:
            # Import here to avoid circular imports
            from core.models import AISettings
            self._ai_settings = AISettings.get_settings()
            print(f"تنظیمات AI از دیتابیس بارگذاری شد: {self._ai_settings.ollama_host}:{self._ai_settings.ollama_port}")
        except Exception as e:
            print(f" خطا در بارگذاری تنظیمات از دیتابیس: {e}")
            print("از مقادیر پیش‌فرض استفاده می‌شود")
            self._ai_settings = None
    
    def _get_base_url_from_settings(self) -> str:
        """دریافت base_url از تنظیمات دیتابیس"""
        if self._ai_settings:
            return f"http://{self._ai_settings.ollama_host}:{self._ai_settings.ollama_port}"
        
        # Fallback به مقادیر پیش‌فرض
        return "http://127.0.0.1:11434"

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            
            if ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                return ip
        except:
            pass
        
        # روش جایگزین: استفاده از hostname
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith('127.'):
                return ip
        except:
            pass
        
        return '127.0.0.1'  # fallback
    
    def _is_management_command(self) -> bool:
        management_commands = ['makemigrations', 'migrate', 'createsuperuser', 'shell', 'test', 'check']
        return any(cmd in sys.argv for cmd in management_commands)
    
    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                tags = response.json()
                models = [tag.get('name') for tag in tags.get('models', [])]
                
                if not models:
                    print(f"❌ هیچ مدلی در Ollama یافت نشد! (آدرس: {self.base_url})")
                    return False
                
                if self.model is None or self.model not in models:
                    self.model = models[0]
                    if not self._is_management_command():
                        print(f"✅ AI متصل است - استفاده از مدل: {self.model}")
                else:
                    if not self._is_management_command():
                        print(f"✅ AI متصل است - مدل {self.model} آماده است")
                
                return True
            return False
        except Exception as e:
            print(f"❌ خطا در اتصال به {self.base_url}: {e}")
            return False
    
    def reload_settings(self):
        """بارگذاری مجدد تنظیمات از دیتابیس"""
        self._load_settings_from_db()
        self.base_url = self._get_base_url_from_settings()
        if self._ai_settings:
            self.model = self._ai_settings.ollama_model
        self.is_available = self.check_connection()
        print(f"🔄 تنظیمات مجدداً بارگذاری شد: {self.base_url}")
        return self.is_available
    
    def _call_llm_stream(self, prompt: str) -> str:
        """ارسال درخواست با streaming برای جلوگیری از timeout"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست. لطفاً Ollama را اجرا کنید."
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True, 
            "options": {
                "temperature": 0.3,
                "num_predict": 1024
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", 
                json=data, 
                stream=True,
                timeout=600  
            )
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            full_response += chunk['response']
                        if chunk.get('done', False):
                            break
                    except:
                        continue
            
            return full_response if full_response else "پاسخ دریافت نشد"
            
        except requests.exceptions.Timeout:
            return "خطا: زمان درخواست به پایان رسید (10 دقیقه). مدل خیلی بزرگ است یا سیستم کند است."
        except Exception as e:
            return f"خطا: {str(e)}"
    
    def _call_llm(self, prompt: str) -> str:
        """نسخه ساده بدون streaming"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست."
        
        # کاهش حجم پرامپت برای سرعت بیشتر
        if len(prompt) > 3000:
            prompt = prompt[:3000] + "..."
        
        data = {
            "model": self.model,
            "prompt": prompt,  
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 500,
                "num_ctx": 2048
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", 
                json=data, 
                timeout=600
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            return f"خطا: {response.status_code}"
        except requests.exceptions.Timeout:
            return "خطا: زمان درخواست به پایان رسید (10 دقیقه). لطفاً از مدل کوچکتر استفاده کنید."
        except Exception as e:
            return f"خطا: {str(e)}"
    
    def summarize_file(self, content: str, filename: str, detail_level: str = "summary") -> str:
        """خلاصه‌سازی فایل"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست."
        
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        prompt = f"""خلاصه‌سازی فایل "{filename}":

محتوا:
{content}

سطح جزئیات: {detail_level}

خلاصه‌ای مفید و دقیق بنویس:"""
        
        return self._call_llm_stream(prompt)
    
    def answer_question_about_file(self, content: str, filename: str, question: str) -> str:
        """پاسخ به سوال درباره فایل"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست."
        
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        prompt = f"""فایل: {filename}

محتوا:
{content}

سوال: {question}

پاسخ دقیق بر اساس محتوای فایل:"""
        
        return self._call_llm_stream(prompt)
    
    def analyze_user_behavior(self, user_data: dict, files_content: list) -> str:
        """تحلیل رفتار کاربر"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست."
        
        user_info = f"""
نام کاربری: {user_data.get('username')}
تعداد آپلود: {user_data.get('total_uploads', 0)}
نوع فایل‌ها: {json.dumps(user_data.get('file_types', {}), ensure_ascii=False)}
وضعیت: {'ادمین' if user_data.get('is_staff') else 'کاربر عادی'}
تاریخ عضویت: {user_data.get('date_joined', 'نامشخص')}
"""
        
        prompt = f"""تحلیل رفتار کاربر:

{user_info}

بر اساس اطلاعات بالا، تحلیل کنید:
1. الگوی فعالیت کاربر
2. نوع فایل‌های آپلود شده
3. سطح ریسک (کم/متوسط/بالا)
4. توصیه‌های امنیتی

تحلیل:"""
        
        return self._call_llm_stream(prompt)
    
    def analyze_user_personality(self, user_data: dict, files_content: str) -> str:
        """تحلیل شخصیت کاربر"""
        if not self.is_available:
            return "⚠️ AI در دسترس نیست."
        
        # کاهش حجم محتوا
        if len(files_content) > 3000:
            files_content = files_content[:3000]
        
        prompt = f"""تحلیل شخصیت کاربر:

کاربر: {user_data.get('username')}
تعداد فایل: {user_data.get('total_uploads', 0)}
نوع فایل: {json.dumps(user_data.get('file_types', {}), ensure_ascii=False)}

محتوای فایل‌ها:
{files_content}

بنویس:
1. تیپ شخصیتی:
2. ویژگی‌ها:
3. سطح ریسک: (کم/متوسط/بالا)
4. توصیه به ادمین:"""
        
        return self._call_llm_stream(prompt)
    
    def test_connection(self, host: str, port: int, model: str = None) -> dict:
        """تست اتصال به Ollama"""
        base_url = f"http://{host}:{port}"
        
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                tags = response.json()
                models = [tag.get('name') for tag in tags.get('models', [])]
                
                if not models:
                    return {
                        'success': False,
                        'message': 'هیچ مدلی در Ollama یافت نشد',
                        'models': []
                    }
                
                # اگر مدل مشخص شده، بررسی کنیم که وجود دارد
                if model and model not in models:
                    return {
                        'success': False,
                        'message': f'مدل "{model}" یافت نشد. مدل‌های موجود: {", ".join(models)}',
                        'models': models
                    }
                
                selected_model = model if model and model in models else models[0]
                
                # تست generate با مدل انتخاب شده
                test_data = {
                    "model": selected_model,
                    "prompt": "سلام",
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 10}
                }
                
                test_response = requests.post(
                    f"{base_url}/api/generate",
                    json=test_data,
                    timeout=10
                )
                
                if test_response.status_code == 200:
                    return {
                        'success': True,
                        'message': f'اتصال برقرار است. مدل {selected_model} آماده است.',
                        'models': models,
                        'selected_model': selected_model
                    }
                else:
                    return {
                        'success': False,
                        'message': f'خطا در تست مدل: {test_response.status_code}',
                        'models': models
                    }
            
            return {
                'success': False,
                'message': f'خطا در اتصال به {base_url}',
                'models': []
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': f'اتصال به {host}:{port} برقرار نشد. آیا Ollama در حال اجراست؟',
                'models': []
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': f'زمان اتصال به {host}:{port} به پایان رسید',
                'models': []
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'خطا: {str(e)}',
                'models': []
            }


# ============================================================
# ✅ ایجاد نمونه جهانی
# ============================================================
_is_management = any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'createsuperuser', 'shell', 'test', 'check'])
if not _is_management:
    try:
        llm_service = LLMService()
    except Exception as e:
        print(f"⚠️ خطا در ایجاد LLMService: {e}")
        llm_service = None
else:
    llm_service = None