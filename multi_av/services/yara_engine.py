import os
import time
import requests
from django.conf import settings


class YaraEngine:
    name = 'yara'

    def __init__(self):
        self.api_url = settings.MULTI_AV.get('YARA_API_URL', 'http://yara:8001')

    def scan(self, file_path):
        start = time.time()
        try:
            with open(file_path, 'rb') as fh:
                files = {'file': (os.path.basename(file_path), fh)}
                r = requests.post(f'{self.api_url}/scan', files=files, timeout=120)
            duration = int((time.time() - start) * 1000)
            if r.status_code != 200:
                return {'score': 0, 'threat': False, 'error': f'YARA HTTP {r.status_code}', 'duration_ms': duration}
            data = r.json()
            return {'score': data.get('score', 0), 'threat': data.get('threat', False),
                    'details': data.get('details', ''), 'duration_ms': duration,
                    'raw': {'matches': data.get('matches', [])}}
        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e), 'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        try:
            r = requests.get(f'{self.api_url}/health', timeout=5)
            d = r.json()
            return {'active': d.get('status') == 'ok', 'rules_loaded': d.get('rules_loaded', False), 'api_url': self.api_url}
        except Exception as e:
            return {'active': False, 'error': str(e)}


yara_engine = YaraEngine()
