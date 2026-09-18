import hashlib
import time
import requests
from django.conf import settings


class VirusTotalEngine:
    name = 'virustotal'
    BASE_URL = 'https://www.virustotal.com/api/v3'

    def _get_api_key(self):
        return settings.MULTI_AV.get('VIRUSTOTAL_API_KEY', '')

    def scan(self, file_path):
        start = time.time()
        api_key = self._get_api_key()
        if not api_key:
            return {'score': 0, 'threat': False, 'error': 'no VT api key',
                    'duration_ms': 0}

        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            headers = {'x-apikey': api_key}
            url = f'{self.BASE_URL}/files/{file_hash}'
            r = requests.get(url, headers=headers, timeout=30)
            duration = int((time.time() - start) * 1000)

            if r.status_code == 404:
                return {'score': 0, 'threat': False,
                        'details': 'not in VT database',
                        'duration_ms': duration, 'raw': {'hash': file_hash}}

            if r.status_code != 200:
                return {'score': 0, 'threat': False,
                        'error': f'VT HTTP {r.status_code}',
                        'duration_ms': duration}

            data = r.json()
            stats = data['data']['attributes']['last_analysis_stats']
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            total = sum(stats.values()) or 1
            score = min(100, int(((malicious * 2 + suspicious) / total) * 100))

            return {
                'score': score,
                'threat': malicious > 0,
                'details': f'VT: {malicious} malicious / {total} engines',
                'duration_ms': duration,
                'raw': {'stats': stats, 'hash': file_hash}
            }
        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e),
                    'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        api_key = self._get_api_key()
        return {'active': bool(api_key), 'has_api_key': bool(api_key)}


virustotal_engine = VirusTotalEngine()