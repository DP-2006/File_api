import os
import re
import time
import requests


class AIEngine:
    name = 'ai'

    def __init__(self):
        host = os.environ.get('OLLAMA_HOST', 'localhost')
        port = int(os.environ.get('OLLAMA_PORT', 11434))
        self.model = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
        self.base_url = f'http://{host}:{port}'

    def scan(self, file_path, file_obj=None):
        start = time.time()
        try:
            content = ''
            try:
                from core.services.file_reader import FileReader
                if file_obj:
                    info = FileReader.read_file(file_obj.file)
                    content = (info.get('content') or '')[:2000]
            except Exception:
                pass
            prompt = (f'فایل "{os.path.basename(file_path)}" را از نظر امنیتی تحلیل کن.\n'
                      f'محتوای خلاصه: {content}\n'
                      'فقط یک عدد بین 0 تا 100 بده که میزان خطرناک بودن را نشان دهد. فقط عدد.')
            r = requests.post(f'{self.base_url}/api/generate',
                              json={'model': self.model, 'prompt': prompt, 'stream': False},
                              timeout=300)
            r.raise_for_status()
            resp = r.json().get('response', '')
            m = re.search(r'\d+', resp)
            score = min(100, int(m.group())) if m else 0
            return {'score': score, 'threat': score >= 60, 'details': f'AI score: {score}',
                    'duration_ms': int((time.time() - start) * 1000), 'raw': {'response': resp[:500]}}
        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e), 'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        try:
            r = requests.get(f'{self.base_url}/api/tags', timeout=5)
            models = [m['name'] for m in r.json().get('models', [])]
            return {'active': any(self.model.split(':')[0] in m for m in models),
                    'models': models, 'configured_model': self.model}
        except Exception as e:
            return {'active': False, 'error': str(e)}


ai_engine = AIEngine()
