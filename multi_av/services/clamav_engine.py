import time
from django.conf import settings


class ClamAVEngine:
    name = 'clamav'

    def scan(self, file_path):
        start = time.time()
        try:
            import clamd
            cd = clamd.ClamdNetworkSocket(
                host=settings.MULTI_AV.get('CLAMAV_HOST', 'localhost'),
                port=settings.MULTI_AV.get('CLAMAV_PORT', 3310),
                timeout=60
            )
            result = cd.scan(file_path)
            duration = int((time.time() - start) * 1000)

            if not result:
                return {'score': 0, 'threat': False, 'details': 'clean',
                        'duration_ms': duration, 'raw': {}}

            status, sig = list(result.values())[0]
            if status == 'FOUND':
                return {'score': 100, 'threat': True,
                        'details': f'ClamAV: {sig}',
                        'duration_ms': duration, 'raw': {'signature': sig}}
            return {'score': 0, 'threat': False, 'details': 'clean',
                    'duration_ms': duration, 'raw': {}}

        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e),
                    'details': 'clamav unavailable',
                    'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        try:
            import clamd
            cd = clamd.ClamdNetworkSocket(
                host=settings.MULTI_AV.get('CLAMAV_HOST', 'localhost'),
                port=settings.MULTI_AV.get('CLAMAV_PORT', 3310),
                timeout=5
            )
            cd.ping()
            return {'active': True, 'version': str(cd.version())}
        except Exception as e:
            return {'active': False, 'error': str(e)}


clamav_engine = ClamAVEngine()