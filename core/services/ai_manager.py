# core/services/ai_manager.py

import requests
import json
from ..models import AISettings

class AIManager:
    """مدیریت ارتباط با هوش مصنوعی"""
    
    @staticmethod
    def get_settings():
        """دریافت تنظیمات جاری"""
        return AISettings.get_settings()
    
    @staticmethod
    def test_connection(host=None, port=None, model=None):
        """تست اتصال به سرور Ollama"""
        settings = AISettings.get_settings()
        
        host = host or settings.ollama_host
        port = port or settings.ollama_port
        model = model or settings.ollama_model
        
        base_url = f"http://{host}:{port}"
        
        result = {
            'success': False,
            'message': '',
            'models': [],
            'version': '',
            'details': {}
        }
        
        try:
            # تست اتصال پایه
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = [tag.get('name') for tag in data.get('models', [])]
                
                result['success'] = True
                result['message'] = f" اتصال به {base_url} برقرار است"
                result['models'] = models
                result['version'] = data.get('version', 'نامشخص')
                result['details'] = {
                    'total_models': len(models),
                    'available_models': models[:10],  # فقط 10 مدل اول
                    'is_model_available': model in models
                }
                
                # بررسی وجود مدل انتخابی
                if model not in models:
                    result['message'] += f"\n⚠️ Model '{model}' cant find any model : {', '.join(models[:5])}"
            else:
                result['message'] = f"Error : {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result['message'] = f" cant connect to ollama server is ollama run ? {base_url}"
        except requests.exceptions.Timeout:
            result['message'] = "Time is over"
        except Exception as e:
            result['message'] = f" Error: {str(e)}"
        
        return result
    
    @staticmethod
    def get_available_models(host=None, port=None):
        """دریافت لیست مدل‌های موجود"""
        settings = AISettings.get_settings()
        host = host or settings.ollama_host
        port = port or settings.ollama_port
        
        base_url = f"http://{host}:{port}"
        
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [tag.get('name') for tag in data.get('models', [])]
                return {
                    'success': True,
                    'models': models,
                    'default': settings.ollama_model
                }
            return {'success': False, 'models': [], 'error': f"Error: {response.status_code}"}
        except Exception as e:
            return {'success': False, 'models': [], 'error': str(e)}
    
    @staticmethod
    def save_settings(data):
        """ذخیره تنظیمات AI"""
        try:
            settings = AISettings.get_settings()
            
            settings.ollama_host = data.get('host', settings.ollama_host)
            settings.ollama_port = int(data.get('port', settings.ollama_port))
            settings.ollama_model = data.get('model', settings.ollama_model)
            settings.is_active = data.get('is_active', True)
            settings.timeout_seconds = int(data.get('timeout', 120))
            settings.max_tokens = int(data.get('max_tokens', 2048))
            settings.temperature = float(data.get('temperature', 0.3))
            
            settings.save()
            
            return {'success': True, 'message': 'The setting sucssefuly'}
        except Exception as e:
            return {'success': False, 'message': f'خطا: {str(e)}'}

ai_manager = AIManager()